# Threat model

## What this project does and where untrusted input enters

uutils sed is a Rust reimplementation of GNU sed. It applies an editing script to input streams
and files, optionally editing files in place (`-i`). It implements the GNU extensions that touch
the outside world: the `e` command and the `s///e` flag run shell commands, `r`/`R` read named
files, and `w`/`W` and the `s///w` flag write named files. `--sandbox` (and `--posix` for `e`)
rejects those at compile time. The tool is a local command-line program with no network service.

A finding is a vulnerability only if it crosses a trust boundary. Name the attacker, what they
control, and what they gain. Typical boundaries:

- a privileged process (root, a package maintainer script, a config-management run, a CI job)
  runs `sed -i` on files in a directory that a less privileged user can modify;
- sed processes file contents an untrusted party controls (logs, templates, uploaded text);
- a service builds a sed script from partly untrusted data and relies on `--sandbox` to stop it
  from running commands or touching files.

## Components that matter most / least

- Most important: `--sandbox` enforcement in `src/sed/compiler.rs`. No script accepted under
  `--sandbox` may execute a command or open a named file for reading or writing, through any
  spelling: `e`, `s///e`, `r`, `R`, `w`, `W`, `s///w`, special file names such as `/dev/stdout`,
  flags combined in any order, commands after `}` or `;`, or scripts split across `-e`/`-f`.
- In-place editing in `src/sed/in_place.rs`. Check symlink and TOCTOU races between the metadata
  lookup, temporary-file creation in the target directory, permission copying, backup rename
  (`-i SUFFIX`, including suffixes containing `*` or `/`) and the final rename; the handling of
  `--follow-symlinks`; and whether ownership and mode bits (including setuid/setgid) of the
  result are what the original owner would expect when root edits another user's file.
- Input I/O in `src/sed/fast_io.rs`: memory-mapped input files exposed as `&'static` slices,
  `as_str_unchecked`, raw-pointer output chunk bookkeeping, and direct `libc::write`. Consider
  files that are truncated or modified while mapped, and inputs that are not valid UTF-8.
- Regular expressions in `src/sed/fast_regex.rs`: the `regex` crate plus `fancy-regex` (a
  backtracking engine used for back-references). Check translation from POSIX BRE/ERE syntax so
  that a pattern cannot match more or less than the user wrote, and catastrophic backtracking
  when patterns or input are untrusted.
- Script parsing and execution: address ranges (`first~step`, `addr,+N`, `0,/re/`), `y`
  transliteration, replacement escapes (`\1`–`\9`, `&`, `\L`/`\U`/`\E`), branches and labels,
  hold/pattern space growth, and `q`/`Q` exit codes.
- Out of scope: `fuzz/`, `benches/`, `tests/`, `util/`, `docs/`, the man page and completion
  generation in `build.rs`, and Windows-only code paths.

## How to exercise it

- The checkout is at `/src`. The binary is `target/debug/sed`.
- Rebuild offline with `cargo build --offline`; build `--release` too when a finding depends on
  overflow checks or optimisation.
- Integration tests are in `tests/by-util/test_sed.rs`: `cargo test --offline -- test_sed::`.
  Unit tests live next to the code in `src/sed/`.
- `fuzz/fuzz_targets/fuzz_sed.rs` shows how scripts and inputs are fed in; use it as a guide.
- The image runs as root. For in-place races, create an unprivileged user (`useradd -m t`), let
  it own a directory, and race a symlink swap in that directory while root runs `sed -i`. Keep
  PoCs inside a temporary directory and never touch real system files.

## How you rate severity

- Critical: a script accepted under `--sandbox` that executes a command or writes an arbitrary
  file; a symlink or TOCTOU attack that makes a root-run `sed -i` overwrite, replace or change
  ownership/mode of a file outside the one it was asked to edit, or produce a root-owned file
  with attacker-chosen content and privileged mode bits.
- High: a `--sandbox` bypass that only reads named files; memory-safety bugs in `fast_io.rs` or
  other `unsafe` code reachable from input files or scripts; the same in-place attacks limited to
  files the attacker can name in advance or needing a narrow race.
- Medium: temporary or backup files created with broader permissions than the original, exposing
  content to other users; regex translation errors that make a substitution touch lines the
  script did not select, in a way that defeats a sanitising step.
- Low: denial of service (backtracking, unbounded hold space, crash, SIGBUS on a truncated mapped
  file) from attacker input in an automated pipeline. A panic or hang that only affects the
  caller's own invocation on their own data is a normal bug, not a vulnerability.

## Anything to leave alone

- `e`, `s///e`, `r` and `w` doing what they are documented to do without `--sandbox`: a script
  is code, and running an untrusted script without `--sandbox` is the caller's choice, as with
  GNU sed.
- A difference from GNU sed on its own is a compatibility bug, not a vulnerability; report it
  as a vulnerability only if it lets an attacker cross a boundary. See the next section.
- Panics, `unwrap`, or wrong exit codes with no safety impact.
- Proposed patches must keep GNU-compatible behaviour and must not be derived from GNU source code
  (GPL); write original code. A regression test in `tests/by-util/test_sed.rs` is appreciated.

## Compatibility differences from GNU sed

We also want to hear about behavioural differences from GNU sed, even when they have no security
impact. uutils aims to be a drop-in replacement, and these reports are valuable to the team. List
them in a separate section after any security findings, clearly marked as compatibility issues, and
do not assign them a security severity.

The GNU reference tools are installed in the image: `/usr/bin/sed` (GNU sed 4.9). Compare them
directly against `target/debug/sed` on the same input, in the same directory, with `LC_ALL=C` and
with `LC_ALL=en_US.UTF-8` when locale matters.

Areas worth comparing: script parsing (addresses, ranges, `;`/`}`/newline handling, `-s`, `-z`,
`-E`), BRE/ERE translation and back-references, replacement escapes and case conversion, `l` line
wrapping, `-i` backup naming and file metadata, `--posix` and `--debug` behaviour, exit status
(`q`/`Q`) and error messages.

Unsupported commands or options are useful to list when you come across them.

For each difference, give:

- the exact command line and a minimal input (inline, or a short script that creates the files);
- GNU's output, error messages and exit status, and ours;
- whether the existing test suite already covers it (name the test if a similar one exists);
- a suggested regression test, and a fix when it is small and clear.

Group differences that share a root cause, and skip pure formatting of `--help`/`--version` text.
