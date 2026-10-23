# Threat model: Zephyr

## What this project does and where untrusted input enters

Zephyr is a desktop GUI client for the Mihomo (Clash Meta) proxy core, built with Tauri 2: a Rust backend (`apps/desktop/src-tauri` plus the workspace crates under `crates/`) and a JavaScript frontend that runs in the system WebView (`apps/desktop/src`). The app downloads, verifies and launches the Mihomo core process, manages its YAML configuration, and can route the whole machine's traffic through the proxy (system proxy settings, or a TUN virtual interface that needs elevated privileges). Users routinely point it at remote subscription services they do not control, so treat everything below as attacker-controlled:

- **Subscription and profile data.** Subscription URLs are fetched over the network (http/https only) and the responses are parsed as Mihomo YAML profiles; subscriptions can also arrive as local files, QR codes, clipboard text and drag-and-drop. Payloads may be base64-encoded. A malicious or compromised subscription provider fully controls this input.
- **Remote rules and overrides.** Prism rule files (`.prism.yaml`), config overrides and rule-library entries can be imported from URLs and are then applied to the effective proxy configuration.
- **JavaScript for the Prism script engine.** Scripts supplied by users or imported with rules run in a sandboxed JS engine with explicit resource limits and permission controls (network, filesystem, child processes, workers). The sandbox boundary is a security boundary.
- **Plugins.** A plugin system discovers and loads plugins with lifecycle hooks and permission checks.
- **The Mihomo core update path.** The app checks for new core versions (racing the GitHub REST API against the Atom feed), downloads the core binary for the detected CPU tier, and caches SHA-256 digests of it. The same dual-source mechanism checks for app updates.
- **Backup archives.** Configuration backup/restore imports ZIP files (with a manifest carrying SHA-256 hashes, and size/ratio limits) and commits them transactionally.
- **Core and network output.** Everything the Mihomo core's controller API returns (connections, traffic, logs, provider state) is rendered in the WebView UI, as are profile and node names that originate from remote subscriptions.
- **Local files.** `settings.json` (versioned schema with migrations), the Prism KV store and persisted proxy-node selections are read back at startup.

## Components that matter most / least

Most important, in roughly this order:

- The **core download/verification/update path** and anything that decides which binary gets executed, including the CPU-tier asset selection and the digest cache.
- The **Prism script sandbox** (`clash-prism-*` crates): escapes, permission-check bypasses, and limit enforcement (`script_set_limits`).
- **Subscription/profile ingestion**: YAML parsing, base64 decoding, URL validation, and the hand-off to the core (configs are pre-checked with `mihomo -t` before the core starts; a way around that check matters).
- The **Tauri IPC command surface**: any command the WebView can invoke that reads/writes files, spawns processes, changes system proxy/TUN state or edits configuration. WebView XSS is only interesting when it reaches this surface — but then it is very interesting.
- **Privileged operations**: TUN setup/teardown, system proxy changes (which have an ownership guard with tamper detection), and OS network tuning apply/revert.
- **Backup ZIP import**: path traversal or manifest/hash verification gaps on restore.

Less critical: theming/design tokens, i18n, traffic charts and other display-only frontend code; the landing page (`landing.html`).

Out of scope: the Mihomo core binary itself (an upstream third-party program that Zephyr downloads and runs but does not build from this repository), and the vendored contents of `Cargo.lock`/`pnpm-lock.yaml` as standalone findings — dependency issues matter only where Zephyr's own code uses the dependency unsafely.

## How to exercise it

The Dockerfile builds the full Rust workspace with debug info and runs both test suites the way CI does:

- `cargo test --workspace --locked` — Rust unit/integration tests, including 68 `insta` snapshot scenarios covering input-handling contracts (name sanitising, URL masking, version parsing, proxy-env formatting and similar).
- `pnpm -r test` — frontend tests under vitest.

The desktop binary lands in `target/debug/` (the Tauri app needs a display and a WebKitGTK runtime to use interactively, so the test suites are the practical exercise surface). A checkout also contains the project's own security tooling configuration (`.semgrep.yml`, `deny.toml`, `osv-scanner.toml`) and an `AUDIT_REPORT.md` summarising a previous audit.

## How you rate severity

- **Critical**: remote code execution in the app's context — a malicious subscription, rule file, script or backup archive that ends in code execution; a Prism sandbox escape with host access; anything that defeats the integrity check on the downloaded core binary (that is supply-chain RCE against every user).
- **High**: privilege escalation through the TUN/system-proxy paths; silent redirection of a user's traffic to attacker-chosen proxies or DNS (traffic interception breaks the product's core promise); WebView XSS that can reach the Tauri IPC surface; path traversal on backup restore that writes outside the config directory.
- **Medium**: leakage of subscription URLs or tokens (they are credentials) into logs or error messages; crashes or core restart loops a malicious profile can trigger; settings/KV corruption on malformed local data.
- **Low**: purely cosmetic UI issues, denial of service that needs an already-privileged local attacker, and findings in display-only code with no path to the IPC surface.

Only the latest stable release receives security fixes; `main` is the development line that feeds it.

## Anything to leave alone

- The downloaded Mihomo core binary (see above) and the packaging/distribution plumbing under `.github/workflows` for AUR/Scoop/winget.
- Generated files: `apps/desktop/src/cm6.bundle.js`, the design-token CSS and `src/_shared/` are build outputs regenerated by the Dockerfile; report issues in their sources instead.
