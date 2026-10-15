"""End-to-end contracts against the real Geode SDK (no substitute headers)."""
import json
import os
from pathlib import Path
import subprocess
import shlex
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get("WARDEN_BINARY", ROOT / "build/warden"))
EXAMPLE = Path(os.environ.get("WARDEN_EXAMPLE", ROOT / ".deps/example-mod"))
PREFIX = "#include <Geode/Geode.hpp>\n#include <Geode/modify/MenuLayer.hpp>\nusing namespace geode::prelude;\n"


class AnalyzerTests(unittest.TestCase):
    def fixture(self, files, units=None, transform=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        build = root / "build"
        build.mkdir()
        (root / "mod.json").write_text((EXAMPLE / "mod.json").read_text())
        for name, source in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
        entries = json.loads((EXAMPLE / "build/compile_commands.json").read_text())
        original = next(e for e in entries if e["file"].endswith("src/main.cpp"))
        base = original.get("arguments") or shlex.split(original["command"])
        commands = []
        for name in units or [n for n in files if n.endswith(".cpp")]:
            args = [str(root / name) if a == original["file"] else a for a in base]
            if transform:
                args = transform(args)
            commands.append({"directory": str(root), "file": str(root / name), "arguments": args})
        (build / "compile_commands.json").write_text(json.dumps(commands))
        return root, build

    def scan(self, files, units=None, transform=None):
        root, build = self.fixture(files, units, transform)
        result = self.run_warden("inspect", root, "-p", build, "--format", "json")
        return result, json.loads(result.stdout)

    def run_warden(self, *args):
        self.assertTrue(BINARY.is_file(), "The native warden executable must exist")
        return subprocess.run([str(BINARY), *map(str, args)], text=True,
                              capture_output=True, timeout=120)

    def test_official_example_hook_and_helper(self):
        # A broken registration matcher that counts every class method fails here.
        result = self.run_warden("inspect", EXAMPLE, "-p", EXAMPLE / "build",
                                 "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["mod"]["id"], "warden.official-example")
        self.assertEqual([(h["target_class"], h["method"]) for h in report["hooks"]],
                         [("MenuLayer", "init")])
        self.assertEqual([h["method"] for h in report["helpers"]], ["onMyButton"])
        hook = report["hooks"][0]
        self.assertEqual(hook["signature"], "bool ()")
        self.assertEqual(hook["location"]["file"], "src/main.cpp")
        self.assertGreater(hook["location"]["line"], 0)
        self.assertEqual(hook["evidence"], "observed")
        self.assertTrue(hook["registration"])
        self.assertEqual(len(report["modifications"]), 1)
        self.assertEqual(report["modifications"][0]["form"], "named")
        self.assertEqual(report["unknown"], [])

    def test_missing_database_is_setup_error(self):
        # Treating absent compiler settings as an empty successful scan fails here.
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_warden("inspect", EXAMPLE, "-p", directory,
                                     "--format", "json")
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "setup_error")
        self.assertTrue(report["unknown"])

    def test_named_and_anonymous_and_inactive_code(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
class $modify(NamedLayer, MenuLayer) { bool init() { return MenuLayer::init(); } };
class $modify(MenuLayer) { bool init() { return MenuLayer::init(); } };
#if 0
class $modify(DoesNotExist) { bool init() { return false; } };
#endif
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(report["hooks"]), 2)
        self.assertEqual(sorted(m["form"] for m in report["modifications"]), ["anonymous", "named"])

    def test_overload_is_helper_not_hook(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
class $modify(Overloaded, MenuLayer) {
  bool init() { return MenuLayer::init(); }
  bool init(int) { return false; }
  void onQuitHelper() {}
};
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual([h["signature"] for h in report["hooks"]], ["bool ()"])
        self.assertEqual(sorted(h["method"] for h in report["helpers"]), ["init", "onQuitHelper"])

    def test_shared_header_deduplicates_declarations(self):
        result, report = self.scan({
            "shared.hpp": "#pragma once\n" + PREFIX +
                "class $modify(Shared, MenuLayer) { bool init() { return MenuLayer::init(); } };\n",
            "first.cpp": '#include "shared.hpp"\n',
            "second.cpp": '#include "shared.hpp"\n',
        })
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(report["hooks"]), 1)
        self.assertEqual(len(report["modifications"]), 1)
        self.assertEqual(report["hooks"][0]["location"]["file"], "shared.hpp")
        self.assertEqual(len(report["files"]), 3)
        self.assertTrue(any(f["file"] == "shared.hpp" and f["status"] == "complete" for f in report["files"]))

    def test_syntax_error_discards_unit_inventory(self):
        result, report = self.scan({"main.cpp": PREFIX +
            "class $modify(Broken, MenuLayer) { bool init() { return MenuLayer::init(); } };\nint broken = ;\n"})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["hooks"], [])
        self.assertEqual(report["files"][0]["status"], "incomplete")
        self.assertTrue(any(d["severity"] == "error" for d in report["files"][0]["diagnostics"]))

    def test_missing_sdk_headers_is_setup_error(self):
        def without_sdk(args):
            return [a for a in args if not a.startswith("-I")]
        result, report = self.scan({"main.cpp": PREFIX}, transform=without_sdk)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["status"], "setup_error")
        self.assertTrue(report["files"][0]["diagnostics"])

    def test_uncompiled_source_is_unknown(self):
        result, report = self.scan({"main.cpp": "int x;\n", "unused.cpp": "int y;\n"}, units=["main.cpp"])
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any(u["location"]["file"] == "unused.cpp" for u in report["unknown"]))

    def test_text_and_json_share_inventory(self):
        root, build = self.fixture({"main.cpp": PREFIX +
            "class $modify(Readable, MenuLayer) { bool init() { return MenuLayer::init(); } void helper() {} };\n"})
        json_result = self.run_warden("inspect", root, "-p", build, "--format", "json")
        text_result = self.run_warden("inspect", root, "-p", build)
        self.assertEqual(json_result.returncode, text_result.returncode)
        report = json.loads(json_result.stdout)
        for record in report["hooks"]:
            self.assertIn(f'HOOK {record["target_class"]}::{record["method"]} {record["signature"]}', text_result.stdout)
        for record in report["helpers"]:
            self.assertIn(f'HELPER {record["target_class"]}::{record["method"]}', text_result.stdout)
        self.assertIn("1 hooks, 1 helpers, 0 unknown cases", text_result.stdout)

    def test_direct_modify_resolves_actual_sdk_registration(self):
        result, report = self.scan({"main.cpp": PREFIX +
            "struct Direct : geode::Modify<Direct, MenuLayer> { bool init() { return MenuLayer::init(); } void helper(){} };\n"})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual([h["method"] for h in report["hooks"]], ["init"])
        self.assertEqual([h["method"] for h in report["helpers"]], ["helper"])
        self.assertEqual(report["modifications"][0]["form"], "direct")
        self.assertTrue(report["hooks"][0]["registration"])

    def test_manual_hook_is_unknown(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void detour() {}
void register_manual() {
  (void)Mod::get()->hook(reinterpret_cast<void*>(0x1000), &detour, "manual");
}
'''})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(report["hooks"], [])
        self.assertTrue(any("Manual/raw" in u["reason"] for u in report["unknown"]))

    def test_empty_hook_inventory_keeps_sdk_version(self):
        result, report = self.scan({"main.cpp": PREFIX + "int ordinary_function() { return 0; }\n"})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["toolchain"]["sdk"], "5.11.1")
        self.assertEqual(report["hooks"], [])

    def test_namespace_names_are_resolved(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
namespace one { class $modify(Layer, MenuLayer) { bool init() { return MenuLayer::init(); } }; }
namespace two { class $modify(Layer, MenuLayer) { bool init() { return MenuLayer::init(); } }; }
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(sorted(h["modified_class"] for h in report["hooks"]), ["one::Layer", "two::Layer"])

    def test_unincluded_header_is_unknown(self):
        result, report = self.scan({"main.cpp": "int x;\n", "unused.hpp": PREFIX +
            "class $modify(Unseen, MenuLayer) { bool init() { return MenuLayer::init(); } };\n"})
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any(u["location"]["file"] == "unused.hpp" for u in report["unknown"]))

    def test_conflicting_commands_are_unknown(self):
        root, build = self.fixture({"main.cpp": PREFIX})
        path = build / "compile_commands.json"
        commands = json.loads(path.read_text())
        other = dict(commands[0], arguments=commands[0]["arguments"] + ["-DOTHER_CONFIGURATION=1"])
        path.write_text(json.dumps(commands + [other]))
        result = self.run_warden("inspect", root, "-p", build, "--format", "json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any("Multiple compiler" in u["reason"] for u in json.loads(result.stdout)["unknown"]))

    def test_unsupported_target_is_unknown(self):
        result, report = self.scan({"main.cpp": PREFIX},
            transform=lambda args: ["x86_64" if a == "arm64" else a for a in args])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(any("Unsupported target" in u["reason"] for u in report["unknown"]))

    def test_review_declaration_only_hook_is_retained(self):
        result, report = self.scan({"main.cpp": PREFIX +
            "class $modify(Declared, MenuLayer) { bool init(); };\n"})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual([(h["method"], h["signature"]) for h in report["hooks"]], [("init", "bool ()")])

    def test_review_separate_hook_definition_is_retained(self):
        result, report = self.scan({"main.cpp": PREFIX +
            "class $modify(Separate, MenuLayer) { bool init(); };\n"
            "bool Separate::init() { return MenuLayer::init(); }\n"})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual([h["method"] for h in report["hooks"]], ["init"])

    def test_review_generic_lifecycle_is_unknown(self):
        result, report = self.scan({"main.cpp": PREFIX +
            "class $modify(Lifecycle, MenuLayer) { static void onModify(auto& self) {} };\n"})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(any("onModify" in u["reason"] for u in report["unknown"]))

    def test_review_geode_constructor_destructor_are_unknown(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
#include <Geode/modify/CCNode.hpp>
class $modify(Lifecycle, cocos2d::CCNode) {
  void constructor() {}
  void destructor() {}
};
'''})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(report["helpers"], [])
        self.assertTrue(any("constructor" in u["reason"] for u in report["unknown"]))
        self.assertTrue(any("destructor" in u["reason"] for u in report["unknown"]))

    def test_review_working_directory_is_configuration_identity(self):
        root, build = self.fixture({
            "main.cpp": PREFIX + '#include <configuration.hpp>\n',
            "one/configuration.hpp": "class $modify(First, MenuLayer) { bool init() { return MenuLayer::init(); } };\n",
            "two/configuration.hpp": "class $modify(Second, MenuLayer) { void onQuit(CCObject*) {} };\n",
        }, units=["main.cpp"])
        database = build / "compile_commands.json"
        command = json.loads(database.read_text())[0]
        command["arguments"] += ["-I."]
        first = dict(command, directory=str(root / "one"))
        second = dict(command, directory=str(root / "two"))
        database.write_text(json.dumps([first, second]))
        result = self.run_warden("inspect", root, "-p", build, "--format", "json")
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(any("Multiple compiler" in u["reason"] for u in report["unknown"]))
        self.assertEqual(report["hooks"], [])

    def test_review_direct_tulip_hook_is_unknown(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void raw_hook(tulip::hook::HandlerHandle handle, void* address, tulip::hook::HookMetadata metadata) {
  tulip::hook::createHook(handle, address, metadata);
}
'''})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(any("Manual/raw" in u["reason"] for u in report["unknown"]))

    def test_review_report_retains_command_directory(self):
        root, build = self.fixture({"main.cpp": "int x;\n"})
        result = self.run_warden("inspect", root, "-p", build, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout)
        self.assertIn("directory", report["files"][0])
        self.assertEqual(Path(report["files"][0]["directory"]).resolve(), root.resolve())


if __name__ == "__main__":
    unittest.main()
