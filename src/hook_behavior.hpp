#pragma once
#include "model.hpp"
namespace clang { class CXXMethodDecl; class CXXRecordDecl; class ASTContext; }
namespace warden {
HookBehavior inspectHookBehavior(const clang::CXXMethodDecl&, const clang::CXXRecordDecl&,
    const clang::CXXRecordDecl&, clang::ASTContext&, const Inventory&, const fs::path&);
}
