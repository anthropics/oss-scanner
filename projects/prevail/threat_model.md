# PREVAIL threat model

## Purpose and security boundary

PREVAIL is a C++ eBPF verifier based on abstract interpretation. It loads eBPF
programs, constructs a control-flow graph, and checks safety assertions using
abstract states. It is also embedded as a library by downstream runtimes.

The highest-priority failure is an unsound acceptance: PREVAIL accepts a program
whose concrete execution violates a safety property that the selected platform
and configuration are intended to enforce. A consumer may rely on this result
before executing attacker-controlled bytecode in a more privileged context.
Compromise of the verifier process while parsing or analyzing that bytecode is
an independent security concern.

Focus on memory bounds, pointer provenance and types, initialized registers and
stack bytes, safe helper/kfunc arguments and returns, and sound arithmetic and
control-flow reasoning. Termination is an additional property only when enabled.
These are verification goals, not a claim of complete Linux-verifier parity or
complete coverage of every eBPF feature.

## Attacker-controlled inputs

Treat the following as hostile, including combinations that are malformed,
inconsistent, excessively large, deeply nested, or only partially supported:

- ELF objects: headers, sections, symbols, relocations, strings, map definitions,
  code and data, `.BTF`, `.BTF.ext`, and CO-RE relocation records.
- Raw eBPF instruction sequences supplied to library entry points: opcodes,
  register indices, offsets, immediates, jump and call targets, and instruction
  combinations. An attacker need not use a normal compiler.
- Program-controlled helper/kfunc IDs and arguments, map accesses, callback
  targets, local calls, branch conditions, and loop structure.
- Packet contents, map contents, and other runtime values reachable by an
  accepted program, within the embedding platform's declared contracts.

The normal `bin/prevail` CLI accepts ELF files. Assembly and YAML parsers in
`src/test/` are useful reproducer and regression-test surfaces; they are not an
assembly-input mode of that CLI. State explicitly if a finding is reachable only
through test tooling or a custom library harness.

## Trusted assumptions and configuration

The embedding runtime is responsible for providing accurate platform metadata:
program type and context layout, helper/kfunc contracts and availability,
conformance groups, map descriptors, memory-region sizes, and relevant privilege
or execution constraints. Runtime behavior must match the semantics verified,
and the executed program must be the program that was checked. A malicious
caller deliberately supplying false trusted metadata is a different boundary
from a program causing PREVAIL to misinterpret untrusted metadata.

The Linux CLI infers program type from file/section naming, including a fallback
type; this selects a model and is not an authenticated deployment-privilege
check. An integration must bind that selection to the actual execution context.
Builtin extern constants are modeled values, not queries of the running kernel.

The platform tables shipped by PREVAIL are still in scope: an incorrect builtin
contract, availability check, or translation of untrusted input into a trusted
descriptor can cause an unsound result. Explain which descriptor or contract
is involved rather than assuming all platform data is attacker-controlled.

Important defaults and caveats, defined by `src/config.hpp` and `src/main.cpp`:

- Termination checking is off by default. Use `--termination` when claiming a
  bypass of the optional termination check. A loop accepted without that option
  is not by itself evidence of a termination-checking bug.
- Strict mode is off by default. `--strict` adds checks for some runtime failures;
  reports must name the exact option set and the property being bypassed.
- Division by zero is allowed by default using BPF ISA semantics. Acceptance of
  division by zero alone is not a vulnerability; incorrect modeling can be.
- Default limits are 512 bytes per subprogram stack frame, 8 call-stack frames,
  and a maximum packet size of 65535. Library callers can change these limits.
- The default CLI conformance groups exclude `callx` and legacy `packet`
  instructions. Clearly identify reports requiring an explicitly enabled group.
- Mock map file descriptors are enabled by default. The ordinary offline tests
  do not require loading attacker programs into a live kernel.

Trusted hosts, build tools, dependency repositories, and deliberate changes to
source code are outside the hostile-bytecode boundary. Build failures alone are
not verifier vulnerabilities. Vulnerabilities in the use or integration of a
dependency remain relevant; distinguish them from defects wholly inside that
dependency.

## Highest-value code to review

- `src/io/`: ELF/BTF loading, maps, extern resolution, and CO-RE relocations.
- `src/ir/unmarshal.cpp`, `src/ir/call_resolver.cpp`,
  `src/ir/cfg_builder.cpp`, and `src/ir/assertions.cpp`: instruction validation,
  call resolution, graph construction, inlining, and safety-assertion generation.
- `src/fwd_analyzer.cpp`, `src/cfg/`, and `src/crab/`: transfer functions,
  assertion checking, signed/unsigned and 32/64-bit arithmetic, intervals and
  relational constraints, joins, widening/narrowing, pointer types, stack-cell
  overlap, and initialization tracking. Losing a possible concrete state can
  turn an unsafe path into a false proof of safety.
- `src/linux/`, `src/spec/`, `src/platform.hpp`, and library entry points:
  builtin contracts, their validation, and consistency across the loader and
  analyzer. Include state isolation between repeated or concurrent analyses.
- Dependencies reached while processing hostile ELF/BTF or instruction data,
  including ELFIO and libbtf. Attribute the faulty code and its integration
  precisely; avoid unrelated broad dependency-upgrade patches.

Diagnostic output and failure slicing are lower priority than acceptance logic,
but memory-safety or resource-exhaustion bugs reachable through them can matter.
Tests, fixtures, examples, and build scripts are useful for reproduction and
coverage; identify when an issue has no production-path reachability.

## Known limitations and triage

Read `docs/parity/` and `docs/feature-support-matrix.md` before reporting a missing
feature. In particular, the current tree documents incomplete reference
lifecycle tracking (`docs/parity/lifetime.md`), structural callback checks
without callback-body verification under a callback contract
(`docs/parity/call-model.md`), and incomplete BTF-driven semantic typing beyond
parsing/relocation (`docs/parity/btf-semantics.md`).

These limitations constrain the safety claims a consumer can make. Do not
rediscover a documented gap and present it as a newly identified defect. A new
bypass, additional affected path, or concrete consequence beyond the documented
limitation is useful if the distinction and actual reachability are clear.
They are not blanket exclusions: concrete unsafe acceptance under a supported
configuration still warrants assessment, with known mechanisms identified.
Unsupported features do not make parser crashes or corruption acceptable.

Different accept/reject results from Linux are not sufficient evidence of a
vulnerability. Establish the concrete violated property under matching
instruction semantics, program type, platform contracts, and options. A safe
program rejected because the analysis is conservative is normally a precision
or compatibility issue, not a security finding.

## Severity guidance

- Treat a demonstrated verifier bypass permitting out-of-bounds access,
  uninitialized-data disclosure, forged pointers, or another forbidden effect
  under supported contracts as high priority. Critical severity needs a credible
  deployment and impact chain, such as crossing a kernel or sandbox boundary;
  do not infer that solely from a `PASS` result or a Linux discrepancy.
- Verifier-process memory corruption or information disclosure from hostile
  production input is high priority. Explain attacker control and realistic
  consequences; distinguish demonstrated exploitation from potential impact.
- Crashes, hangs, excessive recursion, and disproportionate CPU/memory use are
  generally availability findings. Severity depends on input size, resource
  amplification, and whether an untrusted submitter can repeatedly disrupt a
  shared verification service. Do not equate every local CLI crash with remote
  code execution or host compromise.
- False rejections, cosmetic diagnostics, and test-only failures generally have
  low or no security severity unless a separate security consequence is shown.

## Build and exercise offline

The repository-root `Dockerfile` builds PREVAIL and its tests on Ubuntu 24.04,
initializes recursive submodules from a normal Git clone, and leaves the source
and build tree in `/prevail`. Build-time network access fetches dependencies;
the commands below need no network after the image is built.

For the project's plain image, from a PREVAIL checkout:

```sh
docker build -t prevail .
docker run --rm --network=none --entrypoint ctest prevail \
  --test-dir build --output-on-failure --no-tests=error --parallel 2
docker run --rm --network=none prevail ebpf-samples/cilium/bpf_lxc.o 2/1
```

After `tools/check prevail` builds the scanner image and opens its offline shell,
run these commands in `/src` (the wrapper maps the existing project there and
resets the image's default entrypoint):

```sh
ctest --test-dir build --output-on-failure --no-tests=error --parallel 2
./bin/prevail ebpf-samples/cilium/bpf_lxc.o 2/1
```

CTest includes sample-object checks and the unit suite. For focused work, run
`./bin/tests '~[samples]'`, or use
`./bin/run_yaml test-data/<fixture>.yaml` for a specific YAML regression.
Read current fixtures and `src/test/ebpf_yaml.cpp` for their actual format.
No live kernel loading or privileged Docker container is needed for these
offline verification checks.

## Useful reports and patches

Include the PREVAIL commit, dependency revisions, compiler/build type, complete
command or minimal API harness, platform/program type, options and enabled
conformance groups. Provide the smallest ELF, bytecode, or YAML regression that
reproduces the issue, with a generator if practical. Record the observed result,
the expected safety property, and why a concrete execution can violate it.

For soundness findings, identify the instruction and abstract-state transition
that loses a required constraint, and show the reachable unsafe operation.
For parser/process failures, include a stack trace and sanitizer output where
available. For denial of service, give input size, elapsed time, peak memory,
resource limits, and a reasonable baseline.

Proposed fixes should preserve conservative analysis and include a focused
regression test. Explain the invariant restored by the fix and list checks
actually run, separating failures and unrun checks from passing results.
Avoid real-world exploitation or execution of unsafe bytecode on production
kernels; a minimized semantic argument or isolated harness is preferable.
