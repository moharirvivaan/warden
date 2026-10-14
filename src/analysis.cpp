#include "model.hpp"
#include "extraction.hpp"
#include <clang/Basic/Diagnostic.h>
#include <clang/Basic/SourceManager.h>
#include <clang/Tooling/ArgumentsAdjusters.h>
#include <clang/Tooling/JSONCompilationDatabase.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/Support/MemoryBuffer.h>
#include <algorithm>
#include <map>
#include <set>

namespace warden {
static fs::path normalized(const fs::path& p) { return fs::weakly_canonical(fs::absolute(p)); }
bool belongsToProject(const fs::path& file, const fs::path& root, const fs::path& build) {
    if (file.empty()) return false;
    auto f = normalized(file), r = normalized(root), b = normalized(build);
    auto relative = f.lexically_relative(r);
    if (relative.empty() || *relative.begin() == "..") return false;
    auto buildRelative = f.lexically_relative(b);
    if (!buildRelative.empty() && *buildRelative.begin() != "..") return false;
    for (const auto& part : relative)
        if (part == ".git" || part == ".deps" || part == "build" || part == ".cache") return false;
    return true;
}
class Diagnostics final : public clang::DiagnosticConsumer {
    FileResult& file;
    fs::path root;
public:
    bool errors = false, missingSdk = false;
    Diagnostics(FileResult& f, fs::path r) : file(f), root(std::move(r)) {}
    void HandleDiagnostic(clang::DiagnosticsEngine::Level level, const clang::Diagnostic& info) override {
        if (level < clang::DiagnosticsEngine::Note) return;
        llvm::SmallString<256> message;
        info.FormatDiagnostic(message);
        std::string severity = level >= clang::DiagnosticsEngine::Error ? "error" :
            level == clang::DiagnosticsEngine::Warning ? "warning" : "note";
        errors |= level >= clang::DiagnosticsEngine::Error;
        missingSdk |= level >= clang::DiagnosticsEngine::Error && message.str().contains("Geode/") && message.str().contains("file not found");
        Location l;
        if (info.hasSourceManager() && info.getLocation().isValid()) {
            auto& sm = info.getSourceManager();
            auto loc = sm.getExpansionLoc(info.getLocation());
            auto name = sm.getFilename(loc).str();
            if (!name.empty()) {
                auto relative = normalized(name).lexically_relative(root);
                l.file = relative.empty() || *relative.begin() == ".." ? name : relative.generic_string();
            }
            l.line = sm.getExpansionLineNumber(loc); l.column = sm.getExpansionColumnNumber(loc);
        }
        file.diagnostics.push_back({severity, message.str().str(), l});
    }
};
class Factory final : public clang::tooling::FrontendActionFactory {
    Inventory& result;
    fs::path root, build;
public:
    Factory(Inventory& r, fs::path p, fs::path b) : result(r), root(std::move(p)), build(std::move(b)) {}
    std::unique_ptr<clang::FrontendAction> create() override { return makeExtractionAction(result, root, build); }
};
static void setupError(Report& r, const std::string& reason) {
    r.status = "setup_error"; r.exitCode = 2; r.unknown.push_back({reason, {}});
}
template<class T, class Key> static void deduplicate(std::vector<T>& items, Key key) {
    std::sort(items.begin(), items.end(), [&](const auto& a, const auto& b) { return key(a) < key(b); });
    items.erase(std::unique(items.begin(), items.end(), [&](const auto& a, const auto& b) {
        return key(a) == key(b);
    }), items.end());
}
Report inspect(const fs::path& rootPath, const fs::path& buildPath) {
    Report report;
    const auto root = normalized(rootPath), build = normalized(buildPath);
    report.root = root.string(); report.database = (build / "compile_commands.json").string();
    auto metadata = llvm::MemoryBuffer::getFile((root / "mod.json").string());
    if (!metadata) { setupError(report, "Cannot read mod.json in the mod directory."); return report; }
    auto parsed = llvm::json::parse((*metadata)->getBuffer());
    if (!parsed) { llvm::consumeError(parsed.takeError()); setupError(report, "mod.json is not valid JSON."); return report; }
    auto object = parsed->getAsObject();
    if (!object || !object->getString("id") || !object->getString("geode")) {
        setupError(report, "mod.json requires string id and geode fields."); return report;
    }
    report.mod = std::move(*object);
    std::string error;
    auto database = clang::tooling::JSONCompilationDatabase::loadFromFile(report.database,
        error, clang::tooling::JSONCommandLineSyntax::AutoDetect);
    if (!database) { setupError(report, "Cannot load compile_commands.json: " + error); return report; }
    std::map<std::string, std::vector<clang::tooling::CompileCommand>> commands;
    for (auto command : database->getAllCompileCommands()) {
        auto path = fs::path(command.Filename);
        if (path.is_relative()) path = fs::path(command.Directory) / path;
        path = normalized(path);
        if (belongsToProject(path, root, build)) commands[path.string()].push_back(std::move(command));
    }
    if (commands.empty()) { setupError(report, "No project translation units in the compilation database."); return report; }
    bool sdkSetupError = false;
    for (auto& [path, variants] : commands) {
        FileResult file;
        file.file = fs::path(path).lexically_relative(root).generic_string();
        std::set<std::vector<std::string>> distinct;
        for (const auto& v : variants) distinct.insert(v.CommandLine);
        if (distinct.size() != 1) {
            file.status = "unknown";
            report.unknown.push_back({"Multiple compiler configurations for this file; select one configuration.", {file.file}});
            report.files.push_back(std::move(file)); continue;
        }
        file.arguments = variants.front().CommandLine;
        Inventory unit;
        clang::tooling::ClangTool tool(*database, {path});
        tool.appendArgumentsAdjuster(clang::tooling::getInsertArgumentAdjuster(
            {"-resource-dir", WARDEN_RESOURCE_DIR}, clang::tooling::ArgumentInsertPosition::BEGIN));
        Diagnostics diagnostics(file, root);
        tool.setDiagnosticConsumer(&diagnostics);
        Factory factory(unit, root, build);
        int status = tool.run(&factory);
        report.sdkVersion = unit.sdkVersion; report.sdkRoot = unit.sdkRoot; report.target = unit.target;
        if (status || diagnostics.errors) {
            file.status = "incomplete";
            report.unknown.push_back({"Compiler errors: inventory for this translation unit was discarded.", {file.file}});
            sdkSetupError |= diagnostics.missingSdk;
        } else {
            report.hooks.insert(report.hooks.end(), unit.hooks.begin(), unit.hooks.end());
            report.helpers.insert(report.helpers.end(), unit.helpers.begin(), unit.helpers.end());
            report.modifications.insert(report.modifications.end(), unit.modifications.begin(), unit.modifications.end());
            report.unknown.insert(report.unknown.end(), unit.unknown.begin(), unit.unknown.end());
            if (!unit.unknown.empty()) file.status = "partial";
        }
        report.files.push_back(std::move(file));
    }
    for (fs::recursive_directory_iterator it(root, fs::directory_options::skip_permission_denied), end; it != end; ++it) {
        if (it->is_directory() && !belongsToProject(it->path(), root, build)) { it.disable_recursion_pending(); continue; }
        const auto extension = it->path().extension().string();
        if (it->is_regular_file() && (extension == ".cpp" || extension == ".cc" || extension == ".cxx") &&
            belongsToProject(it->path(), root, build) && !commands.contains(normalized(it->path()).string())) {
            auto file = it->path().lexically_relative(root).generic_string();
            report.files.push_back({file, "unknown", {}, {}});
            report.unknown.push_back({"Source file has no command in the selected compilation database.", {file}});
        }
    }
    auto methodKey = [](const Method& m) { return std::tuple(m.location.file, m.location.line, m.location.column, m.targetClass, m.name, m.signature); };
    deduplicate(report.hooks, methodKey); deduplicate(report.helpers, methodKey);
    deduplicate(report.modifications, [](const Modification& m) { return std::tuple(m.location.file, m.location.line, m.location.column, m.name, m.targetClass); });
    deduplicate(report.unknown, [](const Unknown& u) { return std::tuple(u.location.file, u.location.line, u.location.column, u.reason); });
    if (sdkSetupError) setupError(report, "Required Geode SDK headers are missing; configure SDK include paths before analysis.");
    else if (!report.unknown.empty()) { report.status = "partial"; report.exitCode = 1; }
    return report;
}
}
