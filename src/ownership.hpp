#pragma once
#include "model.hpp"
#include <clang/AST/ASTContext.h>
#include <clang/AST/Expr.h>

namespace warden {
void inspectQueuedOwnership(const clang::CallExpr& call, clang::ASTContext& context,
    Inventory& result, const fs::path& root, const fs::path& build);
}
