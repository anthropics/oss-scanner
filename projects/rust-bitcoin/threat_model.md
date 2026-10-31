# Threat model

## What this project does and where untrusted input enters
`rust-bitcoin` is a Rust library (a Cargo workspace of crates: `bitcoin`,
`primitives`, `hashes`, `consensus_encoding`, `base58`, `bech32`-style address
handling in `addresses`, `bip158`, `chacha20_poly1305`, `crypto`, `io`,
`network`, `p2p`, `key_expression`, `taproot_primitives`, `units`,
`internals`) for de/serializing and validating Bitcoin data structures and
network messages.

Essentially all input is untrusted: transactions, blocks, scripts, WUtxos,
BIP-0158 filters, P2P messages, addresses and scripts come from the Bitcoin
network or from counterparty software. Deserialization entry points are
`bitcoin::consensus::deserialize`, the `Encodable`/`Decodable` traits in
`consensus_encoding`, address/key parsers in `addresses` and `bitcoin::key`
(WIF, descriptors in `key_expression`), hex/base58 decoding in `base58` and
`hashes`, and message parsing in `p2p` and `network`.

## Components that matter most / least
Most important: parsing/validation of untrusted bytes — consensus encoding,
script parsing, address parsing, key/descriptor parsing, BIP-0158 filter
decoding, the crypto glue in `crypto`/`hashes` (note: the actual secp256k1
operations live in the external `secp256k1` crate, which is out of scope
here), and `chacha20_poly1305`.
Less important but still in scope: amount/weight/time handling in `units`
(wrong rounding or overflow in fee/amount arithmetic can lose users money),
`base58`, `bip158`, `p2p` message framing.
Out of scope: `benches/`, `fuzz/` harness code itself, `contrib/`,
documentation, and anything under `examples/` or test-only code — unless a
finding there reveals a bug in library code.

## How to exercise it
- The workspace builds and tests with plain `cargo`:
  `cargo test --workspace --all-features` (debug and release).
- There are libFuzzer targets for every parsing entry point in `fuzz/`
  (built into `fuzz/target/` by cargo-fuzz; see `fuzz/README.md` and
  `fuzz/fuzz.sh`). Per-target seed corpora from the project's shared corpus
  repository are under `/opt/corpora/<target>` (fetched from
  github.com/rust-bitcoin/qa-assets); copy the relevant one to
  `fuzz/corpus/<target>` and run e.g.
  `cargo +nightly fuzz run -O --debug-assertions <target> -- -max_total_time=600`
  or replay individual files directly against the built binary.
- `fuzz/fuzz_targets/` shows exactly which parsers the maintainers consider
  untrusted-input boundaries; use them as the map of entry points.
- Some code paths are gated behind features (`serde`, `arbitrary`,
  `rand-0.8`, `no-std` configurations); test both default and
  `--all-features` builds, and no-default-features (no_std) builds.

## How you rate severity
Per the project's SECURITY.md, an issue is a security vulnerability if it
could lead to: loss of funds, loss of privacy, censorship (e.g. by attaching
an incorrectly low fee to a transaction), or any "ordinary" security problem
such as remote code execution or invalid memory access.

- Memory safety violations (the codebase is almost entirely safe Rust; the
  few `unsafe` blocks, e.g. in `primitives/src/script/borrowed.rs` and
  `bitcoin/src/taproot/merkle_branch/borrowed.rs`, are hand-audit targets):
  any out-of-bounds, use-after-free, or unsound `unsafe` is high at minimum;
  parse paths reachable from the network (P2P, block/tx relay) with
  potential for code execution are critical.
- Remote panic / abort / unbounded memory allocation on untrusted input is a
  DoS: high if reachable from default-use network parsing, medium otherwise.
- Accepting invalid data (e.g. malleable transactions, invalid signatures
  accepted at the API level, addresses that are not valid for their network,
  witnesses that should be non-canonical) or rejecting valid data in a way
  that affects funds or interoperability: high.
- Wrong amounts, fee or weight arithmetic (rounding/overflow in `units`):
  high — these can directly cause loss of funds or censorship.
- Side channels (non-constant-time secret handling): medium/high depending on
  whether secret key material is involved.
- Pure API/ergonomics or doc problems, panics only reachable in clearly
  misuse contexts, and anything only about consensus *compatibility* with
  Bitcoin Core (see below) are not vulnerabilities — do not report them.

## Anything to leave alone
- This library explicitly does not aim for consensus validation (see
  "Known limitations" in README.md). If Bitcoin Core rejects data that
  this library accepts, that is fine. If Bitcoin Core accepts data that
  this library rejects, that is not.
- Do not report findings in test-only helpers, or the fuzz harness code
  in `fuzz/` itself.
- Do not report panics that abort only in debug builds when the release
  behaviour is a documented `Result::Err`.
- Performance issues without a demonstrated unbounded-work DoS: do not
  report.
