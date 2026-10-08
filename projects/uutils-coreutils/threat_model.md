# Threat model

The authoritative policy is `SECURITY.md` at the root of the repository; read it first. This file
summarises it for the scanner.

## What this project does and where untrusted input enters

uutils coreutils is a Rust reimplementation of the GNU coreutils (`ls`, `cp`, `rm`, `chmod`,
`sort`, `tr`, ...). The utilities are local command-line tools with no network service.

A finding is a vulnerability only if it crosses a trust boundary on the local system. Name the
attacker, what they control, and what they gain. Typical boundaries:

- a privileged process (root, sudo, a cron job, a package manager hook, a CI pipeline) runs a
  utility on a directory tree, file names or file contents that a less privileged user controls;
- a utility honours a documented safety guard (`--preserve-root`, `-i`, `--no-clobber`,
  `--one-file-system`, `--no-dereference`) and the guard can be bypassed;
- output consumed by scripts for security decisions (`id`, `groups`, `stat`, `whoami`, `test`,
  `tr`/`sort`/`cut` character classes) differs from POSIX/GNU in a way that changes the decision.

## Components that matter most / least

- Most important: utilities that walk directories or modify metadata as a privileged user:
  `rm`, `cp`, `mv`, `install`, `ln`, `chmod`, `chown`, `chgrp`, `chroot`, `du`, `touch`, `mkdir`,
  `shred`. TOCTOU races and symlink following (anything that re-resolves a path instead of using
  `openat`/`O_NOFOLLOW`/fds) are the main class of bug we care about.
- Shared code in `src/uucore/` (safe traversal, permissions, perms/ownership, fs helpers, mode
  parsing, entries/uid lookups) affects many utilities and matters a lot.
- `stdbuf` (preloaded `libstdbuf.so`), `env`, `nohup`, `timeout`, `kill` and `chroot` handle
  privilege or environment and are in scope.
- Parsers of file contents (`sort`, `tr`, `cut`, `od`, `base64`, checksum `-c` files, `dd`,
  `numfmt`, `date` formats) are in scope for memory safety and unbounded allocation reachable
  from untrusted contents.
- Out of scope: `fuzz/`, `tests/`, `util/`, `docs/`, `src/bin/uudoc.rs`, localisation `.ftl`
  files, and Windows/macOS/WASI-only code paths.

## How to exercise it

- The multicall binary is `target/debug/coreutils <utility> [args]`.
- Rebuild offline with `cargo build --offline --features unix`.
- Integration tests live in `tests/by-util/test_<utility>.rs`; run one with
  `cargo test --offline --features unix -p coreutils -- test_<utility>::`.
- The image runs as root, so tests that rely on permission denials (unreadable/read-only files and
  directories, e.g. some `test_cp`/`test_rm` cases) fail there. That is expected, not a finding;
  run them as an unprivileged user (`useradd -m t && su t -c ...`) when it matters.
- `util/check-toctou.sh` and `util/check-safe-traversal.sh` show the syscall patterns we expect
  from recursive utilities (they use `strace`).
- Reproduce races with a small script that swaps a directory for a symlink in a loop while the
  utility runs. Keep PoCs inside a temporary directory; never touch real system files.

## How you rate severity

- Critical: bypassing `--preserve-root` or another guard so a privileged run can act on the whole
  filesystem; symlink/TOCTOU attacks that let an unprivileged user make a root-run `rm`, `chown`,
  `chmod`, `cp` or `mv` delete, overwrite or change ownership/mode of arbitrary files.
- High: the same class of attack limited to files the attacker can name in advance, or requiring
  a narrow race; wrong uid/gid reporting in `id`/`groups`/`stat` that could grant access;
  memory-safety bugs (in `unsafe` or FFI code) reachable from untrusted input.
- Medium: information disclosure across users (e.g. temp files or copies created with too-broad
  permissions), character-class misclassification that changes filtering results.
- Low: denial of service (hang, unbounded memory, crash) from attacker-controlled input processed
  by an automated pipeline. A panic or hang that only affects the caller's own invocation on their
  own data is a normal bug, not a vulnerability.

## Anything to leave alone

- A difference from GNU on its own is a bug, not a vulnerability; report it only if it lets an
  attacker cross a boundary.
- Data loss caused by the caller's own arguments under the caller's own permissions.
- Panics, `unwrap`, or wrong exit codes with no safety impact.
- Proposed patches must keep GNU-compatible behaviour and must not be derived from GNU source code
  (GPL); write original code.
