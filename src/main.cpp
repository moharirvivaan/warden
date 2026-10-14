#include "model.hpp"
#include <llvm/Support/FormatVariadic.h>
#include <llvm/Support/raw_ostream.h>
#include <iostream>

int main(int argc, char** argv) {
    bool json = false;
    for (int i = 1; i + 1 < argc; ++i)
        if (std::string(argv[i]) == "--format" && std::string(argv[i+1]) == "json") json = true;
    std::string root, build, error;
    if (argc < 3 || std::string(argv[1]) != "inspect")
        error = "Usage: warden inspect MOD_DIRECTORY -p BUILD_DIRECTORY [--format text|json]";
    else {
        root = argv[2];
        for (int i = 3; i < argc; ++i) {
            std::string arg = argv[i];
            if ((arg == "-p" || arg == "--format") && i + 1 < argc) {
                std::string value = argv[++i];
                if (arg == "-p") build = value;
                else if (value != "text" && value != "json") error = "Unknown output format: " + value;
            } else error = "Unknown or incomplete argument: " + arg;
        }
        if (build.empty()) error = "A build directory containing compile_commands.json is required (-p).";
    }
    warden::Report report;
    if (!error.empty()) {
        report.status = "setup_error";
        report.exitCode = 2;
        report.unknown.push_back({error, {}});
    } else {
        try { report = warden::inspect(root, build); }
        catch (const std::exception& e) {
            report.status = "setup_error";
            report.exitCode = 2;
            report.unknown.push_back({e.what(), {}});
        }
    }
    if (json) llvm::outs() << llvm::formatv("{0:2}\n", llvm::json::Value(warden::toJson(report)));
    else std::cout << warden::toText(report);
    return report.exitCode;
}
