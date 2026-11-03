# Threat model — libffi

## What this project does and where untrusted input enters

libffi is a portable Foreign Function Interface library. It lets a program describe a C
call interface at runtime (argument and return types, ABI) and then (a) make calls through
that description with `ffi_call`, and (b) build **closures** — executable trampolines that
turn a C function pointer into a dispatch back to a user-supplied handler.

libffi is almost always embedded inside a language runtime or FFI bridge (CPython `ctypes`,
Ruby `fiddle`, many others). It is infrastructure: the direct caller of the libffi API is
trusted code (the runtime), not an attacker. The security question is therefore **what
happens when attacker-influenced data flows *through* a trusted runtime into libffi** —
most importantly the pieces a runtime commonly derives from untrusted input:

- the **type graph** handed to `ffi_prep_cif` / `ffi_prep_cif_var` (element types, struct
  member lists, number of fixed and variadic arguments);
- the **argument buffers** passed to `ffi_call` and the values marshalled into/out of them;
- the data a **closure** receives when the trampoline is invoked and unpacks arguments for
  the user handler.

A memory-safety or integer bug in that marshalling — reachable with a *well-formed but
adversarial* type description and matching arguments — is the finding we most want. The
caller is trusted, but a runtime that lets untrusted scripts shape the cif (field counts,
sizes, nesting) makes these paths attacker-reachable in practice.

## Components that matter most / least

- **Most important:** `src/prep_cif.c` (cif construction, size/alignment accumulation,
  variadic handling), the generic argument marshalling in `src/raw_api.c` and the per-ABI
  `ffi.c` / `ffi64.c` call and closure code (notably `src/x86/`, `src/aarch64/`), struct
  layout in `ffi_prep_cif`, and executable-memory handling in `src/closures.c`.
- **In scope but lower:** less common architectures and the `*_sysv` / `*_win64` variants we
  do not build here — still report if you can show the bug, but we cannot reproduce them in
  this image.
- **Out of scope:** the DejaGnu test harness under `testsuite/`, the autotools build system,
  and generated files (`configure`, `Makefile.in`, `fficonfig.h.in`).

## How to exercise it

The image builds libffi twice from the same `/src` checkout:

- `/src/build` — plain `-g` build; `make check` (the DejaGnu suite in `testsuite/`) has been
  run against it. The test cases there are the best worked examples of driving `ffi_prep_cif`,
  `ffi_call`, and closures across many type signatures.
- `/src/build-asan` — AddressSanitizer + UBSan build of the library; link small reproducers
  against `/src/build-asan/.libs/libffi.a` (or the shared object) to confirm memory-safety and
  undefined-behaviour findings. The sanitizer runtimes are installed, so reproducers can be
  compiled offline with `-fsanitize=address,undefined`.

## How you rate severity

- A **heap/stack buffer overflow, use-after-free, double free, or type-confusion** in cif
  construction, argument marshalling, or closure dispatch that is reachable from the public
  API with a plausible (well-formed) type description and arguments: **high** at minimum, and
  **critical** if it is controllable in a way that plausibly leads to code execution (libffi
  already deals in executable memory and indirect calls, so treat control-flow-relevant
  corruption as critical-leaning).
- An **integer overflow / truncation** in a size or alignment computation that leads to an
  undersized allocation or out-of-bounds access: rate by the memory effect it produces (so
  usually high+).
- A failure to enforce **W^X** on closure/executable memory, or a path that leaves memory
  simultaneously writable and executable, where the platform is expected to support it:
  **high**.
- Pure **DoS** reachable only through the libffi API (e.g. a crash or abort on a degenerate
  but well-formed cif) with no memory-safety consequence: **medium**.

## Anything to leave alone

- The direct caller of the libffi API is trusted. A "bug" that requires passing a
  self-evidently malformed `ffi_cif` / `ffi_type` (bad `type` tag, lying `size`/`alignment`
  that contradicts the elements, a NULL where the API documents a required pointer) — i.e.
  something no correct runtime would ever construct — is **informational at most**: say so,
  but do not rate it high. Prefer findings reachable from a *valid* type description.
- Do not report the test programs under `testsuite/` crashing under sanitizers as libffi
  vulnerabilities unless the fault is inside libffi itself.
