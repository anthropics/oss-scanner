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
The architecture and SIMD implementations are in scope when they affect memory
safety, integer or floating-point bounds, or control flow. `tests/` and
`examples/` are useful drivers and are in scope when they expose library bugs;
benchmarks and generated performance data are lower priority.

## How to exercise it

Use the built `duck` driver to compile and run focused programs from
`tests/rigor/`, `tests/core/`, `tests/memory/`, `tests/hash/`, `tests/math/`,
`tests/locks/`, `tests/elf/`, and `tests/adv/`. Prefer small hosted tests first,
then inspect freestanding and syscall-specific paths where the relevant test
provides them. The repository's `verify_compile_gcc.duck` and
`verify_compile_clang.duck` files describe broader compile matrices.

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

