#!/usr/bin/env python3
"""Prepare the pinned real Geode example for syntax analysis, without a game profile.

Only writes under .deps. Does not install a mod or modify global shell/Geode settings.
Network access is needed on first use; subsequent configuration reuses the caches.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
LOCK = json.loads((ROOT / "docs/toolchain-lock.json").read_text())


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def revision(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def checkout(name, repository, expected):
    destination = DEPS / name
    if not destination.exists():
        run("git", "clone", "https://github.com/" + repository + ".git", destination)
        run("git", "-C", destination, "checkout", "--detach", expected)
    if revision(destination) != expected:
        raise RuntimeError(f"{destination} has another revision; preserve it and use a fresh .deps directory.")
    return destination


def verified_download(url, digest, cached):
    if cached.exists():
        content = cached.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=60) as response:
            content = response.read()
    if hashlib.sha256(content).hexdigest() != digest:
        raise RuntimeError(f"Checksum differs from the recorded toolchain: {url}")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(content)
    return content


def main():
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("The demo setup currently supports macOS ARM64 only.")
    for command in ("git", "cmake", "ninja", "xcrun", "brew"):
        if not shutil.which(command):
            raise RuntimeError(f"Install {command} before preparing the example.")
    llvm = Path(subprocess.check_output(["brew", "--prefix", "llvm@21"], text=True).strip())
    compiler_version = subprocess.check_output([str(llvm / "bin/clang++"), "--version"], text=True)
    if "version " + LOCK["llvm"] not in compiler_version:
        raise RuntimeError("The demo requires LLVM " + LOCK["llvm"])
    DEPS.mkdir(exist_ok=True)
    sdk = checkout("geode", "geode-sdk/geode", LOCK["geode"]["revision"])
    bindings = checkout("bindings", "geode-sdk/bindings", LOCK["bindings"]["revision"])
    example = checkout("example-mod", "geode-sdk/example-mod", LOCK["example"]["revision"])
    source = example / "src/main.cpp"
    if hashlib.sha256(source.read_bytes()).hexdigest() != LOCK["example"]["main_sha256"]:
        raise RuntimeError("Official example C++ source has local edits; preserving them and stopping.")
    archive = verified_download(LOCK["geode"]["mac_binary_url"],
                               LOCK["geode"]["mac_binary_sha256"], DEPS / "geode-mac.zip")
    binary_dir = sdk / "bin" / LOCK["geode"]["version"]
    binary_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for filename in ("Geode.dylib", "GeodeBootstrapper.dylib"):
            (binary_dir / filename).write_bytes(bundle.read(filename))
    build = example / "build"
    codegen = build / "bindings/codegen/Codegen"
    verified_download(LOCK["bindings"]["codegen_url"], LOCK["bindings"]["codegen_sha256"], codegen)
    codegen.chmod(0o755)

    # Restore the exact upstream configuration from git, then apply only documented
    # configuration substitutions. The upstream C++ source stays byte-for-byte intact.
    cmake = subprocess.check_output(["git", "-C", str(example), "show", "HEAD:CMakeLists.txt"], text=True)
    cmake = cmake.replace('set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64")',
                          'set(CMAKE_OSX_ARCHITECTURES "arm64")')
    cmake = cmake.replace("add_library(${PROJECT_NAME} SHARED ${SOURCES})",
                          'add_library(${PROJECT_NAME} SHARED ${SOURCES})\n'
                          'target_compile_definitions(${PROJECT_NAME} PRIVATE GEODE_MOD_ID="warden.official-example")')
    cmake = cmake.replace("setup_geode_mod(${PROJECT_NAME})", "setup_geode_mod(${PROJECT_NAME} DONT_INSTALL)")
    (example / "CMakeLists.txt").write_text(cmake)
    metadata = json.loads(subprocess.check_output(["git", "-C", str(example), "show", "HEAD:mod.json"], text=True))
    metadata.update(geode=LOCK["geode"]["version"], id="warden.official-example", name="Warden Official Example",
                    version="1.0.0", developer="Warden", description="Official Geode example for static analysis")
    (example / "mod.json").write_text(json.dumps(metadata, indent=2) + "\n")
    env = dict(os.environ, GEODE_SDK=str(sdk), CPM_SOURCE_CACHE=str(DEPS / "cpm"))
    sysroot = subprocess.check_output(["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True).strip()
    run("cmake", "-S", example, "-B", build, "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
        "-DCMAKE_CXX_COMPILER=" + str(llvm / "bin/clang++"),
        "-DCMAKE_C_COMPILER=" + str(llvm / "bin/clang"),
        "-DCMAKE_OSX_SYSROOT=" + sysroot, "-DGEODE_BINDINGS_REPO_PATH=" + str(bindings),
        "-DGEODE_DISABLE_CLI_CALLS=ON", "-DGEODE_DISABLE_PRECOMPILED_HEADERS=ON",
        "-DSKIP_BUILDING_CODEGEN=ON", env=env)
    manifest = dict(LOCK, macos_sdk=sysroot, sdk_root=str(sdk), bindings_root=str(bindings))
    manifest["dependencies"] = {}
    for head in (DEPS / "cpm").glob("*/*/.git"):
        if head.is_dir():
            manifest["dependencies"][str(head.parent.relative_to(DEPS))] = revision(head.parent)
    (example / "warden-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Prepared real SDK-backed example:", example)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
