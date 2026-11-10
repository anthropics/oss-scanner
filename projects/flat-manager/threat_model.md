# Threat model: flat-manager

## What this project does

flat-manager is the HTTP service and job runner behind a Flatpak repository. It:

- exposes a JSON/HTTP API for creating builds, uploading OSTree objects and
  deltas, creating refs, committing, publishing, republishing, purging and
  reviewing check results;
- runs commit, publish, republish, check, prune and update-repo jobs from a
  PostgreSQL queue (`src/jobs/`);
- imports uploaded commits into the served OSTree repository with
  `flatpak build-commit-from`, signs them with the repository GPG key, and
  updates the summary with `flatpak build-update-repo`;
- serves repository data (objects, summary, deltas, appstream, screenshots,
  `.flatpakref` files) over HTTP (`src/api/repo.rs`);
- executes operator-configured hook commands and post-publish scripts in the
  build directory (`src/config.rs`, `src/jobs/{publish,check,update_repo}_job.rs`).

## Trust boundaries and untrusted input

1. **API clients with build tokens.** Requests to the authenticated API carry a
   JWT signed with the shared `secret` from the config (`src/tokens.rs`);
   repository downloads use a token signed with `repo_secret` and parsed
   optionally. Claims include `sub`, `scope`, `prefixes`, `apps`, `repos`,
   `branches`, `exp` and an optional `jti` used for revocation in the database.
   Treat any token as untrusted input within its granted scope: scope,
   sub/prefix and repo confusion are likely to be easier to reach than forged
   signatures. Note `validation.validate_exp = false` with a manual
   `claims.exp < now` check, that revocation is skipped when `jti` is absent,
   and that the `branches` claim is decoded but not checked by the current
   authorization path.
2. **Uploaded build content.** Everything a build client uploads is fully
   attacker-controlled: OSTree objects and deltas (named `<64 hex>.<type>` or
   `<checksum>.<part>.delta`), ref names, commit metadata (`xa.token-type`,
   `ostree.ref-binding`, `xa.subsets`), repository contents inside commits
   (`files/share/app-info/...`), and screenshots trees. Uploaded objects are
   checked with `fsck_object` in `src/api/utils.rs` before being persisted, and
   screenshots are re-validated for symlinks and `..` components during publish
   (`src/jobs/publish_job.rs`), so look for gaps in those checks and for
   consumers that trust the content later.
3. **Repository read requests.** `handle_repo` (`src/api/repo.rs`) serves files
   from the main repositories; `handle_build_repo` serves build repositories
   and enforces `Download` scope plus repo/app checks when
   `public_download` is false. Both pass the URL tail through
   `canonicalize_path`, which rejects `..`, dot-prefixed, `*`, and trailing
   `:/<>` segments. Authentication for private commits is derived from the
   commit metadata itself (`xa.token-type`, `ostree.ref-binding`), so commit
   metadata parsing is security-relevant.
4. **Hook and post-publish scripts.** Commands come only from the server config
   (`ConfigHook::build_command` runs argv directly, never through a shell). They
   nevertheless execute with the working directory set to an attacker-controlled
   build tree and receive `FLAT_MANAGER_BUILD_ID`/`FLAT_MANAGER_JOB_ID`, so
   anything they read from that tree is attacker data.
5. **PostgreSQL and the filesystem.** Job contents and build rows are written by
   flat-manager itself (diesel, typed queries); the database is part of the
   trusted server infrastructure and build clients do not reach it directly.
   Paths under `build-repo-base` and repository `path` are operator config, but
   attacker-influenced names (build ids, app ids, ref names, upload filenames)
   flow into them.

## Components that matter most

- `src/tokens.rs` and `common/src/tokens.rs`: claim validation, prefix and repo
  matching, token subsetting, revocation.
- `src/api/build.rs` and `src/api/utils.rs`: authorization per build, ref name
  validation, upload filename parsing, object validation, build state machine.
- `src/api/repo.rs`: path canonicalisation, private build authentication,
  commit/superblock parsing for auth decisions, delta fallback to `tmp/`.
- `src/jobs/publish_job.rs`, `commit_job.rs`, `republish_job.rs`: importing
  commits, `.flatpakref` generation, screenshot extraction, GPG-signed commits.
- `src/jobs/update_repo_job.rs`: appstream extraction, delta generation,
  summary signing, post-publish script.
- `src/jobs/job_executor.rs`, `job_queue.rs`: serializable transactions, job
  dependencies, crash recovery (`cleanup_started_jobs`).
- `common/src/ostree.rs`: variant decoding of commit/superblock metadata and
  delta file parsing.

## Specific things worth checking

- `missing_objects` slices each client-supplied string with `object[..2]` and
  `object[2..]`; check what happens with short, empty or multi-byte strings.
- `generate_flatpakref` interpolates ref components (app id, branch) into an INI
  file without escaping; check whether newlines or `=` in a ref name reach the
  served `.flatpakref`.
- `validate_ref` accepts any four-component `app/`/`runtime/` ref whose id
  matches the token prefix; the branch component is not character-restricted.
- `verify_repo_token` takes the first matching app/runtime ref from commit
  metadata and stops; consider commits with multiple ref bindings, mixed
  app/runtime entries, or a missing `xa.token-type`.
- `get_commit_for_file` decides whether to authenticate by inspecting the
  on-disk path (`objects/xx/...commit`, `superblock`); consider alternate paths
  that resolve to an authenticated file or bypass the check.
- Screenshot publishing checks for symlinks and non-normal components; look for
  TOCTOU, hard links, special file types, and path handling in
  `copy_screenshot_file`/`open_destination_directory`.
- Upload permission handling (`set_upload_permissions`), `.tmp` staging in the
  upload repository, and delta files in `deltas/.tmp` served after retirement.
- `token_subset` builds narrower tokens; check that `sub`, `prefixes`, `apps`,
  `repos`, `branches` and `exp` cannot be widened and that intended revocation is
  preserved.
- `flatpak build-commit-from` invocations: `--untrusted` is used at commit time;
  check whether publish/republish paths assume validation that did not happen or
  was skipped.
- Application of `--end-of-life`, `--end-of-life-rebase` and `--token-type`
  values from API JSON into flatpak arguments.
- Error paths log the presented claims on 401/403 (`src/tokens.rs`), and job
  logs capture hook stdout/stderr. Check whether either channel can carry token
  or GPG material.

## How to exercise it

The image has the toolchain, PostgreSQL, flatpak, ostree and gpg, and compiled
test binaries:

```sh
cd /src
cargo test --locked
cargo test --locked -p flat-manager-client
```

Run a local server for API-level testing (all offline):

```sh
cd /src
service postgresql start
runuser -u postgres -- createuser --superuser root
runuser -u postgres -- createdb --owner=root repo
cp example-config.json config.json
mkdir -p build-repo
ostree --repo=repo init --mode=archive-z2
ostree --repo=beta-repo init --mode=archive-z2
./target/debug/flat-manager
```

Both configured repositories need an initialized OSTree repository before the
server starts: `repo` and `beta-repo`, matching the `path` values in
`example-config.json`. `build-repo-base` is `build-repo`.

`example-config.json` uses two repos (`stable`, `beta`), no GPG keys, a check
hook and a publish hook, and `secret: c2VjcmV0` (base64 `secret`), so tokens can
be minted locally. The `flat-manager-client` binary (`./target/release/`) and
`client/src/gentoken.rs` are useful for driving the API.

The end-to-end suite in `tests/` needs a privileged container with
`flatpak-builder` and Docker Compose, so it is not expected to run in the audit
VM. Use `tests/run-test.py`, `tests/docker-compose.yml` and `tests/Dockerfile` as
a description of intended API behaviour instead.

## How we rate severity

- Critical: remote code execution, arbitrary file write outside the
  build/repository directories, authentication bypass on a private repository
  or build, or forgery of signed commits/summary.
- High: privilege escalation between apps or repos using a scoped token,
  access to another app's build or private download, path traversal with
  controlled write, or disclosure of GPG private material or the token secret.
- Medium: denial of service reachable by an authenticated build client that
  disrupts other builds or the server, storing arbitrary attacker content where
  another security boundary consumes it, or token/claims leakage in logs.
- Low: panics that only fail the requesting build, information leaks of public
  data, or hardening gaps with no demonstrated impact.
- Plain volume-based denial of service (flooding requests, uploading very large
  files) is a property of a shared build service, so report it only when it is
  not simple volume: for example, a crafted input that wedges a job or the
  server and survives restart, or one build's input affecting other builds.

## Out of scope / do not report

- `/metrics` and `/status` are unauthenticated routes in `src/app.rs`; the
  missing authentication alone is the current design. Report sensitive data that
  they disclose, not the absence of a token check.
- The absence of CSRF protection and browser security headers: the API
  authenticates with bearer tokens, not cookies.
- `example-config.json`/`example.env` values (`secret: c2VjcmV0` is the literal
  base64 of "secret"): they are test fixtures.
- Container image and host hardening choices (for example the process running as
  root in the shipped Dockerfile) are deployment matters; issues in this
  codebase that cross a trust boundary remain in scope.
- Dependency-internal vulnerabilities in flatpak, OSTree, GLib, PostgreSQL,
  actix-web or rustls are out of scope unless this project's use of them makes
  the flaw reachable across the boundaries described above.
- The vendored `vendor/actix-multipart` crate is a real part of the codebase:
  parsing bugs in it are in scope, but do not report dependency versions alone.

## Reporting preferences

- A reproducer should name the endpoint, the token claims needed, and the exact
  request sequence (create build, upload, ref, commit, publish/download).
- For auth issues, state the required token scope and whether an unauthenticated
  client or a different app's token can trigger the same path.
- Prefer a minimal, deterministic proof of concept over a fuzzing campaign
  description. Build logs and database state are available locally, so include
  them when they establish the claim.
