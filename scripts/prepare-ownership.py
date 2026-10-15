#!/usr/bin/env python3
"""Prepare a focused, SDK-adapted BetterInfo source benchmark from cached inputs.

No downloads, external API stubs, installation, game launch, or historical-SDK
claim. Only the cached mod's documented CMake configuration may be changed.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / ".deps/betterinfo-benchmark"
REVISION = "04365ad20d13bd9618413f134fba6ff9ada074b7"
BEFORE = "b68e2fda4be2e671b0907c2e803c4094124e2fa4"


def output(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def prepare():
    if not PROJECT.is_dir():
        raise RuntimeError("Clone Cvolton/betterinfo-geode into .deps/betterinfo-benchmark and check out " + REVISION)
    if output("git", "-C", PROJECT, "rev-parse", "HEAD") != REVISION:
        raise RuntimeError("BetterInfo revision differs; preserving checkout")
    lock = json.loads((ROOT / "docs/toolchain-lock.json").read_text())
    dependencies = json.loads((ROOT / ".deps/example-mod/warden-provenance.json").read_text())["dependencies"]
    for directory, revision in ((ROOT / ".deps/geode", lock["geode"]["revision"]),
                                (ROOT / ".deps/bindings", lock["bindings"]["revision"])):
        if output("git", "-C", directory, "rev-parse", "HEAD") != revision or output("git", "-C", directory, "status", "--porcelain"):
            raise RuntimeError("Pinned SDK/bindings checkout differs: " + str(directory))
    for relative, revision in dependencies.items():
        directory = ROOT / ".deps" / relative
        if output("git", "-C", directory, "rev-parse", "HEAD") != revision or output("git", "-C", directory, "status", "--porcelain"):
            raise RuntimeError("Pinned cached dependency differs: " + str(directory))
    upstream = subprocess.check_output(["git", "-C", str(PROJECT), "show", "HEAD:CMakeLists.txt"], text=True)
    patched = upstream.replace('set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64")', 'set(CMAKE_OSX_ARCHITECTURES "arm64")')
    patched = patched.replace("add_subdirectory($ENV{GEODE_SDK} $ENV{GEODE_SDK}/build)",
                              "add_subdirectory($ENV{GEODE_SDK} ${CMAKE_CURRENT_BINARY_DIR}/geode)")
    patched = patched.replace("setup_geode_mod(${PROJECT_NAME} EXTERNALS geode.node-ids:1.23.0)",
        'target_compile_definitions(${PROJECT_NAME} PRIVATE GEODE_MOD_ID="cvolton.betterinfo")\n'
        "setup_geode_mod(${PROJECT_NAME} DONT_INSTALL EXTERNALS geode.node-ids:1.23.0)")
    if patched == upstream:
        raise RuntimeError("Upstream configuration changed; review adaptation")
    cmake = PROJECT / "CMakeLists.txt"
    if cmake.read_text() not in (upstream, patched):
        raise RuntimeError("BetterInfo CMake has unrelated edits; preserving checkout")
    changes = output("git", "-C", PROJECT, "diff", "HEAD", "--name-only").splitlines()
    if any(name != "CMakeLists.txt" for name in changes) or output("git", "-C", PROJECT, "ls-files", "--others", "--exclude-standard"):
        raise RuntimeError("BetterInfo inputs have unrelated edits/untracked files; preserving checkout")
    build = PROJECT / "build"
    codegen = ROOT / ".deps/example-mod/build/bindings/codegen/Codegen"
    if hashlib.sha256(codegen.read_bytes()).hexdigest() != lock["bindings"]["codegen_sha256"]:
        raise RuntimeError("Cached codegen differs from toolchain lock")
    llvm = Path(output("brew", "--prefix", "llvm@21"))
    if "version " + lock["llvm"] not in output(llvm / "bin/clang++", "--version"):
        raise RuntimeError("Compiler differs from toolchain lock")
    destination = build / "bindings/codegen/Codegen"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(codegen, destination)
    cmake.write_text(patched)
    env = dict(os.environ, GEODE_SDK=str(ROOT / ".deps/geode"), CPM_SOURCE_CACHE=str(ROOT / ".deps/cpm"))
    command = ["cmake", "-S", str(PROJECT), "-B", str(build), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        "-DCMAKE_CXX_COMPILER=" + str(llvm / "bin/clang++"), "-DCMAKE_C_COMPILER=" + str(llvm / "bin/clang"),
        "-DCMAKE_OSX_SYSROOT=" + output("xcrun", "--sdk", "macosx", "--show-sdk-path"),
        "-DGEODE_BINDINGS_REPO_PATH=" + str(ROOT / ".deps/bindings"),
        "-DGEODE_DISABLE_CLI_CALLS=ON", "-DGEODE_DISABLE_PRECOMPILED_HEADERS=ON",
        "-DSKIP_BUILDING_CODEGEN=ON", "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"]
    subprocess.run(command, env=env, check=True)
    entries = json.loads((build / "compile_commands.json").read_text())
    relative = "src/layers/LevelIDLayer.cpp"
    selected = [entry for entry in entries if Path(entry["file"]).resolve() == (PROJECT / relative).resolve()]
    if len(selected) != 1:
        raise RuntimeError("Expected exactly one LevelIDLayer compiler configuration")
    focused = build / "level-id-only"
    focused.mkdir(exist_ok=True)
    (focused / "compile_commands.json").write_text(json.dumps(selected, indent=2) + "\n")
    provenance = dict(lock, dependencies=dependencies, revision=REVISION, before_revision=BEFORE, metadata_sdk="5.10.1",
        analysis_sdk="5.11.1", scope="selected_translation_unit", runtime_status="not_run",
        mode="SDK-adapted source benchmark; original SDK/full-project dependency build unverified",
        source_sha256=hashlib.sha256((PROJECT / relative).read_bytes()).hexdigest(),
        configuration_command=command, configuration_patch=output("git", "-C", PROJECT, "diff", "--", "CMakeLists.txt"))
    (build / "warden-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print("Prepared unchanged BetterInfo source with SDK 5.11.1 (metadata: 5.10.1).")
    print("Selected LevelIDLayer only; other units, external APIs, historical build, and runtime remain unverified.")


if __name__ == "__main__":
    try:
        prepare()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
