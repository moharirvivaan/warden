#include "ownership.hpp"
#include <clang/AST/DeclTemplate.h>
#include <clang/AST/ExprCXX.h>
#include <clang/AST/ParentMapContext.h>
#include <clang/AST/RecursiveASTVisitor.h>
#include <clang/Basic/SourceManager.h>

namespace warden {
using namespace clang;
namespace {
Location site(SourceLocation loc, ASTContext& context, const fs::path& root) {
    auto& sm = context.getSourceManager();
    if (loc.isInvalid()) return {};
    loc = sm.getExpansionLoc(loc);
    auto file = fs::weakly_canonical(sm.getFilename(loc).str());
    auto relative = file.lexically_relative(root);
    return {relative.empty() || *relative.begin() == ".." ? file.string() : relative.generic_string(),
        sm.getExpansionLineNumber(loc), sm.getExpansionColumnNumber(loc)};
}
bool sdkDeclaration(const Decl& decl, ASTContext& context, const fs::path& sdk) {
    auto& sm = context.getSourceManager();
    auto file = fs::weakly_canonical(sm.getFilename(sm.getSpellingLoc(decl.getLocation())).str());
    auto relative = file.lexically_relative(fs::weakly_canonical(sdk));
    return !relative.empty() && *relative.begin() != "..";
}
bool cocosObject(const CXXRecordDecl* record) {
    if (!record) return false;
    if (record->getQualifiedNameAsString() == "cocos2d::CCObject") return true;
    record = record->getDefinition();
    if (!record) return false;
    for (const auto& base : record->bases())
        if (cocosObject(base.getType()->getAsCXXRecordDecl())) return true;
    return false;
}
bool retainingRef(QualType type, ASTContext& context, const fs::path& sdk) {
    auto record = dyn_cast_or_null<ClassTemplateSpecializationDecl>(type->getAsCXXRecordDecl());
    return record && record->getSpecializedTemplate()->getQualifiedNameAsString() == "geode::Ref" &&
        sdkDeclaration(*record->getSpecializedTemplate(), context, sdk);
}
bool containsCocosType(QualType type, unsigned depth = 0) {
    if (depth > 4) return false;
    type = type.getNonReferenceType();
    if (type->isPointerType()) return cocosObject(type->getPointeeType()->getAsCXXRecordDecl());
    auto record = type->getAsCXXRecordDecl();
    if (cocosObject(record)) return true;
    auto specialization = dyn_cast_or_null<ClassTemplateSpecializationDecl>(record);
    if (!specialization) return false;
    auto argumentContains = [&](auto&& self, const TemplateArgument& argument, unsigned level) -> bool {
        if (level > 4) return false;
        if (argument.getKind() == TemplateArgument::Type) return containsCocosType(argument.getAsType(), level + 1);
        if (argument.getKind() == TemplateArgument::Pack)
            for (const auto& packed : argument.pack_elements())
                if (self(self, packed, level + 1)) return true;
        return false;
    };
    for (const auto& argument : specialization->getTemplateArgs().asArray())
        if (argumentContains(argumentContains, argument, depth)) return true;
    return false;
}
bool retainingConstruction(const Expr* expr, ASTContext& context, const fs::path& sdk) {
    if (!expr) return false;
    expr = expr->IgnoreParenImpCasts();
    if (auto clean = dyn_cast<ExprWithCleanups>(expr)) return retainingConstruction(clean->getSubExpr(), context, sdk);
    if (auto temp = dyn_cast<MaterializeTemporaryExpr>(expr)) return retainingConstruction(temp->getSubExpr(), context, sdk);
    if (auto bind = dyn_cast<CXXBindTemporaryExpr>(expr)) return retainingConstruction(bind->getSubExpr(), context, sdk);
    if (auto cast = dyn_cast<CXXFunctionalCastExpr>(expr)) return retainingConstruction(cast->getSubExpr(), context, sdk);
    auto ctor = dyn_cast<CXXConstructExpr>(expr);
    return ctor && retainingRef(ctor->getType(), context, sdk) && ctor->getNumArgs() == 1 &&
        ctor->getArg(0)->getType()->isPointerType() &&
        cocosObject(ctor->getArg(0)->getType()->getPointeeType()->getAsCXXRecordDecl());
}
// Only unwrap the direct conversion into ScheduledFunction, never search a
// callback factory's arguments or a nested lambda for an unrelated closure.
const LambdaExpr* directLambda(const Expr* expr) {
    if (!expr) return nullptr;
    expr = expr->IgnoreParenImpCasts();
    if (auto lambda = dyn_cast<LambdaExpr>(expr)) return lambda;
    if (auto cleanup = dyn_cast<ExprWithCleanups>(expr)) return directLambda(cleanup->getSubExpr());
    if (auto temp = dyn_cast<MaterializeTemporaryExpr>(expr)) return directLambda(temp->getSubExpr());
    if (auto bind = dyn_cast<CXXBindTemporaryExpr>(expr)) return directLambda(bind->getSubExpr());
    if (auto ctor = dyn_cast<CXXConstructExpr>(expr))
        if (ctor->getNumArgs() == 1) return directLambda(ctor->getArg(0));
    return nullptr;
}
class Uses final : public RecursiveASTVisitor<Uses> {
    const VarDecl* variable;
    bool refers(const Expr* expr) const {
        if (!expr) return false;
        expr = expr->IgnoreParenCasts();
        auto reference = dyn_cast<DeclRefExpr>(expr);
        return reference && reference->getDecl()->getCanonicalDecl() == variable;
    }
public:
    const DeclRefExpr* first = nullptr;
    bool nestedLambda = false, ownershipOperation = false;
    explicit Uses(const VarDecl* var) : variable(var->getCanonicalDecl()) {}
    bool VisitDeclRefExpr(DeclRefExpr* ref) {
        if (ref->getDecl()->getCanonicalDecl() == variable && !first) first = ref;
        return true;
    }
    bool VisitLambdaExpr(LambdaExpr*) { nestedLambda = true; return true; }
    bool VisitVarDecl(VarDecl* decl) {
        if (decl == variable || !decl->hasInit() || !containsCocosType(decl->getType())) return true;
        const Expr* init = decl->getInit()->IgnoreParenCasts();
        if (auto clean = dyn_cast<ExprWithCleanups>(init)) init = clean->getSubExpr()->IgnoreParenCasts();
        if (auto bind = dyn_cast<CXXBindTemporaryExpr>(init)) init = bind->getSubExpr()->IgnoreParenCasts();
        if (refers(init)) ownershipOperation = true;
        if (auto conversion = dyn_cast<CXXMemberCallExpr>(init))
            if (isa_and_nonnull<CXXConversionDecl>(conversion->getMethodDecl()) && refers(conversion->getImplicitObjectArgument()))
                ownershipOperation = true;
        if (auto ctor = dyn_cast<CXXConstructExpr>(init))
            for (const auto* argument : ctor->arguments())
                if (refers(argument)) ownershipOperation = true;
        return true;
    }
    bool VisitBinaryOperator(BinaryOperator* binary) {
        if (binary->isAssignmentOp() && refers(binary->getLHS())) ownershipOperation = true;
        return true;
    }
    bool VisitCXXMemberCallExpr(CXXMemberCallExpr* call) {
        auto method = call->getMethodDecl();
        if (!method) return true;
        auto name = method->getNameAsString();
        if (name == "retain" || name == "release" || name == "autorelease" ||
            name == "take" || name == "swap" || name == "data") ownershipOperation = true;
        return true;
    }
    bool VisitCXXOperatorCallExpr(CXXOperatorCallExpr* call) {
        if (call->getOperator() == OO_Equal && call->getNumArgs() > 0) {
            auto object = call->getArg(0)->getType()->getAsCXXRecordDecl();
            auto ref = dyn_cast_or_null<ClassTemplateSpecializationDecl>(object);
            if (ref && ref->getSpecializedTemplate()->getQualifiedNameAsString() == "geode::Ref")
                ownershipOperation = true;
        }
        return true;
    }
};
const CompoundStmt* directBody(const Stmt* stmt, ASTContext& context, const Stmt*& top) {
    top = stmt;
    while (true) {
        auto parents = context.getParents(*top);
        if (parents.size() != 1) return nullptr;
        if (auto body = parents[0].get<CompoundStmt>()) return body;
        auto parent = parents[0].get<Stmt>();
        if (!parent) return nullptr;
        top = parent;
    }
}
bool fieldWrite(const Stmt* statement, const VarDecl* variable) {
    auto expr = dyn_cast<Expr>(statement);
    if (!expr) return false;
    expr = expr->IgnoreParenImpCasts();
    const Expr* lhs = nullptr;
    const Expr* rhsExpr = nullptr;
    if (auto binary = dyn_cast<BinaryOperator>(expr)) {
        if (!binary->isAssignmentOp()) return false;
        lhs = binary->getLHS(); rhsExpr = binary->getRHS();
    } else if (auto op = dyn_cast<CXXOperatorCallExpr>(expr)) {
        // GD stores some numeric fields in SDK SeedValue wrappers. Their
        // assignment receives the field and an integer, not the Cocos pointer.
        if (op->getOperator() != OO_Equal || op->getNumArgs() != 2) return false;
        auto record = op->getArg(0)->getType()->getAsCXXRecordDecl();
        if (!record || (record->getQualifiedNameAsString() != "geode::SeedValueRSV" &&
            record->getQualifiedNameAsString() != "geode::SeedValueVRS" &&
            record->getQualifiedNameAsString() != "geode::SeedValueRVS")) return false;
        lhs = op->getArg(0); rhsExpr = op->getArg(1);
    }
    if (!lhs || !rhsExpr) return false;
    auto member = dyn_cast<MemberExpr>(lhs->IgnoreParenImpCasts());
    auto base = member ? dyn_cast<DeclRefExpr>(member->getBase()->IgnoreParenImpCasts()) : nullptr;
    Uses rhs(variable);
    rhs.TraverseStmt(const_cast<Expr*>(rhsExpr));
    return base && base->getDecl()->getCanonicalDecl() == variable->getCanonicalDecl() && !rhs.first;
}
std::string unsupportedFlow(const VarDecl& variable, const CallExpr& call, ASTContext& context) {
    const Stmt* top = nullptr;
    auto body = directBody(&call, context, top);
    if (!body) return "callback is not a direct statement in a function body";
    auto parents = context.getParents(*body);
    if (parents.size() != 1 || !parents[0].get<FunctionDecl>())
        return "conditional or nested control flow is not modeled";
    bool foundOrigin = false, foundQueue = false;
    for (auto statement : body->body()) {
        if (auto declarations = dyn_cast<DeclStmt>(statement)) {
            bool origin = false;
            for (auto decl : declarations->decls()) origin |= decl == &variable;
            if (origin) {
                if (!declarations->isSingleDecl()) return "multiple-declaration ownership flow is not modeled";
                foundOrigin = true;
                continue;
            }
        }
        if (statement == top) {
            if (!foundOrigin) return "object is not initialized earlier in the same function body";
            // A queue call hidden in a larger expression can change ownership.
            auto expr = dyn_cast<Expr>(top);
            if (!expr || expr->IgnoreParenImpCasts()->IgnoreImplicit() != &call)
                return "queue call is embedded in an unsupported expression";
            foundQueue = true;
            continue;
        }
        if (!foundOrigin) continue;
        if (isa<IfStmt>(statement) || isa<ForStmt>(statement) || isa<WhileStmt>(statement) ||
            isa<SwitchStmt>(statement) || isa<DoStmt>(statement) || isa<CompoundStmt>(statement) ||
            isa<GotoStmt>(statement) || isa<LabelStmt>(statement))
            return "branching ownership flow is not modeled";
        Uses uses(&variable);
        uses.TraverseStmt(const_cast<Stmt*>(statement));
        if (uses.first && !(fieldWrite(statement, &variable) && !foundQueue))
            return "object has aliases, escapes, reassignment, or manual lifetime operations outside the callback";
    }
    return foundOrigin && foundQueue ? "" : "object origin is outside supported local flow";
}
}
void inspectQueuedOwnership(const CallExpr& call, ASTContext& context,
    Inventory& result, const fs::path& root, const fs::path& build) {
    auto callee = call.getDirectCallee();
    if (!callee || result.sdkRoot.empty() || !sdkDeclaration(*callee->getCanonicalDecl(), context, result.sdkRoot)) return;
    auto name = callee->getQualifiedNameAsString();
    if (name != "geode::Loader::queueInMainThread" && name != "geode::queueInMainThread") return;
    auto& sm = context.getSourceManager();
    if (!belongsToProject(sm.getFilename(sm.getExpansionLoc(call.getExprLoc())).str(), root, build)) return;
    auto queueSite = site(call.getExprLoc(), context, root);
    result.queuedCallbacks.push_back(queueSite);
    const auto* lambda = call.getNumArgs() == 1 ? directLambda(call.getArg(0)) : nullptr;
    auto unknown = [&](SourceLocation loc, const std::string& reason) {
        result.unknown.push_back({"Deferred Cocos ownership unknown: " + reason, site(loc, context, root)});
    };
    if (!lambda) { unknown(call.getExprLoc(), "queued callable is not a direct lambda"); return; }
    for (const auto& capture : lambda->captures()) {
        if (!capture.capturesVariable()) {
            if (capture.capturesThis()) unknown(capture.getLocation(), "captured this requires an owner-lifetime model");
            continue;
        }
        auto variable = dyn_cast<VarDecl>(capture.getCapturedVar());
        if (!variable) {
            if (containsCocosType(capture.getCapturedVar()->getType()))
                unknown(capture.getLocation(), "Cocos structured-binding capture is not modeled");
            continue;
        }
        auto type = variable->getType();
        if (type->isReferenceType() && containsCocosType(type)) {
            unknown(capture.getLocation(), "reference-typed Cocos capture is not modeled"); continue;
        }
        bool ref = retainingRef(type, context, result.sdkRoot);
        bool pointer = type->isPointerType() && cocosObject(type->getPointeeType()->getAsCXXRecordDecl());
        if (!ref && !pointer) {
            if (containsCocosType(type)) unknown(capture.getLocation(), "Cocos wrapper/container ownership is not modeled");
            continue;
        }
        Uses uses(variable);
        uses.TraverseStmt(const_cast<Stmt*>(lambda->getBody()));
        if (!uses.first) continue;
        if (capture.getCaptureKind() != LCK_ByCopy || capture.isImplicit()) {
            unknown(capture.getLocation(), "reference/default capture is not modeled"); continue;
        }
        if (uses.nestedLambda || uses.ownershipOperation) {
            unknown(capture.getLocation(), "callback contains nested captures, owner aliases, or manual lifetime operations"); continue;
        }
        if (ref) {
            if (!variable->hasInit() || !retainingConstruction(variable->getInit(), context, result.sdkRoot)) {
                unknown(capture.getLocation(), "Ref origin is not a supported retaining constructor (adopt/move/custom origins are not modeled)");
                continue;
            }
            if (!variable->isInitCapture()) {
                auto flow = unsupportedFlow(*variable, call, context);
                if (!flow.empty()) { unknown(capture.getLocation(), flow); continue; }
            }
            result.retainingCaptures.push_back(site(capture.getLocation(), context, root));
            continue;
        }
        if (variable->isInitCapture()) {
            unknown(capture.getLocation(), "raw init capture may alias another owner"); continue;
        }
        auto origin = variable->hasInit() ? dyn_cast<CallExpr>(variable->getInit()->IgnoreParenImpCasts()) : nullptr;
        auto factory = origin ? origin->getDirectCallee() : nullptr;
        auto method = dyn_cast_or_null<CXXMethodDecl>(factory);
        std::string contract;
        if (method && method->isStatic() && origin->getNumArgs() == 0) {
            auto factoryName = factory->getQualifiedNameAsString();
            if (factoryName == "cocos2d::CCNode::create" && sdkDeclaration(*factory, context, result.sdkRoot))
                contract = "documented_autorelease";
            else if (factoryName == "GJGameLevel::create" &&
                !belongsToProject(sm.getFilename(factory->getLocation()).str(), root, build))
                contract = "mac_implementation_unverified";
        }
        if (contract.empty()) { unknown(capture.getLocation(), "object origin/factory ownership is not modeled"); continue; }
        auto flow = unsupportedFlow(*variable, call, context);
        if (!flow.empty()) { unknown(capture.getLocation(), flow); continue; }
        Finding finding;
        finding.rule = "geode.deferred-cocos-ownership";
        finding.severity = "review";
        finding.evidence = "inferred_risk";
        finding.variable = variable->getNameAsString();
        finding.message = "Queued callback captures a raw Cocos object without retaining it.";
        finding.suggestion = "Review the object's owner and callback timing. Consider a by-value Ref capture to retain it until queued work completes; verify intended behavior after the change.";
        finding.limitations = "External owners and runtime scheduling are not established; a crash was not reproduced. This is an ownership review, not a confirmed defect.";
        if (contract == "mac_implementation_unverified")
            finding.limitations += " The macOS GJGameLevel factory implementation is unavailable in the bindings; autorelease behavior is not independently verified.";
        finding.factoryContract = contract;
        finding.location = site(capture.getLocation(), context, root);
        finding.related = {{"origin", site(variable->getLocation(), context, root)},
            {"use", site(uses.first->getLocation(), context, root)}};
        result.findings.push_back(std::move(finding));
    }
}
}
