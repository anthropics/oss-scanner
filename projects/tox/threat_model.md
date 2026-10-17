# Threat model

The reporting policy is `.github/SECURITY.md`. Submit vulnerabilities through GitHub private vulnerability reporting or
the Tidelift contact described there; do not open a public issue.

## What tox does and where untrusted input enters

tox reads project configuration from `tox.ini`, `setup.cfg`, `pyproject.toml` (native `[tool.tox]` TOML or deprecated
`legacy_tox_ini`), or `tox.toml`. It selects Python interpreters, creates and reuses environments, builds the project,
installs packages and runs configured commands. Configuration loading lives under `src/tox/config/`; environment
selection under `session/`; package construction under `tox_env/package/`; installation in `tox_env/installer.py`;
command execution under `execute/`; and automatic self-provisioning in `provision.py`.

Project configuration is code. A checkout can name commands, build backends, dependencies, package indexes and plugins
that execute with the user's privileges. Running tox on an untrusted checkout is therefore equivalent to running that
checkout. As in other build frontends, arbitrary behavior requested by configuration is not an escape from a sandbox:
tox provides no operating-system sandbox.

Security boundaries remain where tox transforms data into a command or path, cleans files outside the requested
workspace, selects code other than the configured package, or exposes a secret it promises to redact. Inputs to test
include:

- INI and TOML values, substitutions, factors, labels, `posargs`, command argument arrays, environment-file lines and
  package configuration;
- branch names, paths and other CI values passed into substitutions or positional arguments;
- package metadata, wheel and sdist filenames, backend hook results, installer output and subprocess byte streams;
- checkout, work and environment trees containing symlinks or files exchanged during recreation and cleanup;
- plugin metadata and inline-plugin configuration; tox trusts installed plugins as code, but must load the distribution
  the configuration selected;
- URLs, tokens and environment values that pass through command rendering, journals, errors or debug output.

virtualenv, python-discovery and pyproject-api are adjacent trust domains. Their own threat models trust an interpreter
that the user selected, a configured build backend and a user-owned cache. A report against tox should identify the
unsafe argument, path or result handling that tox adds around those dependencies.

## Components to prioritize

Review `execute/` for argv construction, Windows quoting, shell selection, working directories, interrupts, terminal
handling and decoding of hostile output. A configured argument must remain one argument through replacements and
re-execution. Treat terminal control sequences as low impact unless the report demonstrates a boundary beyond displaying
command output.

In `config/`, trace each replacement and type conversion until its consumer. Pay particular attention to `set_env.py`,
positional-argument expansion and TOML versus INI parity. Configuration may request a command, but a data value must not
create an extra command or option unless the documented syntax grants that power.

Audit environment recreation, package staging, temporary directories, result journals, work-directory cleanup and
`util/venv_redirect.py` for symlink races and recursive operations outside tox's own roots. `provision.py` must install
and re-exec the requested tox requirement with the original argv and interpreter constraints. `util/redact.py`, reports
and journals must not expose credentials that match tox's documented redaction rules.

Tests, documentation and release automation are not production entry points. Use them as fixtures and regression
locations, not as the sole affected code.

## How to exercise the image

The checkout is at `/src`; the image installs tox in `/opt/venv` with the completion extra and test dependency group.
Run `python -m pytest tests`. Focused tests under `tests/config`, `tests/execute`, `tests/session` and `tests/tox_env`
create temporary projects without network access.

A useful reproducer is a minimal project containing one tox environment and only the crafted value needed for the issue.
Place sentinels inside and outside `.tox`, record the spawned argv, and show any filesystem effect or disclosed value.
Run permission and cross-user cases as an unprivileged account because the scanner shell is root.

## Severity

- Critical: a service that documents tox configuration as non-executable data suffers code execution outside its stated
  containment. Name that service and its boundary; tox alone makes no such promise.
- High: a crafted checkout or race makes tox delete, overwrite or disclose a file outside its work, environment and
  package directories with privileges beyond the attacker's; or tox emits a CI credential covered by its redaction
  contract.
- Medium: data crosses an argv boundary and invokes an additional command or option beyond the configuration's
  documented meaning; provisioning selects an unintended tox package or interpreter; or a journal persists sensitive
  data outside the project workspace.
- Low: a crash, hang, terminal effect without demonstrated code execution, or corruption limited to the disposable tox
  environment.

## Reports and exclusions

Include the tox commit, platform, command, complete configuration, relevant environment, spawned argv and minimal
checkout. Identify the least privilege the attacker needs and the path that crosses the boundary.

Do not report:

- commands, backends, installers, indexes, interpreters or plugins selected by project configuration;
- access by a configured command to the user's files, network or environment;
- installation-time code execution by a requested package or dependency;
- dependency confusion caused only by the configured package index;
- a defect in virtualenv, python-discovery, pyproject-api, pip, uv or a plugin when tox invokes it as documented.
