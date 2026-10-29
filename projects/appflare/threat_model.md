# Threat model

## What this project does and where untrusted input enters

Appflare is an app store that runs in the user's own Cloudflare account. The **manager** (`apps/manager`, a
Cloudflare Worker with a React UI) holds a Cloudflare credential that can change Workers, D1, KV, R2, DNS and Access
across the whole account. It installs, updates and removes third-party open-source apps from a public catalog,
attaches custom domains, and manages Cloudflare Access. That credential is either an API token stored as the Worker
secret `CF_API_TOKEN`, or an OAuth refresh token kept in D1, encrypted under the `CF_GRANT_KEY` secret. Anything
that lets an outsider, a lower-privileged user or a catalog app act with that credential is the most serious kind
of bug.

`apps/docs/content/docs/security.md` is the authoritative description of the intended security properties. Treat
any behaviour that contradicts it as a finding.

Untrusted input enters at:

- **The manager's HTTP surface.** Pages and APIs are reached by unauthenticated visitors (sign-in, setup wizard,
  password reset, `/api/health`, `/api/handoff`, `/api/cloudflare/oauth-return`), by signed-in **members**, who
  are read-only, and by **admins**. Only the **owner** may change roles, delete users or transfer ownership.
  Authentication uses Better Auth (`apps/manager/src/auth`): email and password, passkeys, sessions, recovery codes
  and reset links. With Cloudflare Access protection on, the manager verifies `Cf-Access-Jwt-Assertion` itself
  (`apps/manager/src/access`).
- **The catalog.** The manager fetches the catalog index over HTTPS, and release artifacts from GitHub. Artifacts
  carry an Ed25519-signed `manifest.json` that lists every file's sha256. Verification lives in `packages/schema`
  (`keys.ts`, `artifact.ts`) and in the manager's install path. Catalog manifests (`appflare.jsonc`), the index,
  manifests and zip contents should all be treated as attacker-influenced: names, paths, bindings, settings,
  placeholders, D1 migrations and seed SQL (`sql-guard.ts`), and Access settings.
- **App code and app settings.** Installed apps are third-party code. An app must never get the manager's
  credential, other apps' secrets, or the ability to change Appflare's own Worker. Settings and secrets that admins
  enter for an app reach the Cloudflare API through `packages/cf-api`.
- **The sandbox Worker** (`apps/sandbox`, an optional Cloudflare Container). It clones a pinned upstream commit
  and builds it with third-party build scripts and internet access, then hands an unsigned artifact back to the
  manager over a service binding. Build containers must never hold a credential. A self-deploying app's installer
  receives only that app's own token (`APP_TOKEN_<install>`), and only in its deploy or destroy command. Watch
  for escaping the build environment, `.env` or environment-variable injection (`build-env.ts`), zip and path
  traversal (`zip-check.ts`), log redaction gaps, and an unsigned artifact the manager accepts when it should not.
- **The hosted installer** (`apps/installer`, served at appflare.dev through the docs Worker's service binding).
  Every request carries a visitor's short-lived Cloudflare access token. It must use that token only for the
  visitor's own deploy, never log it, and never adopt or remove resources the installation did not create. The
  browser-to-manager handoff (`apps/manager/src/handoff`) must accept a refresh token only with the secret whose
  SHA-256 was deployed as `APPFLARE_HANDOFF`.
- **The packer** (`packages/pack`). It builds catalog apps in CI from upstream checkouts: it parses wrangler
  config (TOML and JSONC), runs build commands with a scrubbed environment (`scrub-env.ts`), and zips and signs
  artifacts. Upstream repositories are untrusted. The signing key must never reach a process that runs app code.
- **The CLI** (`packages/cli`, `npx create-appflare`). It runs on a user's machine with their Cloudflare login,
  and also handles recovery codes.
- **Outbound requests the manager makes for the user**: notification webhooks (Slack, Discord, Telegram, generic
  signed webhooks), app health checks, and custom-domain moves. Look for SSRF, redirects being followed, and
  credentials leaking into stored error text.

## Components that matter most / least

- Most: `apps/manager/src/server`, `auth`, `access`, `handoff`, `cloudflare`, `installs`, `jobs`, `sandbox`,
  `domains`, `notifications`, `danger`; `apps/sandbox/src`; `apps/installer/src`; `packages/schema`, especially
  signature and hash verification, manifest and catalog validation, the SQL guard, build environment rules and
  token permissions; `packages/cf-api`; `packages/pack/src` (`sign.ts`, `verify.ts`, `scrub-env.ts`,
  `build-command.ts`, `zip.ts`, `wrangler-config.ts`).
- In scope: everything under `apps/` and `packages/`, including the docs Worker (`apps/docs/worker`), and the
  production sandbox image `apps/sandbox/Dockerfile`.
- Low: the documentation content and static site pages (`apps/docs/content`, `apps/docs/src`), `packages/brand`,
  UI-only components with no server effect, and `scripts/` (release tooling run by maintainers).
- Out of scope: test files (`*.test.ts`, `src/test`), `.github/` workflow configuration, and the code of catalog
  apps themselves, which lives in other repositories.

## How to exercise it

- `pnpm install --frozen-lockfile && pnpm build` has already run in the image.
- Tests: `pnpm exec turbo run test` for everything, or `pnpm --filter <package> test`, for example
  `pnpm --filter @appflare/manager test` or `pnpm --filter @appflare/sandbox-worker test`. Worker tests run in
  workerd through `@cloudflare/vitest-pool-workers`, with D1, KV and Workflows simulated locally and the
  Cloudflare API mocked, so they work offline. The manager's suite is large, so pass a file path to run one test.
- The packer runs locally: `node packages/pack/bin/appflare-pack.js --help`, with `inspect`, `verify` and packing a
  directory.

## How you rate severity

- **Critical:** an unauthenticated attacker (or an installed app, a catalog entry that passes catalog validation,
  or code run in a sandbox build) reads or uses the manager's Cloudflare credential, the hosted installer's
  visitor tokens or the OAuth refresh token; signed-artifact verification is bypassed so unsigned or modified code
  gets deployed; remote code execution in the manager or the installer; taking over the owner account
  without credentials.
- **High:** a member, or an admin acting against the owner, escalates privileges or changes things their role
  forbids; authentication or Cloudflare Access bypass; stored XSS in the manager reachable by a non-admin or by
  catalog data; an app reads another app's secrets or a self-deploying app's token is leaked to a build step;
  SSRF from the manager that reaches credentialed endpoints; the installer adopting or deleting resources it did
  not create.
- **Medium:** information disclosure of non-credential data across roles, CSRF on state-changing endpoints,
  rate-limit bypass on sign-in, recovery or setup, secrets leaking into logs or job logs, and denial of service
  that stops a single manager from working.
- **Low:** issues that require control of the Cloudflare account (which already grants everything), self-XSS, and
  missing hardening headers without a concrete exploit.

## Anything to leave alone

- Whoever controls the Cloudflare account, or can set secrets on the manager's Worker, controls Appflare by design
  (for example, recovery codes through `RECOVERY_CODE_HASH`). That is not a vulnerability.
- Admins can install any catalog app and enter its settings; an app doing what an installed app can do in its own
  Worker is expected. So is a catalog maintainer choosing what the catalog contains. Report only cases where
  Appflare gives an app or a catalog entry more than the security model says.
- Sandbox builds have internet access and can reach `api.cloudflare.com` by IP address; the docs state that the
  host-name filter is not a firewall. Report it only if a credential is reachable from a build.
- The anonymous PostHog report is documented and opt-out; report it only if it carries data the docs say it
  never does.
