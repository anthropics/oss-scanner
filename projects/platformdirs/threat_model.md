# Threat model

The project's security policy is `.github/SECURITY.md`. Report findings through the Tidelift security contact named
there, not through a public issue.

## What platformdirs does and where untrusted input enters

platformdirs maps application names to the operating system's conventional data, configuration, cache, state, log,
runtime and site directories. Downstream tools such as virtualenv use these paths for caches and application data. The
functional API in `platformdirs/__init__.py` and the classes in `api.py`, `unix.py`, `windows.py`, `macos.py`,
`android.py` and `ios.py` share this responsibility. With `ensure_exists=True`, a lookup also creates its directory. The
`place_*_file` helpers create parent directories for a relative filename, while `find_*_file` searches the configured
user and site paths.

platformdirs has no network or archive parser. Untrusted data reaches it when an application derives `appname`,
`appauthor`, `version` or a `place_*_file`/`find_*_file` name from package metadata, a plugin, an archive or a remote
configuration. Exercise absolute paths, `..`, drive and UNC forms, mixed separators, empty components, reserved names,
control characters and long values. These names must stay under the selected base; `_ensure_inside_base` enforces that
contract.

Directory bases come from `HOME`, `XDG_*`, `TMPDIR`, `APPDATA`, `LOCALAPPDATA`, `PROGRAMDATA`, Android state, Apple
runtime APIs, `pwd` and `/etc/xdg`. A process that lets an attacker set its environment has already lost this boundary.
The relevant cases are platformdirs choosing a different base than the operating-system convention promises, or acting
on a hostile filesystem entry after the application selected a legitimate base.

Treat existing filesystem entries as hostile when a privileged or long-running process creates a directory in a location
another user can modify. A peer can plant or exchange symlinks, files and directories between lookup and creation. State
which user owns every parent and whether the directory is private, shared or sticky.

## Components to prioritize

Start with `PlatformDirsABC` in `api.py`: `_ensure_inside_base`, `_optionally_create_directory`,
`_make_private_directories`, `_place_file`, `_find_files`, the iterator helpers and `use_site_for_root`. Check that
every relative-name API applies the same containment rules and that private XDG directories receive `0o700` without
changing the permissions of existing directories. A failure that creates or finds a file outside the chosen base matters
more than a spelling or ordering difference.

Review each platform implementation on its own. On Unix, cover XDG path lists, `XDG_RUNTIME_DIR`, root redirection,
temporary runtime fallbacks and home-directory expansion. On Windows, cover known-folder API errors, drive-relative
paths, UNC paths, roaming and author-name handling. On macOS, cover Homebrew prefixes and multipath site results.
Android and iOS detection must not confuse host and mobile paths.

The pytest plugin in `pytest_plugin.py` redirects platform directories during tests. It must cover every public path and
avoid stale values that send a test into the real user's directories. The CLI, documentation and release automation are
lower priority unless they expose a production-library defect.

## How to exercise the image

The repository is at `/src`, installed in editable mode in `/opt/venv`, which is on `PATH`. A built wheel is available
under `/opt/wheels`. Run `python -m pytest tests`.

Use the public API in a temporary directory. Instantiate each platform class with crafted names and a patched
environment, enable `ensure_exists`, and record the returned path, ownership and mode. For filesystem races, run the
victim as an unprivileged user and swap a component for a symlink from a second process. Linux tests can instantiate
platform-specific classes with mocked platform APIs, but a claim about Windows behavior should include a Windows
reproducer.

## Severity

- High: attacker-controlled application metadata or a relative filename escapes a legitimate base and makes a privileged
  caller create, overwrite or disclose an attacker-chosen file without control of the caller's environment or base
  directory.
- High: a symlink or TOCTOU race in a shared parent makes `ensure_exists` or `place_*_file` act on an arbitrary path
  with the victim's privileges.
- Medium: platformdirs creates a private user or runtime directory with permissions that expose credentials or
  executable configuration to another local user, or `find_*_file` returns another user's file contrary to its
  documented search order.
- Low: a crafted value causes a crash, hang or malformed path without crossing a filesystem or user boundary.

## Reports and exclusions

Include the platformdirs commit, platform class, public API call, constructor values, environment, user IDs, initial
filesystem tree, returned path and final filesystem changes. Prefer a regression test through the public API.

Do not report:

- paths chosen by an attacker who already controls the process environment, home directory or configured base;
- behavior from an application supplying a documented base path, unless platformdirs escapes that base;
- a platform-specific result that follows the documented operating-system convention;
- the caller's later handling of a correct path;
- test, documentation or release behavior with no path into the installed library.
