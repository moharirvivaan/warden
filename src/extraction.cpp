#include "extraction.hpp"
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
    std::set<unsigned> registrations;
    bool supportedSdk = false;
    State(Inventory& r, fs::path p, fs::path b) : result(r), root(std::move(p)), build(std::move(b)) {}
};
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
    return belongsToProject(sm.getFilename(sm.getExpansionLoc(loc)).str(), state.root, state.build);
}
class MacroTracker final : public PPCallbacks {
    State& state;
    SourceManager& sm;
public:
    MacroTracker(State& s, SourceManager& source) : state(s), sm(source) {}
    void MacroExpands(const Token& name, const MacroDefinition& definition,
                      SourceRange range, const MacroArgs* args) override {
        if (!name.getIdentifierInfo()) return;
        auto spelling = name.getIdentifierInfo()->getName();
        if (spelling == "GEODE_APPLY_MODIFY_FOR_FUNCTION")
            state.registrations.insert(sm.getExpansionLoc(range.getBegin()).getRawEncoding());
        if (spelling != "$modify" || !projectLocation(range.getBegin(), sm, state)) return;
        state.origins.push_back({sm.getExpansionLoc(range.getBegin()),
            args && args->getNumMacroArguments() == 1 ? "anonymous" : "named"});
        const auto definitionFile = fs::path(sm.getFilename(sm.getSpellingLoc(
            definition.getMacroInfo()->getDefinitionLoc())).str());
        // Geode's real Modify.hpp lives at SDK/loader/include/Geode/modify/Modify.hpp.
        auto sdk = definitionFile.parent_path().parent_path().parent_path().parent_path().parent_path();
        std::ifstream version(sdk / "VERSION");
        std::string value; version >> value;
        state.result.sdkVersion = value; state.result.sdkRoot = sdk.string();
        state.supportedSdk = definitionFile.filename() == "Modify.hpp" && value == "5.11.1";
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
        if (stmt->isConstexpr() && state.registrations.contains(site.getRawEncoding())) {
            bool active = false;
            if (!stmt->getCond()->EvaluateAsBooleanCondition(active, context)) {
                state.result.unknown.push_back({"Cannot evaluate Geode registration branch.", record.modification.location});
            } else if (active) {
                auto method = differentMethod(*stmt);
                if (method && method->getParent()->getCanonicalDecl() == record.record->getCanonicalDecl())
                    record.hooks[method->getCanonicalDecl()] = "GEODE_APPLY_MODIFY_FOR_FUNCTION";
                else state.result.unknown.push_back({"Cannot resolve method in active Geode registration.", record.modification.location});
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
            if (!origin) {
                state.result.unknown.push_back({"Direct geode::Modify inheritance is outside supported $modify coverage.", declLocation});
                continue;
            }
            Modification modification{decl->getNameAsString(), target->getQualifiedNameAsString(),
                origin->form, location(origin->location, sm, state.root)};
            records.emplace(decl->getCanonicalDecl(), ModifiedRecord{decl, target, modification, false, {}});
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
        if (name == "geode::Mod::hook" || name == "geode::Hook::create")
            state.result.unknown.push_back({"Manual/raw hook call is outside supported coverage.", location(call->getExprLoc(), sm, state.root)});
        return true;
    }
    void finish() {
        const auto triple = context.getTargetInfo().getTriple();
        state.result.target = triple.str();
        if (!state.origins.empty() && !state.supportedSdk) {
            state.result.unknown.push_back({"Unsupported or unresolved SDK: only Geode 5.11.1 is validated.", {}});
            return;
        }
        if (!triple.isMacOSX() || triple.getArch() != llvm::Triple::aarch64) {
            state.result.unknown.push_back({"Unsupported target: only macOS ARM64 is validated.", {}});
            return;
        }
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
                if (method->isImplicit() || !method->hasBody()) continue;
                Method result{record.modification.name, record.modification.targetClass,
                    method->getNameAsString(), method->getType().getCanonicalType().getAsString(context.getPrintingPolicy()), "",
                    location(method->getLocation(), context.getSourceManager(), state.root)};
                auto hook = record.hooks.find(method->getCanonicalDecl());
                if (hook != record.hooks.end()) {
                    result.registration = hook->second; state.result.hooks.push_back(std::move(result));
                } else if (isa<CXXConstructorDecl>(method) || isa<CXXDestructorDecl>(method) || method->getNameAsString() == "onModify") {
                    state.result.unknown.push_back({"Lifecycle/constructor/destructor modification is outside supported coverage.", result.location});
                } else {
                    bool sameBaseName = false;
                    for (const auto* baseMethod : record.base->methods())
                        sameBaseName |= baseMethod->getNameAsString() == method->getNameAsString();
                    if (sameBaseName) state.result.unknown.push_back({"Method shares a base name but has no supported registration evidence: " + result.name, result.location});
                    else state.result.helpers.push_back(std::move(result));
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
