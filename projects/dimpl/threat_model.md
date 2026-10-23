# dimpl threat model

dimpl is a synchronous Sans I/O implementation of DTLS 1.2 and DTLS 1.3 for Rust,
used for WebRTC and other datagram protocols. The caller supplies datagrams and
timeouts, drains output records and events, validates peer identity, and uses
the exported application data or DTLS-SRTP keys.

## Trust boundaries and scope

The target is https://github.com/algesten/dimpl on main. Treat every received
datagram, handshake field, certificate, extension, fragment, record number,
epoch, and encrypted record as adversarial, including traffic received before
authentication. Exercise clients, servers, automatic version selection, PSK,
both crypto providers, and established sessions.

Prioritize handshake/transcript and Finished verification, certificate signature
verification, version/cipher negotiation, PSK authentication, key derivation,
SRTP exporters, record authentication, replay windows, epochs, and key updates.
Also examine fragmented handshakes, out-of-order and duplicate records,
retransmission/timer behavior, queues, parser bounds, and resource use before
and after authentication.

The certificate model is explicit: dimpl verifies DTLS handshake signatures and
emits Output::PeerCert, but does not perform PKI identity validation. The caller
must apply its own fingerprint, pinning, certificate-chain, name, and usage
policy. Missing application identity checks alone are not a dimpl bypass;
cryptographic verification and faithful delivery of the peer certificate remain
security requirements.

The caller supplies sockets, transport routing, time, configuration, trust
policy, and PSK resolution. Every Error returned by the public API is fatal;
the application must discard that Dtls instance. Malformed/replayed datagrams
that can be tolerated are discarded internally. Reproducers should respect
this documented error contract and use realistic packet/time sequences.

Cryptographic dependencies are separate projects. Identify defects in dimpl or
its use of those dependencies precisely, rather than reporting unrelated
dependency implementation issues as dimpl findings.

## Build, offline tests, and fuzzing

The checkout and build artifacts are in /src. The image installs the C toolchain,
autotools and libclang needed for the OpenSSL/wolfSSL test peers, fetches the
main and fuzz dependencies, and installs nightly Rust and cargo-fuzz before
setting CARGO_NET_OFFLINE=true. The fuzz targets are precompiled.

Run the default suite and each provider independently without Internet access:

```sh
cd /src
cargo test --locked
cargo test --locked --no-default-features --features aws-lc-rs
cargo test --locked --no-default-features --features rust-crypto
```

tests/dtls12, tests/dtls13, and tests/auto contain in-memory peers and tests for
handshakes, fragmentation, reordering, retransmission, PSK, key updates, and
version selection. tests/ossl and tests/wolfssl provide interoperability peers
without external servers. Prefer these helpers for deterministic reproducers.

The fuzz targets exercise full DTLS 1.2/1.3 state machines and record parsers:

```sh
cargo +nightly fuzz list
cargo +nightly fuzz run fuzz_dtls_packet -- -max_total_time=60
cargo +nightly fuzz run fuzz_dtls13_packet -- -max_total_time=60
```

## Reports

Include the revision, DTLS version, crypto provider and feature flags, attacker
capabilities, caller trust policy, expected and observed behavior, and a minimal
packet/API sequence or minimized fuzz input. Prefer a small patch and regression
test addressing the root cause, and combine variants of the same defect.

Explain demonstrated impact and prerequisites, especially for authentication
bypass, disclosure, forged plaintext, or incorrect exported keys. For denial of
service, show public-API reachability and quantify attacker input, memory, CPU,
or retransmissions. Distinguish security impact from harmless interoperability
or protocol-conformance differences.
