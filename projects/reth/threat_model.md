# Reth

Reth is an Ethereum execution client and a collection of Rust libraries used to build execution nodes. It validates and executes blocks, maintains Ethereum state, manages transactions, and serves peers and RPC clients. Consensus correctness, node availability, persistent state integrity, and protection of operator secrets are security properties.

## Scope and trust boundaries

Review the whole repository. The priorities below guide investigation without excluding other production components, optional features, or supporting tools. Identify the feature, deployment, and privileges needed to reach an issue.

- Treat discovery packets, RLPx handshakes, eth/snap messages, transactions, blocks, receipts, and downloaded state as adversarial. Prioritize remotely reachable parsing and resource-accounting paths in `crates/net/`, `crates/transaction-pool/`, and `crates/stages/`.
- Review block validation, fork rules, payload handling, execution, and state-root computation in `crates/consensus/`, `crates/ethereum/`, `crates/evm/`, `crates/engine/`, `crates/payload/`, and `crates/trie/`. Acceptance of invalid blocks, rejection of valid blocks, execution discrepancies, or incorrect roots can affect consensus. Include JIT/interpreter equivalence and precompile behavior where reachable through Reth.
- JSON-RPC requests are untrusted when the operator exposes the relevant listener and namespaces. Review `crates/rpc/` for authorization, work limits, expensive tracing and simulation, subscriptions, input validation, and accidental secret disclosure. State the transport, bind address, enabled methods, and authentication needed by a reproducer.
- The Engine API is intended for a trusted consensus client authenticated with JWT. Its intended fork-choice and payload-building authority is not itself a vulnerability. Authentication bypasses and robustness failures remain relevant; distinguish attacks requiring control of the trusted client from unauthenticated attacks.
- Review `crates/storage/`, `crates/static-file/`, pruning, import/export, and recovery for corruption caused by adversarial data or interrupted operations. Explain how an attacker can influence files or persisted state; arbitrary edits by an already privileged local administrator are not a remote attack.
- Review unsafe Rust, native libraries, cryptographic operations, and dependencies where Reth exposes them to untrusted data. Trace the actual Reth entry point and identify the component that needs the fix.
- Node configuration, installed extensions, and local administrator actions are trusted unless a separate boundary is crossed. Public blockchain data is not confidential. Reth is an execution client, not a validator signing service; do not assume it holds validator withdrawal keys or user wallets.

## Severity and evidence

Assess severity using realistic reachability, required privileges, attacker cost, and demonstrated impact. Remote code execution, disclosure of secrets, and exploitable consensus violations deserve the highest attention. Distinguish a single-node outage from a demonstrated network-wide consensus or liveness failure.

For denial of service, quantify input size and attacker effort against victim CPU, memory, disk, and time. Account for gas limits, transaction and peer limits, backpressure, timeouts, and cleanup. A slow test, ordinary synchronization cost, or a panic in unreachable test code does not establish a production vulnerability. Confirm debug-only failures with the release binary before assigning production impact.

Reports should include the exact revision, entry point, attacker capabilities, required configuration, root cause, expected and actual behavior, and a minimal deterministic reproducer. For consensus issues, include the relevant fork and block/transaction/state conditions. Group findings with the same root cause, and include a focused patch and regression test where practical. Follow `SECURITY.md` and send findings privately to `security@tempo.xyz`.

## Build and offline investigation

The source is at `/src`, with the Rust toolchain, LLVM, Cargo dependency caches, native build tools, and build outputs retained. `target/release/reth` uses the node's default features, including JIT, JavaScript tracing, and jemalloc. Release builds retain debug information and frame pointers; LTO is disabled to reduce build resource requirements. Cargo is configured for offline operation with four build jobs; lower `CARGO_BUILD_JOBS` if the analysis VM needs it.

Rebuild the node after a change with:

```sh
cargo build --locked --release --bin reth
```

The following unit-test targets are precompiled and can run without external services:

```sh
cargo test --locked --release --lib \
  -p reth-eth-wire -p reth-ecies -p reth-trie-common -p reth-ethereum-consensus
```

Other workspace crates can be tested with `cargo test --locked --release -p <package>`. Test selection above does not restrict audit scope. Some integration suites require external execution fixtures, other binaries, a consensus client, or additional services that are not installed by this image; inspect each suite's prerequisites before running it. Read `crates/e2e-test-utils/README.md` before adding node integration tests. Use isolated temporary databases and local development networks; do not connect reproducers to public networks.
