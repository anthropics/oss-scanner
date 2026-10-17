# Threat model

The authoritative reporting policy is `.github/SECURITY.md`. It supports the latest release and accepts private reports
through GitHub.

## What pyproject-api does and where untrusted input enters

pyproject-api reads PEP 517 build-system configuration and communicates with the selected backend through either a
persistent process or a fresh subprocess. It exposes hook results for requirements, metadata, source distributions,
wheels and editable wheels. When a backend lacks a metadata hook, pyproject-api builds a wheel and extracts its
`.dist-info` directory.

The backend selected by `pyproject.toml` is arbitrary project code. It runs with the frontend process's operating-system
privileges, so pyproject-api is not a sandbox for an untrusted source tree. This matches the boundary in PyPA build and
tox: the frontend expects backend execution; the useful findings are validation and protocol defects that cause it or
its caller to trust a different backend, result or path than requested.

Inputs to test include:

- `[build-system]` values, with emphasis on `build-backend`, `backend-path` and requirement strings;
- backend hook return values, exception fields, stdout and stderr;
- wheel, sdist and metadata filenames returned by hooks;
- wheel members inspected by the metadata fallback;
- output and metadata directories supplied by the API caller, including symlinks and existing contents;
- configuration settings serialized to the backend;
- response JSON, missing or replaced response files, truncated output and messages from overlapping hook calls.

pyproject-api returns requirements to the caller without installing them. The caller decides how to provision a backend
and where to place artifacts.

## Components to prioritize

Start with `src/pyproject_api/_frontend.py`. `create_args_from_folder` and `_in_tree_path` enforce the PEP 517 rule that
each backend path is relative and resolves inside the project. Cover absolute, `..`, symlink-loop, NUL, Windows drive
and UNC forms. Backend object parsing must preserve dotted object names and reject type-confused configuration.

Every hook result needs type and path validation before the frontend presents it as an artifact. Test absolute names,
separators, `..`, alternate Windows separators and names that collide with files from an earlier hook. Because the
backend already executes arbitrary code, a report must explain the additional trust a frontend caller places in the
returned `Path`; direct file writes fall within the backend's existing authority.

`metadata_from_built` opens a backend-produced wheel and extracts members whose first component ends in `.dist-info`.
Check traversal, backslashes, absolute names, duplicate entries, multiple distributions, symlinks and compression
ratios. The result must identify one distribution's metadata under the caller's metadata directory. Separate a ZipFile
defect from pyproject-api's member-selection and destination logic.

Review `_send`, `_send_msg` implementations, `_backend.py` and `_via_fresh_subprocess.py` for response-file replacement,
JSON type confusion, output decoding, hangs and persistent-backend state crossing hook calls. `ensure_empty_dir` and
`_check_metadata_dir` must not erase the project root or follow a caller-controlled alias while removing a directory
tree.

## How to exercise the image

The project is at `/src`, installed in editable mode in `/opt/venv`; test dependencies and a wheel are available
offline. Run `python -m pytest tests`. `tests/demo_pkg_inline` and the backend fixtures cover in-tree backends and both
frontend implementations.

Write a minimal backend that returns one crafted value or produces one crafted wheel, then invoke only the public
`Frontend` API. Record the project and output trees, hook sequence, response JSON and returned `Path`. Run persistent
and fresh-subprocess variants because their protocol lifetimes differ.

## Severity

- High: pyproject-api accepts a backend outside the PEP 517 in-tree roots and causes a caller to execute code the
  project did not select, or metadata extraction writes outside the caller's destination through a library operation
  distinct from the backend's trusted execution.
- Medium: the frontend returns another build's artifact, extracts metadata from the wrong distribution, operates on an
  unrelated response file, or removes a directory tree outside the supplied output directory.
- Medium: a small backend response or wheel causes sustained resource exhaustion in the frontend after the backend
  process exits.
- Low: a controlled exception, bounded hang, invalid result or leftover file confined to the backend's temporary or
  output directory.

## Reports and exclusions

Include the pyproject-api commit, frontend implementation, Python version, project tree, `[build-system]` table, backend
code, hook sequence, response data, output tree and returned result. State what additional authority or trust the
frontend adds beyond running the backend.

Do not report:

- arbitrary code execution, file access or output from the selected backend;
- requirement installation or resolution, which the caller performs;
- a caller using the project root as an output directory after documented rejection;
- backend stdout or stderr containing a secret the backend printed;
- a defect in a build backend, `packaging` or Python's zip implementation that reproduces without pyproject-api.
