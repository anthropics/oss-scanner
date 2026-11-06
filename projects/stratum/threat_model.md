# Threat model: stratum

## What this project does and where untrusted input enters

This repository holds the protocol libraries of the Stratum V2 Reference Implementation (SRI). The applications that use them (pool, Job Declarator Server, Job Declarator Client, Translator Proxy) live in https://github.com/stratum-mining/sv2-apps and belong in a separate enrolment. Everything here is a library: it never opens a socket itself, but every byte it decodes was read from one by an application, so treat every decoder input as attacker-controlled.

Crates, from the wire upwards:

- `sv2/noise-sv2`: the Noise handshake (secp256k1 Diffie-Hellman, ChaCha20-Poly1305) and the cipher state that every Sv2 connection runs on. Handshake messages, certificates and ciphertext arrive from the peer. The handshake is also how a client authenticates a server.
- `sv2/framing-sv2`: the 6-byte Sv2 frame header (extension type, message type, length) and the frame body, plus Noise handshake frames.
- `sv2/codec-sv2`: ties framing and noise together into the encoder and decoder an application reads from a socket with.
- `sv2/binary-sv2`: the Sv2 binary data types (fixed and variable-length fields, sequences) and the derive macros that encode and decode every message struct.
- `sv2/subprotocols/*` (common-messages, mining, job-declaration, template-distribution) and `sv2/extensions-sv2`: the message definitions of each Sv2 subprotocol and of the negotiated extensions, including the TLV fields of worker-specific hashrate tracking.
- `sv2/parsers-sv2`: maps a decoded frame to the message enum of its subprotocol.
- `sv2/handlers-sv2`: the handler traits an application implements to dispatch parsed messages.
- `sv2/channels-sv2`: channel state for mining servers and clients (standard, extended and group channels), share validation and share accounting, and the target and difficulty arithmetic.
- `sv2/buffer-sv2`: the decoder's buffer in both configurations: `BufferFromSystemMemory` by default, `BufferPool` with `with_buffer_pool`. It is the one crate whose library code has `unsafe`.
- `sv1`: the Stratum V1 JSON-RPC protocol, which arrives in plain text from miners.
- `stratum-core/stratum-translation`: pure Sv1 <-> Sv2 message conversion.
- `stratum-core`: the single crate that re-exports all of the above; it is what applications depend on.

Both sides of a connection are untrusted to the other. A pool runs these decoders against every miner on the Internet; a miner or proxy runs them against a pool it has no reason to trust.

## Components that matter most / least

Most important, in this order:

1. `noise-sv2` and `codec-sv2`: a flaw here breaks confidentiality or authentication of every Sv2 connection, or lets a peer crash the process before it has authenticated.
2. `binary-sv2`, `framing-sv2`, `parsers-sv2` and the subprotocol crates: parsing of attacker-controlled bytes, including length fields and sequence counts.
3. `channels-sv2` and `stratum-translation`: share validation, target and difficulty arithmetic, and the Sv1 <-> Sv2 conversions. A mistake here lets a miner be paid for work it did not do, or lets a pool reject valid work.
4. `sv1`: the JSON-RPC parser that the Translator Proxy exposes to miners.
5. `buffer-sv2`: the `unsafe` buffer code under every decoder; look for aliasing and lifetime errors, with and without the pool.
6. `extensions-sv2` and `handlers-sv2`.

Out of scope: `fuzz/` (the harness itself), benchmarks, examples, CI configuration and `scripts/`. Dependencies (`bitcoin`, `secp256k1`, `chacha20poly1305`, `serde_json`) have their own security processes; report a flaw in one only when this repository's use of it makes it reachable from a peer, and show the path.

## How to exercise it

The image is offline. Every dependency is in the cargo cache, `CARGO_NET_OFFLINE` is set, and the workspace, its tests, its examples and the fuzz targets are already built in `/src`.

- **Tests**: `cargo test --workspace`, with the default features as CI runs them; the `no_std` feature of `channels-sv2` is for library builds and its tests do not compile under it. The repository's own toolchain file selects Rust 1.75.0 here.
- **Fuzz targets**: in `fuzz/`, `cargo fuzz list` names them and `cargo fuzz run <target> repo-corpus/corpus/<target>` runs one from the shared seed corpus CI uses, already cloned to `fuzz/repo-corpus` (the directory's toolchain file selects nightly). They cover frame decoding, round-trip serialization of every subprotocol's messages and data types, the Noise handshake with encryption round trips, and the Sv1 method parsers and wire format. A new target next to them is the quickest way to reproduce a parser finding.
- **Examples**: the crates have runnable examples: `cargo run --manifest-path=<dir>/Cargo.toml --example <name>` (`sv2/<crate>` or `sv1`). The eight that CI runs are already built and `buffer-sv2`'s three compile from the cache; among them `codec-sv2`'s `encrypted` (with `--features=noise_sv2`) and `noise-sv2`'s `handshake`, which stand up both sides of a connection in one process, and `sv1`'s `client_and_server` (runs for 30 seconds, then exits).
- **Not in the image**: Miri (CI runs `cargo miri test` on `buffer_sv2` and `noise_sv2` with a pinned nightly; this image has no `miri` component), and the integration tests, which live in sv2-apps (`scripts/run-integration-tests.sh` clones that repository and fails offline).
- **The protocol specification** is at https://github.com/stratum-mining/sv2-spec; it is not in the image, so quote the section you rely on when a finding is about spec conformance.

## How you rate severity

A finding counts when a peer that speaks the protocol can make an application built on these crates misbehave. State which crate and which API. "Default configuration" for a library means the features the applications enable: everything `stratum-core` turns on (including `codec_sv2/noise_sv2`) plus its `with_buffer_pool`, `sv1` and `translation` features, which the sv2-apps roles use.

- **Critical**: memory corruption reachable from a peer. A Noise handshake that completes with a peer that does not hold the expected key, or a cipher state that leaks or reuses key material or nonces. A share accepted that does not meet the channel's target, or a target or difficulty computed in the miner's favour, when the input is a message a miner can send.
- **High**: an abort, an unbounded allocation, or a panic in the per-message decode path every connection runs (`noise-sv2`, `framing-sv2`, `codec-sv2`, `buffer-sv2`, `binary-sv2`, `parsers-sv2`, the subprotocol decoders, `extensions-sv2`'s TLV decoding, and `sv1`'s message parsing), reachable from a peer before or after authentication (a length field that allocates its stated size, an unbounded sequence). A valid share or job rejected because of a decoding or arithmetic error (an integer overflow in `channels-sv2`'s target computation, for instance).
- **Medium**: a panic in an API the application calls with already-decoded values and could validate first (`channels-sv2`, `stratum-translation`, `handlers-sv2`). A parsing differential between encoder and decoder, or between `sv1`'s parser and the Sv1 wire format, that a peer can use to make two implementations disagree on a message.
- **Low**: a defect reachable only with a feature none of the applications enable (`buffer-sv2`'s `debug` and `fuzz`, `channels-sv2`'s `no_std`, `codec-sv2` and `noise-sv2` with `default-features = false`), or with a malformed value the application itself constructs.

A deviation from the Sv2 specification with no security consequence is a bug and not a vulnerability; do not report it.

## How to report

- Give a reproducer that runs in this image: a unit test or a fuzz target with the input bytes, and what was observed.
- Name the crate, the API, the cargo features, and the toolchain (1.75.0 or nightly).
- Propose a minimal patch against `main` with a regression test, and keep unrelated refactoring out of it.
- Report one root cause once. The same flaw reachable through several message types is one finding that lists each.

## Anything to leave alone

- Builds without `std` are supported (`binary-sv2`'s default `no_std`, `channels-sv2`'s `no_std`, `codec-sv2` and `noise-sv2` with `default-features = false`), and behaviour that differs between them only in error reporting is not a finding.
- `quickcheck` and `quickcheck_macros` are held below 1.1 so the 1.75.0 toolchain builds (see the comment in `Cargo.toml`), and `rayon-core` is a dev-dependency of `buffer-sv2`, `codec-sv2` and `noise-sv2` pinned to 1.12.1 in the workspace `Cargo.toml`, which no code imports; do not report dependency versions as findings.
- `sv1` implements Stratum V1 as miners speak it, including its plain-text transport. The lack of encryption or authentication in Stratum V1 is the protocol, not a finding.
