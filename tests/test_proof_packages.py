"""Real SDK builds and package contracts; no claim of runtime crash detection."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples/compatibility-proof"
BUILD = ROOT / "build/proof"
VARIANTS = {"remover": "warden.proof-remover", "consumer": "warden.proof-consumer",
            "consumer-guarded": "warden.proof-consumer-guarded"}
TARGETS = ["proof_remover", "proof_consumer", "proof_consumer_guarded"]


def run(*args):
    return subprocess.run(list(map(str, args)), cwd=ROOT, capture_output=True,
                          text=True, timeout=240)


def script_module(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProofInputTests(unittest.TestCase):
    def test_rejects_edited_pinned_source_checkout(self):
        # A matching HEAD cannot authorize modified compiler input content.
        module = script_module("configure-proof")
        self.assertTrue(hasattr(module, "verify_checkout"), "Pinned source validation must reject edits")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            def git(*args):
                result = run("git", "-C", path, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout.strip()
            git("init", "-q")
            (path / "input.hpp").write_text("original\n")
            git("add", "input.hpp")
            git("-c", "user.name=Warden Test", "-c", "user.email=test@example.invalid",
                "commit", "-qm", "temporary validation fixture")
            revision = git("rev-parse", "HEAD")
            module.verify_checkout(path, revision)
            (path / "input.hpp").write_text("modified\n")
            with self.assertRaisesRegex(RuntimeError, "modified"):
                module.verify_checkout(path, revision)

    def test_rejects_untracked_inputs_in_pinned_checkout(self):
        module = script_module("configure-proof")
        self.assertTrue(hasattr(module, "verify_checkout"), "Pinned source validation must reject extra inputs")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for args in [("init", "-q"), ("-c", "user.name=Warden Test", "-c",
                         "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "temporary fixture")]:
                result = run("git", "-C", path, *args)
                self.assertEqual(result.returncode, 0, result.stderr)
            revision = run("git", "-C", path, "rev-parse", "HEAD").stdout.strip()
            (path / "extra.hpp").write_text("untracked input\n")
            with self.assertRaisesRegex(RuntimeError, "modified"):
                module.verify_checkout(path, revision)


class ProofBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = run(sys.executable, ROOT / "scripts/configure-proof.py")
        cls.built = (run("cmake", "--build", BUILD, "--target", *TARGETS)
                     if cls.config.returncode == 0 else cls.config)

    def test_real_sdk_build_and_arm64_linkage(self):
        # Replacing the SDK with declarations or building an incompatible CPU fails.
        self.assertEqual(self.config.returncode, 0, self.config.stdout + self.config.stderr)
        self.assertEqual(self.built.returncode, 0, (self.built.stdout + self.built.stderr)[-7000:])
        for variant, mod_id in VARIANTS.items():
            binary = BUILD / "binaries" / (mod_id + ".dylib")
            self.assertTrue(binary.is_file(), str(binary))
            arch = run("lipo", "-archs", binary)
            self.assertEqual(arch.stdout.strip(), "arm64")
            linked = run("otool", "-L", binary)
            self.assertEqual(linked.returncode, 0, linked.stderr)
            self.assertIn("Geode.dylib", linked.stdout)
            metadata = json.loads((PROJECT / variant / "mod.json").read_text())
            self.assertEqual(metadata["id"], mod_id)
            self.assertEqual(metadata["geode"], "5.11.1")
            self.assertIn("geode.node-ids", metadata["dependencies"])

    def test_inventory_resolves_actual_hooks_with_distinct_compile_settings(self):
        self.assertEqual(self.built.returncode, 0, (self.built.stdout + self.built.stderr)[-7000:])
        for variant, mod_id in VARIANTS.items():
            database = BUILD / "inspect" / variant
            entries = json.loads((database / "compile_commands.json").read_text())
            self.assertEqual(len(entries), 1)
            self.assertIn(mod_id, entries[0]["command"])
            self.assertIn(str(ROOT / ".deps/geode"), entries[0]["command"])
            result = run(ROOT / "build/warden", "inspect", PROJECT / variant,
                         "-p", database, "--format", "json")
            self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["mod"]["id"], mod_id)
            self.assertEqual([(h["target_class"], h["method"]) for h in report["hooks"]],
                             [("MenuLayer", "init")])
            self.assertFalse(any(f["diagnostics"] for f in report["files"]), report)


class ProofPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.destination = Path(cls.directory.name) / "packages"
        cls.prepared = run(sys.executable, ROOT / "scripts/prepare-proof.py",
                           "--output", cls.destination)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def require_packages(self):
        self.assertEqual(self.prepared.returncode, 0, self.prepared.stdout + self.prepared.stderr)

    def test_package_payload_matches_built_artifacts_and_provenance(self):
        # Omitting a dylib, misidentifying a variant, or hashing stale content fails.
        self.require_packages()
        manifest = json.loads((self.destination / "manifest.json").read_text())
        self.assertEqual(manifest["runtime_status"], "not_run")
        self.assertEqual(len(manifest["packages"]), 3)
        for item in manifest["packages"]:
            archive = self.destination / item["filename"]
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), item["sha256"])
            with zipfile.ZipFile(archive) as package:
                self.assertEqual(sorted(package.namelist()), ["mod.json", item["id"] + ".dylib"])
                metadata = json.loads(package.read("mod.json"))
                self.assertEqual(metadata["id"], item["id"])
                self.assertEqual(package.read(item["id"] + ".dylib"),
                                 (BUILD / "binaries" / (item["id"] + ".dylib")).read_bytes())
            for relative, digest in item["sources"].items():
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), digest)

    def test_repeat_packaging_has_identical_archives(self):
        self.require_packages()
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.destination.glob("*.geode")}
        result = run(sys.executable, ROOT / "scripts/prepare-proof.py", "--output", self.destination)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in self.destination.glob("*.geode")})

    def test_refuses_unrelated_output_without_writing(self):
        self.require_packages()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "keep.txt").write_text("user content")
            result = run(sys.executable, ROOT / "scripts/prepare-proof.py", "--output", path)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual([p.name for p in path.iterdir()], ["keep.txt"])
            self.assertEqual((path / "keep.txt").read_text(), "user content")

    def test_refuses_modified_package_without_overwriting(self):
        self.require_packages()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for original in self.destination.iterdir():
                (path / original.name).write_bytes(original.read_bytes())
            archive = next(path.glob("*.geode"))
            archive.write_bytes(b"changed locally")
            before = {p.name: p.read_bytes() for p in path.iterdir()}
            result = run(sys.executable, ROOT / "scripts/prepare-proof.py", "--output", path)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, {p.name: p.read_bytes() for p in path.iterdir()})


class ProofRebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # All mutations occur in a disposable project with the real pinned SDK.
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        for relative in ("scripts", "examples/compatibility-proof"):
            shutil.copytree(ROOT / relative, cls.root / relative, ignore=shutil.ignore_patterns("__pycache__"))
        (cls.root / "docs").mkdir()
        shutil.copy2(ROOT / "docs/toolchain-lock.json", cls.root / "docs/toolchain-lock.json")
        (cls.root / ".deps").symlink_to(ROOT / ".deps", target_is_directory=True)
        cls.destination = cls.root / "build/proof/packages"
        cls.script = cls.root / "scripts/prepare-proof.py"
        cls.prepared = run(sys.executable, cls.script, "--output", cls.destination)
        # Optional test-only mutation proves these checks catch a skipped rebuild.
        if os.environ.get("WARDEN_TEST_SKIP_REBUILD") == "1":
            text = cls.script.read_text()
            text = text.replace('    subprocess.run(["cmake", "--build", str(BUILD), "--target", *TARGETS], check=True)\n', "")
            cls.script.write_text(text)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def require_preparation(self):
        self.assertEqual(self.prepared.returncode, 0,
                         (self.prepared.stdout + self.prepared.stderr)[-6000:])

    def test_failed_build_preserves_existing_packages(self):
        self.require_preparation()
        source = self.root / "examples/compatibility-proof/consumer/src/main.cpp"
        original = source.read_text()
        before = {p.name: p.read_bytes() for p in self.destination.iterdir()}
        try:
            source.write_text(original + "\n#error WARDEN_PROOF_TEST_COMPILE_FAILURE\n")
            result = run(sys.executable, self.script, "--output", self.destination)
            self.assertNotEqual(result.returncode, 0, "Failed compilation must refuse to package old binaries")
            self.assertEqual(before, {p.name: p.read_bytes() for p in self.destination.iterdir()})
        finally:
            source.write_text(original)

    def test_changed_source_rebuilds_the_binary_before_packaging(self):
        self.require_preparation()
        source = self.root / "examples/compatibility-proof/consumer/src/main.cpp"
        original = source.read_text()
        package = self.destination / "warden.proof-consumer.geode"
        before = hashlib.sha256(package.read_bytes()).hexdigest()
        try:
            source.write_text(original.replace('"WARDEN PROOF"', '"WARDEN PROOF REBUILT"'))
            result = run(sys.executable, self.script, "--output", self.destination)
            self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-6000:])
            self.assertNotEqual(before, hashlib.sha256(package.read_bytes()).hexdigest(),
                                "Changing the label must regenerate the compiled package")
            with zipfile.ZipFile(package) as archive:
                self.assertIn(b"WARDEN PROOF REBUILT", archive.read("warden.proof-consumer.dylib"))
            manifest = json.loads((self.destination / "manifest.json").read_text())
            item = next(p for p in manifest["packages"] if p["id"] == "warden.proof-consumer")
            self.assertEqual(item["sources"]["examples/compatibility-proof/consumer/src/main.cpp"],
                             hashlib.sha256(source.read_bytes()).hexdigest())
        finally:
            source.write_text(original)


if __name__ == "__main__":
    unittest.main()
