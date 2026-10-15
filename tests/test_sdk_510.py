"""Actual second SDK configuration; no version-string or header substitution."""
import json
from pathlib import Path
import shlex
import tempfile
import unittest
import test_analyzer


class OriginalSdkTests(unittest.TestCase):
    run_warden = test_analyzer.AnalyzerTests.run_warden

    def test_real_sdk_582_nodeids_configuration(self):
        self.check_sdk("5.8.2", ".deps/nodeids-benchmark/build/compile_commands.json")

    def test_actual_nodeids_pch_preserves_header_context(self):
        root=test_analyzer.ROOT;project=root/".deps/nodeids-benchmark";build=project/"build/pch-582/selected"
        if not (project/"build/pch-582/CMakeFiles/NodeIDs.dir/cmake_pch.hxx.pch").exists():
            self.skipTest("Actual SDK-backed NodeIDs PCH is absent.")
        result=self.run_warden("inspect",project,"-p",build,"--format","json");report=json.loads(result.stdout)
        self.assertEqual(result.returncode,1) # Priority/lifecycle logic and unselected files remain unknown.
        self.assertEqual(report["toolchain"]["sdk"],"5.8.2")
        self.assertEqual([(h["target_class"],h["method"]) for h in report["hooks"]],[("ChallengeNode","init"),("PauseLayer","customSetup")])
        self.assertFalse(any(d["severity"]=="error" for f in report["files"] for d in f["diagnostics"]))

    def test_ownership_resolves_sdk_when_headers_are_precompiled(self):
        root=test_analyzer.ROOT;project=root/".deps/betterinfo-original-sdk";database=project/"build/pch-510/inspect/compile_commands.json"
        if not (project/"build/pch-510/CMakeFiles/BetterInfo.dir/cmake_pch.hxx.pch").exists():
            self.skipTest("Actual BetterInfo SDK PCH is absent.")
        entry=next(e for e in json.loads(database.read_text()) if e["file"].endswith("src/layers/LevelIDLayer.cpp"))
        with tempfile.TemporaryDirectory() as directory:
            mod=Path(directory);build=mod/"build";build.mkdir();source=mod/"main.cpp"
            source.write_text('''void queued(){auto node=cocos2d::CCNode::create();
geode::Loader::get()->queueInMainThread([node](){node->setTag(42);});}
''')
            (mod/"mod.json").write_text(json.dumps({"id":"warden.pch-ownership","geode":"5.10.1"}))
            args=entry.get("arguments") or shlex.split(entry["command"])
            (build/"compile_commands.json").write_text(json.dumps([{"directory":entry["directory"],"file":str(source),"arguments":[str(source) if a==entry["file"] else a for a in args]}]))
            result=self.run_warden("inspect",mod,"-p",build,"--format","json");report=json.loads(result.stdout)
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertEqual(report["toolchain"]["sdk"],"5.10.1")
            self.assertEqual([f["rule"] for f in report["findings"]],["geode.deferred-cocos-ownership"])

    def check_sdk(self, version, database_path):
        root = test_analyzer.ROOT
        database = root / database_path
        if not database.exists():
            self.skipTest("Actual SDK configuration missing; no mock or substituted SDK.")
        entry = next(e for e in json.loads(database.read_text()) if "/src/" in e["file"] and "/.deps/" not in e["file"].split("nodeids-benchmark/")[-1])
        with tempfile.TemporaryDirectory() as directory:
            project=Path(directory); build=project/"build";build.mkdir(); source=project/"main.cpp"
            source.write_text(test_analyzer.PREFIX + '''
struct $modify(ActualSdk, MenuLayer){bool init(){return MenuLayer::init();}};
void queued(){auto node=cocos2d::CCNode::create(); Loader::get()->queueInMainThread([node](){node->setTag(42);});}
''')
            (project/"mod.json").write_text(json.dumps({"id":"warden.actual-sdk", "geode":version}))
            args=entry.get("arguments") or shlex.split(entry["command"])
            copied={"directory":entry["directory"],"file":str(source),"arguments":[str(source) if a==entry["file"] else a for a in args]}
            (build/"compile_commands.json").write_text(json.dumps([copied]))
            result=self.run_warden("inspect",project,"-p",build,"--format","json");report=json.loads(result.stdout)
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertEqual(report["toolchain"]["sdk"],version)
            self.assertEqual([(h["target_class"],h["method"]) for h in report["hooks"]],[("MenuLayer","init")])
            self.assertEqual(len(report["findings"]),1)
            self.assertEqual(report["unknown"],[])

    def test_real_sdk_510_hook_and_ownership(self):
        root = test_analyzer.ROOT
        database = root / ".deps/betterinfo-original-sdk/build/compile_commands.json"
        if not database.exists():
            self.skipTest("Original SDK configuration missing; no mock or substituted SDK.")
        entry = next(e for e in json.loads(database.read_text()) if e["file"].endswith("src/layers/LevelIDLayer.cpp"))
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            build = project / "build"
            build.mkdir()
            source = project / "main.cpp"
            source.write_text(test_analyzer.PREFIX + '''
struct $modify(Sdk510, MenuLayer) { bool init(){return MenuLayer::init();} };
void queued(){auto node=cocos2d::CCNode::create();
    Loader::get()->queueInMainThread([node](){node->setTag(42);});}
''')
            (project / "mod.json").write_text(json.dumps({"id":"warden.sdk-510", "geode":"5.10.1"}))
            args = entry.get("arguments") or shlex.split(entry["command"])
            copied = {"directory":entry["directory"], "file":str(source), "arguments":[str(source) if a == entry["file"] else a for a in args]}
            (build / "compile_commands.json").write_text(json.dumps([copied]))
            result = self.run_warden("inspect", project, "-p", build, "--format", "json")
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(report["toolchain"]["sdk"], "5.10.1")
            self.assertEqual([(h["target_class"],h["method"]) for h in report["hooks"]], [("MenuLayer","init")])
            self.assertEqual(len(report["findings"]), 1)
            self.assertEqual(report["unknown"], [])
