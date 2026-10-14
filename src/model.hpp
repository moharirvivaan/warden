#pragma once
#include <filesystem>
#include <string>
#include <vector>
#include <llvm/Support/JSON.h>

namespace warden {
namespace fs = std::filesystem;
struct Location {
    std::string file;
    unsigned line = 0, column = 0;
};
struct Unknown {
    std::string reason;
    Location location;
};
struct Method {
    std::string modifiedClass, targetClass, name, signature, registration;
    Location location;
};
struct Modification {
    std::string name, targetClass, form;
    Location location;
};
struct Diagnostic {
    std::string severity, message;
    Location location;
};
struct FileResult {
    std::string file, status = "complete";
    std::vector<Diagnostic> diagnostics;
    std::vector<std::string> arguments;
};
struct Inventory {
    std::vector<Method> hooks, helpers;
    std::vector<Modification> modifications;
    std::vector<Unknown> unknown;
    std::string sdkVersion, sdkRoot, target;
};
struct Report : Inventory {
    std::string status = "complete", root, database;
    llvm::json::Object mod;
    std::vector<FileResult> files;
    int exitCode = 0;
};
bool belongsToProject(const fs::path& file, const fs::path& root, const fs::path& build);
Report inspect(const fs::path& root, const fs::path& build);
llvm::json::Object toJson(const Report& report);
std::string toText(const Report& report);
}
