# Threat model

The authoritative reporting policy is `.github/SECURITY.md`. It supports the latest release and accepts private reports
through GitHub.

## What python-discovery does and where untrusted input enters

python-discovery finds interpreters from an explicit path or specification, preferred candidates, the running
interpreter, `PATH`, Windows PEP 514 registrations and uv-managed installations. It runs a bundled interrogation script
in each candidate, parses the result into `PythonInfo`, applies `PythonSpec` constraints and may cache the metadata on
disk. virtualenv and tox depend on this selection when choosing the process that will run project code.

The caller trusts interpreters that it names, finds on its trusted `PATH`, reads from the same Windows user's registry
or finds in that user's uv directory. Discovery executes those interpreters by design. A report needs a boundary beyond
“a malicious interpreter runs”: argument injection, selection outside the requested source, cross-user cache poisoning
or a constraint bypass that causes a higher-privilege caller to execute an interpreter the attacker could not otherwise
select.

Inputs to test include:

- interpreter specifications, absolute and relative paths, `try_first_with` candidates and caller predicates;
- `PATH`, home, uv and timeout values from the supplied environment mapping;
- directory entries, symlinks and shims encountered during search;
- stdout, stderr, exit status, timing and metadata returned by a candidate process;
- PEP 514 registry values, including `ExecutablePath`, `InstallPath` and raw `ExecutableArguments`;
- JSON and lock files under a shared or populated `DiskCache`;
- slow, non-Python or adversarial executables with Python-like names.

## Components to prioritize

Review `src/python_discovery/_discovery.py`, `_specifier.py` and `_py_spec.py` for search order and final constraint
checks. Version, implementation, architecture, free-threaded and debug requirements must apply to the selected
`system_executable` as well as the shim or launcher. Relative specifications must follow the documented
current-interpreter and `PATH` order without an implicit working-directory search.

`_cached_py_info.py` constructs the interrogation command, adds PEP 514 arguments on Windows, frames JSON between random
cookies, retries failures and enforces `PY_DISCOVERY_TIMEOUT`. Check Windows command-line quoting with raw
`ExecutableArguments`; cookie confusion from hostile stdout; output size before JSON parsing; timeout cleanup; and child
processes that keep pipes open. A candidate is already trusted code, so command-injection severity depends on executing
something other than that candidate and its registered arguments.

`_cache.py` keys entries by interpreter path and records the path mtime, interrogation-script hash and PEP 514
arguments. Audit symlink races, file ownership, JSON replacement, lock paths, atomicity and aliases between executable
paths. Cross-user cache poisoning matters when a victim uses a cache directory the attacker can modify but cannot
replace the selected interpreter itself. Apply filelock's threat model to lock-file mechanics and keep python-discovery
findings focused on the decision to trust cached interpreter data.

Under `_windows/`, test the HKEY_CURRENT_USER and HKEY_LOCAL_MACHINE precedence, 32-bit and 64-bit views, malformed
value types, duplicate registrations and `ExecutableArguments`. uv traversal must stay in the configured uv root and
reject installations that fail the final specification.

## How to exercise the image

The image installs the project from `/src` into `/opt/venv` with its test group. Run `python -m pytest tests`. The suite
includes executable fixtures, cache corruption and timeout cases.

Pass an explicit environment mapping and temporary `DiskCache`, then create executable fixtures that emit missing,
repeated or partial cookie markers, large output, invalid JSON and delayed child output. Record every spawned argv and
the final `PythonInfo`. Linux can test Windows parsers and command construction, but a claim about Windows process
parsing needs a Windows reproducer.

## Severity

- High: a constrained specification or PEP 514 record executes a separate attacker-controlled command through argument
  handling, without attacker control of the trusted interpreter source, `PATH` or registry scope.
- High: a local user poisons a shared cache so a higher-privilege victim accepts and executes an interpreter outside the
  requested constraints, while the attacker cannot modify that interpreter or the victim's search sources.
- Medium: cache poisoning changes security-relevant interpreter metadata without execution, cache cleanup changes a path
  outside the configured root, or a small candidate response causes sustained memory or process exhaustion.
- Low: discovery returns the wrong interpreter without crossing a privilege boundary, rejects a valid interpreter,
  crashes on malformed output or uses stale metadata from a cache owned by the same user.

## Reports and exclusions

Include the python-discovery commit, platform, public API call, specification, environment mapping, candidate filesystem
or registry state, cache ownership, spawned argv, raw framed output and selected `PythonInfo`. State why the selected
interpreter was outside the caller's trusted sources.

Do not report:

- execution by an interpreter the caller named, placed on trusted `PATH`, registered in its trusted registry scope or
  installed in its uv directory;
- arbitrary behavior in a caller-supplied predicate;
- false metadata printed by a hostile interpreter unless it breaks a separate caller-enforced selection boundary;
- a cache modified by the same user who controls every interpreter source;
- a defect in filelock, the Windows registry API or uv's installer that reproduces without python-discovery.
