"""Ownership review contracts using actual Geode headers and compiler settings."""
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_analyzer

PREFIX = test_analyzer.PREFIX


class OwnershipTests(unittest.TestCase):
    fixture = test_analyzer.AnalyzerTests.fixture
    scan = test_analyzer.AnalyzerTests.scan
    run_warden = test_analyzer.AnalyzerTests.run_warden

    def test_raw_autoreleased_node_has_source_linked_review(self):
        # Ignoring ownership or treating raw capture as retaining fails here.
        result, report = self.scan({"main.cpp": PREFIX + '''
void inspectLifetime() {
    auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node]() { node->setTag(42); });
}
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(report.get("findings", [])), 1)
        finding = report["findings"][0]
        self.assertEqual(finding["rule"], "geode.deferred-cocos-ownership")
        self.assertEqual(finding["severity"], "review")
        self.assertEqual(finding["evidence"], "inferred_risk")
        self.assertEqual(finding["variable"], "node")
        self.assertEqual(finding["factory_contract"], "documented_autorelease")
        self.assertEqual(finding["location"]["file"], "main.cpp")
        self.assertEqual({x["role"] for x in finding["related"]}, {"origin", "use"})
        self.assertIn("Ref", finding["suggestion"])
        self.assertIn("not reproduced", finding["limitations"])

    def test_ref_capture_is_retained_without_safe_verdict(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void heldLifetime() {
    auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node = Ref(node)]() { node->setTag(42); });
}
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report.get("findings"), [])
        self.assertEqual(report.get("ownership", {}).get("retaining_captures"), 1)
        self.assertNotIn("safe", report["ownership"].values())

    def test_game_factory_has_explicit_unverified_mac_contract(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void comments() {
    auto level = GJGameLevel::create();
    level->m_levelID = 42;
    Loader::get()->queueInMainThread([level]() {
        InfoLayer::create(level, nullptr, nullptr)->show();
    });
}
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(report.get("findings", [])), 1)
        self.assertEqual(report["findings"][0]["factory_contract"], "mac_implementation_unverified")
        self.assertIn("macOS", report["findings"][0]["limitations"])

    def test_values_and_immediate_callbacks_have_no_ownership_finding(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void values() {
    int id = 42;
    Loader::get()->queueInMainThread([id]() { (void)id; });
    auto node = cocos2d::CCNode::create();
    [node]() { node->setTag(42); }();
}
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report.get("findings"), [])
        self.assertEqual(report["ownership"]["queued_callbacks"], 1)

    def test_structured_value_capture_is_not_a_cocos_ownership_gap(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void pairValues() { auto [id, count] = std::pair{42, 3};
    Loader::get()->queueInMainThread([id]() { (void)id; }); }
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["unknown"], [])

    def test_adopt_capture_does_not_claim_a_retaining_constructor(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void adopted() { auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node = Ref<cocos2d::CCNode>::adopt(node)]() { node->setTag(42); }); }
'''})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(report["ownership"]["retaining_captures"], 0)
        self.assertEqual(report["findings"], [])
        self.assertTrue(any("ownership" in u["reason"] for u in report["unknown"]))

    def test_stored_callables_this_and_nested_capture_remain_unknown(self):
        cases = [
            'auto node = cocos2d::CCNode::create(); auto fn = [node](){node->setTag(42);}; Loader::get()->queueInMainThread(std::move(fn));',
            'Loader::get()->queueInMainThread([this](){this->setTag(42);});',
            'auto node = cocos2d::CCNode::create(); Loader::get()->queueInMainThread([node](){[node](){node->setTag(42);}();});',
        ]
        for body in cases:
            with self.subTest(body=body):
                result, report = self.scan({"main.cpp": PREFIX + 'struct Nested : cocos2d::CCNode { void schedule(){' + body + '} };\n'})
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(report["findings"], [])
                self.assertTrue(any("ownership" in u["reason"] for u in report["unknown"]))

    def test_free_sdk_queue_and_unused_capture(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void freeQueue() { auto node = cocos2d::CCNode::create();
    geode::queueInMainThread([node](){node->setTag(42);}); }
void unused() { auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node](){}); }
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(report["findings"]), 1)
        self.assertEqual(report["ownership"]["queued_callbacks"], 2)

    def test_wrong_target_has_no_ownership_claim(self):
        def intel(args):
            return ["x86_64" if a == "arm64" else a for a in args]
        result, report = self.scan({"main.cpp": PREFIX + '''
void queued() { auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node](){node->setTag(42);}); }
'''}, transform=intel)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["ownership"]["queued_callbacks"], 0)

    def test_declared_sdk_difference_is_visible_unknown(self):
        root, build = self.fixture({"main.cpp": PREFIX + '''
void queued() { auto node=cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node](){node->setTag(42);}); }
'''})
        metadata = json.loads((root / "mod.json").read_text())
        metadata["geode"] = "5.10.1"
        (root / "mod.json").write_text(json.dumps(metadata))
        result = self.run_warden("inspect", root, "-p", build, "--format", "json")
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(len(report["findings"]), 1, "Selected-SDK evidence is preserved")
        self.assertTrue(any("5.10.1" in u["reason"] and "5.11.1" in u["reason"] for u in report["unknown"]))
        terminal = self.run_warden("inspect", root, "-p", build)
        self.assertIn("5.10.1", terminal.stdout)
        self.assertIn("5.11.1", terminal.stdout)

    def test_reference_variables_and_cocos_wrappers_are_unknown(self):
        bodies = [
            'void references(cocos2d::CCNode*& alias) { Loader::get()->queueInMainThread([alias](){alias->setTag(42);}); }',
            'void refs(Ref<cocos2d::CCNode>& owner) { Loader::get()->queueInMainThread([owner](){owner->setTag(42);}); }',
            'void array() { std::array<cocos2d::CCNode*,1> nodes{cocos2d::CCNode::create()}; Loader::get()->queueInMainThread([nodes](){nodes[0]->setTag(42);}); }',
            'void tuple() { std::tuple<cocos2d::CCNode*> nodes{cocos2d::CCNode::create()}; Loader::get()->queueInMainThread([nodes](){std::get<0>(nodes)->setTag(42);}); }',
        ]
        for body in bodies:
            with self.subTest(body=body):
                result, report = self.scan({"main.cpp": PREFIX + '\n#include <array>\n#include <tuple>\n' + body})
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(report["findings"], [])
                self.assertEqual(report["ownership"]["retaining_captures"], 0)
                self.assertTrue(any("ownership" in u["reason"] for u in report["unknown"]))

    def test_callback_local_aliases_and_reassignment_are_unknown(self):
        callbacks = [
            '[node]() { auto alias=node; alias->setTag(42); }',
            '[node]() mutable { node=cocos2d::CCNode::create(); node->setTag(42); }',
            '[node=Ref(node)]() { cocos2d::CCNode* alias=node; alias->setTag(42); }',
        ]
        for callback in callbacks:
            with self.subTest(callback=callback):
                result, report = self.scan({"main.cpp": PREFIX + 'void alias(){auto node=cocos2d::CCNode::create(); Loader::get()->queueInMainThread(' + callback + ');}'})
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(report["findings"], [])
                self.assertEqual(report["ownership"]["retaining_captures"], 0)
                self.assertTrue(any("ownership" in u["reason"] for u in report["unknown"]))

    def test_mutating_ref_owner_in_callback_is_unknown(self):
        operations = [
            'auto raw = node.data(); node = nullptr; raw->setTag(42);',
            'auto raw = node.take(); raw->setTag(42);',
            'node->release(); node->setTag(42);',
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                result, report = self.scan({"main.cpp": PREFIX + 'void mutation(){auto node=cocos2d::CCNode::create(); Loader::get()->queueInMainThread([node=Ref(node)]() mutable {' + operation + '});}'})
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(report["findings"], [])
                self.assertEqual(report["ownership"]["retaining_captures"], 0)
                self.assertTrue(any("ownership" in u["reason"] for u in report["unknown"]))

    def test_alias_manual_ownership_and_reference_capture_remain_unknown(self):
        cases = {
            "alias": 'auto alias = node; Loader::get()->queueInMainThread([alias]() { alias->setTag(42); });',
            "manual": 'node->retain(); Loader::get()->queueInMainThread([node]() { node->setTag(42); node->release(); });',
            "reference": 'Loader::get()->queueInMainThread([&node]() { node->setTag(42); });',
            "conditional": 'if (node) { Loader::get()->queueInMainThread([node]() { node->setTag(42); }); }',
            "escape": 'consume(node); Loader::get()->queueInMainThread([node]() { node->setTag(42); });',
            "reassignment": 'node = cocos2d::CCNode::create(); Loader::get()->queueInMainThread([node]() { node->setTag(42); });',
        }
        for name, body in cases.items():
            with self.subTest(name=name):
                result, report = self.scan({"main.cpp": PREFIX + '\nvoid consume(cocos2d::CCNode*);\nvoid uncertain() { auto node = cocos2d::CCNode::create(); ' + body + ' }\n'})
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(report.get("findings"), [])
                self.assertTrue(any("ownership" in item["reason"] for item in report["unknown"]))

    def test_same_named_user_queue_does_not_match_sdk_api(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
struct LocalQueue { template<class F> void queueInMainThread(F fn) { fn(); } };
void local() { auto node = cocos2d::CCNode::create();
    LocalQueue().queueInMainThread([node]() { node->setTag(42); }); }
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(report.get("findings"), [])
        self.assertEqual(report["ownership"]["queued_callbacks"], 0)

    def test_sdk_queue_redeclaration_keeps_canonical_identity(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
namespace geode { void queueInMainThread(ScheduledFunction&&); }
void canonical() { auto node = cocos2d::CCNode::create();
    geode::queueInMainThread([node](){node->setTag(42);}); }
'''})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(report["findings"]), 1)
        self.assertEqual(report["ownership"]["queued_callbacks"], 1)

    def test_nonlocal_and_custom_factory_are_unknown(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
cocos2d::CCNode* externalFactory();
void external(cocos2d::CCNode* borrowed) {
    auto node = externalFactory();
    Loader::get()->queueInMainThread([node, borrowed]() { node->setTag(borrowed->getTag()); });
}
'''})
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(report.get("findings"), [])
        self.assertEqual(len([u for u in report["unknown"] if "ownership" in u["reason"]]), 2)

    def test_parse_failure_discards_ownership_evidence(self):
        result, report = self.scan({"main.cpp": PREFIX + '''
void broken() { auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node]() { node->setTag(42); }); }
int invalid = ;
'''})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report.get("findings"), [])
        self.assertEqual(report["ownership"]["queued_callbacks"], 0)

    def test_header_findings_and_counts_deduplicate_across_units(self):
        result, report = self.scan({
            "shared.hpp": '#pragma once\n' + PREFIX + '''
inline void queued() { auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node]() { node->setTag(42); }); }
''',
            "first.cpp": '#include "shared.hpp"\n',
            "second.cpp": '#include "shared.hpp"\n',
        })
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(len(report.get("findings", [])), 1)
        self.assertEqual(report["ownership"]["queued_callbacks"], 1)
        self.assertEqual(report["findings"][0]["location"]["file"], "shared.hpp")

    def test_ownership_findings_are_consistent_in_text_and_json(self):
        root, build = self.fixture({"main.cpp": PREFIX + '''
void queued() { auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node]() { node->setTag(42); }); }
'''})
        js = self.run_warden("inspect", root, "-p", build, "--format", "json")
        terminal = self.run_warden("inspect", root, "-p", build)
        finding = json.loads(js.stdout).get("findings", [{}])[0]
        self.assertEqual(js.returncode, terminal.returncode)
        self.assertIn(finding.get("rule", "MISSING_OWNERSHIP_RULE"), terminal.stdout)
        self.assertIn("Review", terminal.stdout)
        self.assertIn("documented_autorelease", terminal.stdout)
        self.assertIn("1 queued callbacks", terminal.stdout)

    def test_retaining_capture_is_visible_in_terminal(self):
        root, build = self.fixture({"main.cpp": PREFIX + '''
void owned() { auto node = cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node=Ref(node)](){node->setTag(42);}); }
'''})
        terminal = self.run_warden("inspect", root, "-p", build)
        self.assertEqual(terminal.returncode, 0, terminal.stdout)
        self.assertIn("1 queued callbacks", terminal.stdout)
        self.assertIn("1 retaining captures", terminal.stdout)
        self.assertIn("not a safety verdict", terminal.stdout)


class BetterInfoBenchmarkTests(unittest.TestCase):
    """Actual revision sources; selected unit and adapted SDK are explicit."""
    def test_reproducible_setup_and_actual_before_after_source(self):
        root = test_analyzer.ROOT
        project = root / ".deps/betterinfo-benchmark"
        if not project.is_dir():
            self.skipTest("Cache missing: clone BetterInfo and run scripts/prepare-ownership.py; no substituted benchmark.")
        setup = root / "scripts/prepare-ownership.py"
        self.assertTrue(setup.is_file(), "Reproducible benchmark preparation must exist")
        result = subprocess.run([sys.executable, str(setup)], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        manifest = json.loads((project / "build/warden-provenance.json").read_text())
        self.assertEqual(manifest["metadata_sdk"], "5.10.1")
        self.assertEqual(manifest["analysis_sdk"], "5.11.1")
        self.assertEqual(manifest["runtime_status"], "not_run")
        self.assertEqual(manifest["scope"], "selected_translation_unit")
        fixed_revision = "04365ad20d13bd9618413f134fba6ff9ada074b7"
        original_revision = "b68e2fda4be2e671b0907c2e803c4094124e2fa4"
        relative = "src/layers/LevelIDLayer.cpp"
        snapshots = [subprocess.check_output(["git", "-C", str(project), "show", revision + ":" + relative]) for revision in (original_revision, fixed_revision)]
        self.assertEqual((project / relative).read_bytes(), snapshots[1])
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "BetterInfo"
            shutil.copytree(project, copied, ignore=shutil.ignore_patterns(".git", "build", "resources"))
            build = copied / "build"
            build.mkdir()
            selected = json.loads((project / "build/level-id-only/compile_commands.json").read_text())
            for entry in selected:
                args = entry.get("arguments") or shlex.split(entry["command"])
                entry["arguments"] = [str(copied / relative) if arg == entry["file"] else arg for arg in args]
                entry.pop("command", None)
                entry["file"] = str(copied / relative)
            (build / "compile_commands.json").write_text(json.dumps(selected))
            reports = []
            for source in snapshots:
                (copied / relative).write_bytes(source)
                scan = subprocess.run([str(test_analyzer.BINARY), "inspect", str(copied), "-p", str(build), "--format", "json"], text=True, capture_output=True, timeout=120)
                self.assertEqual(scan.returncode, 1, scan.stderr)
                report = json.loads(scan.stdout)
                self.assertEqual(next(f["status"] for f in report["files"] if f["file"] == relative), "complete")
                self.assertEqual(report["toolchain"]["sdk"], "5.11.1")
                self.assertTrue(any(f["kind"] == "uncompiled_source" for f in report["files"]))
                reports.append(report)
            before, after = reports
            self.assertEqual([f["location"]["line"] for f in before["findings"]], [28, 50, 65])
            self.assertEqual([f["location"]["line"] for f in after["findings"]], [50, 65])
            self.assertEqual(before["ownership"]["retaining_captures"], 0)
            self.assertEqual(after["ownership"]["retaining_captures"], 1)
            self.assertTrue(all(f["factory_contract"] == "mac_implementation_unverified" for f in before["findings"]))
            self.assertEqual((project / relative).read_bytes(), snapshots[1], "Benchmark must preserve cached source")


if __name__ == "__main__":
    unittest.main()
