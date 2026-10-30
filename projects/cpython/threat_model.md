# Threat model

The [Python security policy](https://devguide.python.org/security/policy/) is
the threat model and is authoritative over this file (a copy is in the image
at `/opt/security-policy.rst`). Check every candidate finding against it
before reporting.

## What CPython is and where untrusted input enters

CPython is the Python interpreter and the standard library. Python code is
trusted, that is, whoever runs the interpreter chooses what it runs.
Untrusted input is data that correct, documented use of the interpreter or a
stdlib module processes on the program's behalf, e.g. network protocols or file
formats parsed by stdlib modules, built-in type conversions on attacker-sized
input, or paths taken from data.

## Check the documentation first

Documented behaviour is not a vulnerability. Before reporting, read the docs
for the API involved and look for security considerations or disclaimers. If
the docs explicitly disclaim the behaviour, it is not a vulnerability. Do not
report it.

## Availability and algorithmic complexity

The bar is high and most findings here are rejected. Per the policy, an
availability issue (DoS, ReDoS, super-linear behaviour, resource exhaustion,
crashes, deadlocks) must be triggerable with input reasonably sized for the
use case and must give the attacker an "upward" change in posture. Slow
handling of large input is a performance issue, not a security issue.

Assume programs pass limited, use-case-sized input, typically a few KB. Reject
findings that need tens of KB or more to cost a few seconds, or that an
existing limit already blocks. Report only when small input causes clearly
disproportionate cost. Quantify: input size, wall time, growth order.

## Not vulnerabilities (per the policy)

- Anything reachable only by running attacker-written Python code or misusing a
  C API outside its documented contract. Those are ordinary bugs.
- Anything the documentation discloses as a limitation (see above).
- Control of launch conditions, including command line arguments, environment
  variables, and files on the host.
- Unhandled exceptions, e.g. `RecursionError` or `MemoryError`.
- Availability issues that need unreasonably large input or give the attacker
  no upward change in posture (see above).
- Bugs in bundled or system third-party code (expat, HACL\*, OpenSSL, zlib,
  Tcl/Tk) unless CPython's use of it is wrong.
- Experimental features, unsupported platforms (PEP 11) and unsupported Python
  versions.

## How to exercise it

`/src/python` is an in-tree pydebug build. Run tests with `./python -m test
test_<name> -v`. Tests are found in `Lib/test/`. Rebuild after a patch with
`make -s -j"$(nproc)"`. Reconfigure with sanitizers if useful, e.g.
`./configure --with-pydebug --with-address-sanitizer --without-pymalloc`.

## Reports

Follow the policy's "what to include" section. It should consist of a few succinct
sentences, a minimal PoC script that exits 1 when vulnerable and 0 when not,
the versions tested, and ideally a minimal patch against `main`. Quote the
documentation checked, and for availability findings give input size and
timing. Do not include a CVSS score.
