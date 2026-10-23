# Threat model: ethlambda

## What this project does and where untrusted input enters

ethlambda is a Rust Ethereum consensus client with two modes:

- `ethlambda node` participates in Lean Ethereum consensus, including fork choice, block production, attestations, aggregation, and validator signing.
- `ethlambda beacon` follows the Ethereum Beacon Chain from a checkpoint, validates consensus objects, custodies and serves data columns, and can ask an execution client to validate payloads through Engine API. It has no validator duties.

Consensus correctness, signature verification, validator key safety, data availability, and node availability are security properties. Account for the current deployment and spec version; distinguish Lean devnet impact from Beacon Chain impact.

Treat these inputs as attacker-controlled:

- libp2p QUIC and TCP connections, Noise/yamux streams, gossipsub messages, discovery packets and ENRs, STATUS messages, block/attestation gossip, and req/resp or range-sync responses.
- SSZ containers, signatures, checkpoints, blocks, attestations, data columns, proofs, fork-choice messages, and state-diff data supplied by peers or checkpoint/sync providers.
- Beacon API and other HTTP/RPC requests when the corresponding listener is exposed.
- Engine API responses and execution-payload status returned by the configured execution client. Engine API credentials and endpoint configuration are operator-controlled, but parsing and validation of the response remains in scope.
- Genesis, validator registry, network, and state files when an attacker can supply them. A deliberately malicious local configuration alone is not a vulnerability.

For checkpoint sync, state exactly which values are cryptographically verified and which rely on the operator's checkpoint provider. Do not assume that every checkpoint-sync response is trustworthy, or that the documented weak-subjectivity trust assumption is itself a bug.

## Components that matter most

- `crates/blockchain/state_transition`: Lean and Beacon consensus rules, epoch and block processing, signature verification, and fork-specific behavior. Prioritize acceptance of invalid transitions and rejection of valid ones.
- `crates/blockchain/fork_choice` and `crates/blockchain`: head selection, finalization, pending blocks, reorgs, and interaction between gossip and sync.
- `crates/validator`: validator assignment, block and attestation production, aggregation, key use, and slashing protection. Remote input that causes unauthorized or slashable signing is especially important.
- `crates/net/p2p`: discovery, libp2p protocols, gossip validation, request/response decoding, sync, peer scoring, and resource limits. Prioritize pre-authentication crashes, amplification, and cheap memory, CPU, disk, or task exhaustion.
- `crates/net/api` and `crates/net/rpc`: Beacon API and other request handlers, including input bounds, correctness, accidental state changes, and sensitive-data exposure.
- `crates/net/engine`: JWT handling, Engine API requests/responses, and the decision to accept, reject, or optimistically import a payload.
- `crates/common/crypto`, `crates/common/types`, and `crates/common/ssz-tree`: XMSS and aggregate-signature verification, canonical SSZ, hash-tree roots, and consensus types. A flaw in libssz or leanVM that is reachable here is in scope; identify the upstream crate that needs the patch.
- `crates/storage`: persistent chain state, state-diff reconstruction, recovery, and corruption caused by malformed or interrupted writes.

Test fixtures, benchmarks, docs, devnet orchestration, and Shadow simulation support are lower priority unless they are used in a production path. Review third-party code only with a demonstrated reachable path from ethlambda.

## Severity guidance

Use realistic reachability, privileges, spec limits, attacker cost, and impact. A failure in a test helper or a performance regression alone is not a vulnerability.

- **Critical:** remote code execution; validator key theft or unauthorized signing with a credible slashing/loss path; signature-verification bypass; or finalization of a demonstrably invalid chain state.
- **High:** consensus divergence or fork-choice manipulation with a credible chain-impact path; acceptance of invalid blocks, attestations, data columns, or checkpoint data; a remote unauthenticated crash, persistent database corruption, or cheap unbounded resource exhaustion; Engine API or operator authorization bypass.
- **Medium:** bounded denial of service, a failure confined to an optional/authenticated interface, incorrect API or serving behavior with limited security impact, and attacks needing a malicious execution endpoint without a broader trust-boundary violation. Escalate if the same root cause affects many nodes or consensus safety.
- **Low:** issues requiring a malicious local config or compromised host, non-sensitive metrics/diagnostic inaccuracies, and hardening opportunities without a demonstrated attack.

For denial of service, quantify the input and attacker cost against CPU, memory, disk, bandwidth, or wall time. Ordinary processing of protocol-valid objects and generic network flooding are not enough. Distinguish a single-node outage from a viable network-wide attack.

## How to exercise it offline

The source is at `/src`; all Cargo and Git dependencies, leanSpec fixtures, and `release-fast` build/test outputs are installed. `CARGO_NET_OFFLINE=true` is set. Use the `release-fast` profile: the repository notes that signature verification and aggregation can stack-overflow in an unoptimized dev build.

Run the two standard test halves separately to limit disk and memory pressure:

```sh
make test-consensus
make test-node
```

Additional useful checks are:

```sh
cargo test --locked --profile release-fast -p ethlambda-types --lib --features preset-minimal
cargo test --locked --profile release-fast -p ethlambda-state-transition --lib --features preset-minimal
cargo test --locked --manifest-path tooling/event-monitor/Cargo.toml
cargo test --locked --profile release-fast -p ethlambda-p2p
cargo test --locked --profile release-fast -p ethlambda-state-transition
```

The binary is `target/release-fast/ethlambda`. An offline end-to-end smoke test is:

```sh
target/release-fast/ethlambda benchmark synthetic --mock-crypto \
  --num-validators 4 --warmup-slots 4 --iterations 3 --format json
```

The multi-gigabyte Beacon Chain spec fixtures are not included; do not enable `beacon-spec-tests` without provisioning them during the image build. There is no running execution client, checkpoint provider, Lean devnet, or public network access. `lean-quickstart` and external interoperability suites require separate setup.

The Beacon Chain follower intentionally imports execution payloads without execution validation when no execution endpoint is configured; this is documented behavior, not a finding. Its lack of validator duties is also intentional. Metrics endpoints are intended for trusted networks unless a separate exposure or privilege issue is demonstrated.

## Reporting and exclusions

Provide the affected revision, node mode, attacker position, network/preset and configuration, root cause, expected versus actual behavior, and a minimal deterministic offline reproducer. For consensus findings, include the relevant fork, slot/epoch, signed objects, and reference to the protocol rules. For resource findings, include measurements. Propose a minimal patch and regression test where practical, and group duplicate reports with the same root cause.

Do not report public chain data being public, generic P2P traffic floods, a malicious local configuration without another trust-boundary crossing, or a dependency issue with no reachable ethlambda path. Do not contact public peers or live networks.

Report findings privately to `security@lambdaclass.com` and follow `.github/SECURITY.md`. Do not open public issues or publish unpatched vulnerability details.
