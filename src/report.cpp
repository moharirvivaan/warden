#include "model.hpp"
#include <clang/Basic/Version.h>
#include <sstream>
#include <algorithm>

namespace warden {
static llvm::json::Object location(const Location& l) {
    return llvm::json::Object{{"file", l.file}, {"line", l.line}, {"column", l.column}};
}
static llvm::json::Array methods(const std::vector<Method>& entries) {
    llvm::json::Array result;
    for (const auto& m : entries) {
        llvm::json::Object item{{"modified_class", m.modifiedClass}, {"target_class", m.targetClass},
            {"method", m.name}, {"signature", m.signature}, {"location", location(m.location)},
            {"evidence", "observed"}, {"registration", m.registration}};
        if(m.behavior) {
            llvm::json::Array calls,requests,unknown;
            for(const auto& c:m.behavior->forwardingCalls)calls.push_back(llvm::json::Object{{"location",location(c.location)},{"context",c.context}});
            for(const auto& p:m.behavior->priorityRequests) {
                llvm::json::Object request{{"location",location(p.location)},{"hook",p.hookName},{"api",p.api},{"status",p.status},{"relative_mod",p.relativeMod}};
                request["requested_value"]=p.requestedValue?llvm::json::Value(*p.requestedValue):llvm::json::Value(nullptr);
                request["pre_order_value"]=p.preOrderValue?llvm::json::Value(*p.preOrderValue):llvm::json::Value(nullptr);
                requests.push_back(std::move(request));
            }
            for(const auto& u:m.behavior->unknown)unknown.push_back(llvm::json::Object{{"location",location(u.location)},{"reason",u.reason}});
            item["behavior"]=llvm::json::Object{{"scope","source_facts_only"},{"forwarding_calls",std::move(calls)},{"priority_requests",std::move(requests)},{"unknown",std::move(unknown)}};
        }
        result.push_back(std::move(item));
    }
    return result;
}
llvm::json::Object toJson(const Report& r) {
    llvm::json::Array files, mods, unknown, findings;
    for (const auto& f : r.files) {
        llvm::json::Array diagnostics, args;
        for (const auto& d : f.diagnostics) diagnostics.push_back(llvm::json::Object{
            {"severity", d.severity}, {"message", d.message}, {"location", location(d.location)}});
        for (const auto& a : f.arguments) args.push_back(a);
        files.push_back(llvm::json::Object{{"file", f.file}, {"status", f.status}, {"kind", f.kind},
            {"directory", f.directory}, {"diagnostics", std::move(diagnostics)}, {"arguments", std::move(args)}});
    }
    for (const auto& m : r.modifications) mods.push_back(llvm::json::Object{
        {"modified_class", m.name}, {"target_class", m.targetClass},
        {"form", m.form}, {"location", location(m.location)}});
    for (const auto& u : r.unknown) unknown.push_back(llvm::json::Object{
        {"reason", u.reason}, {"location", location(u.location)}, {"evidence", "unknown"}});
    for (const auto& f : r.findings) {
        llvm::json::Array related;
        for (const auto& l : f.related) related.push_back(llvm::json::Object{
            {"role", l.role}, {"location", location(l.location)}});
        llvm::json::Object finding{{"rule", f.rule}, {"severity", f.severity},
            {"evidence", f.evidence}, {"variable", f.variable}, {"message", f.message},
            {"suggestion", f.suggestion}, {"limitations", f.limitations},
            {"factory_contract", f.factoryContract}, {"location", location(f.location)},
            {"related", std::move(related)}};
        if (f.repair) finding["repair"] = llvm::json::Object{
            {"file", f.repair->file}, {"sha256", f.repair->sha256},
            {"start_byte", static_cast<int64_t>(f.repair->startByte)},
            {"end_byte", static_cast<int64_t>(f.repair->endByte)},
            {"expected", f.repair->expected}, {"replacement", f.repair->replacement}};
        findings.push_back(std::move(finding));
    }
    llvm::json::Object metadata;
    for (const auto& kv : r.mod) metadata[kv.first] = kv.second;
    return llvm::json::Object{{"schema_version", 2}, {"status", r.status}, {"mod", std::move(metadata)},
        {"project_root", r.root}, {"compilation_database", r.database},
        {"toolchain", llvm::json::Object{{"warden", "0.1.0"}, {"clang", CLANG_VERSION_STRING},
            {"sdk", r.sdkVersion}, {"sdk_root", r.sdkRoot}, {"target", r.target}}},
        {"coverage", "Static hook declarations, limited deferred Cocos ownership and late array-bounds reviews for Geode 5.8.2/5.10.1/5.11.1 macOS ARM64; no runtime compatibility certification."},
        {"files", std::move(files)}, {"modifications", std::move(mods)},
        {"hooks", methods(r.hooks)}, {"helpers", methods(r.helpers)}, {"unknown", std::move(unknown)},
        {"findings", std::move(findings)}, {"ownership", llvm::json::Object{
            {"queued_callbacks", static_cast<int64_t>(r.queuedCallbacks.size())},
            {"retaining_captures", static_cast<int64_t>(r.retainingCaptures.size())},
            {"scope", "Direct lambdas, explicit by-value captures, supported local factories; other ownership flows remain unknown."}}}};
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
        for (const auto& m : entries) {
            out << label << " " << m.targetClass << "::" << m.name << " " << m.signature << " at " << m.location.file << ":" << m.location.line << ":" << m.location.column << "\n";
            if(m.behavior) {
                for(const auto& c:m.behavior->forwardingCalls)out << "  Forwarding source call (" << c.context << ") at " << c.location.file << ":" << c.location.line << "\n";
                for(const auto& p:m.behavior->priorityRequests)out << "  Priority request " << p.api << " " << (p.requestedValue?std::to_string(*p.requestedValue):p.relativeMod) << " (" << p.status << ") at " << p.location.file << ":" << p.location.line << "; runtime order unverified\n";
                for(const auto& u:m.behavior->unknown)out << "  Behavior unknown: " << u.reason << "\n";
            }
        }
    };
    printMethods(r.hooks, "HOOK"); printMethods(r.helpers, "HELPER");
    for (const auto& f : r.findings) {
        out << "Review [" << f.rule << "] " << f.variable << " at " << f.location.file
            << ":" << f.location.line << ":" << f.location.column << "\n  " << f.message << "\n";
        for (const auto& l : f.related)
            out << "  " << l.role << ": " << l.location.file << ":" << l.location.line << ":" << l.location.column << "\n";
        out << "  Suggestion: " << f.suggestion << "\n  Evidence: " << f.evidence
            << " | Factory contract: " << f.factoryContract << "\n  " << f.limitations << "\n";
    }
    for (const auto& f : r.files) {
        out << "FILE " << f.file << " — " << f.status << "\n";
        if (!f.directory.empty()) out << "  Working directory: " << f.directory << "\n";
        for (const auto& d : f.diagnostics) out << "  " << d.severity << ": " << d.message
            << " at " << d.location.file << ":" << d.location.line << "\n";
    }
    for (const auto& u : r.unknown) out << "UNKNOWN " << u.reason << " at "
        << u.location.file << ":" << u.location.line << "\n";
    out << "Ownership: " << r.queuedCallbacks.size() << " queued callbacks, "
        << r.retainingCaptures.size() << " retaining captures, "
        << std::count_if(r.findings.begin(),r.findings.end(),[](const Finding& f){return f.rule=="geode.deferred-cocos-ownership";})
        << " ownership reviews; not a safety verdict.\n"
        << "  Scope: direct lambdas, explicit by-value captures, supported local factories.\n";
    out << std::count_if(r.findings.begin(),r.findings.end(),[](const Finding& f){return f.rule=="geode.late-array-bounds-check";})
        << " bounds reviews; not general bounds proof.\n";
    out << r.hooks.size() << " hooks, " << r.helpers.size() << " helpers, "
        << r.unknown.size() << " unknown cases\n";
    return out.str();
}
}
