# Threat model: uuid-rs

`uuid` is the Rust implementation of RFC 9562 UUIDs: it generates them (time-based, name-based, random and
caller-defined versions), parses them from text and bytes, and formats them. It is `no_std`-compatible, has no
required dependencies, and is a leaf dependency of much of the Rust ecosystem, so identifiers from the network,
files and databases pass through it before any application-level validation.

Parsers run on attacker-controlled input and must never panic, fail to parse a valid UUID in a supported format
to its correct value, successfully parse an invalid UUID, or hang.

Unsafe code wrapped in safe APIs must never allow triggering of undefined behavior.

Expected uniqueness and monotonicity guarantees must be maintained as per the RFC when generating UUIDs using
implementations supplied in the crate. Pay particular attention to version 7 UUIDs, which are the most complex.

A deviation from the RFC with no effect on uniqueness, parsing or memory safety is a bug, not a vulnerability.

Reports should carry a failing Rust test, the features, target and toolchain used, and Miri output for undefined
behaviour; for uniqueness or randomness, the sample count and observed pattern. Propose a minimal patch against
`main` with a regression test that builds on the MSRV, keeps `no_std` and no-default-features working, adds no
dependencies, and keeps the 1.x public API stable. Report one root cause once, listing each entry point that
reaches it.
