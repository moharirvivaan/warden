#!/usr/bin/env python3
"""Build and package controlled Geode test mods. Never install or launch them."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples/compatibility-proof"
BUILD = ROOT / "build/proof"
VARIANTS = {"remover": "warden.proof-remover", "consumer": "warden.proof-consumer",
            "consumer-guarded": "warden.proof-consumer-guarded"}
TARGETS = ["proof_remover", "proof_consumer", "proof_consumer_guarded"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_destination(path):
    if path.is_symlink():
        raise RuntimeError("Refusing a symlink output directory")
    if not path.exists():
        return
    if not path.is_dir():
        raise RuntimeError("Output must be a directory")
    entries = list(path.iterdir())
    if not entries:
        return
    expected = {mod_id + ".geode" for mod_id in VARIANTS.values()} | {"manifest.json"}
    if {entry.name for entry in entries} != expected or any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise RuntimeError("Refusing to overwrite unrelated output files")
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("kind") != "warden-controlled-proof" or manifest.get("schema_version") != 1:
        raise RuntimeError("Output is not an owned Warden proof bundle")
    packages = manifest.get("packages", [])
    if {item["filename"] for item in packages} != expected - {"manifest.json"} or len(packages) != 3:
        raise RuntimeError("Existing manifest package set is invalid")
    for item in packages:
        if digest((path / item["filename"]).read_bytes()) != item["sha256"]:
            raise RuntimeError("Refusing to overwrite a package modified locally")


def archive_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    return buffer.getvalue()


def prepare(destination):
    check_destination(destination)
    subprocess.run([sys.executable, str(ROOT / "scripts/configure-proof.py")], check=True)
    subprocess.run(["cmake", "--build", str(BUILD), "--target", *TARGETS], check=True)
    lock = json.loads((ROOT / "docs/toolchain-lock.json").read_text())
    provenance = json.loads((ROOT / ".deps/example-mod/warden-provenance.json").read_text())
    manifest = {"schema_version": 1, "kind": "warden-controlled-proof",
                "runtime_status": "not_run", "architecture": "arm64", "toolchain": lock,
                "dependencies": provenance["dependencies"],
                "bindings_cmake_patch": {"change": "add VERBATIM to generator custom command",
                    "sha256": digest((BUILD / "bindings-source/CMakeLists.txt").read_bytes())},
                "packages": []}
    payloads = {}
    common = [PROJECT / "CMakeLists.txt", ROOT / "docs/toolchain-lock.json",
              ROOT / "scripts/configure-proof.py", ROOT / "scripts/prepare-proof.py"]
    for variant, mod_id in VARIANTS.items():
        metadata_path = PROJECT / variant / "mod.json"
        metadata_bytes = metadata_path.read_bytes()
        metadata = json.loads(metadata_bytes)
        if metadata["id"] != mod_id or metadata["geode"] != lock["geode"]["version"]:
            raise RuntimeError("Metadata differs from the configured variant: " + variant)
        binary = BUILD / "binaries" / (mod_id + ".dylib")
        architecture = subprocess.check_output(["lipo", "-archs", str(binary)], text=True).strip()
        if architecture != "arm64":
            raise RuntimeError("Unexpected architecture for " + mod_id)
        linkage = subprocess.check_output(["otool", "-L", str(binary)], text=True)
        if "Geode.dylib" not in linkage:
            raise RuntimeError("Missing real Geode linkage for " + mod_id)
        compiled = binary.read_bytes()
        filename = mod_id + ".geode"
        payloads[filename] = archive_bytes({"mod.json": metadata_bytes, mod_id + ".dylib": compiled})
        inputs = common + [metadata_path, PROJECT / variant / "src/main.cpp"]
        manifest["packages"].append({"id": mod_id, "version": metadata["version"],
            "filename": filename, "sha256": digest(payloads[filename]),
            "binary_sha256": digest(compiled), "dependencies": metadata["dependencies"],
            "compiler_database_sha256": digest((BUILD / "inspect" / variant / "compile_commands.json").read_bytes()),
            "sources": {str(source.relative_to(ROOT)): digest(source.read_bytes()) for source in inputs}})
    payloads["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    # Stage only after a successful real build. Recheck before replacing owned files.
    check_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="warden-proof-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        for filename, data in payloads.items():
            (stage / filename).write_bytes(data)
        destination.mkdir(exist_ok=True)
        for filename in payloads:
            os.replace(stage / filename, destination / filename)
    print("Prepared three controlled test packages in", destination)
    print("Runtime status: NOT RUN. No game installation or launch performed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BUILD / "packages")
    options = parser.parse_args()
    try:
        prepare(options.output.absolute())
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
