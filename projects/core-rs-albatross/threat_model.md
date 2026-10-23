# Threat model: Nimiq core-rs-albatross

## What this project does and where untrusted input enters

core-rs-albatross is the reference node for the Nimiq Proof-of-Stake blockchain (the Albatross protocol). Mainnet runs on it, and NIM held on that chain has real value. One binary, `nimiq-client`, runs as a full node, a history node (full plus all transaction history), a light node, or a validator. `web-client/` compiles the light client to WebAssembly so it runs in browsers. The scanned branch is `albatross`, which is the released line.

The security model rests on a few rules. The chain is valid only if every block, transaction and state transition passes the consensus rules. Validators are trusted only as a group: the protocol stays safe and live while less than 1/3 of the validator slots are Byzantine. Peers, the data they send, and all network addresses are untrusted. Light clients trust nothing they cannot check against signed macro blocks and Merkle or trie proofs.

Treat all of the following as attacker-controlled.

**From any peer on the P2P network (`network-libp2p/`, `consensus/`):**

- Every inbound libp2p connection, over TCP or WebSocket. This covers the noise handshake, yamux, identify, ping, autonat, the custom discovery protocol (`network-libp2p/src/discovery/`) and the Kademlia DHT (`network-libp2p/src/dht.rs`). Validator records in the DHT are signed, and a forged or replayed record must be rejected.
- Every gossipsub message: block headers and bodies, transactions, control transactions (`consensus/src/messages/mod.rs`, `primitives/transaction/src/lib.rs`). A peer can send any bytes on any topic.
- Every request and response in the request-response protocol (`consensus/src/messages/mod.rs`): macro chain, batch sets, history chunks, blocks, missing blocks, head, transaction and block proofs, receipts by address, trie proofs, and address subscriptions. Both sides are untrusted: a node handling a request, and a syncing node handling a response.
- All of these go through `nimiq-serde` (`serde/`). Length prefixes, nesting and sizes come from the attacker.

**From validators (`validator/`, `validator-network/`, `tendermint/`, `handel/`, `bls/`):**

- Tendermint proposals and votes, skip-block aggregation and Handel aggregation messages. A single malicious validator, or any peer that impersonates one, must not be able to make honest validators sign conflicting data, accept a forged aggregate signature, stall the chain, or get an honest validator jailed or slashed.
- BLS aggregate signatures and the signer bitsets that come with them. VRF seeds (`vrf/`) in blocks.
- Equivocation proofs (`primitives/block/src/equivocation_proof.rs`). A forged proof must never punish an honest validator.

**Blocks, transactions and state (`blockchain/`, `light-blockchain/`, `primitives/`, `mempool/`):**

- Every field of every micro, macro and skip block (`primitives/block/`), and the justifications that sign them.
- Every transaction, with its signature proof (`primitives/transaction/src/signature_proof.rs`: Ed25519, ES256 and WebAuthn, and multisig through the Merkle path in the proof). The same goes for the contracts in `primitives/account/src/account/`: basic accounts, vesting, HTLC and the staking contract. A transaction must never move funds its signer does not control, create or destroy NIM, or leave the accounts tree different on two honest nodes.
- State sync chunks and trie proofs (`primitives/trie/`), history proofs and MMR proofs (`primitives/mmr/`). A light or syncing node must never accept state or history that the signed chain does not commit to.
- The mempool (`mempool/`) admits transactions from any peer and from RPC. Admission, eviction and per-sender limits must hold up against a spammer.

**JSON-RPC (`rpc-server/`):**

- The server binds to 127.0.0.1 by default. Operators can expose it with HTTP basic auth (`username`/`password`), an IP allowlist (`allowip`), a method allowlist (`methods`) and CORS domains. When any of these are set, bypassing them is in scope. So is anything that reaches the HTTP or WebSocket layer before authentication.
- A client that is allowed in is trusted by design. It can unlock accounts, sign and send transactions, and control the validator. Don't report what such a client can do on purpose.

**Web client (`web-client/`):**

- Everything a web page's JavaScript passes into the WASM API: transactions and addresses parsed from hex, bytes, base64 or user-friendly strings, and plain objects. It also has the same network inputs as a light node, over WebSocket only.

## Components that matter most / least

- Most: consensus validity, meaning block and transaction verification and the account and staking state transitions (`blockchain/`, `light-blockchain/`, `primitives/account/`, `primitives/transaction/`, `primitives/block/`). Also signature and proof checks (`keys/`, `bls/`, `vrf/`, `primitives/trie/`, `primitives/mmr/`), peer message decoding and handling (`serde/`, `consensus/`, `network-libp2p/`), and the validator's aggregation logic (`validator/`, `tendermint/`, `handel/`).
- Also in scope: `mempool/`, `rpc-server/`, `web-client/`, `dht/`, `lib/` (how the node is wired together and configured), `wallet/`, `key-derivation/`, `mnemonic/`.
- Lower: `metrics-server/` (operator-facing, optionally behind basic auth) and `database/` (local MDBX storage, which we trust).
- Out of scope: `spammer/`, `test-utils/`, `test-log/`, `network-mock/`, `genesis-builder/`, `tools/` (offline CLI helpers), `scripts/`, `fuzz/` (the harnesses themselves), `.github/`, and the example configs.

## How to exercise it

- The image has every test binary built in the dev profile, so debug assertions and overflow checks are on. Run one crate's tests with `cargo nextest run -p <crate>` (for example `-p nimiq-blockchain`, `-p nimiq-account`, `-p nimiq-consensus`, `-p nimiq-network-libp2p`), or the whole workspace with `cargo nextest run`. Doc tests run with `cargo test --doc -p <crate>`. The agent has 2 CPUs, so build and test one crate at a time instead of the whole workspace.
- Some slow tests sit behind the `expensive-tests` feature: `cargo nextest run -p <crate> --features expensive-tests`.
- Binaries are in `target/debug/`: `nimiq-client`, `nimiq-rpc` (a JSON-RPC client), `nimiq-spammer` (floods a node with transactions), and the tools `nimiq-address`, `nimiq-bls`, `nimiq-mktx`, `nimiq-signtx`. `lib/src/config/config_file/client.example.toml` documents every client setting.
- A local network with four validators and a seed runs offline: `python3 scripts/devnet/devnet.py -t .github/devnet_topologies/four_validators.toml -r 1`. The genesis configs it uses are in `genesis/src/genesis/` (`dev-albatross*.toml`, and `unit-albatross.toml` for the unit tests).
- `network-libp2p/tests/` and `consensus/tests/` show how to start real libp2p nodes and sync between them inside one process. A peer that sends hand-crafted messages is the most direct way to prove a P2P bug.
- `fuzz/src/bin/` has AFL harnesses for a few `Deserialize` implementations, with seeds in `fuzz/in/`.

## How you rate severity

- **Critical:** anything an unprivileged party (any peer, any transaction sender, or a single validator) can use to steal, create or destroy funds, or to forge or bypass a signature or proof check. Also: making honest nodes disagree about which blocks or transactions are valid, or about the resulting state (a chain split, including differences between 32-bit WASM and 64-bit builds). Also: halting or forking the chain, getting an honest validator slashed or jailed, or remote code execution.
- **High:** a panic, abort, deadlock, unbounded memory growth or CPU exhaustion in one node that a single unauthenticated peer can trigger with a few messages. Also: a light client accepting invalid state, history or blocks. Also: bypassing a configured RPC authentication setting (`username`/`password`, `allowip`, `methods`).
- **Medium:** denial of service that needs sustained traffic from many peers, or that only degrades service (slower sync, dropped peers, a mempool that is easy to fill). Also: escaping peer bans or rate limits. Also: a web-client API that a hostile page input can crash or corrupt.
- **Low:** problems that need an operator's mistake or local access, information leaks that cannot be used to attack, and log injection.
- Any panic reachable from peer data is at least High. We treat a remote crash as a real bug even when the process restarts.

## Anything to leave alone

- Attacks that need 1/3 or more of the validator slots, or that need control of a node's configuration, CLI, database files or key files.
- What an authenticated RPC client does on purpose, and anything against an RPC server bound to localhost with no credentials (the default, by design).
- Advisories in dependencies, unless you show they can be reached through this code.
- Anything only in `test-utils/`, `spammer/`, `network-mock/`, `scripts/` or test code.

## Reports and patches

- Give a reproducer we can run: preferably a `#[test]` in the affected crate that fails before the patch and passes after it, or a small in-process peer that sends the offending messages.
- Patches must keep the consensus rules unchanged for blocks that are already valid. A change to what makes a block or transaction valid is a hard fork. Point that out plainly, and don't make it silently.
- Keep patches minimal, in the style of the surrounding code, and pass `cargo clippy` and `cargo fmt`.
