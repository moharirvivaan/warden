#include "hook_behavior.hpp"
#include <clang/AST/ASTContext.h>
#include <clang/AST/DeclTemplate.h>
#include <clang/AST/ExprCXX.h>
#include <clang/AST/Stmt.h>
#include <clang/Basic/SourceManager.h>
#include <functional>
#include <limits>

namespace warden {
using namespace clang;
namespace {
Location site(SourceLocation loc, ASTContext& ctx, const fs::path& root) {
    auto& sm=ctx.getSourceManager(); loc=sm.getExpansionLoc(loc);
    if(loc.isInvalid()) return {};
    auto file=fs::weakly_canonical(sm.getFilename(loc).str());
    return {file.lexically_relative(root).generic_string(),sm.getExpansionLineNumber(loc),sm.getExpansionColumnNumber(loc)};
}
bool sdkDecl(const Decl& decl, ASTContext& ctx, const Inventory& inv) {
    auto file=fs::weakly_canonical(ctx.getSourceManager().getFilename(ctx.getSourceManager().getSpellingLoc(decl.getLocation())).str());
    auto rel=file.lexically_relative(fs::weakly_canonical(inv.sdkRoot));
    return !rel.empty()&&*rel.begin()!="..";
}
// Context is syntactic placement, never a claim about execution or all paths.
void walk(const Stmt* stmt, const std::string& context,
          const std::function<void(const CallExpr&,const std::string&)>& visit) {
    if(!stmt) return;
    if(auto call=dyn_cast<CallExpr>(stmt)) visit(*call,context);
    if(auto lambda=dyn_cast<LambdaExpr>(stmt)) {
        walk(lambda->getBody(),"nested_callable",visit); return;
    }
    const bool nested=context=="nested_callable";
    if(auto branch=dyn_cast<IfStmt>(stmt)) {
        walk(branch->getInit(),context,visit);
        walk(branch->getCond(),context=="body"?"condition":context,visit);
        walk(branch->getThen(),nested?context:"conditional_branch",visit);
        walk(branch->getElse(),nested?context:"conditional_branch",visit); return;
    }
    if(auto binary=dyn_cast<BinaryOperator>(stmt);binary&&binary->isLogicalOp()) {
        walk(binary->getLHS(),context,visit);
        walk(binary->getRHS(),nested?context:"conditional_branch",visit); return;
    }
    if(auto branch=dyn_cast<ConditionalOperator>(stmt)) {
        walk(branch->getCond(),context,visit);
        walk(branch->getTrueExpr(),nested?context:"conditional_branch",visit);
        walk(branch->getFalseExpr(),nested?context:"conditional_branch",visit); return;
    }
    auto childContext=context;
    if(!nested&&(isa<ForStmt>(stmt)||isa<WhileStmt>(stmt)||isa<DoStmt>(stmt)||isa<CXXForRangeStmt>(stmt)))childContext="loop";
    if(!nested&&isa<SwitchStmt>(stmt))childContext="conditional_branch";
    for(auto child:stmt->children())walk(child,childContext,visit);
}
std::string literal(const Stmt* stmt) {
    if(!stmt) return {};
    if(auto value=dyn_cast<StringLiteral>(stmt)) return value->getString().str();
    // Only literal/conversion wrappers, never arbitrary calls with string arguments.
    if(isa<ExprWithCleanups>(stmt)||isa<MaterializeTemporaryExpr>(stmt)||isa<CXXBindTemporaryExpr>(stmt)||
       isa<ImplicitCastExpr>(stmt)||isa<CXXConstructExpr>(stmt)||isa<ParenExpr>(stmt)) {
        for(auto child:stmt->children()) {auto value=literal(child);if(!value.empty())return value;}
    }
    return {};
}
}
HookBehavior inspectHookBehavior(const CXXMethodDecl& method,const CXXRecordDecl& modification,
    const CXXRecordDecl& target,ASTContext& ctx,const Inventory& inv,const fs::path& root) {
    HookBehavior result;
    const auto* definition=method.getDefinition();
    if(definition&&definition->getBody()) {
        walk(definition->getBody(),"body",[&](const CallExpr& call,const std::string& context){
            auto member=dyn_cast<CXXMemberCallExpr>(&call);
            auto callee=member?member->getMethodDecl():nullptr;
            if(!callee||callee->getParent()->getCanonicalDecl()!=target.getCanonicalDecl()||
               callee->getName()!=method.getName()||!ctx.hasSameType(callee->getType(),method.getType()))return;
            auto receiver=member->getImplicitObjectArgument();
            if(receiver&&isa<CXXThisExpr>(receiver->IgnoreParenImpCasts()))
                result.forwardingCalls.push_back({site(call.getExprLoc(),ctx,root),context});
        });
    }
    if(result.forwardingCalls.empty())result.unknown.push_back({
        "No supported direct forwarding call observed; helper-mediated or intentional replacement behavior is unresolved.",site(method.getLocation(),ctx,root)});
    bool priorityContext=false;
    for(auto decl:modification.decls()) {
        auto templ=dyn_cast<FunctionTemplateDecl>(decl);
        if(!templ||templ->getNameAsString()!="onModify")continue;
        for(auto spec:templ->specializations()) {
            if(!spec->hasBody()||spec->getNumParams()!=1)continue;
            priorityContext=true;
            auto self=spec->getParamDecl(0);
            walk(spec->getBody(),"body",[&](const CallExpr& call,const std::string& context){
                auto member=dyn_cast<CXXMemberCallExpr>(&call);
                auto callee=member?member->getMethodDecl():nullptr;
                if(!callee||call.getNumArgs()<2||!sdkDecl(*callee,ctx,inv)||
                   callee->getQualifiedNameAsString().find("geode::modifier::ModifyBase")!=0)return;
                auto receiver=member->getImplicitObjectArgument();
                auto ref=receiver?dyn_cast<DeclRefExpr>(receiver->IgnoreParenImpCasts()):nullptr;
                if(!ref||ref->getDecl()->getCanonicalDecl()!=self->getCanonicalDecl())return;
                auto api=callee->getNameAsString();
                if(api.rfind("setHookPriority",0)!=0)return;
                auto name=literal(call.getArg(0));
                const auto expected=target.getQualifiedNameAsString()+"::"+method.getNameAsString();
                if(name!=expected) {
                    if(name.empty())result.unknown.push_back({"Dynamic priority hook name is unresolved.",site(call.getExprLoc(),ctx,root)});
                    return;
                }
                PriorityRequest request{site(call.getExprLoc(),ctx,root),name,api,"unknown","",{}, {}};
                bool unconditional=context=="body"||context=="condition";
                if(api=="setHookPriority"||api=="setHookPriorityPre"||api=="setHookPriorityPost") {
                    Expr::EvalResult value;
                    if(call.getArg(1)->EvaluateAsInt(value,ctx)&&value.Val.getInt().isSignedIntN(32)) {
                        auto number=value.Val.getInt().getSExtValue();request.requestedValue=number;
                        if(unconditional&&!(api=="setHookPriorityPost"&&number==std::numeric_limits<int32_t>::min())) {
                            request.status="observed_constant";
                            request.preOrderValue=api=="setHookPriorityPost"?-number:number;
                        }
                    }
                } else {
                    request.relativeMod=literal(call.getArg(1));
                    if(unconditional&&!request.relativeMod.empty())request.status="observed_relative";
                }
                if(request.status=="unknown")result.unknown.push_back({"Priority request is dynamic, conditional, unsupported or outside the numeric range; effective order is unknown.",request.location});
                result.priorityRequests.push_back(std::move(request));
            });
        }
    }
    if(!priorityContext) result.unknown.push_back({"No instantiated priority context observed; no default priority is assumed.",site(method.getLocation(),ctx,root)});
    return result;
}
}
