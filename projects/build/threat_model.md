# Threat model

## What build does and where untrusted input enters

build is the PyPA frontend for building source distributions and wheels from PEP 517 projects. `ProjectBuilder` reads
the `[build-system]` table, invokes backend hooks, checks build requirements and returns the backend's artifact. The CLI
adds isolated-environment creation, requirement installation, sdist-to-wheel builds and report generation.

Project build configuration is executable. The backend named by `pyproject.toml`, its in-tree `backend-path`, its build
requirements and legacy `setup.py` can run arbitrary code with the caller's privileges. No sandbox contains an untrusted
checkout. This is the same boundary used by other build tools: configuration can request code execution, while an input
escaping a promised path or argument boundary is not.

Inputs worth treating as hostile are:

- the types and values under `[build-system]`, including requirement strings, backend names and `backend-path` entries;
- values returned by backend hooks, including additional requirements, metadata directory names, artifact filenames and
  exceptions;
- source, output, report, constraint and isolated-environment paths, including pre-existing symlinks and files;
- wheel and sdist filenames and archive contents when build opens them to inspect metadata or chains an sdist build into
  a wheel build;
- backend and installer stdout, stderr, encodings and exit statuses;
- custom runners supplied through the Python API. build trusts the runner as code, but must pass the documented argv,
  working directory and environment without changing their meaning.

pip, uv, `venv`, `pyproject-hooks` and the selected backend have separate security boundaries. Attribute a report to
build only when its validation, path handling or invocation makes the defect reachable.

## Components to prioritize

Start with `src/build/_builder.py`. Review `_parse_build_system_table`, backend-path validation, dependency checks,
metadata preparation, hook exception handling and artifact selection. A backend path must satisfy the PEP 517 in-tree
rule on every platform, including through symlinks, `..`, drive-relative and UNC forms. Hook results must name the
artifact produced for that invocation rather than an absolute path, an earlier file or a sibling outside the backend
output directory.

In `src/build/env.py`, inspect isolated-environment creation, caller-supplied environment paths, interpreter selection,
dependency installation, `PATH`/`PYTHONPATH` construction and cleanup. A requirement string is one installer operand,
even when it contains URLs, markers or shell metacharacters. Recursive cleanup must not follow a path exchanged after
validation.

The CLI in `src/build/__main__.py` controls temporary directories, output replacement, sdist extraction, config
settings, constraint files and build reports. Treat archive members from a backend-produced sdist as coming from already
trusted backend code, but still check whether build adds an unsafe extraction or destination choice beyond that trust.

Tests and documentation are useful fixtures. Release and CI automation are outside the installed frontend unless a
production code path shares the defect.

## How to exercise the image

The checkout is at `/src`; the image installs build and its test dependencies in `/opt/venv` and places a wheel under
`/opt/wheels`. Run `python -m pytest tests`. The fixtures under `tests/packages` and helpers in
`tests/integration_sources.py` cover in-tree backends, malformed metadata and artifact production.

Use a minimal source tree and backend for a security reproducer. Make one hook return the crafted requirement, metadata
path or artifact name, then call the public `ProjectBuilder` API or `python -m build`. Record the runner arguments and
filesystem before and after the call. Use local wheels or a mocked installer because the scan is offline.

## Severity

- High: build accepts a backend or artifact outside the PEP 517 permitted roots and thereby executes, overwrites or
  discloses code or data that the selected backend could not already reach through its trusted execution.
- High: an attacker who controls a path inside the source or isolated environment uses a symlink race to make build
  delete or overwrite an unrelated file with higher privileges.
- Medium: a requirement or config value crosses an argv boundary and changes the installer operation; build reports an
  artifact from the wrong directory or invocation; or cleanup escapes a caller-supplied temporary root.
- Low: a controlled exception, hang, misleading diagnostic or invalid artifact with no demonstrated confidentiality or
  integrity impact.

## Reports and exclusions

Include the build commit, API or CLI command, source tree, complete `[build-system]` table, backend hook results,
selected runner, spawned argv and resulting files. State which behavior belongs to build rather than the backend or
installer.

Do not report:

- arbitrary behavior by the backend, `setup.py` or build requirements selected by the project;
- installation-time execution by a requested dependency;
- a custom runner changing the command it receives;
- malicious wheel or sdist contents that build returns without interpreting;
- package-index compromise or dependency confusion when build preserves the requested requirements and index
  configuration;
- a defect in pip, uv, `venv`, `pyproject-hooks` or a backend that reproduces without build.
