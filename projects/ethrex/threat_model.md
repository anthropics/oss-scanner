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
- **Consensus client:** only its intended chain-control powers are trusted after Engine API JWT authentication. Malformed requests, body-budget bypasses, timeouts, resource exhaustion, and state-integrity failures remain in scope even when the caller is correctly authenticated. An authentication bypass or an unauthenticated request reaching the same powers is also in scope.
- **Operator configuration and L1 RPC endpoint:** the operator's local configuration and chosen L1 RPC endpoint are trusted. Do not model a deliberately malicious config file or endpoint as an attack by itself. On-chain calldata, events, and contract inputs supplied by other parties remain untrusted.
- **Provers and settlement modes:** in proof-required deployments, provers are not trusted for correctness; a false state requires a valid proof of an invalid guest-program transition or a separate L1 verification/authorization failure. Settlement currently recognizes Exec, RISC0, SP1, and TDX. Exec is an intentional no-proof mode whose verification always succeeds, so its execution trust and lack of a proof are design assumptions rather than vulnerabilities. TDX uses attestation and registered-signer trust, not a zero-knowledge validity proof. A reachable proof coordinator that stores or submits invalid proofs can suffer verification delays; assess remote prover attacks only when the deployment exposes them.
- **TDX setup:** the proof coordinator binds loopback by default, but a reachable `ProverSetup` is a privileged boundary. It processes quote material, invokes registration, and sends an L1 transaction funded and signed by the coordinator's TDX key. `TDXVerifier.register` requires the caller to be a sequencer, validates the quote and report outside dev mode, and changes the authorized signer. Review listener exposure, quote/report and measurement validation, L1 spending authority, and signer-registration authorization. `isDevMode` deliberately skips quote verification and is not itself a finding; unauthorized setup, spending, or registration outside those intentional development settings is in scope.
- **Sponsor account:** `ethrex_sendTransaction` uses the sponsor key to sign and pay gas for permitted sponsored calls. The built-in default sponsor private key is public and must be treated as development-only; operators must set `SPONSOR_PRIVATE_KEY` for a real deployment. Loss of funds controlled by the known default key is not a finding. Disclosure of an operator-supplied key, bypass of sponsorable-address checks, or evasion of the sponsored gas limit is in scope.

## Audit scope

Audit the entire checkout, including L1 and L2 modes, optional features, production components, supporting tools, import/export paths, and build/test infrastructure. The priorities below guide investigation rather than excluding directories. For optional features and supporting tools, state the feature, privileges, and deployment that make an attack reachable.

## Components that matter most

- `crates/blockchain`, `crates/vm`, and `crates/vm/levm`: block validation, execution isolation, gas accounting, state access, payload building, and consensus rules. Look for acceptance of invalid blocks, rejection of valid blocks, and divergent state or receipt roots, using the official execution-spec fixtures as the offline oracle.
- `crates/vm/levm/src/precompiles.rs` and `crates/vm/levm/src/execute_precompile.rs`: precompile input parsing, gas accounting, edge cases, and cross-fork behavior. Precompile discrepancies can cause consensus splits.
- `crates/blockchain/mempool.rs` and `crates/networking/rpc/mempool.rs`: transaction admission, nonce handling, eviction, and per-sender/global resource limits. Prioritize cheap memory, CPU, and validation-work exhaustion.
- `crates/networking/p2p`: discovery, RLPx, protocol decoding, sync, peer management, and request/response handling. Prioritize pre-authentication crashes, hangs, resource leaks, decompression bombs, and validation gaps reachable by a remote peer.
- `crates/networking/rpc`: public JSON-RPC, WebSocket, metrics, and authenticated Engine API handlers. Check authentication, method exposure, input bounds, transaction validation, and accidental disclosure or state changes. Record the transport, enabled namespaces, authentication, and bind configuration needed to reach a handler.
- `crates/common`, especially RLP, trie, crypto, and SSZ users: canonical decoding, bounds checking, hashing, and consensus-critical data structures.
- `crates/storage` and filesystem/import boundaries: persistent state integrity, recovery, path handling, snapshot/archive extraction, unsafe/native interop, and corruption caused by malformed input or interrupted operations. Name the feature and filesystem privileges required for a path to be reachable.
- `crates/guest-program`: the highest-priority L2 correctness component in proof-required deployments. The program can execute under SP1, RISC0, ZisK, and OpenVM; current settlement recognizes Exec, RISC0, SP1, and TDX, so do not assume that every execution backend is an implemented L1 proof path. Review initial/final state-root checks, block and witness validation, message and withdrawal commitments, blob/data-availability checks, and deterministic outputs. In proof-required deployments, a malicious sequencer or prover must not be able to turn an invalid transition into an L1-finalized state.
- `crates/l2` and `cmd/ethrex/l2`: sequencer authorization, batch commitment, bridge deposits and withdrawals, message inclusion, proof verification, upgrade controls, replay protection, and L1/L2 RPC handlers. Solidity contracts under `crates/l2/contracts` are in scope.

Review dependencies when ethrex makes a flaw reachable; show the call path and name the crate that needs the fix. Test-only utilities, benchmarks, release tooling, and local developer conveniences are lower priority but are not automatically excluded when they cross a real trust boundary.

## Severity guidance

Assess severity from realistic reachability, attacker cost, required configuration, and impact. Do not equate a panic in a test or a performance regression with a vulnerability.

- **Critical:** demonstrated loss or theft of user/bridge funds; finalization of an invalid L2 state or withdrawal in a proof-required deployment, including through a guest-program validation error; remote code execution; or an unauthenticated Engine API bypass that gives an attacker block-production or state-transition control.
- **High:** acceptance of consensus-invalid data or rejection of valid data with a credible chain-impact path; a remote unauthenticated crash or hang, persistent database corruption or resource leak, or cheap unbounded resource exhaustion; bypass of L2 sequencer, proof, bridge, upgrade, or TDX signer-registration authorization; unauthorized L1 spending; disclosure of private keys or JWT secrets. A single unauthenticated JSON-RPC request that crashes a node is High whenever the listener is reachable by untrusted users, as on an L2 or a public RPC deployment.
- **Medium:** bounded denial of service, failures confined to loopback-only or authenticated interfaces without a broader impact, and validation or RPC correctness defects with limited downstream impact. In proof-required deployments, invalid prover output that temporarily delays batch verification is normally Medium; escalate a demonstrated cheap, sustained finalization delay to High. Invalid proofs alone cannot create a Critical state-validity impact without a separate guest-program or L1 verification failure.
- **Low:** issues requiring a malicious local configuration or an already-compromised host, non-sensitive diagnostic inaccuracies, and hardening gaps without a demonstrated attack.

For resource-exhaustion reports, measure input size and attacker cost against victim CPU, memory, disk, or wall time. Account for gas accounting, peer scoring and penalties, RPC work budgets, backpressure, and resource cleanup on disconnect when assessing whether input is cheap or resource use is unbounded. Protocol limits and ordinary sync cost are not vulnerabilities by themselves. Distinguish one-node denial of service from a demonstrated network-wide consensus failure.

The client and all prebuilt test targets use the production `release` profile and a shared Cargo target directory. If additional debug or assertion-enabled test variants are built during analysis, confirm any panic or arithmetic discrepancy against `target/release/ethrex` before assigning production severity. A debug-assertion-only crash is not a High production denial of service.

## How to exercise it offline

The checkout is `/src`; root and `tooling/` Cargo dependencies, build outputs, test binaries, official execution-spec fixtures, `solc`, and commit-pinned contract dependencies are installed. `CARGO_NET_OFFLINE=true` is set, and child Git operations for contract dependencies resolve only to the vendored checkouts. The production client is at `target/release/ethrex` and was built with `l2,l2-sql`.

After editing Solidity sources, rebuild them and the client with no network access:

```sh
cargo build --locked --profile release --bin ethrex --features l2,l2-sql
```

The full L1 suite can run offline and will compile any test targets not already built on its first run:

```sh
cargo test --locked --profile release --workspace --features rocksdb \
  --exclude 'ethrex-l2*' --exclude ethrex-prover --exclude ethrex-guest-program
```

The guest program needs no zkVM toolchain for its native tests. Those tests, the L2 library tests, and the execution-spec blockchain runner are prebuilt with the same production profile and target directory:

```sh
cargo test --locked --profile release -p ethrex-guest-program --no-default-features
cargo test --locked --profile release -p ethrex-l2 --lib native_rollup
cargo test --locked --profile release --manifest-path tooling/Cargo.toml -p ef_tests-blockchain
cargo test --locked --profile release --manifest-path tooling/Cargo.toml -p ef_tests-blockchain --features stateless
```

Other useful narrower commands include:

```sh
cargo test --locked --profile release -p ethrex-levm
cargo test --locked --profile release -p ethrex-rlp
cargo test --locked --profile release -p ethrex-trie
cargo test --locked --profile release -p ethrex-p2p
cargo test --locked --profile release -p ethrex-rpc
```

`target/release/ethrex --dev --datadir memory` starts a local development node without a public-network sync. Use private local networks and loopback RPC for reproducers. The image does not include a running consensus client, an L1/L2 devnet, proving services, or public network access. Hive and L2 integration suites need additional services; identify missing prerequisites rather than reporting them as client vulnerabilities. Consult `docs/known_issues.md` for intentionally skipped execution-spec cases.

## Reproducers and exclusions

Provide the affected revision, attacker position, required interfaces and configuration, root cause, expected versus actual behavior, and a minimal deterministic reproducer that runs offline. For consensus bugs, include the block, transaction, state, or fork conditions and compare against the protocol rules and pinned execution-spec expectations. Include a minimal patch and regression test where practical, and group duplicate reports with the same root cause.

Do not report public blockchain data being public, ordinary resource use within protocol limits, a malicious local config file with no additional trust-boundary crossing, or a dependency issue with no reachable ethrex path.
