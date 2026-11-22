# Thunderbolt threat model

## What Thunderbolt is

Thunderbolt is an open-source AI chat client. The React app runs in a browser and in a Tauri shell on desktop and mobile. Each device keeps the user's data in a local SQLite database and syncs it with the user's other devices through PowerSync and an Elysia API on Bun (`backend/`). Users bring their own model keys or use models the deployment manages, connect MCP servers, and can hand a chat to an external coding agent over ACP. A terminal agent (`cli/`) ships as a single binary and can serve agents to the app through a bridge.

Deployment modes, all built from this repository:

- A hosted service; the apps link to `app.thunderbolt.io` (`src-tauri/tauri.conf.json`). The backend default, `AUTH_MODE=consumer`, is email-code sign-in behind a waitlist.
- Self-hosted Docker Compose (`deploy/docker-compose.yml`), Helm (`deploy/k8s/`) and Pulumi for AWS (`deploy/pulumi/`). They ship Keycloak and default to OIDC; SAML is also supported (`docs/self-hosting/README.md`).
- Tauri builds for macOS, Windows, Linux, iOS and Android (`src-tauri/`), pointed at a backend when they are built.
- The CLI, which uses managed inference through a device-grant session or calls providers with a local key.

The application has no organisation object and no admin role. A deployment belongs to one operator, and the unit of isolation between people is the user account.

## Trust boundaries and where untrusted input enters

### Clients of the backend

Every route sits under `/v1` in `backend/src/index.ts`. `docs/internals/architecture/backend-api-surface.md` lists each route with its auth mode, rate limit and version-gate exemption. Treat all request input as hostile. Without a session a caller reaches Better Auth (`/v1/api/auth/*`), `POST /v1/waitlist/join`, `/v1/config`, `/v1/health`, the PostHog relay, the Mini App registry, the desktop SSO bridge and, when enabled, anonymous sign-in and the CLI device grant.

The credential flows are in `backend/src/auth/`: email OTP bound to a challenge token, OIDC and SAML with a desktop loopback bridge (`sso-desktop-callback.ts`), the RFC 8628 device grant with CLI device binding (`backend/src/api/account.ts`), personal access tokens, and the WebSocket subprotocol bearer (`ws-bearer-auth.ts`). Apart from the monitoring token on `/v1/health` (`backend/src/api/health.ts`) and the debug-transcript intake's own client key (`backend/src/api/debug-transcripts-intake.ts`), every credential resolves to a Better Auth session, and the bearer's HMAC signature is required (`backend/docs/authentication.md`).

### One account against another

Any signed-in user, anonymous sessions included, may try to reach another account's data.

- Reads are isolated by the PowerSync sync rules, where every bucket filters on the `user_id` in the sync JWT. The rules exist in three copies: `powersync-service/config/config.yaml`, `deploy/config/powersync-config.yaml` and `deploy/k8s/templates/configmaps.yaml`.
- Writes go through `applyOperation` in `backend/src/dal/powersync.ts`, behind `PUT /v1/powersync/upload` (`backend/src/api/powersync.ts`). It takes the user from the session, strips client-supplied `id`, `user_id` and server-managed columns, and scopes every write by `user_id`. For tables with a global `id` primary key that scope is the only cross-account guard (`docs/internals/architecture/powersync-upload-authorization.md`).
- Device and key routes are in `backend/src/api/encryption.ts`, `backend/src/api/account.ts`, `backend/src/dal/devices.ts` and `backend/src/dal/encryption.ts`. They act only as the device bound to the session.
- Managed inference is admitted and billed per user (`backend/src/inference/`, `backend/src/tinfoil/routes.ts`). Mini App tokens are signed per app (`backend/src/api/mini-apps.ts`).
- Managed agents call upstreams with credentials the deployment holds, on behalf of the signed-in user: the hosted agent (`backend/src/hosted-agent/`) and Haystack (`backend/src/haystack/`, see `docs/internals/architecture/acp-agents.md`).

### The server and its operator

End-to-end encryption is always on in current builds (`docs/internals/architecture/e2e-encryption.md`). The client encrypts only the columns listed in `encryptedColumnsMap` (`shared/e2ee-types.ts`). For those the server should hold ciphertext and wrapped keys, and nothing that opens them. Ids, timestamps and all other columns are readable server-side by design.

`docs/internals/architecture/e2ee-threat-model.md` is the authority here. It defines adversaries A1 to A10 and claims C1 to C15; please cite them. The headline claim is about A2, a malicious or breached server that can return arbitrary responses. Client code is in `src/crypto/`, `src/db/encryption/`, `src/services/encryption.ts` and `src/db/powersync/`; once an account is on encryption scheme version 2, the server also rejects plaintext in mapped columns (`backend/src/api/powersync.ts`). On the web build the operator also serves the JavaScript, so an attack that consists of shipping a modified bundle is out of scope (C11).

A self-hosted build can pin an organisational escrow key (`VITE_ORG_ESCROW_PUBLIC_KEY`, see "Organizational key escrow" in `docs/self-hosting/configuration.md`). Whoever holds the matching private key can then recover account keys; that is adversary A8 and is by design. A finding here is a way to redirect, suppress or silently enable escrow, which C11 rules out.

Private chats carry a second promise. A thread bound to a confidential model is sealed by the client to an attested Tinfoil enclave, and the backend relays it without seeing either direction (`docs/internals/architecture/managed-inference.md`). The client must ask before such a thread moves to an agent that would send it elsewhere (`src/chats/private-thread.ts`).

### Hostile content shown in the client

Model output is untrusted, and so is everything the model read: web pages, MCP tool results, attached files, link-preview metadata and messages from embedded Mini Apps. A script in the app origin can read the session bearer and the ACP bridge secret from `localStorage`, and the decrypted local database (`docs/internals/architecture/client-auth-and-session.md`). Under Tauri it can also call every IPC command the main window is granted.

- Chat text renders through `react-markdown` and the widgets in `src/widgets/`.
- HTML artifacts render in a `sandbox="allow-scripts"` iframe without `allow-same-origin`, under a CSP that blocks fetch, XHR, WebSocket and external resources (`src/artifacts/harness.ts`, `src/components/artifact/sandboxed-html-frame.tsx`). A script can still navigate its own frame, which sends a GET; see the trade-offs below. DOCX previews use a fully sandboxed `srcdoc` frame (`src/components/chat/docx-thumbnail.tsx`).
- Mini Apps are cross-origin iframes. The host checks origin and source on every message, parses it with zod, and asks before running a tool the app does not mark read-only (`docs/internals/architecture/mini-apps.md`).
- MCP OAuth callbacks are checked in `src/lib/mcp-auth/callback-validation.ts`. Deep links and magic links arrive through `src/hooks/use-deep-link-listener.ts` and `src/components/magic-link-verify.tsx`.

Prompt injection counts only when it gets past a control the product enforces: the containment above, the private-chat guard, Mini App write approval or the CLI permission modes.

### Requests the server makes for users

The universal proxy (`ALL /v1/proxy`, `WS /v1/proxy/ws`) fetches a URL the client names (`backend/src/proxy/`). For HTTP it resolves the hostname, refuses private and reserved ranges, connects to the pinned address, and repeats this on every redirect hop (`backend/src/utils/url-validation.ts`, `shared/ip-classification.ts`). It drops `Authorization` when a redirect leaves the first origin, drops `Set-Cookie`, and forces `Content-Security-Policy: sandbox` on responses served from Thunderbolt's origin (`docs/internals/architecture/universal-proxy.md`). Link previews (`backend/src/api/preview.ts`) use the same module. The confidential route accepts a client-named enclave only on HTTPS `tinfoil.sh` hosts.

### Desktop and mobile shell

The webview is held to `src-tauri/capabilities/default.json` and the CSP in `src-tauri/tauri.conf.json`. Custom commands are in `src-tauri/src/commands.rs`, the OAuth loopback listener in `oauth_server.rs`, and the CLI installer in `cli_installer.rs`. The updater checks a minisign signature against the key pinned in `tauri.conf.json`. The desktop side panel opens arbitrary web pages (`docs/features/webview.md`); they must not reach IPC.

### CLI and agent bridges

Each connection a bridge admits spawns a coding agent on the host (`cli/README.md`). Arguments after `--` choose the spawned command, so a bridge can also run an external agent or MCP server; the jail and permission modes below cover only Thunderbolt's own agent. The `wss` bridge listens on loopback and checks the path, `Origin` and a 256-bit token. The iroh bridge admits a NodeId only from the account allowlist (`GET /v1/devices/allowlist`) or the manual allowlist file (`cli/src/commands/bridge.ts`, `cli/src/iroh/`). The browser dials iroh through a relay-only wasm client from `crates/thunderbolt-acp-client`.

A served agent (`acp serve`) has no `bash`, and its file tools stay inside its launch directory (`cli/src/agent/workspace-jail.ts`). In the local agent, `ask` prompts before `bash`, `write` and `edit`, `accept-edits` allows writes and edits but still asks before `bash`, and `read-only` blocks all three (`cli/src/agent/permissions.ts`). `yolo` allows everything by design. `webfetch` refuses private addresses (`cli/src/agent/webfetch.ts`). In the app, the built-in agent's files stay in a per-thread workspace (`shared/agent-core/browser-env/workspace-jail.ts`).

## Components that matter most and least

Most, roughly in order:

1. Sync authorization: `backend/src/dal/powersync.ts`, `backend/src/api/powersync.ts`, `backend/src/db/powersync-schema.ts` and the sync rules.
2. Sign-in and sessions (`backend/src/auth/`), and the device and key routes.
3. The universal proxy and its SSRF checks.
4. The E2EE client code and `shared/e2ee-types.ts`.
5. Client code that renders untrusted content or handles callbacks.
6. The CLI bridges, and the Tauri commands and capabilities.

Less: metering, the debug-transcript relay, voice, search, and the PostHog relay to a fixed host. Least: `web/` (static Astro site), the `miniapps/` samples, `docs/`, `scripts/` and `.github/`. Files in `deploy/` matter where a shipped default is unsafe and not documented as an evaluation default.

## How to exercise it

The checkout is at `/src` with dependencies installed and no network. Run `bun run test` for `src/` and the `shared/` roots (happy-dom), `bun run test:backend` for the API (in-memory PGlite, no Postgres), `bun run test:agent-core`, `bun run test:agent-core:browser` (Chromium and WebKit through Playwright; on an arm64 host WebKit's OPFS case falls back to in-memory storage, while it passes on x86 in CI), `cd cli && bun run test`, and `cargo test --offline` in `src-tauri/` and `crates/thunderbolt-acp-client/`. A bare `bun test` at the repository root hangs on tests that wait for services. The backend pins an older Bun than the rest of the repository; the image picks it whenever the working directory is under `backend/`, so run backend commands from there (`cd backend && bun test <file>`) rather than with `--cwd`.

The live app also runs offline in this image. Start three processes:

```
cd /src && bun -e "await (await import('./e2e/fake-provider.ts')).createFakeProvider(9878)" &
cd /src/backend && DATABASE_DRIVER=pglite DATABASE_URL=/tmp/tb-pglite BETTER_AUTH_SECRET=offline-check-secret-at-least-32-characters BETTER_AUTH_URL=http://localhost:8000 WAITLIST_AUTO_APPROVE_DOMAINS=example.test RATE_LIMIT_ENABLED=false ANTHROPIC_API_KEY=fake ANTHROPIC_BASE_URL=http://localhost:9878 POWERSYNC_JWT_SECRET=powersync-dev-secret POWERSYNC_JWT_KID=powersync-dev bun src/index.ts &
cd /src && VITE_SKIP_ONBOARDING=true bun run dev &
```

Open `http://localhost:1420` in Playwright's Chromium and sign in with any `@example.test` address. The backend log prints the code after `OTP code:`, and typing all eight digits submits the form. Pick an Anthropic model such as Opus 5.5; the backend routes it to the fake provider. Private (Tinfoil) models and sync need the network. Drop `RATE_LIMIT_ENABLED=false` to test rate limits.

For a reproducer against real routes, use `createTestApp` from `backend/src/test-utils/e2e.ts`. It builds the real app, signs a user in through the real OTP flow and returns a signed bearer. It takes an injected `fetchFn` and `dnsLookup`; `e2eDnsLookup` resolves `private.test` to `192.168.1.1`. Good models are `backend/src/proxy/e2e.test.ts` and the cross-user cases in `backend/src/dal/powersync.test.ts`. The Playwright specs in `e2e/`, including the E2EE attacks in `e2e/e2ee/attacks/`, need a running stack and will not run here. Unit tests use happy-dom, which does not enforce iframe sandboxing or CSP; to show a sandbox or CSP finding, use a standalone Playwright script against the installed Chromium or WebKit, as `scripts/agent-core-browser-check.ts` does.

## How we rate severity

This is the maintainers' current view. Rate by what the attacker gains against the promises above and by the weakest position they need.

Critical:

- Reading another account's content, or writing any of its data, through any backend path.
- A usable session for another user without their credential: bypassing the OTP challenge binding, making OTP guessing practical, an SSO or desktop-bridge flaw that hands the attacker a token, approving a CLI device grant without the user, or a forged bearer the server accepts.
- Getting a device trusted, or obtaining an account's keyring or Account Key, without approval from a trusted device or the recovery phrase.
- A passive or malicious server (A1, A2) obtaining plaintext of a mapped column, or a key that opens one, from an established device (C1, C2).
- Code execution on the backend host.
- Code execution on a user's machine without consent: past the bridge checks, out of a served agent's workspace jail, from web content into Tauri IPC (side panel included), or past the updater signature.
- Script execution in the app origin when the victim only views a model reply or a link preview in a default configuration.

High:

- A request through the proxy, the WebSocket relay, link previews or the Tinfoil route that reaches a private, loopback, link-local or reserved address. Critical when the target returns credentials, such as a cloud metadata service on the AWS deployment.
- Reading only another account's metadata, such as ids, timestamps or row counts, with no content.
- Script execution in the app origin after one more ordinary action, such as opening an attachment or clicking a link.
- Escaping the artifact sandbox to the parent origin, its storage, or the network.
- Private-chat content reaching the backend or a third party without the user's consent.
- The proxy sending the session bearer or the upstream credential to another origin, or a proxied response running as a same-origin document.
- A revoked device that can still sync, fetch keys or authorize a trust operation (C5, C14).
- An E2EE integrity break that needs an active server and discloses nothing, such as moving ciphertext between cells or forcing a downgrade (C3, C4).
- A served CLI agent touching files outside its workspace, or a gated tool call running in `ask` or `read-only` mode without the prompt.
- Charging managed inference to another account.

Medium:

- Getting past a rate limit or one's own inference quota.
- Crossing the in-browser agent's per-thread workspace jail.
- Secrets or message content in logs, telemetry or error bodies. Content from a mapped column is a C1 break, rated as above. A reusable credential (a session bearer, a personal access token, a provider key) is rated by what it unlocks.
- A spoofed CLI permission prompt, for example through terminal escape sequences.
- Account enumeration through sign-in or waitlist responses.

Low:

- Denial of service, such as one user wedging their own sync queue. One unauthenticated request, or a handful, that takes the backend or sync service down for everyone is high.
- Hardening with no demonstrated path.

A finding that needs a documented setting (SSO, anonymous sign-in, Mini Apps, `CONFIDENTIAL_API_KEYS_ENABLED`) keeps its rating; name the setting. One that needs a dev-only or test-only setting is out of scope.

## Known trade-offs that are not findings

Report one of these only if your finding goes further.

- The "Known and accepted" section of `e2ee-threat-model.md` and the residuals under each claim, including the plaintext local database, the AAD-free `"v1"` key slot and trust on first use for new devices.
- The session bearer and the iroh client secret are kept in plaintext `localStorage`.
- A script in an artifact can navigate its own frame (`docs/internals/architecture/artifacts.md`).
- Mini App write approval trusts the app's own `readOnlyHint`; it guards against a confused model, and a hostile app can bypass it.
- Usage receipts do not sign token counts, so a client can under-report its own usage.
- The CLI binary and its checksum come from the same host (`cli/README.md`).
- The OAuth loopback listener accepts the first connection; PKCE protects the code.

## Out of scope

- Published evaluation defaults: the secrets and credentials in `deploy/docker-compose.yml`, the Keycloak admin login, the demo user and realms (`deploy/config/keycloak-realm.json`, `backend/docs/mozilla-realm.json`), and every other value `docs/self-hosting/README.md` tells operators to replace.
- Fields outside `encryptedColumnsMap`, and rows synced in plaintext before a deployment moved to always-on encryption (`SECURITY.md`).
- Misconfiguration the docs warn against, such as `RATE_LIMIT_ENABLED=false` or a missing `TRUSTED_PROXY` behind a proxy.
- Third-party services: model providers, MCP servers, identity providers, Tinfoil, Exa, PostHog and iroh relays. Thunderbolt's own code that talks to them stays in scope.
- Dev and test code: `src/devtools/`, routes guarded by `import.meta.env.DEV` in `src/app.tsx`, `src/settings/dev-settings.tsx`, `backend/src/test-utils/`, `e2e/`, test fixtures, the `NODE_ENV=test` proxy allowance (`isAllowedTestProxyTarget`), and the `native_fetch` Cargo feature, which no shipped build enables.
- Choices the user made: CLI `yolo` mode, MCP servers and agents they added, and what their own provider key can do.
- An attacker who already controls the user's device or operating system.

## Reports and patches

- Give the commit, the deployment mode (hosted, self-hosted OIDC or SAML, a Tauri platform, or the CLI) and any non-default setting. For E2EE, say whether the account is on the v2 keyring and name the adversary and claim ids.
- One root cause per report, even if it shows up in several places; list the other call sites.
- Include a reproducer that fails before the fix and the command that runs it: a `bun test` file next to the source as `<file>.test.ts`, a backend test on `createTestApp`, or a `cargo test`.
- Patches follow `AGENTS.md`: TypeScript without `any`, `type` over `interface`, arrow functions, early returns, no swallowed errors, soft deletes in the frontend. Fix the shared code once and add a regression test beside it.
