# Threat model — Coolify

Coolify (`coollabsio/coolify`) is a self-hosted PaaS / deploy control plane.
Users point it at git remotes and servers; Coolify builds containers, manages
domains and proxies, stores secrets, and SSHes into customer hosts to deploy.
A compromise of Coolify is typically a compromise of every server and secret
it manages. Severity should reflect that blast radius.

## What this project does and where untrusted input enters

Coolify is a Laravel 12 + Livewire application (PHP ^8.4) with a Vite / Svelte
frontend. Treat as untrusted:

- **HTTP / Livewire**: routes, query strings, form fields, Livewire component
  parameters and wire payloads, file uploads (Dockerfiles, compose files,
  logos, chunked uploads), cookies / session, and API tokens (Sanctum).
- **Git / CI webhooks**: GitHub, GitLab, Bitbucket, Gitea payloads and
  delivery signatures; repository contents pulled for builds (Dockerfiles,
  compose, build args, Nixpacks / build-pack config).
- **User-supplied deploy config**: domains, env vars, Docker labels, health
  checks, custom Dockerfiles, compose overlays, build commands, pre/post
  deploy scripts.
- **Outbound integrations**: OAuth callbacks (GitHub, Google, Azure, Discord,
  Authentik, Clerk, Zitadel, Infomaniak, …), Stripe webhooks, cloud provider
  APIs, S3 / SFTP destinations.
- **Multi-tenant data**: team / project membership, shared resources, and any
  content one tenant stores that another might see.

Trusted operator input (out of scope unless Coolify mishandles it): the
host’s Docker socket, root SSH to the Coolify host itself, and values the
instance admin deliberately sets in the root `.env`.

### Where the code is

| Path | What it is |
| --- | --- |
| `/src` | Coolify git checkout (`main`). Patches belong here. |
| `/src/app` | Application code (Actions, Livewire, Jobs, Models, Services). |
| `/src/routes` | HTTP / API / console routes. |
| `/src/resources` | Blade / Livewire views and Vite frontend. |
| `/src/tests` | Pest unit / feature / v4 tests. |

## Critical assets

Highest-value targets an attacker would go after:

1. **SSH private keys** Coolify uses to reach managed servers.
2. **Application / service secrets** (env vars, database URLs, API tokens)
   stored for deployed resources.
3. **Instance credentials**: admin accounts, Sanctum tokens, OAuth tokens for
   linked git providers, Stripe keys, cloud credentials.
4. **Ability to run arbitrary containers or commands** on managed servers
   (effective RCE on the fleet).
5. **Build-time code execution** via malicious Dockerfiles / compose / git
   content that Coolify builds on behalf of a user (especially if builds are
   not isolated per tenant).

## Components that matter most / least

Highest priority:

1. Authn / authz and multi-tenant isolation (teams, projects, resources,
   ability to read another team’s env vars or SSH keys).
2. Secret storage and disclosure (API responses, Livewire payloads, logs,
   error pages, backups).
3. SSH / remote execution paths (`phpseclib`, deploy jobs, helper containers).
4. Webhook signature verification and confused-deputy builds.
5. Dockerfile / compose / env injection that escapes the intended build or
   deploy sandbox.
6. SSRF from features that fetch user-supplied URLs (registries, webhooks,
   health checks, git clones).
7. RCE / object injection / unsafe deserialization; command injection in
   shell wrappers around Docker / git / cloudflared.
8. CSRF on state-changing routes; Livewire authorization bypasses.
9. XSS stored in project names, logs, or terminal output that reaches other
   users’ browsers.

Lower priority or out of scope:

- Vulnerabilities solely in `vendor/`, npm packages, or upstream images
  (Docker Engine, Traefik, etc.) unless Coolify’s usage creates the issue.
- Denial of service that only burns CPU/disk on the attacker’s own resources.
- Missing best-practice hardening that is not exploitable (e.g. HSTS on a
  local IP) without a concrete attack path.
- Social / phishing against Coolify Cloud billing; physical access to the host.

## How you rate severity

- **Critical**: unauthenticated or cross-tenant path to read SSH keys /
  secrets, or to run commands / containers on a managed server; auth bypass
  that yields instance admin; remote code execution on the Coolify host from
  a normal user or from a webhook.
- **High**: same-tenant privilege escalation to project/admin; secret leak to
  another authenticated user; webhook forgery that deploys attacker code;
  SSRF that reaches cloud metadata or internal Docker APIs; stored XSS in an
  admin UI that can steal a session.
- **Medium**: CSRF on sensitive actions; limited info disclosure (non-secret
  config, existence of resources); injection that requires an already-trusted
  role but exceeds that role’s intended power.
- **Low**: low-impact XSS in rarely viewed UI; weak rate limits without a
  concrete account-takeover path; issues that need an already-compromised
  admin session and grant nothing further.

Post-auth SQL injection is at least **High**; if it reaches secrets or
cross-tenant data, **Critical**. Do not file “user can deploy a malicious
container to their own server” — that is intended product behavior — unless
it breaks tenant isolation or escapes onto the Coolify host / other tenants.

## How to exercise it

The image is a PHP CLI environment with Composer deps (including Pest) and
built Vite assets. Working directory: `/src`. A testing `.env` is already in
place (`DB_CONNECTION=testing` → sqlite `:memory:`).

```sh
cd /src
php artisan --version
php artisan about
./vendor/bin/pest --version

# Unit suite (no external services)
./vendor/bin/pest tests/Unit

# Feature / v4 suites (sqlite in-memory; may need migrations per test)
./vendor/bin/pest tests/Feature
./vendor/bin/pest tests/v4

# Static review helpers (offline)
./vendor/bin/phpstan analyse --memory-limit=1G || true
```

Useful entry points for manual review:

- `routes/api.php`, `routes/web.php`, Livewire components under `app/Livewire`
- Deploy / SSH jobs under `app/Jobs` and Actions under `app/Actions`
- Webhook controllers and git provider integrations
- Secret / environment variable models and API resources

There is no Docker daemon or reachable SSH target in the scanner VM. Prefer
Pest feature tests, artisan commands, and static analysis over end-to-end
deploy reproduction. When a finding needs a running HTTP stack, `php artisan
serve` on `127.0.0.1` is enough for most Livewire / API checks.

## Reports

Include a minimal reproducer (Pest test preferred), affected routes or job
classes, tenant/role assumptions, and a proposed patch against `/src`. Send
findings to `security@coollabs.io` (matches Coolify’s `SECURITY.md`).
