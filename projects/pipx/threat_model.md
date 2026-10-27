# Threat model

The authoritative reporting policy is `.github/SECURITY.md`. It supports current pipx releases and directs private
reports to Tidelift.

## What pipx does and where untrusted input enters

pipx installs Python applications into per-environment virtual environments and exposes their commands, manual pages and
shell completions into user-facing directories. It can run a package for one invocation, inject dependencies, upgrade or
rebuild environments, execute pip or uv, install a standalone Python, and import or export manifests.

pipx trusts packages selected by the user to run arbitrary installation and application code. Like virtualenv, pipx does
not sandbox that code. Its boundaries are package and interpreter selection, installer argv, ownership of managed
environments, exposure of package files, transaction recovery, downloaded-interpreter integrity and edits to shell
configuration.

Untrusted or malformed inputs include:

- package specifications, requirement files, VCS and file URLs, editable paths, suffixes, index URLs, interpreter
  requests and explicit installer options;
- distribution metadata, entry points, editable-install metadata, manual pages and completion files returned after
  installation;
- pipx metadata and manifest JSON, including older schemas and files changed by another process;
- existing paths and symlinks in `PIPX_HOME`, `PIPX_BIN_DIR`, `PIPX_MAN_DIR`, completion directories, shared libraries,
  caches and transaction backups;
- the release index, redirects, archive and digest used by `standalone_python.py`;
- installer and interpreter output used to determine whether an operation succeeded.

Directory overrides, custom indexes, passthrough installer arguments and interpreter paths are user choices that pipx
trusts. A report must show that pipx selects something else, changes an unrelated path, or violates a documented
integrity check.

## Components to prioritize

Review `package_specifier.py`, `interpreter.py`, `backends/pip.py`, `backends/uv.py` and `commands/execute.py` for
argument boundaries and precedence. A package specification remains one installer operand unless the user chose a
passthrough option. Metadata must not change the source interpreter, backend or index selected by the CLI.

Review path ownership in `venv.py`, `pipx_metadata_file.py`, `venv_inspect.py`, `commands/expose.py`,
`commands/uninstall.py`, `commands/transaction.py`, `commands/manifest.py`, `paths.py` and `shared_libs.py`. Test
entry-point names containing separators, absolute paths, reserved names and collisions. Exposure and rollback must leave
files outside the managed environment untouched. Concurrent pipx processes must preserve the same boundary.

`standalone_python.py` downloads a python-build-standalone archive, verifies its SHA-256 digest, rejects escaping
archive members and links, and swaps a staged interpreter into the cache. Examine redirect and release-index trust,
resume handling, checksum comparison, tar filters, pre-existing symlinks, backup cleanup and interrupted replacement.
This path downloads executable code and deserves the same scrutiny that scanner threat models give remote cache and
archive restoration.

`commands/ensure_path.py` edits shell startup files. It must choose the requested file, preserve unrelated content and
avoid following an attacker-controlled path across a user boundary.

## How to exercise the image

The repository is at `/src`, installed in `/opt/venv` with the uv extra and test group. Run
`python -m pytest tests -n auto`. The suite uses temporary pipx homes, local package fixtures and a local package
server.

Build a small wheel with crafted entry points and data files, then set every `PIPX_*` directory to a temporary tree.
Place sentinels and symlinks around the managed roots and record changes after install, expose, upgrade, manifest and
uninstall operations. For standalone Python, use a local HTTP fixture and an archive with a controlled digest; do not
contact a public package index in a reproducer.

## Severity

- Critical: under default trust settings, pipx accepts one package or interpreter request but fetches and executes a
  different attacker-selected artifact without prior attacker code execution.
- High: crafted metadata, manifest data, archive entries or a filesystem race makes pipx overwrite, expose or delete a
  file outside its configured roots; installer argument injection changes the package or index; or standalone Python
  proceeds after a digest mismatch.
- Medium: one local user can replace another user's exposed command through supported shared-directory use; a malformed
  metadata file redirects an operation to another managed environment; or transaction recovery restores an
  attacker-selected file.
- Low: denial of service, stale links, incorrect listings or corruption confined to the disposable environment of the
  requested package.

## Reports and exclusions

Include the pipx commit, command, environment variables, interpreter, package artifact and metadata, initial filesystem
tree, spawned installer argv and final files. Identify which input came from the user, package, network or another local
user.

Do not report:

- execution by a package, dependency, backend or application the user selected;
- behavior requested through pip/uv arguments, a custom index, a custom interpreter or relocated pipx directories;
- access by a user who can already write every configured pipx directory and startup file;
- typosquatting or dependency confusion when pipx preserves the requested name and index;
- a defect in pip, uv, virtualenv, filelock, packaging tools or an installed application that reproduces without pipx.
