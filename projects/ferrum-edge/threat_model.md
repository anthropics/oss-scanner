# Ferrum Edge audit scope

Ferrum Edge is a Rust proxy, API/AI gateway, and mesh data plane. Review protocol parsing, proxy routing, authentication and authorization plugins, admin/configuration ingestion, TLS identity, and outbound request handling. Client traffic, upstream responses, imported API specifications, and configuration received across a trust boundary may be adversarial; demonstrate the privileges and deployment configuration needed for a report.

The checkout and build artifacts are in `/src`. This image builds the ordinary gateway with `cloud-secrets` and the default `crypto-ring` backend. FIPS and eBPF builds are separate configurations and are not compiled by this image. Keep those coverage limits explicit.

Offline checks include `cargo test --offline --locked --features cloud-secrets --lib` and the repository's `unit_tests`, `unit_plugins_a_tests`, `unit_plugins_b_tests`, `unit_gateway_core_tests`, and `integration_tests` targets. Tests needing external services, Docker, cloud credentials, or privileged kernel operations require separate fixtures; do not assume they ran. Use local fixtures and loopback services for reproducers, with no live credentials or third-party targets.

This enrollment covers only `ferrum-edge/ferrum-edge`. The `.github` organization repository, the private website repository, and the separately maintained `ferrum-contracts` repository or vendored `contracts/ferrum-contracts/` content are excluded from enrollment and finding ownership. Retained contract fixtures may support builds and tests.
