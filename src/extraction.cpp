#include "extraction.hpp"
#include "hook_behavior.hpp"
#include "ownership.hpp"
#include "array_bounds.hpp"
#include <clang/AST/ASTConsumer.h>
#include <clang/AST/ASTContext.h>
#include <clang/AST/DeclTemplate.h>
#include <clang/AST/RecursiveASTVisitor.h>
#include <clang/Basic/TargetInfo.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Lex/MacroArgs.h>
#include <clang/Lex/PPCallbacks.h>
#include <clang/Lex/Preprocessor.h>
#include <fstream>
#include <map>
#include <set>

namespace warden {
using namespace clang;
namespace {
struct MacroOrigin { SourceLocation location; std::string form; };
struct State {
    Inventory& result;
    fs::path root, build;
    std::vector<MacroOrigin> origins;
    std::map<unsigned, std::string> registrations;
    bool supportedSdk = false;
    mutable std::map<std::string, bool> projectFiles;
    State(Inventory& r, fs::path p, fs::path b) : result(r), root(std::move(p)), build(std::move(b)) {}
};
void noteSdkFile(SourceLocation loc, const SourceManager& sm, State& state) {
    auto file=fs::weakly_canonical(sm.getFilename(sm.getSpellingLoc(loc)).str());
    fs::path suffix;
    unsigned levels=0;
    if (file.filename()=="Modify.hpp") {suffix="loader/include/Geode/modify/Modify.hpp";levels=5;}
    else if (file.filename()=="CCArray.h") {suffix="loader/include/Geode/cocos/cocoa/CCArray.h";levels=6;}
    else if (file.filename()=="Loader.hpp") {suffix="loader/include/Geode/loader/Loader.hpp";levels=5;}
    else return;
    auto sdk=file;for (unsigned i=0;i<levels;++i) sdk=sdk.parent_path();
    if (sdk/suffix!=file) return;
    std::ifstream version(sdk/"VERSION");std::string value;version>>value;
    state.result.sdkVersion=value;state.result.sdkRoot=sdk.string();
    state.supportedSdk=value=="5.11.1"||value=="5.10.1"||value=="5.8.2";
}
Location location(SourceLocation input, const SourceManager& sm, const fs::path& root) {
    if (input.isInvalid()) return {};
    const auto loc = sm.getExpansionLoc(input);
    std::string file = sm.getFilename(loc).str();
    if (!file.empty()) {
        auto relative = fs::weakly_canonical(file).lexically_relative(root);
        if (!relative.empty() && *relative.begin() != "..") file = relative.generic_string();
    }
    return {file, sm.getExpansionLineNumber(loc), sm.getExpansionColumnNumber(loc)};
}
bool projectLocation(SourceLocation loc, const SourceManager& sm, const State& state) {
    if (loc.isInvalid()) return false;
    auto file=sm.getFilename(sm.getExpansionLoc(loc)).str();
    auto known=state.projectFiles.find(file);
    if (known!=state.projectFiles.end()) return known->second;
    return state.projectFiles.emplace(file,belongsToProject(file,state.root,state.build)).first->second;
}
class MacroTracker final : public PPCallbacks {
    State& state;
    SourceManager& sm;
public:
    MacroTracker(State& s, SourceManager& source) : state(s), sm(source) {}
    void FileChanged(SourceLocation loc, FileChangeReason reason,
                     SrcMgr::CharacteristicKind, FileID) override {
        if (reason != EnterFile || !projectLocation(loc, sm, state)) return;
        auto file = fs::path(sm.getFilename(sm.getExpansionLoc(loc)).str());
        auto extension = file.extension().string();
        if (extension == ".h" || extension == ".hpp" || extension == ".hh" || extension == ".hxx")
            state.result.includedHeaders.push_back(fs::weakly_canonical(file).lexically_relative(state.root).generic_string());
    }
    void noteSdk(const MacroInfo* info) {
        if (!info) return;
        noteSdkFile(info->getDefinitionLoc(),sm,state);
    }
    void MacroDefined(const Token& name, const MacroDirective* directive) override {
        if (name.getIdentifierInfo() && name.getIdentifierInfo()->getName() == "$modify")
            noteSdk(directive->getMacroInfo());
    }
    void MacroExpands(const Token& name, const MacroDefinition& definition,
                      SourceRange range, const MacroArgs* args) override {
        if (!name.getIdentifierInfo()) return;
        auto spelling = name.getIdentifierInfo()->getName();
        if (spelling == "GEODE_APPLY_MODIFY_FOR_FUNCTION" || spelling == "GEODE_APPLY_MODIFY_FOR_CONSTRUCTOR" ||
            spelling == "GEODE_APPLY_MODIFY_FOR_DESTRUCTOR")
            state.registrations[sm.getExpansionLoc(range.getBegin()).getRawEncoding()] = spelling.str();
        if (spelling != "$modify" || !projectLocation(range.getBegin(), sm, state)) return;
        // $modify is variadic: both public forms occupy one variadic argument.
        bool named = false;
        if (args) {
            unsigned nesting = 0;
            for (auto token = args->getUnexpArgument(0); !token->is(tok::eof); ++token) {
                if (token->is(tok::l_paren)) ++nesting;
                else if (token->is(tok::r_paren) && nesting) --nesting;
                else if (token->is(tok::comma) && !nesting) named = true;
            }
        }
        state.origins.push_back({sm.getExpansionLoc(range.getBegin()), named ? "named" : "anonymous"});
        noteSdk(definition.getMacroInfo());
    }
};
const CXXMethodDecl* methodArgument(const TemplateArgument& arg) {
    if (arg.getKind() == TemplateArgument::Declaration)
        return dyn_cast_or_null<CXXMethodDecl>(arg.getAsDecl());
    if (arg.getKind() == TemplateArgument::Expression) {
        const Expr* e = arg.getAsExpr()->IgnoreParenImpCasts();
        if (auto unary = dyn_cast<UnaryOperator>(e)) e = unary->getSubExpr()->IgnoreParenImpCasts();
        if (auto ref = dyn_cast<DeclRefExpr>(e)) return dyn_cast<CXXMethodDecl>(ref->getDecl());
        if (auto member = dyn_cast<MemberExpr>(e)) return dyn_cast<CXXMethodDecl>(member->getMemberDecl());
    }
    return nullptr;
}
const CXXMethodDecl* differentMethod(const IfStmt& stmt) {
    auto ref = dyn_cast<DeclRefExpr>(stmt.getCond()->IgnoreParenImpCasts());
    auto variable = ref ? dyn_cast<VarDecl>(ref->getDecl()) : nullptr;
    if (!variable || variable->getName() != "different" || !variable->getInit()) return nullptr;
    auto call = dyn_cast<CallExpr>(variable->getInit()->IgnoreParenImpCasts());
    auto function = call ? call->getDirectCallee() : nullptr;
    auto arguments = function ? function->getTemplateSpecializationArgs() : nullptr;
    if (!arguments || arguments->size() < 2) return nullptr;
    return methodArgument(arguments->get(1));
}
struct ModifiedRecord {
    const CXXRecordDecl* record;
    const CXXRecordDecl* base;
    Modification modification;
    bool scanned = false;
    std::map<const CXXMethodDecl*, std::string> hooks;
    std::set<std::string> unsupportedMethods;
};
class RegistrationVisitor final : public RecursiveASTVisitor<RegistrationVisitor> {
    ASTContext& context;
    State& state;
    ModifiedRecord& record;
public:
    RegistrationVisitor(ASTContext& ctx, State& s, ModifiedRecord& r) : context(ctx), state(s), record(r) {}
    bool TraverseIfStmt(IfStmt* stmt) {
        auto& sm = context.getSourceManager();
        auto site = sm.getExpansionLoc(stmt->getIfLoc());
        auto registration = state.registrations.find(site.getRawEncoding());
        if (stmt->isConstexpr() && registration != state.registrations.end()) {
            bool active = false;
            if (!stmt->getCond()->EvaluateAsBooleanCondition(active, context)) {
                state.result.unknown.push_back({"Cannot evaluate Geode registration branch.", record.modification.location});
            } else if (active && registration->second == "GEODE_APPLY_MODIFY_FOR_FUNCTION") {
                auto method = differentMethod(*stmt);
                if (method && method->getParent()->getCanonicalDecl() == record.record->getCanonicalDecl())
                    record.hooks[method->getCanonicalDecl()] = "GEODE_APPLY_MODIFY_FOR_FUNCTION";
                else state.result.unknown.push_back({"Cannot resolve method in active Geode registration.", record.modification.location});
            } else if (active) {
                record.unsupportedMethods.insert(registration->second == "GEODE_APPLY_MODIFY_FOR_CONSTRUCTOR" ?
                    "constructor" : "destructor");
            }
            return true;
        }
        return RecursiveASTVisitor::TraverseIfStmt(stmt);
    }
};
class Visitor final : public RecursiveASTVisitor<Visitor> {
    ASTContext& context;
    State& state;
    std::map<const CXXRecordDecl*, ModifiedRecord> records;
    std::vector<const CXXMethodDecl*> applications;
    std::vector<const CallExpr*> queuedCalls;
    std::vector<const CXXMemberCallExpr*> arrayCalls;
public:
    Visitor(ASTContext& ctx, State& s) : context(ctx), state(s) {}
    bool shouldVisitTemplateInstantiations() const { return true; }
    bool VisitCXXRecordDecl(CXXRecordDecl* decl) {
        auto& sm = context.getSourceManager();
        if (!decl->isThisDeclarationADefinition() || decl->isImplicit() ||
            !projectLocation(decl->getLocation(), sm, state)) return true;
        for (const auto& base : decl->bases()) {
            auto specialization = dyn_cast_or_null<ClassTemplateSpecializationDecl>(base.getType()->getAsCXXRecordDecl());
            if (!specialization || specialization->getSpecializedTemplate()->getQualifiedNameAsString() != "geode::Modify") continue;
            if (state.result.sdkVersion.empty()) noteSdkFile(specialization->getSpecializedTemplate()->getLocation(),sm,state);
            auto target = specialization->getTemplateArgs().get(1).getAsType()->getAsCXXRecordDecl();
            if (!target) continue;
            const MacroOrigin* origin = nullptr;
            auto declLocation = location(decl->getLocation(), sm, state.root);
            for (const auto& candidate : state.origins) {
                auto macroLocation = location(candidate.location, sm, state.root);
                if (macroLocation.file == declLocation.file && macroLocation.line == declLocation.line &&
                    sm.getExpansionLoc(decl->getBeginLoc()) == candidate.location) { origin = &candidate; break; }
            }
            // The class keyword precedes the macro; the declaration name expands at the macro site.
            if (!origin) for (const auto& candidate : state.origins)
                if (sm.getExpansionLoc(decl->getLocation()) == candidate.location) { origin = &candidate; break; }
            if (!origin && !state.supportedSdk) {
                state.result.unknown.push_back({"Direct geode::Modify inheritance requires a resolved, validated SDK.", declLocation});
                continue;
            }
            Modification modification{decl->getQualifiedNameAsString(), target->getQualifiedNameAsString(),
                origin ? origin->form : "direct", origin ? location(origin->location, sm, state.root) : declLocation};
            records.emplace(decl->getCanonicalDecl(), ModifiedRecord{decl, target, modification, false, {}, {}});
        }
        return true;
    }
    bool VisitCXXMethodDecl(CXXMethodDecl* decl) {
        if (decl->getNameAsString() != "apply" || !decl->hasBody()) return true;
        auto parent = dyn_cast<ClassTemplateSpecializationDecl>(decl->getParent());
        if (parent && parent->getSpecializedTemplate()->getQualifiedNameAsString() == "geode::modifier::ModifyDerive")
            applications.push_back(decl);
        return true;
    }
    bool VisitCallExpr(CallExpr* call) {
        auto& sm = context.getSourceManager();
        if (!projectLocation(call->getExprLoc(), sm, state)) return true;
        auto callee = call->getDirectCallee();
        if (!callee) return true;
        auto name = callee->getQualifiedNameAsString();
        if (name == "cocos2d::CCArray::objectAtIndex") {
            if (state.result.sdkVersion.empty()) noteSdkFile(callee->getCanonicalDecl()->getLocation(),sm,state);
            if (auto member = dyn_cast<CXXMemberCallExpr>(call)) arrayCalls.push_back(member);
        }
        if (name == "geode::Loader::queueInMainThread" || name == "geode::queueInMainThread") {
            if (state.result.sdkVersion.empty()) noteSdkFile(callee->getCanonicalDecl()->getLocation(),sm,state);
            queuedCalls.push_back(call);
        }
        if (name == "geode::Mod::hook" || name == "geode::Hook::create" || name == "tulip::hook::createHook")
            state.result.unknown.push_back({"Manual/raw hook call is outside supported coverage.", location(call->getExprLoc(), sm, state.root)});
        return true;
    }
    void finish() {
        const auto triple = context.getTargetInfo().getTriple();
        state.result.target = triple.str();
        if (!state.origins.empty() && !state.supportedSdk) {
            state.result.unknown.push_back({"Unsupported or unresolved SDK: Geode 5.8.2, 5.10.1 and 5.11.1 are validated.", {}});
            return;
        }
        if (!triple.isMacOSX() || triple.getArch() != llvm::Triple::aarch64) {
            state.result.unknown.push_back({"Unsupported target: only macOS ARM64 is validated.", {}});
            return;
        }
        if (state.supportedSdk)
            for (const auto* call : queuedCalls)
                inspectQueuedOwnership(*call, context, state.result, state.root, state.build);
        else if (!queuedCalls.empty())
            state.result.unknown.push_back({"Deferred Cocos ownership requires validated Geode 5.8.2, 5.10.1 or 5.11.1 SDK contracts.", {}});
        if (state.supportedSdk)
            for (const auto* call : arrayCalls)
                inspectArrayBounds(*call, context, state.result, state.root);
        else if (!arrayCalls.empty())
            state.result.unknown.push_back({"Array bounds analysis requires resolved, validated Geode SDK contracts.", {}});
        for (const auto* application : applications) {
            auto specialization = cast<ClassTemplateSpecializationDecl>(application->getParent());
            auto derived = specialization->getTemplateArgs().get(0).getAsType()->getAsCXXRecordDecl();
            if (!derived) continue;
            auto found = records.find(derived->getCanonicalDecl());
            if (found == records.end()) continue;
            found->second.scanned = true;
            RegistrationVisitor registrations(context, state, found->second);
            registrations.TraverseStmt(const_cast<Stmt*>(application->getBody()));
        }
        for (auto& [_, record] : records) {
            state.result.modifications.push_back(record.modification);
            if (!record.scanned) {
                state.result.unknown.push_back({"Geode registration was not instantiated for this modification.", record.modification.location});
                continue;
            }
            for (const auto* method : record.record->methods()) {
                if (method->isImplicit()) continue;
                Method result{record.modification.name, record.modification.targetClass,
                    method->getNameAsString(), method->getType().getCanonicalType().getAsString(context.getPrintingPolicy()), "",
                    location(method->getLocation(), context.getSourceManager(), state.root), {}};
                auto hook = record.hooks.find(method->getCanonicalDecl());
                if (hook != record.hooks.end()) {
                    result.registration = hook->second;
                    result.behavior = inspectHookBehavior(*method, *record.record, *record.base, context, state.result, state.root);
                    auto sameName=std::count_if(record.hooks.begin(),record.hooks.end(),[&](const auto& item){return item.first->getNameAsString()==method->getNameAsString();});
                    if(sameName>1&&!result.behavior->priorityRequests.empty()) {
                        for(auto& request:result.behavior->priorityRequests){request.status="unknown";request.preOrderValue.reset();}
                        result.behavior->unknown.push_back({"Priority name refers to multiple registered overloads; selected hook and ordering are unknown.",result.location});
                    }
                    state.result.hooks.push_back(std::move(result));
                } else if (record.unsupportedMethods.contains(result.name)) {
                    state.result.unknown.push_back({"Unsupported Geode lifecycle registration: " + result.name, result.location});
                } else if (isa<CXXConstructorDecl>(method) || isa<CXXDestructorDecl>(method) || method->getNameAsString() == "onModify") {
                    state.result.unknown.push_back({"Lifecycle/constructor/destructor modification is outside supported coverage.", result.location});
                } else {
                    bool sameBaseSignature = method->isVirtual();
                    for (const auto* baseMethod : record.base->methods())
                        sameBaseSignature |= baseMethod->getNameAsString() == method->getNameAsString() &&
                            baseMethod->isStatic() == method->isStatic() && context.hasSameType(baseMethod->getType(), method->getType());
                    if (sameBaseSignature) state.result.unknown.push_back({"Method matches a base signature but has no supported registration evidence: " + result.name, result.location});
                    else state.result.helpers.push_back(std::move(result));
                }
            }
            for (const auto* declaration : record.record->decls()) {
                if (auto memberTemplate = dyn_cast<FunctionTemplateDecl>(declaration)) {
                    if (isa<CXXMethodDecl>(memberTemplate->getTemplatedDecl()))
                        state.result.unknown.push_back({"Unsupported member template/lifecycle declaration: " +
                            memberTemplate->getNameAsString(), location(memberTemplate->getLocation(), context.getSourceManager(), state.root)});
                }
            }
        }
        for (const auto& origin : state.origins) {
            auto l = location(origin.location, context.getSourceManager(), state.root);
            bool represented = false;
            for (const auto& [_, record] : records)
                represented |= record.modification.location.file == l.file && record.modification.location.line == l.line &&
                    record.modification.location.column == l.column;
            if (!represented) state.result.unknown.push_back({"Unresolved $modify expansion.", l});
        }
    }
};
class Consumer final : public ASTConsumer {
    State& state;
public:
    explicit Consumer(State& s) : state(s) {}
    void HandleTranslationUnit(ASTContext& context) override {
        Visitor visitor(context, state);
        visitor.TraverseDecl(context.getTranslationUnitDecl());
        visitor.finish();
    }
};
class Action final : public ASTFrontendAction {
    State state;
public:
    Action(Inventory& result, fs::path root, fs::path build) : state(result, std::move(root), std::move(build)) {}
    std::unique_ptr<ASTConsumer> CreateASTConsumer(CompilerInstance& compiler, llvm::StringRef) override {
        compiler.getPreprocessor().addPPCallbacks(std::make_unique<MacroTracker>(state, compiler.getSourceManager()));
        return std::make_unique<Consumer>(state);
    }
};
}
std::unique_ptr<FrontendAction> makeExtractionAction(Inventory& result, const fs::path& root, const fs::path& build) {
    return std::make_unique<Action>(result, root, build);
}
}
