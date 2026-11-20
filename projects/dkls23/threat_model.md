# dkls23 threat model

Rust implementation of the DKLs23 threshold ECDSA protocol (secp256k1):
DKG, DSG, key refresh, key import/export, quorum change, and migration from
GG**/CMP keyshares. It powers the Silent Shard SDK and is used to protect
wallet and custody keys, so a key or signature break is the worst outcome.

## Adversary and untrusted input
- Assume a malicious adversary corrupting up to t-1 of n parties (DKLs23 is
  designed for dishonest majority). Every message received from another
  party via the relay is adversarial: wrong lengths, invalid/identity points,
  non-canonical scalars, inconsistent commitments, bad proofs, malicious OT
  messages, replayed/reordered messages, wrong ids, wrong round.
- The relay/network itself is untrusted (can drop, delay, replay, reorder,
  inject). The library's own message layer (`src/proto`: signed broadcast
  with Ed25519, x25519 + ChaCha20Poly1305 encrypted P2P, message ids derived
  from setup) is in scope and must provide sender authenticity,
  confidentiality and replay/cross-session protection.
- Setup messages are produced by the application and are trusted only as far
  as each party verifies them; report cases where a malicious party or relay
  can make honest parties run with mismatched setup.
- Zero-copy messages are byte arrays cast to structs (bytemuck): any
  attacker-chosen byte pattern must be handled safely.
- The local party's own keyshare at rest and its own RNG are trusted.

## What matters most (in rough order)
1. Secret key / keyshare extraction by malicious parties (OT, MtA/VOLE,
   consistency checks, nonce handling, refresh/quorum change/export leaking
   shares, import of a key without proper verification).
2. Forgery or signing a message/derivation path honest parties did not agree to.
3. Honest parties finishing with inconsistent or attacker-chosen public keys
   without detection.
4. Breaks of the message layer: forged/decrypted/replayed P2P or broadcast
   messages, nonce reuse in ChaCha20Poly1305, cross-session confusion.
5. Secret material not zeroized, secret-dependent timing in our code.
6. Panics / unbounded allocation / hangs reachable from peer messages (DoS).

In scope: `src/` (all modules). Audited vs unaudited components are listed in
the README; unaudited ones (key import/export, quorum change, migration)
deserve extra attention.

## Out of scope
- Bugs inside third-party dependencies and inside `sl-mpc-mate` /
  `sl-oblivious` (separate repo silence-laboratories/sl-crypto); report only
  if our usage is wrong.
- `crates/msg-relay` (local in-memory test relay) and `crates/dkls-metrics`
  (benchmark tool), and `test-support`-only helpers, unless the same code is
  reachable from the library without `test-support`.

## Severity
- Critical: key/keyshare recovery or signature forgery by a coalition below
  the threshold, or by a network attacker.
- High: attacker-controlled public key accepted by honest parties; secret
  leakage requiring several sessions; signing a message not agreed by honest
  parties; breaking authenticity/confidentiality of protocol messages.
- Medium: undetected misbehaviour where the protocol promises detection;
  non-zeroized secrets; remote panics in message handling.
- Low: hardening, defence in depth, unclear docs that may cause misuse.

## How to exercise it
Checkout at /src, deps fetched, builds done. Run offline:
`cargo test --workspace --tests --features sl-dkls23/test-support --release`.
Examples: `cargo run --example keygen` / `sign` / `refresh`.
Doc-tests are not maintained (CI runs `--tests`). Prefer a failing
regression test against this checkout as the PoC.
