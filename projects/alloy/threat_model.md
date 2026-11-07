# Alloy

Alloy is a collection of Rust libraries for interacting with Ethereum and other EVM chains. It provides consensus types (transactions, receipts, headers, blocks) and their RLP and EIP-2718 encodings, EIP implementations, RPC and Engine API types, JSON-RPC clients, providers, transports (HTTP, WebSocket, IPC) and signers. It is a dependency of execution clients such as Reth, of Foundry, and of many wallets, indexers, relayers and bots, so a bug here usually reaches every downstream user at once.

## Scope and trust boundaries

Review the whole repository. The priorities below guide investigation without excluding other crates or optional features. Identify the crate, feature flags and API a downstream user must call to reach an issue.

- Treat any bytes or JSON a downstream application decodes with Alloy as adversarial: P2P and RPC data in execution clients, RPC responses in wallets and tools, and user-supplied transactions. Prioritize decoding and validation in `crates/consensus/`, `crates/eips/` and `crates/consensus-any/`: RLP and EIP-2718 decoding, typed transaction envelopes, blob sidecars and KZG handling, authorization lists (EIP-7702), withdrawals, requests and header fields.
- Encoding/decoding asymmetry, non-canonical encodings that are accepted, wrong transaction or receipt hashes, wrong signature hashes, incorrect sender recovery, or mis-computed roots are security issues when a downstream consensus client or wallet relies on them. Show the downstream impact concretely.
- Review signature handling in `crates/signer/` and `crates/signer-local/`: signature malleability, chain ID and replay protection, EIP-155/EIP-712 hashing, key and mnemonic handling, keystore decryption, and accidental secret disclosure through `Debug`, logs or errors. Hardware and cloud signers (`signer-ledger`, `signer-trezor`, `signer-aws`, `signer-gcp`, `signer-azure`, `signer-turnkey`) should sign exactly what the caller asked for.
- RPC servers and remote nodes are untrusted from a client's perspective. Review `crates/rpc-types-*`, `crates/json-rpc/`, `crates/rpc-client/`, `crates/provider/`, `crates/pubsub/` and `crates/transport*/` for panics, unbounded allocation or recursion, response-ID confusion, subscription mix-ups, and filler logic (nonce, gas, chain ID) that a malicious node could abuse to make a client sign or send something unintended.
- The Engine API types in `crates/rpc-types-engine/` are used by execution clients for payload validation and conversion between payloads and blocks; incorrect conversions or missing checks there can affect consensus.
- Review unsafe Rust and dependencies where Alloy exposes them to untrusted data, and identify the crate that needs the fix.
- The calling application's configuration, the RPC URL it chooses to trust for state, and local keys it supplies are trusted. Public blockchain data is not confidential.

## Severity and evidence

Assess severity by realistic reachability through a downstream user and demonstrated impact. Highest: signing something other than what the caller asked for, key disclosure, and decoding or hashing bugs that let invalid data be accepted or valid data be rejected by a consensus client. A panic or unbounded allocation on attacker-supplied input is relevant when a common downstream path reaches it; quantify input size against CPU and memory. Panics in test code or on inputs only a trusted caller can construct are not vulnerabilities.

Reports should include the exact revision, crate and feature flags, entry point, attacker capabilities, root cause, expected and actual behavior, and a minimal deterministic reproducer, ideally a unit test. Group findings with the same root cause, and include a focused patch and regression test where practical. Send findings privately to `security@tempo.xyz`.

## Build and offline investigation

The source is at `/src`, with the Rust toolchain, Cargo dependency caches and build outputs retained. The workspace is built in release mode with all features, debug information and frame pointers. Cargo is configured for offline operation with four build jobs. `anvil` is on `PATH` for tests that need a local node; `geth` and `reth` are not installed, so tests that need them will skip or fail.

Rebuild after a change with:

```sh
cargo build --locked --release --workspace --all-features
```

The following unit-test targets are precompiled (debug profile, all features) and run without external services:

```sh
cargo test --locked --lib --all-features \
  -p alloy-consensus -p alloy-eips -p alloy-rpc-types-eth -p alloy-rpc-types-engine \
  -p alloy-json-rpc -p alloy-signer -p alloy-signer-local -p alloy-genesis
```

Other crates can be tested with `cargo test --locked --all-features -p <package>`. Run tests in the debug profile: `alloy-signer-local`'s `yubihsm` dev-dependency enables a mock HSM that refuses to compile in release mode. Test selection does not restrict audit scope. Do not connect reproducers to public networks.
