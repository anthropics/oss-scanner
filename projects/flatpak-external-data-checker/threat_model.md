# Threat model — flatpak-external-data-checker

## What this project does and where untrusted input enters

`flatpak-external-data-checker` reads a Flatpak manifest, finds sources with
`x-checker-data`, queries upstream projects for new versions, downloads
candidate artefacts to compute checksums, and can rewrite the manifest. With
`GITHUB_TOKEN` and the commit/PR options it can commit, push and open pull
requests.

Entry points and untrusted inputs:

- CLI modes: read-only check (default), `--lint` (no network, no writes),
  `--update`/`--edit-only` (rewrite manifests), `--commit-only` (commit), and
  default PR mode. Options include `--unsafe`, `--max-manifest-size`,
  `--filter-type`, `--enable-robots-txt`, `--pr-labels` and
  `--commit-to-current-branch` (`src/main.py`).
- Manifest files: JSON or YAML, plus referenced module files and external source
  JSON/YAML files. Each file is capped by `MAX_MANIFEST_SIZE` (1 MiB by
  default); the number of referenced files is not capped.
- `x-checker-data` values: URLs, `baseurl`, regex patterns, jq expressions,
  version templates, `root` package repositories, names, channels and arch
  lists.
- Remote responses: JSON, YAML, HTML, XML (RPM repodata), HTTP headers,
  downloaded archives, `.deb` and `.AppImage` files, and `git ls-remote` output.
- Working tree: `flathub.json` (`automerge-flathubbot-prs`) and the git remote.
- Environment: `GITHUB_TOKEN`, proxy variables (aiohttp uses
  `trust_env=True`), `XDG_CACHE_HOME`, `GITHUB_RUN_ID`,
  `GITHUB_REPOSITORY`.

Code-controlled data:

- The tool's own source, bundled schemas and the runtime image.

## Untrusted source distinction

- `--lint` performs no network requests and writes no files (`src/lint.py`).
  It still parses untrusted YAML/JSON, resolves referenced files, compiles
  manifest-supplied regexes and runs `jq` with empty input to syntax-check
  queries.
- Default check mode performs network reads and does not modify the manifest.
- `--update`, `--edit-only` and the commit/PR modes rewrite files and can push.
  They read the working tree they are pointed at.
- `--unsafe` is parsed into `CheckerOptions.allow_unsafe` but no code in this
  tree reads that field. The option has no effect here.
- Manifest and `x-checker-data` URLs are not checked against an allowlist or a
  set of trusted upstreams.
- `GITHUB_TOKEN` is added explicitly to requests whose URL host is
  `api.github.com` (`src/checkers/jsonchecker.py`). For `git push` it is
  embedded in a temporary HTTPS remote URL and redacted from push failure
  output.
- `flathub.json` is read from the working tree. Its
  `automerge-flathubbot-prs` value participates in the auto-merge decision.

## Network-based logic

- `aiohttp.ClientSession` is created per check run with connect/read/total
  timeouts (10 s / 60 s / 600 s) and `raise_for_status=True`
  (`src/manifest.py`). It uses `trust_env=True`, so proxy environment variables
  affect routing.
- URL checker: fetches the manifest URL or `x-checker-data.url`, follows
  redirects, records the final URL and downloads the artefact to hash it.
- JSON checker: fetches `x-checker-data.url` and any `*-data-url`; later URLs can
  come from the remote JSON via `url-query`.
- HTML checker: fetches `x-checker-data.url`, applies manifest regexes, and
  fetches the resulting absolute or relative URL.
- Anitya checker: fetches `<baseurl>/api/v2/versions/`, where `baseurl` is
  manifest controlled.
- PyPI, GNOME, Snapcraft, JetBrains, Rust and Chromium checkers use hard-coded
  endpoints. Snapcraft uses plain `http://api.snapcraft.io`; the SHA3-384 digest
  it verifies comes from that same response, so neither the metadata nor the
  digest has transport integrity.
- Electron checker fetches `x-checker-data.url`, or `latest-linux.yml` next to
  the current source URL.
- Debian checker: drives python-apt (`apt.Cache.update()`) against a manifest
  `root`, with `trusted=yes` and no GPG verification, then reads package
  metadata and modifies process-global `apt_pkg.config` state.
- RPM checker: fetches `repodata/repomd.xml` and a primary metadata file from a
  manifest `root` and parses the XML.
- Git checker: `git ls-remote` against the manifest git URL through
  `utils.Command`. That wraps the call in `bwrap --unshare-all --share-net` with
  read-only CA and resolver paths when bubblewrap works; otherwise it runs
  unsandboxed.
- Downloads are streamed through `MultiHash` without a size limit.
  `get_extra_data_info_from_url()` rejects HTML/text content for file and
  archive sources with a deny list and `python-magic` after the first chunk.
- Optional robots.txt handling is disabled by default, can be enabled per run or
  per source, fails open on network errors, and caches rules in
  `~/.cache/fedc/robots`.
- `open_pr()` may fork, push with an empty `--force-with-lease`, create a PR,
  set labels, comment, and merge the PR when `automerge-flathubbot-prs` is true
  (or the current source is broken) and the combined commit status is
  `success`.

There is no SSRF protection on these paths: no allowlist, no private, loopback
or link-local address rejection, no DNS pinning, and redirects are followed.

## Components that matter most / least

Highest risk:

- `src/lib/utils.py`: download, hashing, sandbox and command helpers.
- `src/manifest.py`: path resolution for external modules and source files, and
  the update/write path.
- `src/checkers/debianrepochecker.py`: drives apt in-process with
  `trusted=yes` against a selected repository.
- `src/checkers/jsonchecker.py` and `src/lint.py`: jq execution.
- `src/main.py`: git and PR flow, token handling and auto-merge.
- `src/checkers/urlchecker.py`: `.deb` and `.AppImage` handling, including
  `apt_inst.DebFile`, ELF headers and `unsquashfs`.

Lower risk but in scope:

- Fixed-endpoint checkers, version comparison and template expansion.
- Appdata rewriting, which uses lxml with `load_dtd=False` and
  `resolve_entities=False`.
- RPM XML parsing, which uses `XMLPullParser(load_dtd=False,
  resolve_entities=False)`.
- Manifest formatting and newline preservation.

## How to exercise it

The image keeps `/src`, Debian trixie's Python 3.13 with python-apt, git, jq,
bubblewrap and squashfs-tools. Offline-safe commands from `/src`:

```sh
python3 -m unittest tests.test_lint tests.test_manifest tests.test_loader \
  tests.test_version tests.test_robots tests.test_network_timeouts \
  tests.test_appdata tests.test_manifest_load_cli tests.test_newlinepreservation -v
./flatpak-external-data-checker --lint tests/org.gnome.baobab.json
./flatpak-external-data-checker --lint tests/net.invisible_island.xterm.yml
python3 -m compileall -q src
```

`--lint` exercises manifest loading, checker selection, schema validation,
regex compilation, jq syntax and parent/child references without network or
writes.

## How you rate severity

- Critical: code execution or container escape in the checker process, theft of
  `GITHUB_TOKEN`, arbitrary write outside the checkout, or a push or merge to an
  unintended repository.
- High: server-side request forgery reaching cloud metadata or internal
  services, memory-safety or parser issues in python-apt, `unsquashfs` or jq
  reachable from attacker artefacts, arbitrary file read through external source
  references, or bypass of the `--lint` no-network/no-write behaviour.
- Medium: denial of service that breaks the run or exhausts disk/memory
  (unbounded downloads, decompression expansion, regex denial of service, large
  manifest trees), robots cache poisoning, or local file disclosure through
  error output.
- Low: issues that only affect local formatting.

## Triage boundaries

- The only mode with no network requests and no file writes is `--lint`; the
  effects of the other modes are described above.
- Findings that depend on a Python library version must account for the Debian
  package version actually installed, not the pin in `pyproject.toml`.
- The `--update`/PR path is destructive by design; do not run it during analysis
  against a checkout that matters.

## Known limitations of this environment

- The full unittest suite is not offline. `tests.test_checker`,
  `tests.test_htmlchecker`, `tests.test_jsonchecker`, `tests.test_urlchecker`
  and `tests.test_util` include tests that contact `httpbingo.org`,
  `api.github.com`, `github.com` or `dl.google.com`. A full `discover` run
  therefore reports failures with network removed. Use the offline-safe module
  list above.
- The container matches the repository's Debian trixie and Python 3.13
  environment, including the `python3-apt` ABI. Python libraries come from
  Debian packages, as in the upstream `Dockerfile` and `dependencies.apt.txt`,
  not from the exact pins in `pyproject.toml`.
- There is no `GITHUB_TOKEN`, so PR creation, forking, auto-merge and push
  behaviour cannot be exercised end to end; reason about `open_pr()` from source.
- Tests that exercise real Debian or RPM repositories, real upstream metadata,
  `.deb` files or AppImages require network and are not part of the offline
  subset.
