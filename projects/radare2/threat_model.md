# radare2

radare2 inspects executables, firmware, memory dumps, filesystems and malicious
files. Its command-line tools and embeddable libraries also assemble, emulate,
debug, extract, patch and serve data. The whole codebase is in scope:
all libraries, commands, plugins, tools, scripting integrations,
bundled dependencies, and shipped build, installation and packaging helpers.
Directory names and the default Linux build do not limit scope. Review optional
features and other platforms too; state when they cannot be exercised here.

## Inputs and security boundaries

Treat file bytes, names, paths, format metadata, symbols, types, debug information,
projects, archives, compressed streams, instruction bytes and protocol replies as
attacker-controlled when they come from an untrusted artifact or peer. Consider
both CLI use and documented library calls by embedding applications. A debugger
client must not trust the target or remote server's lengths, registers or XML.

Ordinary opening, inspection, rendering, analysis and extraction must not grant
input data unintended command execution, file access, network access or plugin
capabilities. Follow data across parsers, IO backends, analysis, command generation,
output and consumers of exported scripts; a locally safe helper can still be
unsafe in composition. Check read-only, sandbox, command-filter and authenticated
service boundaries against their documented guarantees, including alternate
command spellings, nested evaluation, deferred work and configuration changes.

radare2 deliberately supports shell commands, scripts, native plugins, debugging
and writes. Show what an attacker controls and which additional action or access
they gain beyond the operator's request. For trusted script/project execution or
build helpers, identify any lower-trust input that crosses a real boundary.
For services, give the enabling options, bind address and authentication state;
also inspect work performed before authentication and hostile peer responses.

## Properties to investigate

These are starting points, not an exhaustive list of reportable bugs:

- **Ranges and arithmetic:** are counts, lengths and offsets valid in the type
  used at every subsequent operation? Look for signed and unsigned overflow or
  underflow, narrowing, sign conversion, negative error values becoming sizes,
  sentinel values, invalid shifts, division by zero and pointer arithmetic UB.
  Validate subtraction before computing remaining length, and multiplication or
  addition before allocation or bounds checks. Distinguish file, virtual and
  physical addresses, actual buffer capacity and declared enclosing chunk size.
- **Representation and reads:** do short reads, missing terminators, empty
  records, inconsistent cross-references or wrong type tags leave values that
  later code assumes valid? Investigate uninitialized data, type confusion,
  alignment, invalid enum/boolean values and incompatible callback signatures.
  Check overlapping copies, invalid libc preconditions and variadic type mismatches.
  Follow numeric and string conversions through JSON, commands and serialization
  for silent truncation, changed meaning or disclosure of uninitialized memory.
- **Ownership and state:** who owns each object before and after a split, merge,
  reallocation, callback, cancellation or failed operation? Find stale pointers,
  double frees, iterator invalidation and shared or borrowed data outliving its
  owner. Check cache keys and invalidation against all parameters, configuration
  and object generations. Failure must not publish success, enlarged capacity,
  partial objects or permissions that the operation never actually established.
  Exercise repeated open/close, attach/detach and reset sequences and interactions
  between multiple core instances or background tasks; inspect races and deadlocks.
- **Progress and resource use:** can a small input cause an unbounded loop,
  recursion, retry, expansion or superlinear workload? Look for cyclic type,
  filesystem and analysis graphs, nested compressed payloads, zero-size records,
  reused cursors and missing aggregate budgets. Check timeout, cancellation and
  allocation limits across nested operations, including work before authentication.
- **Authority and injection:** can metadata become radare2 syntax, a shell
  argument, a URI, an output path or executable exported text? Follow quoting,
  newlines, option-shaped names, encodings and canonicalization through every
  interpreter and escaping for terminal, HTML and JSON output. Investigate path
  traversal, symlink escapes, unwanted IO backend redirects, authentication
  fallthrough, information disclosure and restrictions lost through config reset,
  capture, aliasing, background or deferred execution.
- **Semantic integrity:** investigate broken analysis, emulation, register,
  relocation, patching, cryptographic API and serialization invariants even without
  a crash. Examples include a stale cache changing meaning, a failed read accepted
  as valid, the wrong descriptor being closed, partial writes reported as successful
  or mismatched lengths causing incorrect results. Explain the demonstrated effect;
  label a correctness defect as such when no security impact is established.

## Investigation and evidence

Map entry points and trust boundaries throughout the tree, then trace concrete
inputs through callers, helpers and consumers. Read the relevant contracts and
check whether validation survives conversions, nested structures, state changes
and error paths. Test boundary values and operation sequences, not just single
malformed files. Compare sibling implementations and alternate command/API paths
for inconsistent enforcement. Keep track of unexamined and unavailable surfaces.

Use `git log --all --grep='##crash'` and the corresponding diffs and regressions
as leads for broken invariants and incomplete fixes. Historical examples include
negative filesystem geometry, type-tag confusion, metadata-to-command injection,
ownership after analysis block splits, authentication fallthrough and sandbox
permissions restored by config reset or deferred execution. Search for analogous
defects elsewhere and combinations the original tests missed. Confirm that a
candidate still exists in the scanned revision; an old fixed bug is not a finding.

Validate with the smallest appropriate CLI invocation, library harness, command
sequence or local protocol peer. Sanitizers help establish memory/UB failures;
also assert outputs, state, permissions, side effects and bounded resource use.
A sanitizer message or suspicious construct alone does not establish a
vulnerability. Inspect intentional modular arithmetic and platform-specific
assumptions before treating them as defects. Do not require a sanitizer crash
for a reproducible logic, authorization, disclosure or resource-exhaustion bug.

## Environment and testing

The checkout is `/src`. The normal build has debug information and frame pointers;
`/usr/local` uses symlinks into this checkout. GCC, Clang, sanitizer runtimes, GDB
and Python r2pipe are available. Dependencies and `/src/test/bins` are fetched
during setup. Keep them for offline work. Do not execute sample binaries from
the corpus; run trusted radare2 tools and test harnesses against them as data.

From `/src`, use `r2r -u -C test db/formats/elf` for a targeted regression or select
another existing file under `test/db`. `r2r -u -C test` runs the normal suite;
`-u` skips corpus updates; the image also sets `R2R_OFFLINE=1`.
Python r2pipe supports its scripting tests and custom reproducers. Unit tests:
`make -C test unit-tests`. See `test/README.md` for optional suites and requirements.
Useful entry points are `rabin2 -I sample`, `rabin2 -S sample` and
`r2 -N -q -c 'aaa;q' sample`. Keep the filename last. `-n` disables binary loading;
use it only when deliberately testing raw input. Bound potentially hanging runs.

For an offline ASan/UBSan rebuild from `/src`:

```sh
make clean
CC=clang CXX=clang++ \
  CFLAGS='-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined' \
  LDFLAGS='-fsanitize=address,undefined' ./configure --prefix=/usr/local
make -j"$(nproc)" && make symstall && ldconfig
```

Clean and rebuild relevant harnesses too when switching instrumentation.
For arithmetic investigations, Clang's additional
`-fsanitize=unsigned-integer-overflow,implicit-conversion` checks can expose
unsigned underflow, truncation and sign changes not covered by `undefined`;
enable them selectively and examine intentional wraparound. Reproduce findings
with the normal build when relevant. Avoid `make mrproper`, `sys/install.sh` and
`sys/sanitize.sh` offline: their clean rebuild removes downloaded subprojects.
See `DEVELOPERS.md` for debugging guidance. Platform-specific findings may need
source reasoning or a separate host; describe the validation limitation.

## Reports and patches

Give the revision, affected feature and configuration, attacker-controlled input,
entry point, root cause, broken invariant, minimal reproducer and observed result.
Include build flags and traces where applicable. Describe expected behavior and
the demonstrated security or correctness impact separately from speculative
exploitability. Rank severity by consequences, reachability and prerequisites;
a local crash does not by itself prove remote execution. For resource exhaustion,
give input size, time/memory consumed and the relevant limits or service exposure.
Group manifestations of the same root cause and check for existing fixes/reports;
identify the upstream component for defects in bundled dependencies.

Prefer a small fix using existing radare2 APIs that restores the invariant, with
an appropriate regression and a valid-input check. Follow `AGENTS.md` and
`DEVELOPERS.md`. Binary fixtures belong in radare2-testbins. Preserve supported
functionality; avoid blanket rejection, unrelated refactoring and silent error
suppression. `SECURITY.md` documents disclosure and the configured primary
contact receives scanner reports.
