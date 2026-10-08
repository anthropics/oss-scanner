# Ferrum Anvil audit scope

Ferrum Anvil is a Rust API testing application with a Tauri desktop shell and React renderer. Review imported request collections and schemas, protocol responses, request execution and redirects, secret storage and redaction, filesystem portability, and the renderer/native command boundary. Imported files and remote responses are untrusted. Document whether a reproducer requires a user to import a file, follow a link, or grant a capability.

Sources, Cargo caches, the compiled Rust workspace, frontend dependencies, and frontend output remain in `/src` and the toolchain directories. Run `cargo test --offline --locked --workspace --exclude anvil-desktop --no-fail-fast`, `cargo test --offline --locked -p anvil-desktop --lib`, and `npm --prefix apps/desktop test` without fetching dependencies. Linux keychain tests need a private D-Bus/Secret Service session; graphical or WebDriver E2E suites need additional runtime setup and are not claimed as covered by a headless unit run.

Use disposable fixtures and local loopback endpoints. Do not contact live APIs, read real keychain entries, or use real credentials in reproducers.

Only `ferrum-edge/ferrum-anvil` is enrolled. The `.github` organization repository, the private website repository, and the separate `ferrum-contracts` repository or vendored `contracts/ferrum-contracts/` content are excluded from enrollment and finding ownership. Contract fixtures may remain as build/test dependencies.
