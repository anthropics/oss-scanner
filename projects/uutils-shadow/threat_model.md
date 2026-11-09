# Threat model

## What this project does and where untrusted input enters

uutils shadow (shadow-rs) is a Rust reimplementation of the Linux shadow-utils suite: `passwd`,
`chfn`, `chsh`, `chage`, `expiry`, `newgrp`, `sg`, `gpasswd`, `newuidmap`, `newgidmap`, `login`,
`useradd`, `usermod`, `userdel`, `groupadd`, `groupmod`, `groupdel`, `chpasswd`, `chgpasswd`,
`newusers`, `pwck`, `grpck`, `vipw`, `vigr`, `pwconv`, `pwunconv`, `grpconv` and `grpunconv`. It is
shipped either as one tool per binary or as a single multicall binary (`shadow-rs`). The tools
read and rewrite `/etc/passwd`, `/etc/shadow`, `/etc/group`, `/etc/gshadow`, `/etc/subuid`,
`/etc/subgid` and `/etc/login.defs`, create and move home directories, and talk to PAM.

The central trust boundary is privilege. `passwd`, `chfn`, `chsh`, `newgrp`, `sg`, `gpasswd`,
`newuidmap` and `newgidmap` are installed setuid root, and `expiry` and `chage` setgid `shadow`
(setuid root where the group does not exist). In the multicall layout the one binary is setuid
and every other applet must drop to the caller's uid before running (`src/bin/shadow-rs.rs`).
For these tools the attacker is a local unprivileged user who controls:

- `argv` (including `argv[0]`), the environment, umask, resource limits, signal mask and
  disposition, inherited file descriptors, the controlling terminal, and the current directory;
- everything typed at a prompt, and the timing of signals sent to the process;
- the contents of their own home directory, their own GECOS/shell fields within what the tool
  allows, and any directory they own that the tool walks.

The other boundary is root running an administrative tool on data a less privileged party
controls: `useradd`/`usermod`/`userdel` on a home directory owned by the user being changed;
`chpasswd`, `chgpasswd` and `newusers` fed a batch file from a provisioning system; `pwck` and
`grpck` run on account files someone else may have edited; `--prefix`/`--root` pointed at a
directory tree (a container image, a chroot) built by someone else. `login` is run as root by
`getty` on input typed by anyone at the terminal.

A finding is a vulnerability only if it crosses one of these boundaries. Name the attacker, what
they control, and what they gain.

## Components that matter most / least

- Most important: the privilege model of the setuid and setgid tools. `caller_is_root()` must use
  the real uid; the multicall binary must drop privilege for every applet outside the setuid list
  and fail closed if it cannot; `--prefix`/`--root` must be refused to non-root callers; a
  non-root caller must only change their own account (or, for `gpasswd`, a group they
  administer) and only the fields they are allowed to (`CHFN_RESTRICT`, `/etc/shells` for `chsh`).
  Check every path from `uumain` to a write for a missing or bypassable check, including
  username/uid confusion (numeric names, names that resolve differently through NSS), and
  information leaks that tell a user something only root may know (other users' shadow entries,
  existence of files through `chsh`, timing of `newgrp`/`sg` password checks).
- `newuidmap`/`newgidmap` (`src/uu/newuidmap/`): only ranges granted in `/etc/subuid`/`/etc/subgid`
  (plus the caller's own id) may be mapped, into a process the caller owns. Check range
  arithmetic and overflow, overlap checks, `/proc/<pid>` races (pid reuse, opening the target
  through a path rather than a held descriptor), and `setgroups` handling for gid maps.
- Account-file writing in `src/shadow-core/src/{atomic,lock,transaction}.rs` and the record
  parsers and writers (`passwd.rs`, `shadow.rs`, `group.rs`, `gshadow.rs`, `subid.rs`,
  `login_defs.rs`, `validate.rs`). No field a caller supplies may inject `:`, a newline or another
  record; a parse/write round trip must not drop, duplicate or reorder entries; lock handling
  must not let two writers lose an update; a crash, signal or full disk at any point must leave
  the old or the new file, never a truncated or world-readable one; mode, owner, group and
  SELinux label of `/etc/shadow` must survive the rewrite.
- Home directory handling as root on a tree the user owns: `useradd -m` and skeleton copy
  (`skel.rs`, `home.rs`), `usermod -m`/`-u`/`-g` re-owning and moving, `userdel -r` removing home
  and mail spool. Check symlink and TOCTOU races, hard links to files the user does not own,
  path traversal through `-d`, `-b`, `HOME_MODE` and `--prefix`, and btrfs subvolume paths.
- `unsafe` FFI in `src/shadow-core/src/{pam,crypt,process,tty}.rs` and `src/uu/passwd/`: PAM
  conversation buffers, `crypt(3)` strings, `exec*`, `getpw*`, signal masks, terminal echo.
  Check lifetimes, NUL handling, and that secrets are zeroed and never reach logs, error
  messages or core dumps.
- Process hardening (`hardening.rs`, `process.rs`): environment replacement before PAM/NSS/crypt
  run, core dump suppression, signal blocking in critical sections, Landlock in `passwd`, and
  the environment and fds passed to anything spawned (`vipw`/`vigr` editor, `nscd`, the shell
  started by `newgrp`/`sg`/`login`).
- `login`: authentication failures, `-f` preauthentication, `-r`/`-h` host handling, terminal
  ownership and mode, utmp/wtmp records, and that the session runs with the target user's
  credentials and groups only.
- Out of scope: `fuzz/`, `benches/`, `tests/`, `util/`, `docs/`, `docker/`, `hooks/`, shell
  completion generation, and non-Linux code paths.

## How to exercise it

- The checkout is at `/src`. The multicall binary is `target/debug/shadow-rs`; run a tool as
  `target/debug/shadow-rs passwd ...` or through a symlink named after the tool. It is built
  with `--features pam`, as release builds are.
- Rebuild offline with `cargo build --offline --workspace --features pam`; build `--release` too
  when a finding depends on overflow checks, `panic = "abort"` or optimisation.
- Tests: `cargo test --offline --workspace --features pam`. Integration tests are in
  `tests/by-util/`, helpers in `tests/common/mod.rs`. Unit tests live next to the code.
- `fuzz/fuzz_targets/` shows how the record parsers are fed.
- The image runs as root. Accounts `testuser` and `testuser2` and group `testgroup` exist, and
  the PAM services `shadow-rs-test-permit` and `shadow-rs-test-deny` give a known answer. To test
  a setuid boundary, copy the binary, `chown root` and `chmod 4755` it, and run it as `testuser`
  with `setpriv` or `su testuser -c ...`. Use `--prefix` on a temporary tree, or work on a
  copy of `/etc`, for anything that would damage the image's own account files.

## How you rate severity

- Critical: an unprivileged user gains root or another user's identity through a setuid/setgid
  tool or the multicall binary (writing an arbitrary account-file entry, changing another user's
  password, shell or uid, mapping uid 0 or an ungranted range with `newuidmap`, skipping
  authentication in `passwd`, `chfn`, `chsh`, `newgrp`, `sg` or `login`); a user making root
  overwrite, chown or chmod an arbitrary file through their own home directory during `useradd`,
  `usermod` or `userdel`.
- High: an unprivileged user reads `/etc/shadow` or `/etc/gshadow` content of another account, or
  a password reaches a log, an error message, a core dump or another process; memory-safety bugs
  in the FFI code reachable from an unprivileged caller; record injection through a field a
  caller controls; the home-directory attacks above limited to files the attacker must name in
  advance or needing a narrow race.
- Medium: an account file left truncated, corrupted, with an entry lost, or with weaker mode,
  owner or label after an interrupted or concurrent run that an unprivileged user can trigger;
  injection or traversal through batch input (`chpasswd`, `newusers`) or `--prefix` trees that a
  provisioning system takes from a less trusted source; user enumeration or file-existence
  oracles from a setuid tool.
- Low: denial of service an unprivileged user can cause (a stale lock that blocks other account
  changes, a crash that leaves a lock or temporary file behind, terminal left without echo); a
  panic or wrong exit code in a root-only tool on root-supplied input is a normal bug, not a
  vulnerability.

## Anything to leave alone

- Root doing what root asked: a root-only tool given root-chosen arguments, a root-chosen
  `--prefix`, or a root-edited `/etc/login.defs` is trusted, unless the issue is that a less
  privileged party controls that input (see above).
- What PAM, NSS, `crypt(3)` or the kernel do on their own; report only how this code calls them.
- A difference from upstream shadow-utils on its own is a compatibility bug, not a vulnerability;
  report it as a vulnerability only if it lets an attacker cross a boundary. See the next section.
- Panics, `unwrap`, or wrong exit codes with no safety impact.
- Proposed patches must keep upstream-compatible behaviour and must not be derived from
  shadow-utils source code (this project is a clean-room MIT implementation); write original code. A regression test in `tests/by-util/` is appreciated.

## Compatibility differences from upstream shadow-utils

We also want to hear about behavioural differences from upstream shadow-utils, even when they have
no security impact. uutils aims to be a drop-in replacement, and these reports are valuable to the
team. List them in a separate section after any security findings, clearly marked as
compatibility issues, and do not assign them a security severity.

The upstream tools from Debian's `passwd`, `login` and `uidmap` packages are installed in the image
(`/usr/sbin/useradd`, `/usr/bin/passwd`, `/usr/bin/chage`, `/usr/bin/newuidmap`, ...).
`tests/upstream-compat.sh` already compares some of them. Run both on copies of the same account
files, through `--prefix`/`--root` or in a scratch copy of `/etc`, never on the image's real files
for anything that writes.

Areas worth comparing: option parsing and accepted flag combinations, exit codes, the exact
output of `passwd -S`, `chage -l`, `pwck` and `grpck`, the records written by `useradd`, `usermod`,
`groupadd`, `newusers` and `chpasswd` (field values, defaults from `/etc/default/useradd` and
`/etc/login.defs`, ordering, and the shadow/gshadow side), home directory and skeleton handling,
mail spool handling, subordinate id allocation, and the files touched under `--prefix`/`--root`.

Unsupported commands or options are useful to list when you come across them.

For each difference, give:

- the exact command line and a minimal set of input files (inline, or a short script that
  creates them);
- upstream's output, error messages, exit status and resulting file contents, and ours;
- whether the existing test suite already covers it (name the test if a similar one exists);
- a suggested regression test, and a fix when it is small and clear.

Group differences that share a root cause, and skip pure formatting of `--help`/`--version` text.
