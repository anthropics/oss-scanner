# How we would like patches made

Fix the root cause in the layer that owns the contract. Reuse the existing
Rust primitive, validation helper, or adapter as appropriate and preserve
documented wire behavior, numeric codes, and ownership. When the public
operation or error contract changes, update the protobuf schema and its Rust
mapping together, preserve existing field and error numbers, and regenerate
bindings with the repository's pinned tools.

Use checked arithmetic and explicit conversions for sizes, offsets, and
capacities. Keep typed errors and existing zeroizing owners. In TypeScript,
validate values at the boundary and clear owned temporary sensitive buffers.
Keep diagnostics free of raw inputs and secret or personal data. Explain
boundary assumptions and security invariants in comments.

Add a focused regression test to the nearest existing suite using synthetic
data or a public vector. Cover the valid case and the invalid or ambiguous
case, asserting the documented typed failure where it applies. For a parity
fix, compare the bytes, metadata, or typed errors in the affected lanes.
Summarize which format, lint, and test checks ran and identify any affected
runtime that still needs verification.
