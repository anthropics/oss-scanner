# Threat model

## What this project does and where untrusted input enters

Warpo compiles AssemblyScript, a TypeScript-like language, to WebAssembly. A user or build service may compile source supplied by another party. Relevant inputs include source files and imports, `asconfig.json`, command-line options, and packages found through `node_modules` or `--path`. Debugging tools also read WebAssembly, DWARF debug information, source maps, and heap snapshots. The CLI can download and extract prebuilt compiler archives.

`warpo build` can automatically discover and execute a project's `create.ts` build script. The script is compiled to WebAssembly and run with linked host APIs, including module-resolution callbacks. Treat build scripts as executable project code, not as passive configuration or as proof that an untrusted project can safely be built without isolation.

Generated WebAssembly runs in a separate runtime with the host imports and permissions chosen by its operator. Warpo is not responsible for enforcing the external runtime's sandbox or restricting deliberately supplied host imports.

Protect the compiler process and its accessible files, the integrity of generated WebAssembly and compiler binaries, and the confidentiality of source and debug data. Heap snapshots can contain application data and should be treated as sensitive.

## Components that matter most / least

- The parser and frontend (`assemblyscript/`, `warpo_extension/`, `frontend/`), module resolution, and native driver (`driver/`) process source and configuration across the WebAssembly/native boundary. Look for memory corruption, unsafe file access, and unexpected execution while compiling input.
- Optimization and lowering (`passes/`, especially `passes/GC/`) and the runtimes under `assemblyscript/std/` and `warpo_extension/std/` affect object lifetime, shadow-stack GC roots, memory access, and generated code. Incorrect output is security-relevant when it breaks an intended safety property or has a demonstrated downstream impact.
- The build-script runner (`warp_runner/` and `driver/BuildScript.cpp`) and debugging tools (`tools/dwarf/`, `tools/debug_server/`, `tools/heap_analyzer/`) process executable scripts, debugging artifacts, or heap dumps; check host API boundaries and malformed input handling.
- The downloader (`tools/scripts/`) fetches and extracts release archives. Check that downloaded data cannot cause unintended file writes or execution, and specify whether the attacker controls a configured mirror or release source.
- Dependencies such as Binaryen under `third_party/binaryen/` are relevant when reached through Warpo. Identify the affected dependency and a Warpo reproduction so the issue can also be handled upstream.

## How to exercise it

Install dependencies and build with `npm ci` and `npm run build`, then run `npm run test`. The suite covers AssemblyScript and C++ unit tests, frontend and optimization snapshots, driver tests, and debug information tests. Useful test inputs and harnesses are in `tests/assemblyscript/`, `tests/frontend/`, `tests/snapshot_diff/`, `tests/driver/`, `tests/dwarf/`, and `tools/dwarf/tests/`. Debug-server and heap-analyzer tests can also be run with `npm run test:debug_server` and `npm run test:heap_analyzer`.

For a compiler reproduction, use the built CLI (`node dist/warpo.js`) with a source file and the relevant options, such as `--debug`, `--runtime`, or `--path`. Include the source, configuration, and host/runtime setup needed to reproduce the impact.

## How you rate severity

Use the following as preliminary guidance, not a published project policy:

- **Critical:** demonstrated code execution or comparable compromise from untrusted input across a meaningful trust boundary in a realistic deployment.
- **High:** reproducible memory corruption, a significant unintended host capability, or incorrect generated code with a demonstrated serious security impact.
- **Medium:** a reproducible denial of service or information disclosure with a plausible security impact and attack scenario.
- **Low:** limited impact or unusually restrictive attacker prerequisites. Assess the actual deployment and privileges rather than rating a compiler crash by itself as critical.

## Anything to leave alone

Do not report normal diagnostics for invalid input, expected program behavior, or a crash without a plausible security impact as a vulnerability. Running a project's own `create.ts`, tests, or explicitly provided host imports is expected behavior; report unintended privilege crossings or unsafe handling of their inputs instead. An explicitly configured compiler binary or download mirror is a trusted choice by the operator. Distinguish problems in an external WebAssembly runtime from problems in Warpo's generated code or integration.