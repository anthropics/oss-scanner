# RTL (Ride The Lightning) threat model

RTL is a self-hosted web UI for operating a Lightning node: an Angular single-page frontend
and a Node.js/Express backend, both in TypeScript. It supports three Lightning
implementations, LND, Core Lightning (CLN) and Eclair, and is bundled by BTCPay Server,
Umbrel, Start9, RaspiBlitz and other node distributions. The backend holds node credentials
(LND macaroons, CLN runes, Eclair API passwords) and proxies the UI's requests to the node's
REST/WebSocket API. A flaw in RTL can therefore let an attacker act on the node, including
sending funds, closing channels or exposing credentials.

RTL has a single operator account: one password (optionally with TOTP 2FA), or single
sign-on through a host application. Every authenticated session has full control of every
node configured in that RTL instance. There are no lower-privileged users.

## Scope and priorities

Production source is in `server/` (backend), `src/app/` (frontend) and `rtl.js` (entry
point). The code is organised as parallel `lnd/`, `cln/`, `eclair/` and `shared/` subtrees in
each of `server/controllers/`, `server/routes/` and `src/app/`; the same weakness often
appears in more than one implementation, so check the sibling subtrees and report them
together.

Prioritise:

- Authentication and sessions: `server/utils/authCheck.ts`,
  `server/controllers/shared/authenticate.ts` (password, 2FA, JWT issue and verification,
  failed-login lockout and its client-address handling with `trustedProxies`), the session
  cookie, and logout and password reset.
- Single sign-on (`SSO.rtlSSO`): RTL reads a one-time value from a cookie file written by the
  host application (BTCPay Server) and accepts it in place of the password. BTCPay serves
  RTL under a sub-path (`/rtl`) through a reverse proxy.
- CSRF and cross-origin protection: `server/utils/csrf.ts`, `server/utils/cors.ts`, the
  `XSRF-TOKEN` cookie minted by the catch-all handler in `server/utils/app.ts`, and the
  WebSocket upgrade check (`verifyWSUser`, `server/utils/webSocketServer.ts`).
- Any path from an unauthenticated request to a node action, node data or credentials:
  routes missing `isAuthenticated`, the routes that are deliberately public (login, logout,
  application settings, currency rates), and the static/catch-all handlers.
- Exposure of credentials or config contents (macaroons, runes, passwords, `secret2FA`,
  config file paths and contents, channel backups) in API responses, logs, error messages
  or WebSocket messages.
- Config and file handling in `server/controllers/shared/RTLConf.ts` and
  `server/utils/config.ts`: reading or writing files outside what RTL should touch, path
  traversal, and settings updates that change security properties.
- Stored XSS in the frontend from data that originates **outside** the operator's control
  (see below), especially through the raw-HTML sinks (`innerHTML`,
  `bypassSecurityTrust*`) in `src/app/`.
- Request construction toward the node (`server/utils/request.ts` and the controllers):
  injection of path segments or query parameters into the node API URL from API input.

`frontend/` and `backend/` are committed build output of `src/` and `server/`
(CI fails if they differ). Review the sources, not the generated bundles. `test/`,
`src/**/*.spec.ts` and `src/app/shared/test-helpers/` are tests. `docker/` is a regtest
development fixture whose credentials are throwaway and intentionally committed: out of
scope. Third-party npm packages are out of scope unless you show that RTL reaches the
vulnerable code with attacker-controlled input.

## Attackers and trust boundaries

Treat as adversarial:

- Unauthenticated network clients that can reach RTL's port, directly or through a reverse
  proxy.
- Other web origins in the operator's browser (CSRF, cross-origin reads).
- **Data from the Lightning network and other remote parties**, which RTL displays: node
  aliases, colours and addresses from the gossip graph, peer and channel fields, invoice and
  offer descriptions, payment metadata and keysend data, and responses from block
  explorers and exchange-rate services.
- Request headers such as `X-Forwarded-For`, which are trusted only from addresses listed in
  `trustedProxies`.

Trusted:

- The authenticated operator. An authenticated session is meant to have full control of the
  node, so showing that it can do something powerful is not a vulnerability.
- Configuration the operator writes (`RTL-Config.json`, `RTL.conf`, environment variables),
  and values the operator types into the UI for their own use. Self-XSS or a bounded
  misbehaviour from operator-entered values is not a vulnerability.
- The host, the Lightning node and its API, the host application in SSO mode (it writes the
  cookie file), and the reverse proxy in front of RTL.

By design, not vulnerabilities:

- `disableAuth`: RTL can run with authentication off for vendors that put their own
  authentication in front of it.
- Plain HTTP: TLS is terminated by a reverse proxy or the distribution. Cookies are not
  marked `Secure` for this reason.
- Denial of service that requires an authenticated session.

## Build and offline reproduction

The image contains the source tree in `/src`, all npm dependencies (including dev
dependencies), and `backend/` freshly compiled from `server/`. There is no Lightning node
and no browser in the image.

- Recompile after changing `server/`: `npm run buildbackend`.
- Backend regression tests: `npm run testbackend` (`node --test test/backend/*.test.mjs`),
  running against the compiled `backend/`. One test: `node --test test/backend/<file>.test.mjs`.
  Run as root, one test fails: "updateApplicationSettings leaves the runtime config untouched
  when the file write fails" relies on file permissions that root ignores. It passes as the
  `node` user (`su node -s /bin/bash -c '...'`) and is not a finding.
- Write reproducers as `node:test` files in `test/backend/` in the style of the existing ones:
  they import controllers and utilities from `backend/`, set `Common.appConfig` and the
  selected node directly, and fake the node's REST API with a local HTTP server or stubs
  instead of a real node.
- RTL can also be started end to end: put an `RTL-Config.json` (see
  `Sample-RTL-Config.json`) whose node `lnServerUrl` points at a local fake node API in a
  directory, run `RTL_CONFIG_PATH=<dir> node rtl.js`, and drive it with `curl` on
  `http://127.0.0.1:3000/rtl/api/...`. `GET /rtl/` sets the `_csrf` and `XSRF-TOKEN`
  cookies; every POST, including login, must send the cookies back and echo `XSRF-TOKEN` in
  an `X-XSRF-TOKEN` header. Log in with `POST /rtl/api/authenticate` and
  `{"authenticateWith":"PASSWORD","authenticationValue":"<sha256 hex of the password>"}`
  (the UI hashes before sending), then send the returned token as
  `Authorization: Bearer <token>`.

## Severity

- **Critical**: an unauthenticated network attacker, or a malicious web page visited by the
  logged-in operator, can move funds, open or close channels, change node settings, or
  obtain node credentials (macaroon, rune, API password) or the RTL password or 2FA secret.
  Authentication or SSO bypass is critical.
- **High**: stored XSS from Lightning-network-controlled data (an alias, an invoice or offer
  description, a peer field) that runs in the operator's session, since it can drive the
  node; CSRF on any state-changing endpoint; unauthenticated disclosure of node data such as
  balances, channels or payment history; reading or writing arbitrary files.
- **Medium**: bypass of the login lockout or 2FA rate limits without a full bypass;
  unauthenticated disclosure of configuration that is not a credential; open redirects;
  unauthenticated denial of service that takes the RTL instance down.
- **Low**: hardening gaps without a demonstrated exploit, and issues that need an unusual
  configuration or a position on the operator's machine.
- Not a vulnerability: anything that requires an authenticated session, operator-entered
  configuration or input, or control of the node, the host or the reverse proxy, unless it
  crosses into something the operator did not intend (for example, leaking credentials to a
  third party).

Rate by what is demonstrated, not what is theoretically possible, and state the deployment
assumptions (standalone, behind a reverse proxy, BTCPay SSO) the finding needs.

## Reports and patches

For each report include: the affected commit and source locations, the Lightning
implementation(s) affected, the required configuration and whether a session is needed, the
entry point (route, WebSocket message or rendered field), a self-contained reproducer, and
the concrete impact. Group symptoms with one root cause, and the same flaw across the
LND/CLN/Eclair subtrees, into one report.

Patches should change `server/` or `src/` only (never the generated `frontend/` or
`backend/`), follow the surrounding code style, add no new dependencies, and come with a
focused regression test in `test/backend/` where the fix is in the backend.

Send reports only to the configured security contact. Do not open public issues or publish
unpatched reproduction details.
