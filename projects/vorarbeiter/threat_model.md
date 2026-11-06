# Threat model: Vorarbeiter (`flathub-infra/vorarbeiter`)

## What this project does

Vorarbeiter is Flathub's build dispatcher. It is a FastAPI service that:

- receives GitHub webhooks configured for Flathub repositories, validates
  the `X-Hub-Signature-256` HMAC with `GITHUB_WEBHOOK_SECRET`, and stores accepted events;
- creates build, reprocheck and merge pipelines in PostgreSQL (or SQLite for tests);
- dispatches the GitHub Actions workflows in `.github/workflows/` (`build.yml`, `merge.yml`,
  `reprocheck.yml`) with repository, ref, app ID, flat-manager URL/token, callback URL and callback
  token as workflow inputs;
- verifies per-pipeline bearer callback tokens for status, log URL, metadata, reprocheck and cost
  callbacks, and a per-merge bearer token for merge results;
- records job status, publishes summaries, creates/updates GitHub issues and comments, and cancels
  superseded builds;
- renders public dashboard, reproducibility, app ID status, AppStream preview and diffoscope pages;
- exposes an admin-triggered pipeline API and an HMAC-protected permission-assessment decision
  webhook;
- talks to GitHub's REST/GraphQL API using a GitHub App or token, to `flat-manager`, to
  `status.flathub.org`, and fetches reprocheck result archives from S3 URLs.

This model describes the enrolled revision. The repository does not contain the production
deployment definition, so external exposure is an assumption: routes documented as public are
treated as anonymous, and everything else is treated as reachable only with the relevant bearer
token. Statements that depend on GitHub or deployment configuration are marked as assumptions.

## Trust boundaries and adversarial input

Treat the following as attacker-controlled unless stated otherwise.

1. **GitHub webhook delivery.** The webhook endpoint accepts anonymous POSTs. The HMAC is checked
   with `GITHUB_WEBHOOK_SECRET` only when the secret is configured
   (`if settings.github_webhook_secret`); when it is unset, the check is skipped and unsigned
   payloads are accepted, which is a deployment configuration risk. The delivery UUID is recorded
   with the event and used to identify the delivery. A correctly signed payload is still
   attacker-controlled in its contents: PR titles, bodies, comments, commit messages, branch names,
   repository names, file lists, `flathub.json`, manifests, URLs and actor logins are controlled by
   repository contributors or anyone who can comment on a public repository.
2. **Public HTTP surface.** `/`, `/reproducible`, `/status/{app_id}`, `/api/reproducible`,
   `/api/status-banner`, `/api/inactive-repos.txt`, `/api/pipelines`, `/api/pipelines/{id}`,
   `/api/pipelines/{id}/log_url`, `/appstream/{pipeline_id}` and `/diffoscope/{pipeline_id}...`
   accept anonymous requests. Pipeline IDs are UUIDs but are not secrets. App IDs, query
   parameters and path parameters are untrusted. `POST /api/pipelines` alone authenticates with
   the shared `ADMIN_TOKEN` bearer value.
3. **Pipeline and merge callbacks.** Each pipeline has a bearer `callback_token`, and each merge
   request has its own token; both are stored in the database and compared with
   `secrets.compare_digest`. Anyone who obtains a token can submit or forge status, log URL,
   metadata, reprocheck and cost data for that pipeline/merge. Treat logs, database contents,
   workflow inputs and error output as possible disclosure paths and check the actual redaction.
4. **Permission-assessment webhook.** `POST /api/webhooks/permission-decisions` requires an HS256
   JWT signed with `PERMISSION_ASSESSMENT_SECRET`, subject `permission-assessment`, scope
   `notify`, and `iat`/`exp`. The `source_repository` and `pull_request_number` fields are then used
   to refresh a review.
5. **GitHub Actions workflow inputs.** The service builds workflow-dispatch payloads from stored
   pipeline params (`owner`, `repo`, `workflow_id`, `ref`, arbitrary `inputs` and
   `additional_params`) and adds the flat-manager token and callback token. Some fields originate
   in webhook payloads; others come from stored pipeline params. Workflow dispatch inputs appear in
   GitHub Actions run metadata (assumption: users who can read the dispatching repository's
   Actions runs can see them), so treat that access as inside the trusted boundary and verify
   token redaction there. `build.yml` downloads the `justfile` and `flatpak.seccomp.json` at run
   time; those files are trusted only as much as the repository hosting them.
7. **GitHub API responses.** Repository metadata, PR diffs, file contents, manifests,
   `flathub.json`, check-run annotations, workflow runs and logs, and collaborator/membership
   answers are untrusted data from GitHub. Manifests are parsed with PyYAML (`safe_load`) and
   PyGObject `Json`; resulting values flow into URLs, comments, rendered pages, database fields and
   subsequent workflow inputs.
8. **`flat-manager`.** Build tokens, repository names, job IDs and status values are received over
   HTTP and must be treated as untrusted for parsing and authorization. The flat-manager tokens and
   bearer tokens are secrets that must never be logged or returned to unauthenticated clients.
9. **Outbound fetches and redirects.** Diffoscope archives come from a `result_url` stored from
   reprocheck results; the service downloads the zip and serves `index.html`, `common.css` and
   `icon.png` from it. AppStream previews are fetched from an external service. Log URLs and
   status-page links are rendered or redirected to. Where any of these URLs is derived from
   untrusted data, treat the fetch as an SSRF boundary and the redirect as an open-redirect
   boundary; verify the actual data flow at each call site.
10. **Templates and browser output.** The dashboard and AppStream pages use Jinja2 with
    `select_autoescape()`; the AppStream page explicitly escapes its error text and sets a strict
    CSP. Diffoscope HTML is fetched as bytes and served after rewriting only two asset paths, so its
    content is trusted only if the archive source is trusted. Rendered fields such as comments,
    repository names, app metadata, commit subjects and URLs must be treated as untrusted for XSS
    where they reach HTML.

## Components that matter most

Highest priority:

- `app/routes/webhooks.py` — webhook signature check, replay/idempotency, event parsing, PR/push
  dispatch decisions, EOL-only and submodule-only fast paths, retry permissions.
- `app/routes/pipelines.py` and `app/pipelines/build.py` — admin authentication, callback-token
  verification, workflow dispatch inputs and flat-manager token creation.
- `app/routes/merge.py` and `app/services/merge.py` — merge callback authorization, commit SHA
  handling, `flathubbot` push and token use.
- `app/routes/permission_assessment.py` — JWT validation and review refresh.
- `app/utils/github.py`, `app/services/github_actions.py`, `app/utils/flat_manager.py` — outbound
  API clients, retries, URL construction and secret redaction.
- `app/routes/diffoscope.py`, `app/services/diffoscope.py`, `app/routes/appstream.py`,
  `app/services/appstream.py` — untrusted archive/URL handling and HTML output.
- `app/models/` and `app/database.py` — token storage, pipeline state transitions and SQL.
- `.github/workflows/build.yml`, `merge.yml`, `reprocheck.yml` — token handling in workflow inputs,
  log masking, shell interpolation and `runs-on` selection.
- `justfile` and `flatpak.seccomp.json` — shell code executed by the build workflow and the
  sandbox profile.

Lower priority but still in scope: dashboard/status rendering, inactive-repository lists,
reproducibility aggregation, status-page integration, failure-issue parsing, notification
formatting and Alembic migrations. Test-only code, mocks and fixtures are lower priority unless
they affect a production path.

## Security goals

- Only a request that passes webhook authentication can create or mutate pipelines through the
  webhook path; the admin API is a separate authenticated path. Unsigned or replayed deliveries
  cannot cause a build, merge or comment.
- The admin API cannot be reached without `ADMIN_TOKEN`, and a pipeline token cannot act on another
  pipeline. Merge callbacks cannot move an arbitrary commit or branch.
- Workflow dispatch cannot be steered to an arbitrary repository, workflow, ref or shell
  expression by a webhook payload or pipeline parameter.
- `GITHUB_APP_PRIVATE_KEY`, `GITHUB_ACTIONS_TOKEN`, `FLATHUBBOT_TOKEN`, `FLAT_MANAGER_TOKEN`,
  `PERMISSION_ASSESSMENT_SECRET`, `ADMIN_TOKEN` and pipeline/merge callback tokens do not leak
  through HTTP responses, logs, Sentry, GitHub comments, rendered pages or workflow output.
- Webhook and callback bodies cannot inject SQL, shell, YAML, JSON, template syntax, HTTP headers or
  redirect targets.
- Outbound fetches cannot reach internal services, cloud metadata, `localhost` or arbitrary schemes
  through attacker-controlled URLs, and downloaded archives are bounded.
- Untrusted text cannot execute script in the dashboard/AppStream origin, and diffoscope HTML is
  served from a trusted source only.
- State transitions are monotonic and idempotent: a late or duplicate callback cannot resurrect a
  cancelled pipeline, publish an unapproved build or overwrite a completed merge.
- Resource use is bounded for public endpoints and webhook processing; one request cannot exhaust
  memory, disk, database connections or GitHub rate limits for all users.

## How to exercise the project

The image contains the project, its virtualenv and all development dependencies. The CI
configuration sets `DATABASE_URL` to SQLite in memory; the tests mock GitHub, flat-manager,
status-page and S3 access, so no external service is needed:

```bash
cd /src
DATABASE_URL="sqlite+aiosqlite:///:memory:" uv run pytest -v -n 4
# a focused reproducer:
uv run pytest tests/test_webhooks.py -q
uv run pytest tests/test_pipelines.py -q
uv run pytest tests/test_merge.py -q
```

The suites most relevant to security are `test_webhooks.py`, `test_webhook_reconciler.py`,
`test_pipelines.py`, `test_pipeline_service.py`, `test_pipeline_publication.py`,
`test_reprocheck_callback.py`, `test_merge.py`, `test_permission_assessment.py`,
`test_diffoscope.py`, `test_appstream.py`, `test_github_app.py`, `test_github_utils.py`,
`test_flat_manager*.py`, `test_publishing_service.py` and `test_job_monitor*.py`.

Limitations:

- No live GitHub, `flat-manager`, GitHub Actions, S3 or status-page access. Tests use mocks and
  fixtures where applicable; they do not prove live behavior or credential handling.
- PostgreSQL is not running. Tests use SQLite; start a server separately if a reproducer depends on
  PostgreSQL-specific SQL or concurrency. `psycopg` and `postgresql-client` are installed.
- The GitHub Actions workflows and `justfile` are shipped as source and can be reviewed, but they
  are not executed in the image. Build/reprocheck behavior requires a GitHub Actions runner,
  flatpak-builder, the linter image and network access.
- The scanner image does not contain a Flatpak SDK, `flatpak-builder`, the linter or Docker. Those
  belong to the build workflow, not to this service. Findings in them are out of scope here unless
  Vorarbeiter's handling of their inputs is unsafe.
- If a reproducer depends on time, retries or database ordering, use `-n 0` (or `-p no:xdist`) for
  deterministic execution.
- `ADMIN_TOKEN`, `GITHUB_WEBHOOK_SECRET` and `FLAT_MANAGER_TOKEN` have development defaults in
  `app/config.py`. Treat them as configuration risks, not assumed production leaks; report them
  only with a deployment path that uses them and demonstrated impact.

## Severity guidance

The lists below are calibration examples, not automatic mappings. A finding takes its severity
from demonstrated impact, attacker position and prerequisites; when a finding needs a chain, rate
the chain. If impact depends on an unverified deployment assumption, state the assumption instead
of assuming the worst case.

**Critical impact examples**

- Remote code execution or command injection in the FastAPI service, worker, dashboard, appstream
  or diffoscope handlers, including via template injection, unsafe deserialization, archive
  extraction or a crafted URL.
- Authentication bypass of the admin API or permission-assessment webhook; or webhook signature
  bypass that lets an anonymous attacker create pipelines, dispatch builds, merge commits or post
  comments.
- Theft or disclosure of the GitHub App private key, `FLATHUBBOT_TOKEN`/`GITHUB_ACTIONS_TOKEN`,
  `FLAT_MANAGER_TOKEN`, `PERMISSION_ASSESSMENT_SECRET` or a live callback token that grants
  arbitrary build/merge control.
- Arbitrary workflow dispatch to an attacker-chosen owner/repository/workflow/ref, or arbitrary
  `runs-on` selection, leading to execution in a trusted repository context.
- Pre-auth SQL injection, or any path that lets a webhook/callback write arbitrary pipeline, merge
  or job state without possessing the relevant secret.
- SSRF with demonstrated access to cloud metadata or internal control-plane services yielding
  credentials or code execution.

**High impact examples**

- Stored XSS in a Vorarbeiter page (dashboard, AppStream preview, diffoscope viewer) reachable by
  an unprivileged user, especially where it can act as a maintainer or exfiltrate page data.
- IDOR or token confusion allowing one pipeline/merge to read or modify another pipeline's status,
  logs, result URLs or build metadata.
- Forging a callback for an existing pipeline when a token is disclosed through a log, an error
  response or workflow metadata.
- Open redirect or SSRF to internal HTTP services/ports from diffoscope, log URLs, status-page
  links or AppStream previews, with demonstrated impact short of Critical.
- SQL injection post-auth, or stored YAML/JSON injection that changes workflow inputs or shell
  behavior in `build.yml`/`merge.yml`.
- Leaking a merge/commit authorization token or allowing a merge to push an attacker-controlled SHA
  to a branch other than the one recorded for the merge request.
- Denial of service that persists (database growth, stuck pipelines, exhausted GitHub quota) from a
  small number of requests.

**Medium impact examples**

- Reflected XSS or HTML injection requiring an unusual interaction; missing CSP on a page with
  sensitive content.
- CSRF on a state-changing action that relies on ambient credentials; this service uses bearer
  tokens, so a cookie-authenticated path would need to be demonstrated. A missing check with no
  demonstrated impact is not sufficient.
- Single-pipeline or single-user denial of service, unbounded archive download, unbounded log or
  manifest size, regex/pathological YAML causing a hang.
- Limited information disclosure (internal hostnames, stack traces, database schema, whether a
  repository/pipeline exists) without a token or account-takeover path.
- Webhook replay of a signed delivery that causes a duplicate comment or redundant build but does
  not bypass authorization or corrupt state.

**Low impact examples**

- Missing security headers, verbose errors with no secret, rate-limit gaps with no practical abuse,
  self-XSS, log injection without control of a log consumer.
- Best-practice findings (cookie flags, CORS, dependency versions) without a reachable exploit path.
- Findings that require the attacker to already control the database, Redis, the server, GitHub
  itself or a repository's administrator account.

## Not a vulnerability / do not report

- Hard-coded default tokens in `app/config.py`, `docker-entrypoint.sh`, tests and CI fixtures are
  configuration risks, not assumed production leaks; report them only with a deployment path that
  uses them and demonstrated impact. Public dashboard/status/reproducibility data and pipeline
  UUIDs are intended to be public.
- Volumetric DDoS, GitHub rate-limit exhaustion without a code weakness, spam comments without a
  code weakness, social engineering, physical access and compromised maintainer accounts.
- Missing rate limits or headers with no demonstrated security impact.
- Vulnerabilities in GitHub, `flat-manager`, GitHub Actions runners, `flatpak-builder`, the Flathub
  linter image, S3, the status page or the repositories being built. Report those upstream; report
  Vorarbeiter only if its handling of their data creates a distinct weakness.
- Security defects in the Flatpak manifests and applications themselves. Vorarbeiter's parsing,
  validation and dispatch of those inputs remain in scope.
- Build reproducibility, code style, test coverage, or dependency updates without a demonstrated
  reachable vulnerability.
- Findings whose only affected code is tests, mocks, fixtures or snapshots and has no production
  path.

## Reporting and patch expectations

- Reproduce against this image with the commands above. Include the request, the webhook or callback
  payload, the pipeline/merge state involved, and the trust boundary crossed. Redact real tokens,
  private keys and repository data.
- Proposed patches should be minimal and target `flathub-infra/vorarbeiter`. Patches may touch
  `.github/workflows/` or `justfile` when the vulnerability is in how they handle
  Vorarbeiter-supplied inputs, tokens or repository data. Do not change tests, mocks or fixtures to
  make a report pass.
- Prefer a failing regression test with the patch. State whether it needs PostgreSQL, a live
  GitHub App, `flat-manager` or a GitHub Actions runner.
- Do not include live callback tokens, admin tokens or private keys in a report or patch. Use
  documented test defaults for reproducers.
