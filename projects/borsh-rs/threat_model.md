# Borsh Rust implementation

Borsh is a deterministic binary serialization format used by security-critical
applications. This repository implements the Rust runtime and derive macros.
The format and specification are documented at https://borsh.io and in
https://github.com/near/borsh.

## Trust boundaries and priorities

- Serialized bytes, length prefixes, enum discriminants, and collection contents
  may be adversarial. Exercise both slice and streaming-reader entry points.
- Prioritize memory safety, incorrect acceptance or rejection of encodings,
  inconsistent serialization/deserialization, and disproportionate CPU, memory,
  or stack use on untrusted input.
- Review unsafe runtime code, recursive and generic types, collection decoding,
  derive-generated implementations, and schema operations. Optional features,
  including no_std configurations and unstable schema APIs, remain in scope;
  identify the required feature set in each report.
- Rust source and custom serialization implementations supplied by an application
  are trusted code. Show how a reported failure follows from library behavior,
  rather than arbitrary behavior in a custom implementation. Compiler execution
  of a malicious procedural macro is not a Borsh vulnerability.
- Reference identity is not preserved by the documented Rc/Arc implementations.
  Do not treat that documented behavior alone as a vulnerability.

## Reproduction and severity

Provide a minimal Rust type, exact input bytes or reader behavior, Cargo features,
the affected API, and expected versus actual behavior. Prefer a regression test
against this checkout. Measure resource-exhaustion claims in an optimized build,
including encoded input size and peak additional memory or elapsed CPU time.
Distinguish a library defect from the application's responsibility to bound input
size, recursion, work, and concurrent decodes. Lack of an application-specific
resource budget alone is not a finding; establish the amplification and the
relevant documented contract or realistic trust boundary.

Severity should reflect demonstrated consequences and attacker access. Reachable
memory corruption or a demonstrated integrity failure in a security-sensitive use
can be high or critical. A panic, abort, or resource exhaustion in a service parsing
untrusted input can be a denial of service; describe its preconditions and cost.
A panic achievable only through trusted application code is not automatically a
remote vulnerability. Do not infer theft or consensus failure from a parser bug
without showing the necessary application behavior.

Third-party dependency defects belong to their upstream projects. The benchmark
and Honggfuzz programs are test drivers, not independently deployed services.
Do not weaken assertions or update snapshots to make a reproducer pass.

## Build and tests

The checkout is at /src. Rust 1.95 and the dependencies and compiled artifacts for
the upstream CI test matrix are installed in the image. Run the matrix offline:

```sh
bash .github/test.sh
```

For a focused test, use `cargo test -p borsh` with the relevant features, or
`cargo test -p borsh-derive --features schema`. Tests live under borsh/tests and
borsh-derive/src. `--all-features` enables the nightly-only
`force_exhaustive_checks` maintenance check; use explicit feature combinations
for runtime investigations.
