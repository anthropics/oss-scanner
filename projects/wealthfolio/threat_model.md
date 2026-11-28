# Wealthfolio threat model

## What this project does

Wealthfolio is a local-first personal finance and investment tracker. One Rust
core (`crates/`) runs behind two hosts:

- **Desktop/mobile app** (`apps/tauri`, Tauri v2). Single user. Each profile has
  its own SQLite database, optionally SQLCipher-encrypted, with secrets in the
  OS credential store. The React UI (`apps/frontend`) calls Rust through Tauri
  IPC commands (`apps/tauri/src/commands/`).
- **Self-hosted web server** (`apps/server`, Axum). It serves the same UI and a
  REST API under `/api/v1`, usually on a LAN or on the internet behind a reverse
  proxy. One installation has one owner, who may keep several profiles.
  Authentication is an Argon2id password (`WF_AUTH_PASSWORD_HASH`) that yields
  an HS256 JWT session cookie, OIDC (PKCE plus a `sub`/email allowlist), or
  both. Secrets live in a file vault encrypted with keys derived by HKDF from
  `WF_SECRET_KEY` (`apps/server/src/auth.rs`, `apps/server/src/secrets/`).

The data is sensitive: account balances, transactions, holdings, broker and AI
provider API keys, and sync keys. Design notes for the security-relevant parts
are in `docs/architecture/` (credential storage, database encryption and
backups, profiles and app lock, MCP agent access),
`docs/addons/addon-architecture.md` and `docs/self-host/README.md`. Treat these
documents as statements of intent. Report any place where the code breaks them.

## Attack surfaces to examine (highest priority first)

1. **Unauthenticated HTTP to the web server.** Login (`/api/v1/auth/login`,
   rate-limited), the OIDC login, callback and logout flow
   (`apps/server/src/oidc.rs`: state, nonce, code, ID-token claims,
   `email_verified`, allowlist, redirect URLs), `/api/v1/healthz`,
   `/api/v1/readyz`, static files (`apps/server/src/static_files.rs`) and
   `/mcp`. Check the auth middleware in `apps/server/src/api.rs` for routes that
   skip it.
2. **Cross-site attacks on a signed-in owner of the web server.** CSRF on
   state-changing routes, the CORS policy (`WF_CORS_ALLOW_ORIGINS`,
   `cors_layer`), cookie attributes, the CSP and security headers
   (`application_csp`, `security_headers`), and stored XSS from user-controlled
   or imported strings (account and asset names, notes, CSV fields, provider
   responses) rendered by `apps/frontend`.
3. **Profile isolation.** Profiles separate portfolios and credentials within
   one installation. A profile password protects access through the app on both
   hosts (`crates/core/src/profiles/`, `apps/server/src/profiles.rs`, the
   `x-wf-profile-scope` header, browser grants, SSE scoping). Reaching a locked
   profile's data, keys or secret namespace without its password, or crossing
   from one profile into another, is in scope.
4. **Imported files.** CSV activity import
   (`crates/core/src/activities/csv_parser.rs`), database and portable backup
   restore (`apps/server/src/database_restore.rs`,
   `apps/server/src/api/portable_backups.rs`, `crates/storage-sqlite`), and
   addon ZIP packages (`extract_addon_zip_archive` in
   `crates/core/src/addons/service.rs`). Look for path traversal or zip-slip,
   archive bombs, malformed SQLite or SQLCipher files, and restores that replace
   keys or files outside the target profile.
5. **Third-party addons (untrusted code).** Addons run in a sandboxed iframe
   (`apps/frontend/src/addons/iframe/`, `apps/frontend/addon-sandbox.html`) and
   reach the host over a `postMessage` channel, limited by the permissions the
   user approved. Their network requests go through a host-allowlisted proxy
   (`crates/core/src/addons/network.rs`) that blocks private addresses and
   injects per-addon secrets. In scope: escaping the sandbox, calling host APIs
   without the permission, reading another addon's secrets or data, reaching
   hosts outside the allowlist or private addresses (including through DNS
   rebinding or redirects), and leaking injected credentials.
6. **Responses from remote services.** Market data providers
   (`crates/market-data`), user-defined custom providers
   (`crates/core/src/custom_provider`), Wealthfolio Connect and broker sync
   (`crates/connect`), device sync with end-to-end encryption
   (`crates/device-sync`: X25519, XChaCha20-Poly1305, pairing codes), and AI
   provider responses. Treat every payload as attacker-controlled when it comes
   from a network peer or from another synced device.
7. **AI assistant and MCP agent access** (`crates/ai`, `crates/agent-tools`,
   `crates/wealthfolio-mcp`, `apps/server/src/mcp`, `apps/tauri/src/mcp`).
   Personal access tokens are stored as SHA-256 hashes and carry scopes. The
   desktop endpoint binds to loopback and checks `Origin`. In scope: bypassing a
   scope (for example, a read-only token that writes), using a revoked or
   expired token, leaking tokens through logs or audit records, and prompt
   injection through imported data that makes an agent run a write tool the user
   did not confirm.
8. **Desktop entry points.** Deep links (`wealthfolio://`,
   `https://connect.wealthfolio.app/deeplink`), the updater
   (`apps/tauri/src/updater.rs`), and Tauri capabilities
   (`apps/tauri/capabilities/*.json`). Content from an addon, a provider or a
   deep link must not reach privileged IPC commands. Updates are minisign-signed
   (`plugins.updater.pubkey` in `apps/tauri/tauri.conf.json`). Installing an
   update that the release key did not sign, or a downgrade, is in scope.
9. **Release pipeline.** `.github/workflows/` holds the jobs that sign and
   publish desktop builds and Docker images. Only one thing is in scope here:
   pull-request, issue or branch content that reaches a job with release or
   signing secrets. Action pinning and other CI hardening are not.

## Trust assumptions (not vulnerabilities on their own)

- The authenticated owner of an installation is fully trusted. Owner-configured
  URLs (custom providers, AI base URLs, the OIDC issuer) may point anywhere,
  including private hosts; owner-initiated SSRF is not a finding. Only an addon,
  a remote payload or an unauthenticated party crossing that boundary is.
- These are documented operator choices: loopback binding without auth,
  `WF_AUTH_REQUIRED=false` behind an authenticating proxy,
  `WF_OIDC_ALLOW_ANY=true`, `WF_CORS_ALLOW_ORIGINS=*` when auth is off, and no
  `Host` allowlist on `/mcp` while `WF_MCP_ALLOWED_HOSTS` is unset (the bearer
  token is the boundary).
- Anyone holding the OS account, the server host, the data directory,
  `WF_SECRET_KEY` or the environment is outside the application boundary.
  Unencrypted databases are readable at rest by design; encryption is optional.
- A dependency advisory is only a finding if this code reaches the vulnerable
  path.
- Wrong financial calculations are correctness bugs, not security findings. Do
  not report them.
- An AI answer that is wrong or manipulated is not a finding by itself. It
  becomes one only when it leads to a write, a tool call or data leaving the
  device that the user did not approve.
- Out of scope: `e2e/`, `docs/`, test fixtures, `scripts/`, `packaging/`, and
  everything under `.github/` except the release pipeline case above.

## How to exercise it (offline)

The image contains the checkout at `/src` with `node_modules`, the web build in
`/src/dist`, the server binary at `/src/target/debug/wealthfolio-server`, all
workspace test binaries, and Playwright Chromium and WebKit.
`CONNECT_API_URL=http://test.local` and `CARGO_NET_OFFLINE=true` are set.

Two Rust tests prove that file permissions deny a write. They fail as root by
design, so skip them: `failed_write_preserves_existing_vault` and
`read_only_output_preserves_inputs_and_saved_snapshots`. To focus a run, add a
test-name filter to `--workspace` rather than using `-p <crate>`. A single
package resolves different dependency features and recompiles about 130 crates
first.

```bash
cd /src
SKIP="--skip failed_write_preserves_existing_vault --skip read_only_output_preserves_inputs_and_saved_snapshots"
cargo test --locked --workspace --no-fail-fast -- $SKIP   # about 10 minutes on 2 CPUs
cargo test --locked --workspace -- <test-name-filter>
cargo test --locked -p wealthfolio-ai --features test-utils
pnpm --filter frontend exec vitest run <path>        # frontend unit tests

# Addon iframe sandbox in real browsers, against the prebuilt /src/dist
pnpm --filter frontend preview --host 127.0.0.1 --port 4174 --strictPort &
pnpm exec playwright test --config playwright.addon-sandbox.config.ts --project=chromium --project=webkit
```

To run the web server with authentication on loopback:

```bash
mkdir -p /tmp/wf
export WF_DATA_DIR=/tmp/wf WF_LISTEN_ADDR=127.0.0.1:8088 WF_STATIC_DIR=/src/dist \
       WF_SECRET_KEY="$(openssl rand -base64 32)" WF_CORS_ALLOW_ORIGINS=http://127.0.0.1:8088 \
       WF_AUTH_PASSWORD_HASH="$(printf 'test-password' | argon2 wealthfolio-salt -id -e)"
/src/target/debug/wealthfolio-server &
curl -s -c /tmp/jar -H 'content-type: application/json' -d '{"password":"test-password"}' \
     http://127.0.0.1:8088/api/v1/auth/login
```

Set `WF_MCP_ENABLED=true` to expose `/mcp`; tokens are created through
`/api/v1/agent-access/tokens`. The Playwright specs in `e2e/` show how to seed
accounts and activities through `/api/v1`. Market data and Connect calls fail
offline, which is expected. The desktop app cannot run headless here. Exercise
its IPC commands through the shared services they wrap in `crates/core` and
their unit tests.

## How we rate severity

- **Critical:** unauthenticated remote code execution on the server;
  unauthenticated read or write of financial data or secrets (auth, OIDC or
  session bypass, JWT forgery); decrypting the vault, a SQLCipher database or
  sync payloads without the key; an addon escaping the sandbox to code execution
  or privileged IPC on desktop; installing an unsigned or downgraded desktop
  update; untrusted content reaching release or signing secrets.
- **High:** CSRF that performs writes; stored XSS that runs on the app origin as
  the owner; an addon reading another addon's secrets, using undeclared host
  APIs, or reaching private networks through the proxy; zip-slip or path
  traversal outside the data directory from an imported file or addon; MCP scope
  or revocation bypass; OIDC allowlist bypass; bypassing a profile password or
  reading across profiles.
- **Medium:** unauthenticated denial of service from a single request or small
  payload (crash, unbounded memory or disk); secrets or financial data in logs
  or error responses; open redirects in the auth flow; a malicious peer or
  provider corrupting stored data beyond the values it supplies.
- **Low:** missing hardening (headers, cookie flags) without a demonstrated
  exploit; issues that need the owner's own configuration to be hostile.

## What a report should include

Reports reach us without human review, so keep the signal high. Medium and
higher findings need a working reproducer; without one, label the finding
unconfirmed. Put all Low findings in a single combined report.

Name the host (desktop, server, or both), the commit, and the configuration
needed (environment variables, enabled features, whether auth is on). Give the
attacker's position (unauthenticated network, cross-site page, addon, remote
provider, synced device). Include a minimal offline reproducer: a `curl`
sequence against the local server, or a failing Rust or Vitest test next to the
affected code. Patches should follow `AGENTS.md`: business logic in the owning
crate, thin handlers and commands, no `unwrap()` or `panic!` outside tests, and
a regression test. When one root cause in a shared crate affects both hosts,
file one report and list both entry points.
