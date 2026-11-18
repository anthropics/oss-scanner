# Threat model

## What this project does and where untrusted input enters
MoneroUSD is a post-quantum, private block-DAG cryptocurrency (testnet; mainnet not launched). Its full node
(`monerousd-node-zkdag`, binary `usdmd-node`) relays and verifies blocks, transactions, zero-knowledge proofs and sync
bundles from untrusted peers over Tor onion services, and serves a local HTTP RPC to the wallet. Every byte from a peer
is untrusted: block and header decoding, proof verification (`vendor/Plonky3/usdm-decider`, the WHIR recursive
verifier and its AIRs), join/sync bundles (`src/node/sync.rs`, `src/node/join.rs`), the mempool and the bulk/relay lanes
(`src/arti_transport.rs`, `src/relay.rs`). The wallet (`monerousd-wallet-v2/src-tauri`) holds the user's keys and talks
only to its own node.

## Components that matter most / least
- Most: anything that lets value be created or spent twice (nullifier set, `nf_sparse`, the fold), a proof or
  signature the verifier accepts though it is false in one place, a crash or unbounded allocation a remote peer can
  trigger, anything that leaks a note's amount, owner or linkage, and the wallet's key handling.
- Also in scope: the bridge custody code (`btc_*`, `xmr_*`), the DEX/pool settlement (`defi_lane`, `ion_*`).
- Less: the static web sites under `monerousd-node-zkdag/sites/` (served locally to the wallet's own browser).
- Out of scope: vendored third-party crates other than `vendor/Plonky3/usdm-decider` (our prover/verifier).

## How to exercise it
`target/release/usdmd-node serve` with `MONEROUSD_NET=testnet` starts a node; the unit and pin tests are in the node crate
(`cargo test --release --lib <module>`). The wallet's core is driven by `wallet-harness` (one command per stdin line).

## How you rate severity
- Critical: creating value from nothing, spending a note twice, a verifier accepting a false statement, stealing or
  moving another user's funds, recovering a key or a note's owner/amount.
- High: a remote crash or permanent chain halt any peer can cause; a privacy leak that links two notes or a note to an IP.
- Medium: a remote slowdown or resource exhaustion that recovers; a local-only RPC issue.
- Low: everything else.

## Anything to leave alone
Testnet parameters (block time targets, faucet amounts) are not bugs. Pre-quantum primitives appear only where a foreign
chain's own signatures are checked (Bitcoin, Monero); that is intended.
