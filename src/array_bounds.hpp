#pragma once
#include "model.hpp"
#include <clang/AST/ASTContext.h>
#include <clang/AST/ExprCXX.h>

namespace warden {
void inspectArrayBounds(const clang::CXXMemberCallExpr& call, clang::ASTContext& context,
    Inventory& result, const fs::path& root);
}
