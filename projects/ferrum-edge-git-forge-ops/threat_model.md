# Ferrum Git Forge Ops audit scope

Git Forge Ops validates and applies Ferrum Edge configuration from Git pull requests. Review untrusted PR content, resource parsing, path and symlink boundaries, credential references, revision-bound approvals, workflow trust boundaries, and the boundary between validation and applying gateway mutations. Establish which GitHub permissions or gateway credentials an attacker would need and which trusted checkout executes each script.

Sources and debug artifacts are in `/src`; the pinned gateway validator is on `PATH`. Offline checks include `cargo test --offline --locked --test unit_tests` and `cargo test --offline --locked --lib`. Python workflow helper tests live in `.github/scripts/tests/`; they are part of this repository's security-sensitive implementation. Full lifecycle acceptance requires disposable GitHub/gateway fixtures and is separate from these local suites.

Use temporary repositories and mock/loopback services for reproducers. Do not apply changes to live gateways, modify repository settings, or use real deployment credentials.

Only `ferrum-edge/ferrum-edge-git-forge-ops` is enrolled. Its own workflow implementation is in scope; the separate `.github` organization repository is excluded. The private website and the separate `ferrum-contracts` repository or vendored `contracts/ferrum-contracts/` content are also excluded from enrollment and finding ownership. The retained Edge binary is a fixture, not a second enrollment.
