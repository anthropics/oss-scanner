# Threat model: Solidus Protocol

## What this project is and where untrusted input enters
A Rust workspace (21 crates) for a layer-1 blockchain: HotStuff-style BFT consensus, a RocksDB state store, a
libp2p network layer and a JSON-RPC server. Two generations share the workspace: the original crates
(`solidus-node`, `solidus-consensus`, `solidus-p2p`, `solidus-rpc`, `solidus-state`, `solidus-txns`) and the
v2 crates (`solidus-noded`, `solidus-node2`, `solidus-hotstuff2`, `solidus-p2p2`, `solidus-rpc2`,
`solidus-exec`, `solidus-mempool-dag`, `solidus-store2`, `solidus-state-tree`, `solidus-bridge-codec`,
`solidus-evm`). Review both. Treat as adversarial:
- Every byte from a libp2p peer: gossipsub messages, request-response (CBOR) payloads, block-range and sync replies, handshake data.
- Every JSON-RPC request, in particular `solidus_sendTransaction`, `solidus_submitTransaction`, `solidus_bbsVerifyProof`,
  `solidus_bbsVerifyCredentialProof`, `solidus_getStateProof`, the bridge methods (`solidus_getBridgeMessages`,
  `solidus_getBridgeAttestation`) and `faucet_drip`. Assume the RPC port is reachable by anyone.
- Transaction bytes (binary v2 wire format, `docs/v2-wire-format.md`), signatures, quorum certificates, timeout
  certificates and BBS+ proofs, before and after verification.
- A validator in the committee may be Byzantine. Safety must hold with fewer than one third faulty validators.
Trusted: the local operator, the config file, the genesis file and the local filesystem.

## Components that matter most / least
Most: `solidus-hotstuff2`, `solidus-consensus`, `solidus-p2p2`, `solidus-p2p`, `solidus-exec`, `solidus-txns`,
`solidus-crypto`, `solidus-bridge-codec`, `solidus-rpc2`, `solidus-rpc`, `solidus-state-tree`, `solidus-store2`,
`solidus-mempool-dag`, `solidus-noded` (keygen, config generation, faucet).
Medium: `solidus-evm` (scaffold with identity precompiles), `solidus-node2`, `solidus-client` (a malicious server answering a client).
Least: `solidus-vectors` (conformance fixtures), the load harness in `solidus-node2`, tests, `docs/`, the TLA+ models.

## How to exercise it
- `cargo test --workspace --offline`: several hundred tests. One test target does not compile in this repository layout:
  `crates/solidus-hotstuff2/tests/pop_committee.rs` reads a fixture from outside the repository. Run that crate's other
  targets with `cargo test -p solidus-hotstuff2 --lib --test block_map_is_bounded --test block_pacing --test four_node --test header_layout_frozen --test header_size --test resume_view_sync`, or skip the crate with `--exclude solidus-hotstuff2`. Tests that open RocksDB can fail when run in parallel; rerun the
  single crate with `-- --test-threads=1` before reporting. Everything is already compiled in this image.
- `docs/v2-validator-join.md` is a rehearsed runbook for a local four-validator devnet (keygen, config, run, faucet transfer).
  `target/debug/solidus-noded` has `run`, `keygen` and `faucet` subcommands. Use a local devnet for reproducers, never a public endpoint.
- `crates/solidus-vectors` and `docs/v2-wire-format.md` give valid and invalid encodings to start from.
- `docs/v2-audit-readiness.md` lists, per component, what is most worth reading first.

## How we rate severity
- Critical: two conflicting blocks finalised, or a consensus stall, by a single unauthenticated peer or by fewer than
  one third faulty validators. Accepting a forged signature, quorum certificate or state proof. Honest nodes reaching different
  state roots from the same valid input. Spending or minting funds without a valid signature. Remote code execution. Disclosure of a validator key.
- High: a crash, panic, abort, hang or unbounded memory or disk growth of a validator or RPC server caused by one
  unauthenticated peer or one RPC caller (for a BFT network, availability is part of safety). Bypass of nonce, replay, fee or
  stake rules. BBS+ proof acceptance or malleability that differs from the IRTF BBS draft.
- Medium: denial of service that needs many peers or large resources. Wrong answers from read-only RPC methods. Secret
  material written with loose permissions by `keygen`. Faucet limit bypass. A non-constant-time comparison of secret data.
- Low: problems that need local file or shell access, or panics on malformed local config.

## Reports and patches
Give a reproducer that runs against a local devnet or as a `cargo test`. A minimal patch that fixes the root cause is
better than a refactor. One report per root cause.

## Anything to leave alone
- `unwrap` or `expect` in tests, build scripts and the CLI paths that read local files, unless network input can reach them.
- Code behind the `test-activation-schedule` feature: it is for the local test harness, and a binary built with it refuses to start.
- Benchmark numbers and performance claims. Dependency CVEs with no reachable call path from the inputs listed above.
