#include "model.hpp"
#include <clang/Basic/Version.h>
#include <sstream>

namespace warden {
static llvm::json::Object location(const Location& l) {
    return llvm::json::Object{{"file", l.file}, {"line", l.line}, {"column", l.column}};
}
static llvm::json::Array methods(const std::vector<Method>& entries) {
    llvm::json::Array result;
    for (const auto& m : entries) result.push_back(llvm::json::Object{
        {"modified_class", m.modifiedClass}, {"target_class", m.targetClass},
        {"method", m.name}, {"signature", m.signature}, {"location", location(m.location)},
        {"evidence", "observed"}, {"registration", m.registration}});
    return result;
}
llvm::json::Object toJson(const Report& r) {
    llvm::json::Array files, mods, unknown;
    for (const auto& f : r.files) {
        llvm::json::Array diagnostics, args;
        for (const auto& d : f.diagnostics) diagnostics.push_back(llvm::json::Object{
            {"severity", d.severity}, {"message", d.message}, {"location", location(d.location)}});
        for (const auto& a : f.arguments) args.push_back(a);
        files.push_back(llvm::json::Object{{"file", f.file}, {"status", f.status},
            {"diagnostics", std::move(diagnostics)}, {"arguments", std::move(args)}});
    }
    for (const auto& m : r.modifications) mods.push_back(llvm::json::Object{
        {"modified_class", m.name}, {"target_class", m.targetClass},
        {"form", m.form}, {"location", location(m.location)}});
    for (const auto& u : r.unknown) unknown.push_back(llvm::json::Object{
        {"reason", u.reason}, {"location", location(u.location)}, {"evidence", "unknown"}});
    llvm::json::Object metadata;
    for (const auto& kv : r.mod) metadata[kv.first] = kv.second;
    return llvm::json::Object{{"schema_version", 1}, {"status", r.status}, {"mod", std::move(metadata)},
        {"project_root", r.root}, {"compilation_database", r.database},
        {"toolchain", llvm::json::Object{{"warden", "0.1.0"}, {"clang", CLANG_VERSION_STRING},
            {"sdk", r.sdkVersion}, {"sdk_root", r.sdkRoot}, {"target", r.target}}},
        {"coverage", "Static hook declarations in the selected macOS ARM64 configuration; no runtime compatibility certification."},
        {"files", std::move(files)}, {"modifications", std::move(mods)},
        {"hooks", methods(r.hooks)}, {"helpers", methods(r.helpers)}, {"unknown", std::move(unknown)}};
}
std::string toText(const Report& r) {
    std::ostringstream out;
    out << "Warden Preflight — " << r.status << "\n";
    if (auto id = r.mod.getString("id")) out << "Mod: " << id->str() << "\n";
    out << "Clang " << CLANG_VERSION_STRING << " | Geode " << r.sdkVersion << " | " << r.target << "\n"
        << "Static declarations; runtime installation and compatibility are not established.\n";
    for (const auto& m : r.modifications)
        out << "MODIFY " << m.name << " -> " << m.targetClass << " (" << m.form << ")\n";
    auto printMethods = [&](const auto& entries, const char* label) {
        for (const auto& m : entries) out << label << " " << m.targetClass << "::" << m.name
            << " " << m.signature << " at " << m.location.file << ":" << m.location.line
            << ":" << m.location.column << "\n";
    };
    printMethods(r.hooks, "HOOK"); printMethods(r.helpers, "HELPER");
    for (const auto& f : r.files) {
        out << "FILE " << f.file << " — " << f.status << "\n";
        for (const auto& d : f.diagnostics) out << "  " << d.severity << ": " << d.message
            << " at " << d.location.file << ":" << d.location.line << "\n";
    }
    for (const auto& u : r.unknown) out << "UNKNOWN " << u.reason << " at "
        << u.location.file << ":" << u.location.line << "\n";
    out << r.hooks.size() << " hooks, " << r.helpers.size() << " helpers, "
        << r.unknown.size() << " unknown cases\n";
    return out.str();
}
}
