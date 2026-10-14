#pragma once
#include "model.hpp"
#include <clang/Frontend/FrontendAction.h>
#include <memory>

namespace warden {
std::unique_ptr<clang::FrontendAction> makeExtractionAction(
    Inventory& result, const fs::path& root, const fs::path& build);
}
