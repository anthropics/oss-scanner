## 1. Overview
Gitea is a self-hosted Git service providing a web UI, REST API, and Git over HTTP/SSH. It includes repository management, issues/PRs, wiki/markdown rendering, package registry, Git LFS, webhooks, and an OAuth2 provider. It is typically deployed as a multi-tenant service hosting many organizations, with user accounts, teams, access tokens, and secrets. Gitea stores data in a SQL database (models/), a filesystem or object storage backend (modules/storage), and executes Git operations via git binaries/modules/git and services/git. It orchestrates background queues, scheduled tasks, and optional Actions workflows.

Security-relevant data includes user credentials, SSH keys, access tokens, OAuth client secrets, repository contents (often proprietary), package artifacts, LFS files, and admin configuration (app.ini). The server is exposed to untrusted users and integrates with external services (OAuth, LDAP, email, webhooks), so input validation and strict authorization are critical.

## 2. Threat model, Trust boundaries and assumptions
### Trust boundaries
- **External network boundary:** HTTP(S) traffic to `routers/web/*` and `routers/api/v1/*`, Git HTTP in `routers/web/githttp.go`, LFS/attachment/package uploads in `services/lfs` and `services/packages`.
- **SSH boundary:** built-in SSH server (`modules/ssh/`) or external sshd invoking `gitea serv`; attackers can provide SSH keys and Git commands.
- **User-generated content boundary:** Markdown, diffs, filenames, avatars, and release assets rendered via `modules/markup/` and `templates/`.
- **Integration boundary:** outbound webhooks (`services/webhook/`), OAuth/OIDC, LDAP/PAM, email; these accept or emit data to third-party systems.
- **Internal service boundary:** private endpoints in `routers/private/` are protected by `InternalToken` (loaded in `modules/setting/security.go`) and should only be used by local Gitea processes (SSH, hook runners).
- **Storage boundary:** repositories, attachments, LFS, packages stored on local disk or object storage (`modules/storage/`).
- **Admin/operator boundary:** configuration (`modules/setting/*`), secrets, and admin UI (`routers/web/admin/`) are trusted and have high impact.

### Assumptions
- Operators secure `SECRET_KEY`, `InternalToken`, database credentials, and storage access; and enforce TLS.
- Reverse proxies are trusted and configured with correct headers (`ReverseProxyTrustedProxies`).
- Actions runners execute untrusted workflows in separate, isolated hosts; a compromised runner does not imply server compromise unless server over-shares secrets.
- Build scripts/tests (`build/`, `tools/`, `tests/`, `web_src/`) are developer-controlled and not exposed to attackers.

### Inputs by trust level
- **Attacker-controlled:** network requests, Git pack data, LFS/package uploads, issue/PR/wiki content, webhook target URLs, OAuth/OIDC callbacks, migration URLs.
- **Operator-controlled:** config files, environment variables, storage backend choice, custom templates/hooks, admin UI actions.
- **Developer-controlled:** CI/build tooling, tests, sample fixtures, local dev configs.

## 3. Attack surface, mitigations and attacker stories
### Web UI & REST API
- **Surface:** HTTP routes under `routers/web/` and `routers/api/v1/` handle user login, repo browsing, repository mutations, admin actions, and API calls.
- **Mitigations/controls:** session storage in `modules/session/`, security settings (`XFrameOptions`, `DisableQueryAuthToken`, cookie name) in `modules/setting/security.go`, and API token models in `models/auth/`. ORM usage in `models/` can reduce SQL injection risk but query construction should still be reviewed.
- **Attacker story:** an unauthenticated attacker attempts to bypass login or exploit parameter validation to access private repositories or admin APIs.

### Authentication & identity providers
- **Surface:** local password auth, OAuth2/OIDC, reverse-proxy auth, PAM/LDAP, WebAuthn.
- **Mitigations/controls:** password hashing algorithms in `modules/auth/password/hash/*` (argon2/bcrypt/scrypt), 2FA and WebAuthn support (`models/auth/twofactor.go`, `modules/auth/webauthn`), Pwned password checks, and enforced 2FA setting (`modules/setting/security.go`).
- **Attacker story:** credential-stuffing or OAuth token substitution to gain a session.

### Authorization & multi-tenancy
- **Surface:** access control decisions in `models/perm/`, `services/repository/`, and org/team logic.
- **Mitigations/controls:** access mode enforcement in `models/perm/access_mode.go`, repository services perform permission checks before write operations.
- **Attacker story:** a normal user attempts to read/write another organization’s private repository or steal Actions secrets.

### Git HTTP/SSH transport and hooks
- **Surface:** Git over HTTP handler (`routers/web/githttp.go`), SSH server (`modules/ssh/`), Git execution helpers (`modules/git/`, `services/git/`), and internal hook endpoints (`routers/private/`).
- **Mitigations/controls:** internal `InternalToken` gate for private routes, ability to disable git hooks (`DisableGitHooks`) and require Gitea environment (`OnlyAllowPushIfGiteaEnvironmentSet`), and minimum SSH key size checks (`modules/setting/ssh.go`).
- **Attacker story:** a malicious user crafts Git requests to access repositories outside their permissions or to trigger command injection in git operations.

### Content rendering (Markdown, diffs, templates)
- **Surface:** rendering of README, issues, comments, and diffs via `modules/markup/` and `templates/`.
- **Mitigations/controls:** markup rendering pipeline should sanitize HTML and restrict dangerous attributes; templates should avoid unsafe `html/template` bypasses.
- **Attacker story:** a stored XSS payload in a README steals an admin’s session token.

### File uploads: LFS, attachments, packages
- **Surface:** LFS endpoints (`services/lfs/`, `modules/lfs/`), attachment uploads, and package registries (`services/packages/`, `modules/packages/`).
- **Mitigations/controls:** storage abstraction in `modules/storage/` helps isolate paths; configuration can enforce size limits and storage segregation.
- **Attacker story:** attacker uploads oversized or crafted files to exhaust storage or attempt path traversal to read/write outside allowed directories.

### Webhooks and outbound integrations
- **Surface:** webhook delivery (`services/webhook/`) to attacker-controlled URLs, and integrations like Slack/Discord/etc.
- **Mitigations/controls:** webhook secrets and event types (`modules/webhook/`) allow signing; webhooks can be disabled (`DisableWebhooks`).
- **Attacker story:** attacker configures a webhook to SSRF internal services or cloud metadata endpoints.

### OAuth2 provider and token issuance
- **Surface:** OAuth2 flows and JWT signing (`services/oauth2_provider/`), stored tokens in `models/auth/`.
- **Mitigations/controls:** explicit JWT signing key management (`services/oauth2_provider/jwtsigningkey.go`), encrypted secrets at rest using `modules/secret/secret.go`.
- **Attacker story:** exploit token validation or key handling to forge access tokens.

### Migration/import features
- **Surface:** repository import/migration in `modules/migration/` and services/migrations.
- **Mitigations/controls:** `ImportLocalPaths` defaults to false (`modules/setting/security.go`) to prevent local file reads.
- **Attacker story:** attacker supplies a crafted import URL to trigger SSRF or access local file paths when misconfigured.

### Actions and automation
- **Surface:** actions orchestration (`modules/actions/`, `services/actions/`) and secret distribution to runners.
- **Mitigations/controls:** scopes and secret validation logic should limit what workflows can access; runners are isolated hosts.
- **Attacker story:** a repo collaborator attempts to exfiltrate Actions secrets or trigger unauthorized workflow runs.

### Admin configuration & secrets
- **Surface:** admin UI and config in `modules/setting/`; secrets (`SECRET_KEY`, `InternalToken`) loaded via `loadSecret`.
- **Mitigations/controls:** secrets can be loaded from files (`*_URI`), internal token auto-generation, and encryption utilities in `modules/secret/`.
- **Attacker story:** an attacker finds a path to read `app.ini` or override config values, leading to full compromise.

### Unique considerations
- Gitea blends web, Git HTTP, and SSH protocols with internal hook endpoints; failures in any one can expose repositories or enable RCE.
- The system is multi-tenant and stores untrusted repository content that is routinely rendered and indexed.
- It relies on external services (SMTP, OAuth, webhooks, object stores), increasing SSRF and credential-leak risks.

## 4. How to exercise it (offline build and reproduction)
The scanner image holds the full checkout at `/src` (owned by a `gitea` user created during the build), the built server at `/src/gitea`, and the compiled frontend assets under `public/assets/` (built with `TAGS="bindata timetzdata" make build`, CGO disabled; sqlite runs through modernc.org/sqlite). Go modules and the pnpm store are pre-fetched, and `GOPROXY=off`, `GOSUMDB=off`, and `GOTOOLCHAIN=local` are set: no network is available after the image build, and nothing may be downloaded.

- **Gitea refuses to run as root** (`mustNotRunAsRoot` in `modules/setting/setting.go`), and the scanner's shell is root. The image sets `GITEA_I_AM_BEING_UNSAFE_RUNNING_AS_ROOT=true`, which lets the `/src/gitea` binary itself run as root, but the unit-test harness (`SetupGiteaTestEnv`) deliberately scrubs that override. Run unit tests as the `gitea` user: `runuser -u gitea -- make test-backend` (offline, against a throwaway sqlite database), or focused with e.g. `runuser -u gitea -- go test -tags 'bindata timetzdata' ./modules/... ./services/...`. The image build runs these tests the same way (capped at 20 minutes, failures logged as warnings); check the build log for pre-existing failures before attributing them to a change.
- For an end-to-end reproducer, run `/src/gitea web` with a temporary `GITEA_WORK_DIR` and sqlite on localhost (the env override above permits root), or use the integration suite in `tests/integration` with `GITEA_TEST_DATABASE=sqlite` (slow; not part of the image baseline). git is installed for push/pull fixtures.
- One known-flaky unit test: `modules/queue`'s `TestWorkerPoolQueueActiveWorkers` asserts exact active-worker counts and can fail when the full suite runs under parallel load (it may be the failure in the image build log); it passes when rerun alone with `runuser -u gitea -- go test -count=1 ./modules/queue/`. Do not chase it.
- Frontend tests (`pnpm exec vitest run`) drive a real browser through Playwright; browsers are not installed in the image, so prefer Go-side reproducers.
- Gitea refactors `models/` and friends regularly: confirm package paths and setting names against the scanned checkout instead of trusting this document.

## 5. Report requirements
Each report should state the scanned commit, the attacker position and lowest privileges needed (unauthenticated, regular user, repository collaborator, organization owner, site admin), any non-default configuration required, the entry point, and the full path to the security impact, with a reproducible request, git operation, or UI sequence and a proposed patch plus regression test where possible. Trace the reachable route and its remaining guards before claiming a missing check is exploitable, and distinguish a demonstrated result from a source-level possibility. Deduplicate reports that share a root cause; report dependency-caused findings separately with their reachability through Gitea.

## 6. Criticality calibration (critical, high, medium, low)
- **Critical:** vulnerabilities enabling unauthenticated RCE, full auth bypass, or global secret compromise.
  - Example: command injection in `modules/git/` via HTTP/SSH leading to server RCE.
  - Example: leakage of `InternalToken` or OAuth signing keys allowing arbitrary admin/API access.
- **High:** vulnerabilities enabling cross-tenant data access or persistent compromise of privileged users.
  - Example: authorization bypass in `services/repository/` that exposes private repos.
  - Example: stored XSS in `templates/` that steals an admin session and elevates access.
  - Example: SSRF via webhooks/migrations reaching cloud metadata.
- **Medium:** vulnerabilities with limited impact or requiring additional conditions.
  - Example: CSRF on non-admin actions (e.g., stars) or on actions protected by additional confirmation.
  - Example: information disclosure of non-sensitive metadata or user enumeration.
  - Example: resource-exhaustion DoS via large LFS uploads without size limits.
- **Low:** issues with narrow scope or requiring strong attacker preconditions.
  - Example: self-XSS or UI redress attacks requiring user interaction.
  - Example: misconfigurations that only apply when operators explicitly enable risky options (`ImportLocalPaths`, disabling auth).
  - Example: vulnerabilities in developer-only build/test tooling; these are out of scope unless they affect production artifacts.

## 7. Out of scope / what to leave alone
- Actions of a site administrator or the operator (managing users, editing `app.ini`, installing custom templates or git hooks, running queues) are trusted by design; do not report admin capabilities as vulnerabilities without showing privilege gain from a less-privileged attacker.
- Findings that need explicitly insecure opt-in settings (`ImportLocalPaths`, disabled git hooks or authentication) are low at best; name the setting and its default.
- Dependency vulnerabilities are in scope only with a demonstrated path reachable through Gitea itself.
- Build, CI, and developer tooling (`build/`, `tools/`, `tests/`, lint configuration in `web_src/`) and generated files (`modules/*/bindata.*`, `public/assets/`) are out of scope unless they affect the shipped binary.
- External services (SMTP, LDAP, OIDC providers, object storage, Actions runners) cannot be exercised in the offline image; reason about them from source and state that limitation.
  