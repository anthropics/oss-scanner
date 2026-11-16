# Threat model: Pydantic Logfire (Rust SDK)

## What this project does and where untrusted input enters
This workspace holds the Rust SDK for the Logfire observability platform, built on OpenTelemetry:
- `logfire/`: the SDK. Configuration, macros (`info!`, `span!`), the `tracing` and `log` bridges, the console
  exporter and the OTLP exporters (HTTP protobuf, HTTP JSON, gRPC).
- `logfire-core/`: token parsing and the token-to-region mapping.
- `logfire-client/`: an HTTP client for the Logfire query API.

The backend is closed source and is not in this repository.

The application, its code, its configuration and its environment variables are trusted. Untrusted input is:
- Data the application records: span names, messages, attribute values, errors and panics.
- Responses from the network: the OTLP endpoint and the query API.

## Components that matter most
1. **Credentials and endpoints**: `logfire/src/config.rs`, `logfire/src/exporters.rs`,
   `logfire-core/src/token.rs`, `logfire-client/src/builder.rs`. Of interest: a write or read token sent to a
   host other than the configured one (the token-to-region mapping, redirects), sent without TLS, or written
   to logs and error messages. With the `data-dir` feature, the credentials file read from
   `LOGFIRE_CREDENTIALS_DIR`.
2. **Recording and exporting**: `logfire/src/logfire.rs`, `logfire/src/macros/`, `logfire/src/bridges/`,
   `logfire/src/internal/`. Of interest: a recorded value that makes the SDK panic, deadlock, block shutdown,
   or use CPU or memory out of proportion to its size. The SDK must never break the application it observes.
3. **Query client**: `logfire-client/src/client.rs`, `types.rs`. Of interest: a response that makes the
   client panic or allocate without bound.

## How to exercise it
- Run `cargo test --workspace --all-features` from `/src`. Every crate is already fetched, and
  `CARGO_NET_OFFLINE=true` and `LOGFIRE_SEND_TO_LOGFIRE=no` are set, as in CI.
- `logfire/tests/` has integration tests that start local HTTP and gRPC sinks (`test_http_sink.rs`,
  `test_grpc_sink.rs`); use them as the model for a hostile or slow endpoint. `logfire/examples/` has small
  programs.

## How we rate severity
- **Critical**: memory corruption or code execution.
- **High**: a token sent to another host, sent in clear text under the default configuration, or written to
  logs; a small recorded value that crashes or hangs the application under the default configuration.
- **Medium**: the same issues when they need a non-default but documented option or feature.
- **Low**: cost that grows linearly with the recorded data, and issues that need a malicious Logfire backend.

## Anything to leave alone
- The Logfire backend, and vulnerabilities in dependencies (`opentelemetry*`, `tonic`, `reqwest`, `rustls`)
  themselves, unless the SDK uses them in an unsafe way.
- The application recording a secret on purpose: this SDK does not scrub attributes.
- A hostile environment or configuration, and `unsafe` blocks in `tests/` (they set environment variables).
