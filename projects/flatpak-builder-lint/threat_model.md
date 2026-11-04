# Threat model — flatpak-builder-lint

## What this project does and where untrusted input enters

`flatpak-builder-lint` is a Python linter for Flatpak manifests, build
directories, exported OSTree repositories and AppStream metadata. It parses
artefacts and reports errors and warnings; it does not build the application.
The code can read the network and can execute helper programs.

Entry points and untrusted inputs:

- CLI: `flatpak-builder-lint {manifest,builddir,repo,appstream} PATH`, plus
  `--appid`, `--ref`, `--user-exceptions`, `--exceptions`,
  `--janitor-exceptions`, `--cwd` (`flatpak_builder_lint/cli.py`).
- Manifests: YAML and JSON, including sub-manifests referenced by string module
  and source entries. `manifest.show_manifest()` runs
  `flatpak-builder --show-manifest`; `collect_sub_manifests()` follows relative
  paths recursively.
- Build directories: `metadata` (GLib key file), `files/flathub.json`,
  `files/share/metainfo/*.xml`, `files/share/appdata/*.xml`,
  `files/share/app-info/xmls/*.xml.gz`, desktop files and ELF binaries.
- OSTree repositories: refs, commit metadata and checked-out `files/share`
  subtrees, via `ostree.extract_subpath()`.
- AppStream: `appstream.parse_xml()` uses lxml; metainfo checks call
  `appstreamcli validate --no-net --format yaml`. Direct `appstream` mode calls
  `appstreamcli validate --explain PATH` and does not pass `--no-net`.

Code-controlled data:

- `flatpak_builder_lint/staticfiles/`: exception list, JSON schema and fallback
  summary files, shipped with the code.
- Installed binaries (`flatpak-builder`, `appstreamcli`,
  `desktop-file-validate`, `ostree`) and Python packages.

Process environment, not manifest input: `REPO`, `REF`,
`FLAT_MANAGER_BUILD_ID`, `FLAT_MANAGER_BUILD_INFO`, `FLATPAK_BUILDER_LINT` and
`GITHUB_TOKEN`. `FLAT_MANAGER_BUILD_INFO` is parsed as JSON and used by
flat-manager checks.

## Untrusted source distinction

- Manifest, builddir and repository contents are untrusted. Paths, app IDs,
  URLs and XML derived from them are attacker-controlled.
- Network responses from Flathub and `raw.githubusercontent.com` are fetched over
  TLS from fixed endpoints. The app ID reachability check is different: the host
  comes from the manifest `id`, so the manifest selects the outbound
  destination.
- Exceptions change the result, not the input. `run_checks()` fetches remote
  exceptions first, falls back to the bundled `exceptions.json`, and then
  subtracts matching entries from `errors`, `warnings` and `info`.
  `--user-exceptions` takes precedence over both.
- Pipeline behaviour depends on `REPO`, `REF`, `FLAT_MANAGER_BUILD_ID` and
  `FLATPAK_BUILDER_LINT` (`config.is_flathub_*_pipeline()`). These are process
  environment values; a manifest cannot set them.

## Network-based logic

- `domainutils.check_url()` issues `requests.get` with
  `allow_redirects=False`. `checks/appid.py` calls it for an app-ID-derived
  `https://` URL built by `get_domain()` or `get_proj_url()`.
- `domainutils.fetch_summary_bytes()` fetches
  `https://dl.flathub.org/repo/summary` and
  `https://dl.flathub.org/beta-repo/summary`, with a bundled fallback file.
- `_get_manual_verification_domains()` fetches
  `raw.githubusercontent.com/flathub-infra/website/HEAD/backend/app/staticfiles/manual_verifications.json`.
- `get_remote_exceptions_flathub()` fetches
  `https://flathub.org/api/v2/exceptions/<appid>`;
  `get_remote_exceptions_github()` fetches the linter's
  `exceptions.json` from `raw.githubusercontent.com`.
- `exceptions_janitor` posts to the GitHub API when `--janitor-exceptions` is
  used in a Flathub pipeline with `GITHUB_TOKEN` set.
- `urllib3` is forced to IPv4 DNS resolution. `requests-cache` stores responses
  in SQLite under `XDG_CACHE_HOME/flatpak-builder_lint`.
- There is no allowlist and no private-address, loopback or link-local filter
  on `check_url()`. Redirects are disabled there.
- `appstreamcli` receives `--no-net` for metainfo validation but not in direct
  `appstream` mode, where its own network checks remain enabled.

## Components that matter most / least

Highest risk:

- `domainutils` URL construction, fetching and the persistent SQLite cache.
- `appstream.parse_xml()`, which parses attacker XML with lxml's default
  parser (no explicit `load_dtd`/`resolve_entities` settings), and gzip
  decompression of AppStream catalogues.
- `manifest.collect_sub_manifests()` and `validate_manifest_files()` path
  handling, including symlinks and recursive scans.
- `manifest.show_manifest()`, because `flatpak-builder` parses the untrusted
  manifest in a native program.
- Exception loading, because exceptions remove reported errors and warnings.

Lower risk but in scope:

- String checks in `finish_args`, `desktop`, `modules`, `flathub_json`,
  `catalogue` and `toplevel`.
- ELF architecture sniffing and repository size accounting.
- Logging to `XDG_STATE_HOME/flatpak_builder_lint/linter.log`.

## How to exercise it

The image starts from the project's published production image, pinned by
digest, and keeps the checkout at `/src`. It uses that image's Python 3.14
environment; `pytest` and `pytest-xdist` are installed in `/opt/venv` with
system site packages, and the bundled Flathub summary files are copied into
`/src/flatpak_builder_lint/staticfiles`. Run from `/src`:

```sh
python -m pytest -vv
python -m pytest tests/test_unit_manifest.py tests/test_unit_domainutils.py -vv
python -m pytest tests/test_builddir_and_repo.py -vv
python utils/validator.py
```

The default pytest configuration in `pyproject.toml` ignores `tests/repo` and
`tests/test_httpserver.py` and deselects tests marked `integration`. The
autouse `mock_domainutils` fixture in `tests/conftest.py` mocks `check_url`,
`get_remote_exceptions_*`, manual verification domains and EOL data.

Direct invocations:

```sh
flatpak-builder-lint manifest tests/manifests/finish_args.json
flatpak-builder-lint builddir tests/builddir/finish_args
flatpak-builder-lint appstream \
  tests/builddir/appstream-broken-icon/org.flathub.appstream_broken_icon.metainfo.xml
```

The `manifest` invocation calls `flatpak-builder`; the `appstream` invocation is
the mode that does not pass `--no-net`.

## How you rate severity

- Critical: code execution or container escape in the linter process,
  credential theft, or arbitrary file write through a manifest or builddir.
- High: server-side request forgery that reaches metadata services or internal
  HTTP endpoints, command injection, or parser memory-safety/entity issues
  reachable from attacker XML.
- Medium: denial of service that reliably fails CI (deep YAML/JSON, gzip
  expansion, huge repositories, pathological regex), or information disclosure
  through error output.
- Low: issues that require trusted environment configuration or only affect
  local formatting.

## Triage boundaries

- Filesystem writes are not limited to `exceptions_janitor`, which requires
  `--janitor-exceptions`, a Flathub pipeline environment and `GITHUB_TOKEN`.
  Normal CLI runs create a log directory and file; importing `domainutils`
  creates a cache directory and SQLite cache; repository checks check out
  attacker-controlled objects. Treat these writes as part of the analysis.
- Findings in the linter's use of `flatpak-builder`, `appstreamcli`, OSTree or
  lxml are in scope when linter input crosses a trust boundary.

## Known limitations of this environment

- `tests/test_integration_smoke.py` (marker `integration`) needs flatpak,
  flatpak-builder, dbus, network and Flathub runtimes. The image installs the
  tools but not the Flathub runtimes, so these tests are not part of the offline
  scan.
- The base image is the project's published production image pinned by digest.
  It provides Python 3.14, `appstreamcli` 1.2.0 and `flatpak-builder` 1.4.12,
  and its installed `staticfiles` supply the summary files copied into `/src`.
  Rebuilding that production image from `docker/Dockerfile` still requires the
  nested `org.flatpak.Builder/builddir/files` build.
- Network-dependent behaviour (app-ID reachability, summary downloads, remote
  exceptions, janitor comments) cannot be exercised after network removal;
  those paths are covered by mocked unit tests.
