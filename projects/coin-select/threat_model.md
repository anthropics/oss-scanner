# Threat model

## Project and trust boundaries
`bdk_coin_select` is a zero-dependency library for Bitcoin input selection: BNB, SRD, changeless, lowest-fee, RBF, and fee/weight arithmetic. It returns a selection and change/fee values that a wallet uses to build a transaction.

## Untrusted inputs
- Candidate sets (values, weights, input counts), including very large or adversarial sets.
- Target outputs, fee rates, target fees, drain weights, and max-weight constraints.
- Caller-supplied weights and values, including boundary and overflow values.

## In scope
- Selection algorithm correctness and termination.
- Fee, change, and weight arithmetic, including `f64` fee math.
- Boundary conditions, overflow/underflow, NaN/infinity, division by zero.
- DoS via large candidate sets or pathological input.
- Ensure selections never exceed max weight or produce negative/overflowing values.

## Out of scope
- `rust-bitcoin`, `rust-miniscript`, `proptest`, `criterion`, or other dev-dependencies.
- Benchmarks and test-only code.
- Wallet policy above the selector (for example, which candidates are eligible).

## How to exercise the code offline
Run:
- `cargo test --all-features`
- `cargo test --release` for the proptest suite

No external services are required.

## Severity rubric
- Critical: a selection produces a transaction that is invalid or loses funds (negative fee/change, value overflow, weight violation) under realistic input.
- High: a deterministic panic/non-termination or DoS on attacker-influenced candidates; selection violates a documented invariant with fund impact.
- Medium: panic/DoS requiring unusual input, or suboptimal selection with a clear security consequence.
- Low: suboptimal selection, excess fees, or robustness issues without demonstrated fund loss.

## Report and patch preferences
- Minimal reproducer as a Rust test with the exact candidate/target values.
- State whether `std`/`no_std` and release mode are required.
- Prefer a minimal patch; call out behavior changes.
- Deduplicate by root cause and affected function.

## Known non-issues / do not report
- Suboptimal but valid selections.
- Benchmarks, proptest regressions, and test-only code.
- Caller-supplied candidates that are already invalid.
