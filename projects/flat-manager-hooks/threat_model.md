# Threat model: flat-manager-hooks (flathub-hooks)

## What this project does

`flathub-hooks` is the Rust binary that Flathub's flat-manager runs as its
publish and review hooks, plus a standalone `validate` subcommand. One binary,
three subcommands (`src/main.rs`):

- **publish** (`src/cmd_publish.rs`): runs inside a build repository directory
  during flat-manager's publish job. It lists the refs in the build, fetches
  storefront metadata from the Flathub backend for each app id, rewrites the
  app's `files/share/app-info/xmls/<app>.xml.gz` with `flathub::` metadata,
  verification, pricing, build-log URLs and a bugtracker URL, rewrites commit
  metadata (`xa.subsets`, `xa.token-type`), and writes new commits and refs into
  the build repository. flat-manager then imports and signs those commits.
- **review** (`src/review/`): runs during flat-manager's check job. It validates
  every primary `app/` ref: launches `flatpak-builder-lint` through `flatpak run`
  in the `org.flatpak.Builder` application, validates the appstream catalog file
  (gzip + XML, single `<component>`, matching app id, build-log URL for free
  software), reports diagnostics, asks the backend whether the change needs
  moderator review, and sets the check status through flat-manager's API.
- **validate** (`src/cmd_validate.rs`): the same validation as review, with no
  backend calls, printing JSON diagnostics; used by `tests/run_tests.sh`.

The binary receives a JSON config file (`--config`) containing `backend_url`,
`flat_manager_url`, `flat_manager_token` and `validation_observe_only`, and
flat-manager passes `FLAT_MANAGER_BUILD_ID`, `FLAT_MANAGER_JOB_ID` and
`FLAT_MANAGER_IS_REPUBLISH` in the environment.

## Trust boundaries and untrusted input

1. **The build repository is attacker-controlled.** The objects, trees, blobs,
   refs and commit metadata in the build repository were uploaded by an app
   developer. Publish and review parse that data directly with the `ostree`
   crate and `elementtree`, and decompress gzip streams from it (`GzDecoder` in
   `src/utils.rs` and `src/cmd_publish.rs`). Treat ref names, appstream XML,
   desktop/ELF files and commit metadata as hostile.
2. **The Flathub backend is semi-trusted.** `StorefrontInfo` and the
   `is-free-software` response (`src/storefront.rs`) are typed JSON from another
   service; their strings are injected into appstream XML. `backend_url` and
   `flat_manager_url` come from the operator config, not from the build.
3. **The flat-manager token is highly privileged.** `flat_manager_token` lets
   the review hook set check status (`/api/v1/job/<id>/check/review`) and read
   build metadata; the same token is sent as a bearer to the backend for
   moderation and email notifications (`src/config.rs`). It is material to
   protect: it must not leak into job logs or diagnostics.
4. **The Flatpak application sandbox is the isolation boundary for linting.**
   The review hook runs `flatpak run --command=flatpak-builder-lint
   org.flatpak.Builder --exceptions --exceptions-repo <backend repo> repo`
   (`src/review/validation.rs`). That Flatpak application's own sandbox controls
   what its linter process can access; repository contents and the backend's
   exceptions response are attacker-influenced inputs to it. Check the child
   process boundary and the data passed to it.
5. **Execution location.** These hooks execute as the flat-manager service
   inside the build directory, with write access to the build repository and
   with the flat-manager token in its config file. There is no second privilege
   drop between the hook and the build tree.

## Components that matter most

- `src/review/validation.rs`: linter invocation and arguments, appstream
  validation, commit and appstream parsing.
- `src/cmd_publish.rs`: gzip decompression, XML rewriting, commit rewriting and
  ref updates; the only subcommand here that writes to the repository.
- `src/utils.rs`: `load_appstream`, `read_file_from_repo`, `mtree_lookup`,
  `app_id_from_ref`, `Transaction`.
- `src/config.rs`: where the token lives, which URLs it is sent to, error and
  retry behaviour.
- `src/review/mod.rs` and `moderation.rs`: decision to fail, request review, or
  leave pending; a mistake here can let a build through review.

## Specific things worth checking

- Unbounded gzip and XML handling: `GzDecoder::read_to_string` on
  `files/share/app-info/xmls/<app>.xml.gz`, `Element::from_reader`, and
  `repo.load_file(...).read_all(&mut buffer)`, whose buffer size comes from the
  commit's file metadata. Check whether a commit can make the declared or
  decompressed size far larger than the stored object.
- `app_id_from_ref` unwraps the second `/`-separated component; `publish`
  applies it to every ref in the repository, while `review` applies it to each
  primary ref. Consider ref names with fewer components or unusual characters.
- `rewrite_appstream_xml` assumes exactly one `<component>` element and mutates
  `<custom>`, `<metadata>` and `<url type="bugtracker">` nodes. Check whether
  attacker XML can steer values that the website, appstream consumers, or
  Flatpak clients later trust (for example `flathub::manifest`, preserved
  intentionally).
- `flathub::build::build_log_url` and `build_ref_log_url` come from flat-manager
  build metadata and are inserted without scheme validation; only
  `validate_appstream_catalog_file` checks `Url::parse` on the FOSS path.
- Path handling around `mtree_lookup`, the appstream filename
  (`<app_id>.xml.gz`), and the rewritten commit tree. Confirm an app can only
  rewrite paths belonging to its own ref.
- The linter command construction and `--exceptions-repo` argument. Values are
  passed as argv, not through a shell, but the repository string and response
  content are attacker-influenced.
- Token handling: every `reqwest` call, retry closure, error message and
  `anyhow` context in `src/config.rs` and `src/storefront.rs`; and diagnostics
  written back to flat-manager that may include attacker content or local paths.
- `Transaction::drop` expects `abort_transaction` to succeed and panics
  otherwise; `diff::lines` builds a full string of the appstream diff and logs
  it at info level. Check both for availability impact on the publish job.
- `is-free-software` sends the appstream `<project_license>` text as a query
  parameter; consider size and content of that value.
- `validation_observe_only` changes a failure into `Pending`; make sure it
  cannot be used to bypass a real check.

## How to exercise it

The image contains the toolchain, libostree/glib, flatpak, flatpak-builder,
org.flatpak.Builder and the fixture runtimes, and compiled test binaries:

```sh
cd /src
cargo test --locked
```

Unit tests cover ref/app-id helpers and appstream rewriting. The fixture suite
in `/src/tests/run_tests.sh` builds Flatpak commits and compares `validate`
output. It needs user namespaces and a remote screenshot, so the suite is not
available offline as written. To exercise validation offline, use a prepared
repository:


```sh
cd /path/to/prepared/build/repo
/src/target/debug/flathub-hooks validate
```

`publish` and `review` need a running flat-manager and backend. The audit VM
has no outbound network, so if loopback is usable, point `backend_url` and
`flat_manager_url` at a local stub HTTP server (for example
`python3 -m http.server` plus a small handler), set `FLAT_MANAGER_BUILD_ID`,
`FLAT_MANAGER_JOB_ID` and `FLAT_MANAGER_IS_REPUBLISH`, and run
`/src/target/debug/flathub-hooks publish --config /path/config.json` or
`review --config ...` from inside a build repository.

## How we rate severity

- Critical: sandbox escape or host file write from the lint child process,
  arbitrary code execution inside the hook process, or disclosure of
  `flat_manager_token` to the build author.
- High: an app can cause the publish hook to modify another app's refs or
  metadata; a check can be forced to pass without review; or path traversal
  with write outside the build repository.
- Medium: memory exhaustion or panic on attacker input that is not limited to
  the author's own build, sensitive path disclosure in diagnostics, or
  injection into appstream values consumed by clients.
- Low: crashes or log noise that only affect the submitting build, or
  hardening gaps without demonstrated impact.

## Out of scope / do not report

- Dependency-internal vulnerabilities in `flatpak-builder-lint`, Flatpak,
  bubblewrap, OSTree, GLib, serde, elementtree, flate2, reqwest or rustls are
  out of scope unless this project's use of them crosses the boundaries above.
- The Flathub backend, the moderation service, the email service and the
  storefront API; only their responses as consumed here are in scope.
- Appstream specification disagreements, metadata quality, or linter policy
  (for example the license-URL rule and its exceptions).
- Resource limits on the `flatpak run` child process; the hook sets none and
  that is a current design choice, not a finding by itself. An input that
  persistently exhausts the hook or escapes the `org.flatpak.Builder`
  application sandbox is still reportable.
- The contents of `tests/` fixtures as vulnerabilities; they are test data.
- Whether `validation_observe_only` should be enabled is an operator policy
  decision. A code path that ignores the setting, or lets build content flip
  it, is in scope.

## Reporting preferences

- For sandbox or write bugs, give the exact repository layout needed (ref name,
  commit tree entries, appstream file) and the command that exhibits it.
- For token or information leaks, show which log, response or diagnostic field
  carries the value and who can read it.
- Prefer a minimal fixture commit plus a before/after `validate` JSON over a
  description of a fuzzing run.
