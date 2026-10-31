# Threat model

## What this project does and where untrusted input enters
- An XDP/eBPF firewall in front of Minecraft Java Edition servers (1.8 to current), plus a Rust userspace loader that runs as root, attaches the program to a NIC and keeps it attached.
- `xdp/minecraft_filter.c` runs on every received frame. Ethernet, IPv4 and TCP headers and the TCP payload are fully attacker-controlled, from any source address. This is the primary attack surface.
- For TCP to the filtered port range, a per-flow state machine checks the TCP handshake (SYN, then the ACK with the expected sequence) and the first Minecraft packets (handshake, then status request + ping, legacy ping, or login start). Only flows that finish that sequence are moved into `player_connection_map` and pass uninspected from then on; everything else is dropped. New connections are rate limited per source IP (`connection_throttle`). All map cleanup happens in-kernel via `bpf_timer`.
- The loader (`loader/`) reads `config.toml` (trusted, written by the local admin) and, only if enabled, serves Prometheus metrics over HTTP with `tiny_http` on the configured address. That endpoint may be reachable by untrusted clients.

## Components that matter most / least
- Most: `xdp/minecraft_filter.c`, `xdp/protocol.h`, `xdp/varint.h`, `xdp/common.h` (bounds-check macros) — the packet path and its parsers.
- Then: `loader/metrics.rs` (network-facing when enabled), `loader/ebpf.rs` (how config values and map sizes reach the program).
- Least: `loader/config.rs`, `loader/logging.rs` and the CLI; their input comes from the admin. `.github/` and `build.sh` are out of scope.

## How to exercise it
- `cargo test` runs the Rust unit tests and `tests/c_unit_tests.rs`, which compiles `xdp/tests/protocol_test.c` natively with ASan/UBSan. That harness calls the real inspectors from `xdp/protocol.h` on exact-size heap buffers; add packets there to demonstrate parser bugs.
- The compiled BPF object is `xdp/minecraft_filter.o` (inspect with `llvm-objdump -d`); the loader is `target/release/xdp-loader` and `target/debug/xdp-loader`.
- Attaching the program or using `BPF_PROG_TEST_RUN` needs root/`CAP_BPF` and a real kernel, which the scan environment may not have. Reasoning against the code is fine; say clearly when a finding could not be run end to end.

## How you rate severity
- Critical: a packet or packet sequence that crashes or corrupts the kernel; code execution in the loader from the network.
- High: a filter bypass on the filtered ports — a flow reaching `player_connection_map`, or payload reaching the backend, without passing the inspection sequence; a remote way to evict or lock out verified players with low attacker traffic (asymmetric DoS); remote, unauthenticated loader crash or detach that leaves the server unprotected.
- Medium: getting more SYNs per source IP through than `hit_count` per window; malformed Minecraft packets accepted by an inspector when they cannot be shown to harm the backend; remote crash or resource exhaustion of the metrics endpoint.
- Low: wrong statistics, logging problems, anything that needs control over `config.toml`, the command line or root on the host.
- A parser bug only seen in the native test build counts by its effect on the BPF program; out-of-bounds reads that the verifier would reject are build breaks, not vulnerabilities.

## Anything to leave alone
- IPv6 and non-TCP traffic pass unfiltered; only IPv4 is supported (documented).
- Verified connections are intentionally not inspected again after login; later game packets are the backend's job.
- Non-first IP fragments are passed on purpose (the first fragment is dropped for the filtered range); see the comment in `minecraft_filter`.
- While `connection_throttle` is full, new unverified connections are dropped on purpose (fail closed).
- Many legitimate players behind one NAT being throttled per `hit_count` is the configured behaviour, not a bug.
- Volumetric floods that saturate the link or NIC before XDP runs.
