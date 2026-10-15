#pragma once
#include <filesystem>
#include <string>
#include <vector>
#include <optional>
#include <llvm/Support/JSON.h>

namespace warden {
namespace fs = std::filesystem;
struct Location {
    std::string file;
    unsigned line = 0, column = 0;
    bool operator==(const Location&) const = default;
};
struct Unknown {
    std::string reason;
    Location location;
    bool operator==(const Unknown&) const = default;
};
struct ForwardingCall {
    Location location; std::string context;
    bool operator==(const ForwardingCall&) const = default;
};
struct PriorityRequest {
    Location location; std::string hookName, api, status, relativeMod;
    std::optional<int64_t> requestedValue, preOrderValue;
    bool operator==(const PriorityRequest&) const = default;
};
struct HookBehavior {
    std::vector<ForwardingCall> forwardingCalls;
    std::vector<PriorityRequest> priorityRequests;
    std::vector<Unknown> unknown;
    bool operator==(const HookBehavior&) const = default;
};
struct Method {
    std::string modifiedClass, targetClass, name, signature, registration;
    Location location;
    std::optional<HookBehavior> behavior;
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
    std::string kind = "translation_unit";
    std::string directory = "";
};
struct RelatedLocation {
    std::string role;
    Location location;
};
struct Repair {
    std::string file, sha256, expected, replacement;
    uint64_t startByte = 0, endByte = 0;
};
struct Finding {
    std::string rule, severity, evidence, variable, message, suggestion, limitations, factoryContract;
    Location location;
    std::vector<RelatedLocation> related;
    std::optional<Repair> repair;
};
struct Inventory {
    std::vector<Method> hooks, helpers;
    std::vector<Modification> modifications;
    std::vector<Unknown> unknown;
    std::string sdkVersion, sdkRoot, target;
    std::vector<std::string> includedHeaders;
    std::vector<Finding> findings;
    std::vector<Location> queuedCallbacks, retainingCaptures;
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
