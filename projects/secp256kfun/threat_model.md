# Threat model

## What this project does and where untrusted input enters

A Cargo workspace of secp256k1 cryptography crates:
- `secp256kfun`: `Point` and `Scalar` types, with compile-time markers for zero/non-zero, secret/public and point
  normalisation; arithmetic vendored from `k256` (`src/vendor/k256`); hashing, nonce derivation, polynomials,
  hash-to-curve.
- `schnorr_fun`: BIP340 Schnorr, adaptor signatures, MuSig2, FROST (`src/frost`: shared keys, shares, signing
  sessions, binonces) and its distributed key generation (`src/frost/chilldkg`: simplepedpop, encpedpop,
  certpedpop), and `share_backup`.
- `ecdsa_fun` (ECDSA, ECDSA adaptor signatures), `sigma_fun` (sigma protocols and Fiat-Shamir), `vrf_fun` (VRF,
  including RFC 9381), `arithmetic_macros` (the `g!` and `s!` expression macros).

This is a library, so the untrusted inputs are whatever an application passes in from peers: signatures, public
keys, points and scalars from bytes, hex, serde and bincode; FROST and MuSig nonces, signature shares and DKG
messages from other participants; proofs and VRF outputs to verify.

The heaviest user is Frostsnap, a FROST hardware wallet (ESP32-C3, 32-bit RISC-V) that secures real bitcoin. Its
security model (in frostsnap's `SECURITY.md`) relies on this code: fewer than the threshold of corrupt participants
must not be able to forge, steal key material, or bias the joint key; nonces must never repeat or leak.

## Components that matter most / least

Most: `schnorr_fun/src/frost` (including `chilldkg`), `binonce.rs`, `schnorr.rs`, `musig.rs`; in `secp256kfun`,
scalar and point arithmetic in `src/op.rs`, `src/backend`, `src/vendor/k256` (both the 64-bit `5x52`/`4x64` and the
32-bit `10x26`/`8x32` backends), decoding in `point.rs`/`scalar.rs`, `nonce.rs`, `hash.rs`, `poly.rs`, and the
`marker` types that decide constant- versus variable-time paths.

Less, but in scope: `ecdsa_fun`, `sigma_fun`, `vrf_fun`, `share_backup`, adaptor signatures, `libsecp_compat`.

Out of scope: `benches/`, `publish.sh`, documentation examples, test-only code (unless it shows a library bug).

## How to exercise it

- `cargo test --workspace --all-features --release`, as CI does. The image also builds and tests for
  `i686-unknown-linux-gnu`, which selects the 32-bit field and scalar code; run it with
  `--target i686-unknown-linux-gnu`.
- No-default-features (no_std) builds per crate: `cargo test --release --no-default-features -p <crate>`.
- Tests compare against libsecp256k1 (`tests/against_c_lib.rs` in three crates), BIP340 vectors, MuSig vectors,
  ECDSA and ECDSA-adaptor vectors, RFC 9381 VRF vectors, and FROST property tests (`schnorr_fun/tests/frost_prop.rs`).
  Differential tests against libsecp256k1 are the quickest way to show an arithmetic bug.
- Debug builds wrap the field code in `field_impl.rs`, which adds checks; release builds use the backend directly. The
  image pre-builds release; test debug too.

## How you rate severity

- **Critical:** forgery (a signature, FROST or MuSig aggregate, adaptor signature, or proof that verifies without
  the key or the threshold); recovery of a secret key or FROST share from signatures, nonces or protocol messages;
  nonce reuse or nonce derivation that an honest caller cannot avoid; a malicious participant in FROST signing or
  DKG that can bias or control the joint key, or obtain a share it should not have; wrong arithmetic results on any
  supported backend, including 32-bit.
- **High:** the above needing an unlikely precondition; a verifier accepting invalid encodings (non-canonical
  scalars or points, points off the curve, wrong-subgroup or zero values where the type says `NonZero`) in a way
  that affects signature or key validity; a `Secret`-marked value going through a variable-time operation on a path
  that handles keys or nonces.
- **Medium:** API that makes a security-relevant misuse easy and is not documented as unsafe; partial leakage of
  secret information.
- **Low:** panics on malformed input, denial of service, performance.

## Anything to leave alone

- The README says the library is not reviewed for side channels and does not zero secrets in memory. Do not report
  the absence of memory zeroing. Report a timing difference only when it is on a `Secret`-marked path; variable time
  on `Public` values is by design.
- Values the caller marks `Public` are the caller's responsibility.
- Panics in debug-only checks where release builds behave correctly.
- Issues found only in test vectors, benches or test helpers.
