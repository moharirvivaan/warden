# Controlled compatibility probe

These are test mods for a runtime experiment, not historical bugs discovered by
Warden. The analyzer currently inventories their hooks; it does not diagnose
their interaction. Do not install these into a normal mod collection.

| Variant | Intended behavior |
|---|---|
| `warden.proof-remover` | Removes the `bottom-menu` UI node after base initialization |
| `warden.proof-consumer` | Adds a visible `WARDEN PROOF` label to that node without checking its existence |
| `warden.proof-consumer-guarded` | Adds the same label when the node exists; otherwise skips the optional feature and preserves initialization |

The consumer variants are alternatives: never load both together. The remover's
post-hook priority is 100 and the consumer's is 200. Their actual order must be
verified from runtime logs; assigning priorities alone is not reproduction evidence.
NodeIDs >=v1.23.3 and Geometry Dash 2.2081 on macOS ARM64 are the initial context.

From the repository root:

```bash
python3 scripts/configure-proof.py
cmake --build build/proof --target proof_remover proof_consumer proof_consumer_guarded
python3 scripts/prepare-proof.py --output build/proof/packages
python3 -m pip install -r tests/requirements.txt
python3 -m unittest discover -s tests -p test_proof_packages.py -v
python3 -m unittest discover -s tests -p test_proof_records.py -v
```

Configuration requires the previously prepared pinned SDK, bindings, dependency
cache, code generator, and LLVM. It does not install dependencies or launch a game.
The local bindings mirror adds `VERBATIM` to one upstream CMake command to support
this checkout's parentheses. Original bindings sources are preserved; the patch
hash is recorded in the package manifest.

Inventory a variant:

```bash
./build/warden inspect examples/compatibility-proof/consumer \
  -p build/proof/inspect/consumer --format json
```

The filtered databases preserve the actual build commands and avoid combining
different configurations for one translation unit. `onModify` is a lifecycle
construct outside the inventory's supported coverage and may make the report
partial; the registered `init` hook must still appear. Compiler errors are not
acceptable preparation results.

Packages contain the loader-required archive-root `mod.json` and `<mod-id>.dylib`.
The producer rebuilds before packaging and records source, binary, package,
compiler database, and toolchain evidence. Stable input binaries produce stable
archive bytes. It refuses unrelated or modified output files. This does not prove
that the game will accept a package or that the scenario will behave as intended.

Follow [the reviewed runtime procedure](../../docs/runtime-test-procedure.md).
Runtime outcomes are initially **not run**. Do not describe the guarded consumer
as a validated fix until both its present-node behavior and absent-node fallback
have been observed and accepted by a person.
