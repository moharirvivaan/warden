#include "array_bounds.hpp"
#include <clang/AST/ParentMapContext.h>
#include <clang/AST/DeclTemplate.h>
#include <clang/Basic/SourceManager.h>
#include <clang/Lex/Lexer.h>
#include <llvm/Support/SHA256.h>
#include <llvm/ADT/StringExtras.h>
#include <algorithm>

namespace warden {
using namespace clang;
namespace {
Location location(SourceLocation loc, ASTContext& context, const fs::path& root) {
    auto& sm=context.getSourceManager(); loc=sm.getExpansionLoc(loc);
    auto file=fs::weakly_canonical(sm.getFilename(loc).str());
    auto relative=file.lexically_relative(root);
    return {relative.empty() || *relative.begin()==".." ? file.string() : relative.generic_string(),
        sm.getExpansionLineNumber(loc), sm.getExpansionColumnNumber(loc)};
}
bool sdkMethod(const CXXMethodDecl* method, const char* name, ASTContext& context, const Inventory& result) {
    if (!method || method->getQualifiedNameAsString()!=name || result.sdkRoot.empty()) return false;
    auto& sm=context.getSourceManager();
    auto file=fs::weakly_canonical(sm.getFilename(method->getCanonicalDecl()->getLocation()).str());
    auto relative=file.lexically_relative(fs::weakly_canonical(result.sdkRoot));
    return !relative.empty() && *relative.begin()!="..";
}
bool same(const Expr* first, const Expr* second) {
    if (!first || !second) return false;
    first=first->IgnoreParenImpCasts(); second=second->IgnoreParenImpCasts();
    if (auto a=dyn_cast<DeclRefExpr>(first)) {
        auto b=dyn_cast<DeclRefExpr>(second);
        return b && a->getDecl()->getCanonicalDecl()==b->getDecl()->getCanonicalDecl();
    }
    if (auto a=dyn_cast<MemberExpr>(first)) {
        auto b=dyn_cast<MemberExpr>(second);
        return b && a->getMemberDecl()->getCanonicalDecl()==b->getMemberDecl()->getCanonicalDecl() && same(a->getBase(), b->getBase());
    }
    if (isa<CXXThisExpr>(first) && isa<CXXThisExpr>(second)) return first->getType()==second->getType();
    if (auto a=dyn_cast<CXXOperatorCallExpr>(first)) {
        auto b=dyn_cast<CXXOperatorCallExpr>(second);
        auto method=dyn_cast_or_null<CXXMethodDecl>(a->getDirectCallee());
        auto parent=dyn_cast_or_null<ClassTemplateSpecializationDecl>(method ? method->getParent() : nullptr);
        return b && parent && parent->getSpecializedTemplate()->getQualifiedNameAsString()=="geode::Ref" &&
            a->getOperator()==OO_Arrow && b->getOperator()==OO_Arrow && a->getNumArgs()==1 && b->getNumArgs()==1 &&
            a->getDirectCallee()->getCanonicalDecl()==b->getDirectCallee()->getCanonicalDecl() && same(a->getArg(0),b->getArg(0));
    }
    if (auto a=dyn_cast<IntegerLiteral>(first)) {
        auto b=dyn_cast<IntegerLiteral>(second); return b && a->getValue()==b->getValue();
    }
    return false;
}
const Expr* guard(const Expr* condition, const Expr* array, const Expr* index,
    ASTContext& context, const Inventory& result, bool inRange=false) {
    if (!condition) return nullptr;
    auto binary=dyn_cast<BinaryOperator>(condition->IgnoreParenImpCasts());
    if (!binary) return nullptr;
    if (binary->getOpcode()==(inRange ? BO_LAnd : BO_LOr)) {
        if (auto found=guard(binary->getLHS(),array,index,context,result,inRange)) return found;
        return guard(binary->getRHS(),array,index,context,result,inRange);
    }
    auto left=binary->getLHS()->IgnoreParenImpCasts();
    auto right=binary->getRHS()->IgnoreParenImpCasts();
    const CXXMemberCallExpr* count=nullptr;
    bool matches=false;
    if (same(left,index)) {
        count=dyn_cast<CXXMemberCallExpr>(right);
        matches=binary->getOpcode()==(inRange ? BO_LT : BO_GE);
    } else if (same(right,index)) {
        count=dyn_cast<CXXMemberCallExpr>(left);
        matches=binary->getOpcode()==(inRange ? BO_GT : BO_LE);
    }
    return matches && count && sdkMethod(count->getMethodDecl(),"cocos2d::CCArray::count",context,result) &&
        same(count->getImplicitObjectArgument(),array) ? binary : nullptr;
}
bool terminates(const Stmt* statement) {
    if (!statement) return false;
    if (isa<ReturnStmt>(statement) || isa<BreakStmt>(statement) || isa<ContinueStmt>(statement)) return true;
    auto block=dyn_cast<CompoundStmt>(statement);
    return block && block->size()==1 && terminates(*block->body_begin());
}
bool references(const Stmt* statement, const ValueDecl* variable) {
    if (!statement) return false;
    if (auto ref=dyn_cast<DeclRefExpr>(statement))
        if (ref->getDecl()->getCanonicalDecl()==variable->getCanonicalDecl()) return true;
    for (auto child:statement->children()) if (references(child,variable)) return true;
    return false;
}
bool guardEffects(const Stmt* statement, ASTContext& context, const Inventory& result) {
    if (!statement) return false;
    if (auto unary=dyn_cast<UnaryOperator>(statement)) if (unary->isIncrementDecrementOp()) return true;
    if (auto binary=dyn_cast<BinaryOperator>(statement)) if (binary->isAssignmentOp()) return true;
    if (isa<CXXConstructExpr>(statement) || isa<CXXNewExpr>(statement) || isa<CXXDeleteExpr>(statement) || isa<CXXThrowExpr>(statement)) return true;
    if (auto call=dyn_cast<CallExpr>(statement)) {
        bool pure=false;
        if (auto member=dyn_cast<CXXMemberCallExpr>(call))
            pure=sdkMethod(member->getMethodDecl(),"cocos2d::CCArray::count",context,result) && member->getNumArgs()==0;
        if (auto op=dyn_cast<CXXOperatorCallExpr>(call)) {
            auto method=dyn_cast_or_null<CXXMethodDecl>(op->getDirectCallee());
            auto parent=dyn_cast_or_null<ClassTemplateSpecializationDecl>(method ? method->getParent() : nullptr);
            if (parent && parent->getSpecializedTemplate()->getQualifiedNameAsString()=="geode::Ref" && op->getOperator()==OO_Arrow && op->getNumArgs()==1) {
                auto file=fs::weakly_canonical(context.getSourceManager().getFilename(method->getCanonicalDecl()->getLocation()).str());
                auto relative=file.lexically_relative(fs::weakly_canonical(result.sdkRoot));
                pure=!relative.empty() && *relative.begin()!="..";
            }
        }
        if (!pure) return true;
    }
    for (auto child:statement->children()) if (guardEffects(child,context,result)) return true;
    return false;
}
const CompoundStmt* blockFor(const Stmt& statement, ASTContext& context, const Stmt*& top) {
    top=&statement;
    while (true) {
        auto parents=context.getParents(*top);
        if (parents.size()!=1) return nullptr;
        if (auto block=parents[0].get<CompoundStmt>()) return block;
        if (auto variable=parents[0].get<VarDecl>()) {
            auto declarationParents=context.getParents(*variable);
            if (declarationParents.size()!=1) return nullptr;
            top=declarationParents[0].get<DeclStmt>();
        } else top=parents[0].get<Stmt>();
        if (!top) return nullptr;
    }
}
}
void inspectArrayBounds(const CXXMemberCallExpr& call, ASTContext& context,
    Inventory& result, const fs::path& root) {
    if (!sdkMethod(call.getMethodDecl(),"cocos2d::CCArray::objectAtIndex",context,result) || call.getNumArgs()!=1) return;
    const Stmt* top=nullptr; auto block=blockFor(call,context,top);
    if (!block) return;
    auto index=call.getArg(0); auto array=call.getImplicitObjectArgument();
    std::vector<const Stmt*> statements(block->body_begin(),block->body_end());
    auto position=std::find(statements.begin(),statements.end(),top);
    if (position==statements.end()) return;
    auto offset=static_cast<size_t>(position-statements.begin());
    const IfStmt* late=nullptr; const Expr* check=nullptr;
    for (size_t i=offset+1; i<statements.size() && i<=offset+3; ++i) {
        auto candidate=dyn_cast<IfStmt>(statements[i]);
        if (candidate) {
            check=guard(candidate->getCond(),array,index,context,result);
            if (check) {late=candidate;break;}
        }
    }
    if (!late) return; // General missing-bounds analysis is deliberately outside this rule.
    auto unknown=[&](const std::string& why) {
        result.unknown.push_back({"Late array bounds check unknown: "+why,location(call.getExprLoc(),context,root)});
    };
    if (guardEffects(late->getCond(),context,result)) {unknown("guard evaluation may mutate state or invoke unmodeled effects");return;}
    if (!isa<DeclStmt>(top)) {unknown("access is not a supported standalone local initializer");return;}
    if (!terminates(late->getThen()) || late->getElse()) {unknown("guard has conditional or non-terminating control flow");return;}
    if (statements[offset+1]!=late) {unknown("intervening statements may change the array or index");return;}
    for (size_t i=0;i<offset;++i) {
        auto prior=dyn_cast<IfStmt>(statements[i]);
        if (prior && guard(prior->getCond(),array,index,context,result) && terminates(prior->getThen()) && !prior->getElse()) {
            if (guardEffects(prior->getCond(),context,result)) {unknown("prior guard evaluation has unmodeled effects");return;}
            if (i+1==offset) return;
            unknown("a prior guard exists but intervening effects are not modeled");return;
        }
    }
    auto parents=context.getParents(*block);
    if (parents.size()==1) {
        if (auto loop=parents[0].get<ForStmt>())
            if (guard(loop->getCond(),array,index,context,result,true)) {
                if (guardEffects(loop->getCond(),context,result)) {unknown("loop guard evaluation has unmodeled effects");return;}
                if (offset==0) return;
                unknown("loop checks the bounds but prior body effects are not modeled");return;
            }
        if (auto branch=parents[0].get<IfStmt>())
            if (branch->getThen()==block && guard(branch->getCond(),array,index,context,result,true)) {
                if (guardEffects(branch->getCond(),context,result)) {unknown("branch guard evaluation has unmodeled effects");return;}
                if (offset==0) return;
                unknown("branch checks the bounds but prior body effects are not modeled");return;
            }
    }
    Finding finding;
    finding.rule="geode.late-array-bounds-check"; finding.severity="review"; finding.evidence="inferred_risk";
    if (auto variable=dyn_cast<DeclRefExpr>(index->IgnoreParenImpCasts())) finding.variable=variable->getDecl()->getNameAsString();
    finding.message="CCArray element is accessed before its upper-bound check.";
    finding.suggestion="Check index < array->count() before objectAtIndex. Keep the existing out-of-range exit and null handling, then verify pagination/empty-array behavior.";
    finding.limitations="Observed access/check order; earlier external invariants and runtime index values are not proved. A crash was not reproduced. This is not general bounds analysis.";
    finding.factoryContract="sdk_array_index_contract";
    finding.location=location(call.getExprLoc(),context,root);
    finding.related={{"late_guard",location(check->getExprLoc(),context,root)}};
    // Only propose an insertion for a sole, direct initializer. Keep the original
    // guard/null handling verbatim. The editor verifies the whole-file digest
    // before preview AND application; no automatic source modification occurs here.
    auto declaration=dyn_cast<DeclStmt>(top);
    auto variable=declaration && declaration->isSingleDecl() ? dyn_cast<VarDecl>(declaration->getSingleDecl()) : nullptr;
    auto& sm=context.getSourceManager();
    auto start=top->getBeginLoc();
    auto exit=late->getThen();
    if (auto body=dyn_cast<CompoundStmt>(exit)) exit=*body->body_begin();
    if (variable && !references(exit,variable) && variable->getInit() && variable->getInit()->IgnoreParenImpCasts()==&call &&
        !start.isMacroID() && !check->getBeginLoc().isMacroID() && !check->getEndLoc().isMacroID() &&
        !exit->getBeginLoc().isMacroID() && !exit->getEndLoc().isMacroID() &&
        sm.getFileID(start)==sm.getFileID(check->getBeginLoc()) && sm.getFileID(start)==sm.getFileID(exit->getBeginLoc())) {
        bool invalid=false;
        auto buffer=sm.getBufferData(sm.getFileID(start),&invalid);
        auto boundText=Lexer::getSourceText(CharSourceRange::getTokenRange(check->getSourceRange()),sm,context.getLangOpts());
        auto exitText=Lexer::getSourceText(CharSourceRange::getTokenRange(exit->getSourceRange()),sm,context.getLangOpts()).str();
        if (!exitText.empty() && exitText.back()!=';') exitText+=';';
        auto offset=sm.getFileOffset(start);
        auto lineStart=buffer.rfind('\n',offset);
        auto indentation=buffer.slice(lineStart==llvm::StringRef::npos ? 0 : lineStart+1,offset);
        if (!invalid && !boundText.empty() && !exitText.empty() && indentation.find_first_not_of(" \t")==llvm::StringRef::npos) {
            auto bytes=llvm::ArrayRef<uint8_t>(reinterpret_cast<const uint8_t*>(buffer.data()),buffer.size());
            auto digest=llvm::SHA256::hash(bytes);
            std::string newline=buffer.contains("\r\n") ? "\r\n" : "\n";
            finding.repair=Repair{finding.location.file,llvm::toHex(digest,true),"",
                "if ("+boundText.str()+") "+exitText+newline+indentation.str(),offset,offset};
        }
    }
    result.findings.push_back(std::move(finding));
}
}
