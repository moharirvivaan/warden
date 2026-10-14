"""End-to-end contracts against the real Geode SDK (no substitute headers)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get("WARDEN_BINARY", ROOT / "build/warden"))
EXAMPLE = Path(os.environ.get("WARDEN_EXAMPLE", ROOT / ".deps/example-mod"))


class AnalyzerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
