# Threat model

## What this project does and where untrusted input enters
Tari is a Mimblewimble-based proof-of-work blockchain. The main deliverables are the base node
(`applications/minotari_node`), the console wallet (`applications/minotari_console_wallet`), the miner and merge-mining
proxy, and the libraries they are built on.

Treat everything that arrives from a network peer as untrusted:
- the p2p transport and framing: Noise handshake, yamux multiplexing, peer identity and connection management
  (`comms/core`);
- DHT messages, discovery, store-and-forward and relaying (`comms/dht`);
- RPC requests and responses between peers, including sync streams (`comms/core/src/protocol/rpc`, `comms/rpc_macros`);
- block, header and transaction propagation, header/block sync, and mempool admission (`base_layer/core`);
- transactions and their components: commitments, range proofs, kernels, scripts, covenants, encrypted data
  (`base_layer/transaction_components`, `infrastructure/tari_script`);
- proof-of-work data for every algorithm (RandomX, SHA3x, Cuckaroo, merge-mined Monero headers).

Less exposed, but in scope: the gRPC and JSON-RPC interfaces of the node and wallet, and the merge-mining proxy. These
are normally bound to localhost or protected by credentials, so an attacker there is assumed to be authenticated.

## Components that matter most / least
Most: consensus and validation (`base_layer/core/src/validation`, `consensus`, `proof_of_work`, `chain_storage`),
transaction verification, the comms/DHT/RPC stack, and wallet key handling (`base_layer/transaction_key_manager`,
`base_layer/wallet`, the offline signer and the Ledger comms crates).

Least: `integration_tests/` (the cucumber harness), test utilities (`infrastructure/test_utils`), example code, build
tooling under `buildtools/` and `scripts/`, and the MCP servers (`applications/minotari_mcp_*`), which are local
convenience tools.

## How to exercise it
- `cargo test -p <crate>` runs a crate's unit and integration tests. Prefer `-- --test-threads=1` for `tari_core`.
- `base_layer/core/tests` has chain, sync and mempool tests that build in-memory chains.
- `comms/core/tests` and `comms/dht/tests` set up in-process peer networks.
- The base node and wallet binaries are in `target/debug/` after the image build.

## How you rate severity
- **Critical:** a consensus split between honest nodes; inflation, or any way to create value or break the balance /
  commitment equation; acceptance of an invalid block or transaction; spending another user's funds; leaking wallet
  spend keys, view keys or blinding factors (including through the offline signer or Ledger paths); remote code
  execution.
- **High:** an unauthenticated remote peer can crash a base node, exhaust its memory, or stall it persistently; an
  honest peer can be made to get banned (for example by being blamed for data it only relayed); a single peer can halt
  sync or block mempool / block-template construction; decode or validation work that is unbounded relative to the
  bytes sent.
- **Medium:** DoS that needs an authenticated gRPC/JSON-RPC client; bounded resource exhaustion that recovers on its
  own; privacy leaks that do not expose keys or amounts.
- **Low:** local-only CLI issues, logging hygiene, hardening.

Panics reachable from peer input are at least High. Issues that only appear in debug builds (debug assertions,
overflow checks) should say so; we rate them on their release-build effect.

## Anything to leave alone
- Attacks that need more than 50% of the network hash rate (or equivalent luck).
- Example and test code, proof-of-concept tools, and code marked as not ready for production.
- Tor itself and hidden services run by third parties; Yat.
- Consensus-rule changes in proposed patches: if a fix changes what blocks or transactions are valid, say so
  explicitly, since it needs a coordinated fork.
- Proposed bans: only ban a peer for faults that can be attributed to that peer, not to data it relayed.
