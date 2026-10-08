# Ferrum Alloy audit scope

Alloy provides Rust/Axum application components and Ferrum Edge integration. Review request handling, framework configuration, authentication and authorization integration, diagnostic output, telemetry/redaction, and generation of gateway-facing configuration. Identify which application feature set and trust boundary a finding crosses; example-only behavior should be distinguished from library defaults.

The workspace, examples, all-feature build, test executables, compiler, and Cargo caches remain in `/src` and the toolchain directories. Run `cargo test --offline --locked --workspace --all-features` and `cargo test --offline --locked --workspace` offline. PostgreSQL integration and gateway/collector E2E suites need separate local fixtures. Browser, Docker-based E2E, and nightly fuzz toolchains are not provisioned by this image.

Use disposable application fixtures and loopback services. Do not interact with production databases, gateways, or telemetry destinations.

Only `ferrum-edge/ferrum-alloy` is enrolled. The `.github` organization repository, private website, and separate `ferrum-contracts` repository or vendored `contracts/ferrum-contracts/` content are excluded from enrollment and finding ownership. Any retained contracts remain build/test dependencies.
