# Threat model: ethrex

## What this project does and where untrusted input enters

ethrex is an Ethereum execution client written in Rust. It also includes an L2 sequencer, prover integration, and bridge/prover contracts. Correct state transitions, consensus compatibility, availability, and protection of user, operator, and bridge funds are security properties.

Treat these inputs as attacker-controlled:

- Discovery packets, RLPx sessions, `eth` and `snap` messages, transactions, blocks, receipts, state nodes, and other data supplied by remote peers.
- Transaction bytecode and calldata, contract execution results, block headers, withdrawals, blobs, and all serialized RLP or SSZ data.
- JSON-RPC and WebSocket requests whenever an operator exposes those interfaces. L2 nodes and RPC providers commonly expose them to untrusted users; distinguish that exposure from loopback-only deployments.
- Engine API requests. This interface is intended for an authenticated consensus client; a bypass of JWT or other access control is in scope.
- Metrics requests when `--metrics` is enabled. Metrics are disabled by default, but their default bind address is `0.0.0.0`.
- L1 contract calldata and events, L2 transactions and batches, sequencer/admin requests, proof coordinator messages, and prover outputs. State the listener and deployment needed to reach each path.
- Snapshot, genesis, import/export, and database data when an attacker can supply a file or influence persisted state.

HTTP JSON-RPC, Engine API, and the proof coordinator bind `127.0.0.1` by default. Evaluate the actual deployed exposure rather than assuming either that an interface is public by default or that a non-default bind makes a finding low severity.

## Trusted roles and intended powers

The following roles and powers are part of the design. Their documented use is not a finding by itself. A bypass of a guard that is meant to constrain them, use beyond documented powers, or attacker-controlled input reaching them without the required trust boundary remains in scope.

- **L2 sequencer:** it can order, reorder, include, or censor transactions. Forced inclusion is the documented mitigation for censorship of privileged transactions. Do not report sequencing discretion alone; do report a bypass of forced-inclusion deadlines or other inclusion guarantees.
- **Governance, Timelock, and Security Council:** these roles can upgrade the OnChainProposer and bridge contracts through their documented paths. The Security Council can also use `emergencyExecute` and `revertBatch`. Unauthorized upgrades, role bypasses, missing timelock/authorization checks, and powers beyond those documented are in scope; exercising these intended powers is not.
- **Validium operator:** in validium mode, transaction data is not posted to L1 and the operator is trusted to keep it available. Operator data withholding is intrinsic to that deployment model, not an implementation vulnerability. A mismatch between the documented mode and what is actually committed or verified is in scope.
- **Consensus client:** it is trusted after passing Engine API JWT authentication. A malicious but correctly authenticated consensus client is outside the threat model; an authentication bypass or an unauthenticated request reaching the same powers is in scope.
- **Operator configuration and L1 RPC endpoint:** the operator's local configuration and chosen L1 RPC endpoint are trusted. Do not model a deliberately malicious config file or endpoint as an attack by itself. On-chain calldata, events, and contract inputs supplied by other parties remain untrusted.
- **Provers:** provers are not trusted for correctness. A false state cannot be finalized without a valid proof of the guest program, but a reachable proof coordinator that stores or submits invalid proofs can suffer verification delays. The coordinator binds loopback by default; assess remote prover attacks only when the deployment exposes them.
- **Sponsor account:** `ethrex_sendTransaction` uses the sponsor key to sign and pay gas for permitted sponsored calls. The built-in default sponsor private key is public and must be treated as development-only; operators must set `SPONSOR_PRIVATE_KEY` for a real deployment. Loss of funds controlled by the known default key is not a finding. Disclosure of an operator-supplied key, bypass of sponsorable-address checks, or evasion of the sponsored gas limit is in scope.

## Components that matter most

- `crates/blockchain`, `crates/vm`, and `crates/vm/levm`: block validation, execution, gas accounting, state access, payload building, and consensus rules. Look for acceptance of invalid blocks, rejection of valid blocks, and divergent state or receipt roots, using the official execution-spec fixtures as the offline oracle.
- `crates/vm/levm/src/precompiles.rs` and `crates/vm/levm/src/execute_precompile.rs`: precompile input parsing, gas accounting, edge cases, and cross-fork behavior. Precompile discrepancies can cause consensus splits.
- `crates/blockchain/mempool.rs` and `crates/networking/rpc/mempool.rs`: transaction admission, nonce handling, eviction, and per-sender/global resource limits. Prioritize cheap memory, CPU, and validation-work exhaustion.
- `crates/networking/p2p`: discovery, RLPx, protocol decoding, sync, peer management, and request/response handling. Prioritize pre-authentication crashes, resource exhaustion, decompression bombs, and validation gaps reachable by a remote peer.
- `crates/networking/rpc`: public JSON-RPC, WebSocket, metrics, and authenticated Engine API handlers. Check authentication, method exposure, input bounds, transaction validation, and accidental disclosure or state changes.
- `crates/common`, especially RLP, trie, crypto, and SSZ users: canonical decoding, bounds checking, hashing, and consensus-critical data structures.
- `crates/storage`: persistent state integrity, recovery, snapshot/import paths, and corruption caused by malformed input or interrupted operations.
- `crates/guest-program`: the highest-priority L2 correctness component. This is the program whose execution SP1, RISC0, ZisK, and OpenVM prove; L1 accepts an L2 state transition only when the corresponding proof verifies. Review initial/final state-root checks, block and witness validation, message and withdrawal commitments, blob/data-availability checks, and deterministic outputs. A malicious sequencer or prover must not be able to turn an invalid transition into an L1-finalized state.
- `crates/l2` and `cmd/ethrex/l2`: sequencer authorization, batch commitment, bridge deposits and withdrawals, message inclusion, proof verification, upgrade controls, replay protection, and L1/L2 RPC handlers. Solidity contracts under `crates/l2/contracts` are in scope.

Review dependencies when ethrex makes a flaw reachable; show the call path and name the crate that needs the fix. Test-only utilities, benchmarks, release tooling, and local developer conveniences are lower priority unless they cross a real trust boundary.

## Severity guidance

Assess severity from realistic reachability, attacker cost, required configuration, and impact. Do not equate a panic in a test or a performance regression with a vulnerability.

- **Critical:** demonstrated loss or theft of user/bridge funds; finalization of an invalid L2 state or withdrawal, including through a guest-program validation error; remote code execution; or an unauthenticated Engine API bypass that gives an attacker block-production or state-transition control.
- **High:** acceptance of consensus-invalid data or rejection of valid data with a credible chain-impact path; a remote unauthenticated crash, persistent database corruption, or cheap unbounded resource exhaustion; bypass of L2 sequencer, proof, bridge, or upgrade authorization; disclosure of private keys or JWT secrets. A single unauthenticated JSON-RPC request that crashes a node is High whenever the listener is reachable by untrusted users, as on an L2 or a public RPC deployment.
- **Medium:** bounded denial of service, failures confined to loopback-only or authenticated interfaces without a broader impact, and validation or RPC correctness defects with limited downstream impact. Invalid prover output that temporarily delays batch verification is normally Medium; escalate a demonstrated cheap, sustained finalization delay to High. Invalid proofs alone cannot create a Critical state-validity impact without a separate guest-program or L1 verification failure.
- **Low:** issues requiring a malicious local configuration or an already-compromised host, non-sensitive diagnostic inaccuracies, and hardening gaps without a demonstrated attack.

For resource-exhaustion reports, measure input size and attacker cost against victim CPU, memory, disk, or wall time. Protocol gas limits, peer limits, and ordinary sync cost are not vulnerabilities by themselves. Distinguish one-node denial of service from a demonstrated network-wide consensus failure.

The production binary uses the `release` profile. Test binaries use `release-fast`, which can include assertions that are not present in production. Before assigning a production severity to a panic or arithmetic discrepancy, verify it against `target/release/ethrex` or against source with the extra assertions compiled out. A debug-assertion-only crash is not a High production denial of service.

## How to exercise it offline

The checkout is `/src`; root and `tooling/` Cargo dependencies, build outputs, test binaries, official execution-spec fixtures, and `solc` are installed. `CARGO_NET_OFFLINE=true` is set. The production client is at `target/release/ethrex` and was built with `l2,l2-sql`.

The standard L1 suite, including RocksDB-gated tests, is precompiled:

```sh
cargo test --locked --profile release-fast --workspace --features rocksdb \
  --exclude 'ethrex-l2*' --exclude ethrex-prover --exclude ethrex-guest-program
```

The guest program needs no zkVM toolchain for its native tests. Run those separately, together with the execution-spec blockchain runner and its regular and stateless fixture sets:

```sh
cargo test --locked --profile release-fast -p ethrex-guest-program --no-default-features
cargo test --locked --profile release-fast --manifest-path tooling/Cargo.toml -p ef_tests-blockchain
cargo test --locked --profile release-fast --manifest-path tooling/Cargo.toml -p ef_tests-blockchain --features stateless
```

Other useful narrower commands include:

```sh
cargo test --locked --profile release-fast -p ethrex-levm
cargo test --locked --profile release-fast -p ethrex-rlp
cargo test --locked --profile release-fast -p ethrex-trie
cargo test --locked --profile release-fast -p ethrex-p2p
cargo test --locked --profile release-fast -p ethrex-rpc
cargo test --locked --profile release-fast -p ethrex-l2 --lib native_rollup
```

`target/release/ethrex --dev --datadir memory` starts a local development node without a public-network sync. Use private local networks and loopback RPC for reproducers. The image does not include a running consensus client, an L1/L2 devnet, proving services, or public network access. Hive and L2 integration suites need additional services; identify missing prerequisites rather than reporting them as client vulnerabilities. Consult `docs/known_issues.md` for intentionally skipped execution-spec cases.

## Reproducers and exclusions

Provide the affected revision, attacker position, required interfaces and configuration, root cause, expected versus actual behavior, and a minimal deterministic reproducer that runs offline. For consensus bugs, include the block, transaction, state, or fork conditions and compare against the protocol rules and pinned execution-spec expectations. Include a minimal patch and regression test where practical, and group duplicate reports with the same root cause.

Do not report public blockchain data being public, ordinary resource use within protocol limits, a malicious local config file with no additional trust-boundary crossing, or a dependency issue with no reachable ethrex path.
