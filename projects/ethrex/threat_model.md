# Threat model: ethrex

## What this project does and where untrusted input enters

ethrex is an Ethereum execution client written in Rust. It also includes an L2 sequencer, prover integration, and bridge/prover contracts. Correct state transitions, consensus compatibility, availability, and protection of validator, operator, and bridge funds are security properties.

Treat these inputs as attacker-controlled:

- Discovery packets, RLPx sessions, `eth` and `snap` messages, transactions, blocks, receipts, state nodes, and other data supplied by remote peers.
- Transaction bytecode and calldata, contract execution results, block headers, withdrawals, blobs, and all serialized RLP or SSZ data.
- JSON-RPC and WebSocket requests whenever an operator exposes those interfaces. Distinguish loopback-only, public, and authenticated deployments.
- Engine API requests. This interface is intended for an authenticated consensus client; a bypass of JWT or other access control is in scope.
- L1 contract calldata and events, L2 transactions and batches, sequencer/admin requests, proof coordinator messages, and prover outputs. Identify the privileges and configuration needed to reach each path.
- Snapshot, genesis, import/export, and database data when an attacker can supply a file or influence persisted state.

## Components that matter most

- `crates/blockchain`, `crates/vm`, and `crates/vm/levm`: block validation, execution, gas accounting, state access, payload building, and consensus rules. Look for acceptance of invalid blocks, rejection of valid blocks, divergent state or receipt roots, and inconsistencies between LEVM and REVM or between clients.
- `crates/networking/p2p`: discovery, RLPx, protocol decoding, sync, peer management, and request/response handling. Prioritize pre-authentication crashes, memory or CPU exhaustion, decompression bombs, and validation gaps reachable by a remote peer.
- `crates/networking/rpc`: public JSON-RPC, WebSocket, and authenticated Engine API handlers. Check authentication, method exposure, input bounds, transaction validation, and accidental disclosure or state changes.
- `crates/common`, especially RLP, trie, crypto, and SSZ users: canonical decoding, bounds checking, hashing, and consensus-critical data structures.
- `crates/storage`: persistent state integrity, recovery, snapshot/import paths, and corruption caused by malformed input or interrupted operations.
- `crates/l2` and `cmd/ethrex/l2`: sequencer authorization, batch commitment, bridge deposits and withdrawals, message inclusion, proof verification, upgrade controls, replay protection, and L1/L2 RPC handlers. Solidity contracts under `crates/l2/contracts` are in scope.

Review dependencies when ethrex makes a flaw reachable; show the call path and name the crate that needs the fix. Test-only utilities, benchmarks, release tooling, and local developer conveniences are lower priority unless they cross a real trust boundary.

## Severity guidance

Assess severity from realistic reachability, attacker cost, required configuration, and impact. Do not equate a panic in a test or a performance regression with a vulnerability.

- **Critical:** demonstrated loss or theft of user/bridge funds; finalization of an invalid L2 state or withdrawal; remote code execution; or an unauthenticated Engine API bypass that gives an attacker block-production or state-transition control.
- **High:** acceptance of consensus-invalid data or rejection of valid data with a credible chain-impact path; a remote unauthenticated crash, persistent database corruption, or cheap unbounded resource exhaustion; bypass of L2 sequencer, proof, bridge, or upgrade authorization; disclosure of private keys or JWT secrets.
- **Medium:** bounded denial of service, failures confined to an authenticated or explicitly non-default interface, and validation or RPC correctness defects with limited downstream impact. Escalate when the same defect can affect consensus or many nodes.
- **Low:** issues requiring a malicious local configuration or an already-compromised host, non-sensitive diagnostic inaccuracies, and hardening gaps without a demonstrated attack.

For resource-exhaustion reports, measure input size and attacker cost against victim CPU, memory, disk, or wall time. Protocol gas limits, peer limits, and ordinary sync cost are not vulnerabilities by themselves. Distinguish one-node denial of service from a demonstrated network-wide consensus failure.

## How to exercise it offline

The checkout is `/src`; Cargo dependencies, Git dependencies, build outputs, test binaries, and `solc` are already installed. `CARGO_NET_OFFLINE=true` is set. The client was built with `l2,l2-sql` in the `release-fast` profile and is at `target/release-fast/ethrex`.

The standard L1 suite, including RocksDB-gated tests, is precompiled:

```sh
cargo test --locked --profile release-fast --workspace --features rocksdb \
  --exclude 'ethrex-l2*' --exclude ethrex-prover --exclude ethrex-guest-program
```

Useful narrower commands include:

```sh
cargo test --locked --profile release-fast -p ethrex-levm
cargo test --locked --profile release-fast -p ethrex-rlp
cargo test --locked --profile release-fast -p ethrex-trie
cargo test --locked --profile release-fast -p ethrex-p2p
cargo test --locked --profile release-fast -p ethrex-rpc
cargo test --locked --profile release-fast -p ethrex-l2 --lib native_rollup
```

`target/release-fast/ethrex --dev --datadir memory` starts a local development node without a public-network sync. Use private local networks and loopback RPC for reproducers. The image does not include a running consensus client, an L1/L2 devnet, proving services, or public network access. Some Hive, execution-spec, external-fixture, and L2 integration suites need additional services or downloads; identify missing prerequisites rather than reporting them as client vulnerabilities.

## Reporting and exclusions

Provide the affected revision, attacker position, required interfaces and configuration, root cause, expected versus actual behavior, and a minimal deterministic reproducer that runs offline. For consensus bugs, include the block, transaction, state, or fork conditions and compare against the protocol rules or another implementation where useful. Include a minimal patch and regression test where practical, and group duplicate reports with the same root cause.

Do not report public blockchain data being public, ordinary resource use within protocol limits, a malicious local config file with no additional trust-boundary crossing, or a dependency issue with no reachable ethrex path. Do not contact public peers or live networks.

Report findings privately to `security@lambdaclass.com` and follow `.github/SECURITY.md`. Do not open public issues or publish unpatched vulnerability details.
