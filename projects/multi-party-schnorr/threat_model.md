# multi-party-schnorr threat model

Rust (`no_std`, `#![deny(unsafe_code)]`) implementation of threshold Schnorr
signing: DKG, DSG, key refresh, quorum change, BIP32-style soft derivation,
threshold MPC VRF with VRF-backed hard derivation, and Ed25519, Taproot
(secp256k1), RedPallas and MLSAG variants. Based on "Simple Three-Round
Multiparty Schnorr Signing with Full Simulatability" (eprint 2022/374).
Used to protect wallet and custody keys, so a key or signature break is the
worst outcome.

## Adversary and untrusted input
- Assume a malicious adversary corrupting up to t-1 of n parties (and, for
  properties the protocol claims under dishonest majority, up to n-1). Every
  message received from another party is adversarial: wrong lengths, invalid
  or identity/small-order points, non-canonical scalars, inconsistent
  commitments, bad proofs, replayed or reordered messages, wrong party ids or
  session ids, and wrong-round messages.
- Serialized messages, sessions and keyshares decoded via serde/ciborium
  (`session` / `serde` features) are untrusted when received from peers.
- The local party's own keyshare at rest and its own RNG are trusted.
- Networking, authentication and secure channels are explicitly out of scope
  of this library (see README); do not report the absence of transport
  authentication itself. Do report places where the library relies on
  authenticated channels but this is not documented, or where a party id /
  session id is not bound into what is checked.

## What matters most (in rough order)
1. Secret key or keyshare extraction/leakage by malicious parties
   (e.g. missing proof checks, nonce reuse or bias, rerandomization or
   derivation flaws, refresh/quorum-change leaking shares).
2. Forgery or signing a message/key the honest parties did not agree to
   (message binding, session-id binding, Taproot tweak / even-Y handling,
   derivation-path handling, VRF output manipulation).
3. A malicious party causing honest parties to finish with inconsistent or
   attacker-chosen public keys without detection.
4. Secret material not zeroized, or secret-dependent timing in our own code.
5. Panics / unbounded allocation reachable from peer messages (DoS).

Crates in scope: the root crate (`src/`), `crates/sl-mpc-derive`,
`crates/sl-mpc-vrf`, `crates/sl-mpc-mlsag`. All features are in scope; state
the required feature set in each report.

## Out of scope
- Bugs in third-party dependencies (curve25519-dalek, k256, pasta_curves,
  reddsa, crypto_box, etc.) and in `sl-mpc-mate` (separate repo
  silence-laboratories/sl-crypto); report only if our usage is wrong.
- `examples/` and `test-support`-only helpers, unless the same code is
  reachable without `test-support`.
- An honest party misusing the API in a way the docs forbid (e.g. reusing a
  keyshare from `KeygenParty<VrfPoint>` as a VRF keyshare), unless the API
  silently accepts it and this leads to a key compromise.

## Severity
- Critical: key/keyshare recovery or signature forgery by a coalition below
  the threshold, or by a network attacker.
- High: attacker-controlled public key or derived key accepted by honest
  parties; secret leakage requiring several sessions; signing a message not
  agreed by honest parties.
- Medium: abort-free misbehaviour without identification where the paper
  promises identification; non-zeroized secrets; remote panics in protocol
  message handling.
- Low: hardening, defence in depth, unclear docs that may cause misuse.

## How to exercise it
Checkout at /src, all deps fetched, builds done. Run offline:
`cargo test --workspace --all-features --release`. Tests are in-module
(`#[cfg(test)]`); examples: `cargo run --example keygen --features "eddsa test-support"`.
Prefer a failing regression test against this checkout as the PoC.
