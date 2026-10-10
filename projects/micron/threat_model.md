# Threat model

## What this project does and where untrusted input enters

Micron is a header-only C++ core library that replaces parts of libc and the C++
standard library and targets Linux system calls. Untrusted data can reach any
public parser, formatter, container, algorithm, regular-expression, filesystem,
ELF, process, networking, or sandbox API used by an application built with the
library. Treat data read from files, sockets, command-line arguments, IPC, and
the environment as attacker controlled when exercising those APIs.

## Components that matter most / least

The primary scope is `src/`, especially memory allocation and ownership,
strings and parsing, regular expressions, I/O and filesystem wrappers,
process and security interfaces, concurrency, and the Linux syscall port.
Treat `src/sec/` as a security hotspot and give it priority, including its
callers and the code that establishes or crosses privilege, sandbox, syscall,
and validation boundaries. Fundamental startup and bootstrap code is also a
priority: inspect the earliest initialization, runtime setup, global or thread
state initialization, and shutdown paths because defects there affect every
consumer and can invalidate later security assumptions. The architecture and
SIMD implementations are in scope when they affect memory safety, integer or
floating-point bounds, or control flow. `tests/` and `examples/` are useful
drivers and are in scope when they expose library bugs; benchmarks and
generated performance data are lower priority.

## High-priority review lenses

Check explicitly for aliasing and object-lifetime problems, including strict
aliasing violations, type punning, invalid casts, overlapping ranges, stale
references or views, pointer provenance assumptions, and code that gives two
owners incompatible access to the same storage. Follow these issues through
allocation, containers, parsing, SIMD, and syscall boundaries; compiler
optimizations may turn undefined behavior into a security defect even when a
debug build appears correct.

Review every architecture-dependent assumption. Check 32-bit and 64-bit word
sizes, signedness and truncation, alignment, endianness, structure layout and
ABI assumptions, atomic widths, compiler builtins, syscall types, and SIMD
fallbacks. Use the available compile matrix and inspect paths that are only
selected on a different architecture; a bug that appears only on one supported
architecture is still in scope.

Review concurrency together with allocation. Look for data races, incorrect
atomic ordering, lost wakeups, deadlocks, lock-free ABA or reclamation bugs,
reentrancy and thread-local-state mistakes, signal or interrupt-unsuitable
operations, and cross-thread ownership errors. In allocator and memory-pool
code, check size and alignment calculations, metadata corruption, freelist
integrity, double-free and use-after-free paths, cross-thread frees, exhaustion,
and allocator reentrancy. Give extra weight to defects at the intersection of
concurrency, allocator state, startup, and `src/sec/`, since those paths can
produce broad memory-safety or privilege-boundary impact.

## How to exercise it

Use the built `duck` driver to compile and run focused programs from
`tests/rigor/`, `tests/core/`, `tests/memory/`, `tests/hash/`, `tests/math/`,
`tests/locks/`, `tests/elf/`, and `tests/adv/`. Prefer small hosted tests first,
then inspect freestanding and syscall-specific paths where the relevant test
provides them. Include startup and initialization paths, allocator stress,
threaded and cross-thread ownership cases, and architecture-specific compile
paths when the available drivers support them. The repository's
`verify_compile_gcc.duck` and `verify_compile_clang.duck` files describe broader
compile matrices.

## How you rate severity

Treat a reachable buffer overflow, out-of-bounds access, use-after-free,
double-free, integer overflow that causes an unsafe allocation or bounds
calculation, data race with memory-safety impact, or arbitrary code execution
as high or critical depending on exploitability. Treat a sandbox escape,
privilege boundary bypass, or syscall wrapper that grants unintended authority
as critical when reachable by an untrusted caller. Treat reliable denial of
service, hangs, uncontrolled resource growth, and information disclosure as
medium or high according to reachability and impact. Findings that require a
caller to violate an explicitly documented unsafe precondition should include
that precondition and should be ranked below an unconditional defect.

## Anything to leave alone

Do not report portability differences outside Linux as vulnerabilities; Linux is
the supported target. Do not treat performance regressions, missing optional
architectures, or intentionally unsafe APIs by themselves as security bugs.
