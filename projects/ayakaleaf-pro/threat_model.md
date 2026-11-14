# Threat model: Ayakaleaf Pro

## What it is and where untrusted input enters

An enhanced Overleaf Community Edition (CE): a self-hosted, multi-user LaTeX editor. Our additions are modules under
`services/web/modules/`. Users of an instance do not trust each other.

Untrusted input: HTTP requests to `web` (anonymous and logged in), real-time edits over Socket.IO, project content
(LaTeX, uploads, zips, linked URLs) compiled or converted in `clsi`, SSO responses (LDAP, SAML, OIDC), GitHub /
GitLab / Dropbox / Zotero / Mendeley API data, git-bridge pushes, and MCP / AI assistant requests.

Internal services listen on 127.0.0.1 and trust each other; MongoDB and Redis are trusted.

## Components that matter most / least

Most: `authentication`, `login-register`, `user-activate`, `oauth2-server`, `mcp-server`, `workbench`,
`error-assistant`, `github-sync`, `gitlab-sync`, `dropbox`, `git-bridge`, `tpr-webmodule`, `admin-tools`,
`template-gallery`, and compiles/conversions in `services/clsi`.

Least: `python-runner` (runs in the browser via Pyodide), `symbol-palette`, `learn`.

Out of scope: `develop/`, tests, `doc/`, `.github/`. Bugs in unmodified CE code are welcome; say so in the report.

## How to exercise it

- `ayakaleaf-test-services`: start MongoDB and Redis. `ayakaleaf-start`: start everything; site on http://127.0.0.1/,
  logs in `/var/log/overleaf/`.
- Admin user: `cd /overleaf/services/web && node modules/server-ce-scripts/scripts/create-user.mjs --admin --email=a@example.com`
- Unit tests (after `ayakaleaf-test-services`): `cd /overleaf/services/web && env -u OVERLEAF_CONFIG NODE_ENV=test MONGO_URL=mongodb://127.0.0.1/test-overleaf yarn run test:unit`.
  Tests of SaaS-only features (subscriptions, managed groups, SheerID) fail in CE builds; ignore them.
- External services are offline; mock them on 127.0.0.1. Sandboxed compiles need Docker and are unavailable here.

## How you rate severity

- **Critical**: unauthenticated RCE; auth bypass or account takeover; compile/conversion escaping its project.
- **High**: access to other users' projects without permission; privilege escalation to admin; theft of stored
  third-party tokens; SSRF to internal services; stored XSS.
- **Medium**: reflected XSS, CSRF, info leaks (emails, project names), open redirects, unauthenticated DoS.
- **Low**: admin-only issues, self-XSS, missing headers, authenticated DoS.

Rate above Low only with a reproduction against the running stack or a failing test.
