# Threat model

## What this project does and where untrusted input enters

uutils findutils is a Rust reimplementation of GNU findutils: `find`, `xargs`, `locate` and
`updatedb`. They are local command-line tools with no network service.

A finding is a vulnerability only if it crosses a trust boundary on the local system. Name the
attacker, what they control, and what they gain. Typical boundaries:

- a privileged process (root cron job such as a `/tmp` cleaner, a package manager hook, a backup
  script, a CI pipeline) runs `find` over a directory tree that a less privileged user can modify
  while the traversal is running;
- `find -exec`/`-execdir`/`-ok`, `-delete`, `-fprint`/`-fprintf`/`-fls`, or `xargs` act on file
  names chosen by that user;
- `updatedb` runs as root and builds a database that other users can query with `locate`;
- `locate` reads a database or `LOCATE_PATH` entry that someone else controls.

## Components that matter most / least

- Most important: traversal and actions in `find`. Traversal uses `walkdir` with full path names
  (`src/find/matchers/entry.rs`), and actions re-resolve those paths. TOCTOU and symlink races
  are the main class of bug we care about:
  - `-delete` (`src/find/matchers/delete.rs`): a directory replaced by a symlink between the
    walk and the unlink must not let a privileged `find` delete files outside the starting tree.
  - `-execdir`/`-okdir` (`src/find/matchers/exec.rs`): the command runs in the parent directory
    of the match; check that this directory cannot be swapped for a symlink, and that the
    relative-`PATH` guard cannot be bypassed.
  - `-P`/`-H`/`-L`, `-xdev`/`-mount`, `-prune`, `-maxdepth`/`-mindepth`, and symlink loops: each
    one is a promise about what the walk will not enter.
  - `-fprint`, `-fprintf`, `-fls` create or truncate output files (`src/find/matchers/mod.rs`).
- `xargs` (`src/xargs/mod.rs`): splitting, quoting and escaping in default, `-0`, `-d` and `-I`
  modes, `-E` end-of-file strings, and command-line size computation. A file name must never be
  split into extra arguments or turned into an option of the invoked command.
- `updatedb` (`src/updatedb/mod.rs`): what it indexes when run as root (the `--localuser` and
  `--netuser` options are parsed; check what they actually change), the permissions and
  symlink-following of the database file it writes, and `--prunepaths`/`--prunefs`.
- `locate` (`src/locate/mod.rs`): the LOCATE02 front-coded database decoder (prefix deltas,
  0x80 escapes, truncated or inconsistent records) and `-e`/`-E` existence checks. Treat a
  database you did not generate as untrusted input.
- Regular expressions: `-regex`/`-iregex` and `locate --regex` use Oniguruma (`onig`, a
  backtracking C engine) through the `onig` crate. Catastrophic backtracking matters when the
  pattern or the names come from an untrusted source.
- Numeric and time predicates (`-size`, `-mtime`, `-newerXY`, `-used`, `-perm`, `-printf`
  width/precision) for overflow and wrong-match results.
- Out of scope: `tests/`, `benches/`, `docs/`, `util/`, `src/testing/` (test helper binary), and
  Windows-only code paths.

## How to exercise it

- The checkout is at `/src`. Binaries are `target/debug/find`, `target/debug/xargs`,
  `target/debug/locate` and `target/debug/updatedb`.
- Rebuild offline with `cargo build --offline`; build `--release` too when a finding depends on
  overflow checks or optimisation.
- Integration tests: `cargo test --offline --test test_find --test test_xargs`; also
  `find_exec_tests`, `exec_unit_tests` and `db_tests` under `tests/`. Many unit tests live next
  to the matchers in `src/find/matchers/`.
- The image runs as root, so tests that rely on permission denials (and a few that depend on
  checkout layout, such as symlinks under `test_data/`) can fail there. That is expected, not a
  finding; run as an unprivileged user (`useradd -m t && su t -c ...`) when it matters.
- Reproduce races with a small script that swaps a directory for a symlink in a loop while
  `find` runs; `strace -f -e trace=file` shows whether a path is re-resolved. Keep PoCs inside a
  temporary directory and never touch real system files.

## How you rate severity

- Critical: a symlink or TOCTOU attack that lets an unprivileged user make a root-run `find`
  delete, overwrite or execute a command on arbitrary files outside the tree it was given
  (`-delete`, `-exec`, `-execdir`, `-fprint`).
- High: the same class of attack limited to files the attacker can name in advance or requiring a
  narrow race; a file name injected as an extra argument or option through `xargs`; `updatedb`
  run as root exposing names from directories other users cannot list; memory-safety bugs
  (Oniguruma, `unsafe`) reachable from file names, patterns or a database file.
- Medium: traversal escaping `-xdev`/`-prune`/`-maxdepth` without a destructive action; output
  files created with too-broad permissions; size/time predicates matching the wrong files.
- Low: denial of service (hang, unbounded memory, stack exhaustion, crash) from an attacker-shaped
  tree, database or pattern processed by an automated job. A panic or hang that only affects the
  caller's own invocation on their own data is a normal bug, not a vulnerability.

## Anything to leave alone

- A difference from GNU findutils on its own is a compatibility bug, not a vulnerability; report it
  as a vulnerability only if it lets an attacker cross a boundary. See the next section.
- `-exec sh -c '... {} ...'` written by the caller is the caller's own shell injection, as with
  GNU find; report it only if findutils itself adds the injection.
- Data loss caused by the caller's own arguments under the caller's own permissions.
- Panics, `unwrap`, or wrong exit codes with no safety impact.
- Proposed patches must keep GNU-compatible behaviour and must not be derived from GNU source code
  (GPL); write original code. A regression test is appreciated.

## Compatibility differences from GNU findutils

We also want to hear about behavioural differences from GNU findutils, even when they have no
security impact. uutils aims to be a drop-in replacement, and these reports are valuable to the
team. List them in a separate section after any security findings, clearly marked as compatibility
issues, and do not assign them a security severity.

The GNU reference tools are installed in the image: `/usr/bin/find` and `/usr/bin/xargs` (GNU
findutils 4.10.0; GNU `locate` and `updatedb` are not installed). Compare them directly against
`target/debug/find` / `target/debug/xargs` on the same input, in the same directory, with `LC_ALL=C`
and with `LC_ALL=en_US.UTF-8` when locale matters.

Areas worth comparing: traversal order and depth options, symlink modes (`-P`/`-H`/`-L`), predicate
and operator parsing and precedence, `-printf`/`-fprintf` directives and escapes, `-ls` output,
`-perm`/`-size`/`-mtime` rounding, `xargs` splitting, quoting, `-I`/`-L`/`-n`/`-s` limits, exit
status and error messages.

Unsupported predicates or options are useful to list when you come across them.

For each difference, give:

- the exact command line and a minimal input (inline, or a short script that creates the files);
- GNU's output, error messages and exit status, and ours;
- whether the existing test suite already covers it (name the test if a similar one exists);
- a suggested regression test, and a fix when it is small and clear.

Group differences that share a root cause, and skip pure formatting of `--help`/`--version` text.
