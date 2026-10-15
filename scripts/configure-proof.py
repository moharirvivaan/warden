#!/usr/bin/env python3
"""Configure the controlled probe from pinned, cached inputs; never install or launch."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "examples/compatibility-proof"
BUILD = ROOT / "build/proof"


def output(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def verify_checkout(path, revision):
    if not path.exists() or output("git", "-C", path, "rev-parse", "HEAD") != revision:
        raise RuntimeError("Pinned cached inputs missing or changed; see scripts/prepare-example.py")
    if output("git", "-C", path, "status", "--porcelain", "--untracked-files=normal"):
        raise RuntimeError("Pinned cached input checkout is modified: " + str(path))


def configure():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("The controlled probe supports macOS ARM64 only")
    lock = json.loads((ROOT / "docs/toolchain-lock.json").read_text())
    sdk, bindings = ROOT / ".deps/geode", ROOT / ".deps/bindings"
    for path, expected in [(sdk, lock["geode"]["revision"]), (bindings, lock["bindings"]["revision"])]:
        verify_checkout(path, expected)
    llvm = Path(output("brew", "--prefix", "llvm@21"))
    if "version " + lock["llvm"] not in output(llvm / "bin/clang++", "--version"):
        raise RuntimeError("LLVM differs from docs/toolchain-lock.json")
    codegen = ROOT / ".deps/example-mod/build/bindings/codegen/Codegen"
    if not codegen.is_file() or hashlib.sha256(codegen.read_bytes()).hexdigest() != lock["bindings"]["codegen_sha256"]:
        raise RuntimeError("Pinned cached codegen missing or changed; see scripts/prepare-example.py")
    destination = BUILD / "bindings/codegen/Codegen"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.read_bytes() != codegen.read_bytes():
        shutil.copy2(codegen, destination)
    destination.chmod(0o755)
    # The pinned upstream custom command omits VERBATIM. Use an explicit local
    # CMake-only patch with original source directories linked read-only by convention.
    mirror = BUILD / "bindings-source"
    mirror.mkdir(parents=True, exist_ok=True)
    for original in bindings.iterdir():
        if original.name in (".git", "CMakeLists.txt"):
            continue
        linked = mirror / original.name
        if not linked.exists():
            linked.symlink_to(original, target_is_directory=original.is_dir())
    upstream = (bindings / "CMakeLists.txt").read_text()
    marker = "add_custom_command(\n"
    if upstream.count(marker) != 1:
        raise RuntimeError("Bindings generation changed; review the VERBATIM workaround")
    patched = upstream.replace(marker, marker + "\tVERBATIM\n", 1)
    cmake_patch = mirror / "CMakeLists.txt"
    if not cmake_patch.exists() or cmake_patch.read_text() != patched:
        cmake_patch.write_text(patched)
    provenance = json.loads((ROOT / ".deps/example-mod/warden-provenance.json").read_text())
    for relative, revision in provenance["dependencies"].items():
        cached = ROOT / ".deps" / relative
        verify_checkout(cached, revision)
    env = dict(os.environ, GEODE_SDK=str(sdk), CPM_SOURCE_CACHE=str(ROOT / ".deps/cpm"))
    subprocess.run(["cmake", "-S", str(PROJECT), "-B", str(BUILD), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OSX_ARCHITECTURES=arm64",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON", "-DCMAKE_CXX_COMPILER=" + str(llvm / "bin/clang++"),
        "-DCMAKE_C_COMPILER=" + str(llvm / "bin/clang"),
        "-DCMAKE_OSX_SYSROOT=" + output("xcrun", "--sdk", "macosx", "--show-sdk-path"),
        "-DGEODE_BINDINGS_REPO_PATH=" + str(mirror), "-DGEODE_DISABLE_CLI_CALLS=ON",
        "-DCPM_LOCAL_PACKAGES_ONLY=OFF", "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
        "-DGEODE_DISABLE_PRECOMPILED_HEADERS=ON", "-DSKIP_BUILDING_CODEGEN=ON"], env=env, check=True)
    entries = json.loads((BUILD / "compile_commands.json").read_text())
    for variant in ("remover", "consumer", "consumer-guarded"):
        source = str(PROJECT / variant / "src/main.cpp")
        selected = [entry for entry in entries if str(Path(entry["file"]).resolve()) == source]
        if len(selected) != 1:
            raise RuntimeError("Expected one compiler configuration for " + variant)
        database = BUILD / "inspect" / variant
        database.mkdir(parents=True, exist_ok=True)
        (database / "compile_commands.json").write_text(json.dumps(selected, indent=2) + "\n")
    print("Configured controlled test mods; no installation or runtime test performed.")


if __name__ == "__main__":
    try:
        configure()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
