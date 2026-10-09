# Threat model

Aptos Core is the software an Aptos validator runs. It orders blocks, executes Move transactions, and stores the ledger that results. Input from outside a validator includes signed transactions, published Move modules and scripts, peer-to-peer consensus and sync messages, REST and gRPC request bodies, and JSON Web Keys.

A defect matters when untrusted input can change who owns funds, make two honest validators commit different ledgers, or break type, ability, or reference safety in the Move VM. Signature checks and the rest of `crates/aptos-crypto/` are in that set.

Read `consensus/` except `consensus/src/dag/`, `execution/`, `storage/`, `mempool/`, `network/`, `secure/`, `keyless/`, `types/`, `crates/aptos-crypto/`, `aptos-move/` (the VM, the block executor, the framework, and the natives), and `third_party/move/`. Treat `api/` as in scope when the bug crashes a validator or changes consensus or funds.

Skip `terraform/`, `dashboards/`, documentation, the faucet, telemetry, and the NFT metadata crawler. The indexer-processors submodule is not in this image. Skip `consensus/src/dag/`: that folder is test-only. Skip other trees under `third_party/` except Move, and skip test-only code. A difference in gas charged is out of scope unless a transaction can force unbounded work in the VM.

Use these severity classes:

- Critical: loss of funds, a consensus or safety failure, or a VM type, ability, or reference-safety failure that changes state. The input is untrusted.
- High: remote loss of liveness, remote code execution on a validator, two honest validators executing the same block differently, or a VM crash or out-of-memory kill caused by a transaction.
- Medium: a bounded crash of a node or of the API.
- Low: a bug in tooling or tests, or a hardening issue with no effect on consensus or funds.

Report a bytecode-verifier bypass or a paranoid-mode bypass even when a later check rejects the module or transaction. Name the check that catches it.

This image has the Rust 1.98.1 toolchain, a cargo registry from `cargo fetch --locked`, and the test binaries for the commands below. The scan machine has 2 CPUs and 8 GB of RAM. Run one `.move` or `.masm` file through the VM with:

```
cargo test -p aptos-transactional-test-harness --test tests --offline -- runner::aptos_test_harness/smoke_test.move
```

The filter is `runner::` plus the path under `aptos-move/aptos-transactional-test-harness/tests/`. Put a new file there with a matching `.exp`.

Run one Move end-to-end test with:

```
cargo test -p e2e-move-tests --offline --lib tests::vm::failed_encrypted_transaction_increments_sequence_number
```

A new test is a `#[test]` under `aptos-move/e2e-move-tests/src/tests/`, registered in `src/tests/mod.rs`. It uses `MoveHarness`. A file in `aptos-move/e2e-move-tests/tests/` is a separate binary: `cargo test -p e2e-move-tests --offline --test closure_ty_tag_memory`.

A small crate is `cargo test -p aptos-crypto --offline --lib`.

The minimal consensus tests are safety rules and the message types:

```
cargo test -p aptos-safety-rules --offline --lib
cargo test -p aptos-consensus-types --offline --lib
```

A single AptosBFT test, with the DAG suite left out:

```
cargo test -p aptos-consensus --offline --lib round_manager -- --skip dag::
```

Do not build `aptos-node`, the smoke tests, or Forge.

One report per root cause. The reproducer is a small test or harness. The patch changes only what the bug requires. Skip style findings, guesses, and a second writeup of the same cause.
