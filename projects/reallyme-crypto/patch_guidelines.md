# Patch format

Fix the root cause in the layer that owns the contract. Reuse existing
validators, typed errors, and zeroizing owners. Preserve supported public API
and wire behavior. If a wire error needs to change, update the schema, reason
mapping, and tests together.

Use checked arithmetic and explicit conversions for sizes and offsets. In
Rust, return a typed domain error with a `thiserror` reason mapping and keep
panic paths out of library code. In TypeScript, validate external values at
the boundary and clear temporary secret buffers when ownership permits it.
Keep secrets out of diagnostics and explain security invariants in comments.

Add a focused regression test in the nearest existing suite. Use synthetic
fixtures or public vectors to show the restored invariant and cover both valid
and invalid input. Assert the typed failure when the contract defines one.
Summarize the relevant tests, formatting, and lint checks that ran and identify
any runtime lane that needs separate verification.
