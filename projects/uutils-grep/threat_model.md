# Threat model

## What this project does and where untrusted input enters

uutils grep is a Rust reimplementation of GNU grep. It searches files, standard input or directory
trees (`-r`/`-R`) for lines matching basic, extended, fixed-string or Perl-style (`-P`) patterns.
All regular-expression modes use Oniguruma, a backtracking regex engine written in C, called
directly through `onig_sys` in `src/matcher.rs`. The tool is a local command-line program with no
network service.

A finding is a vulnerability only if it crosses a trust boundary. Name the attacker, what they
control, and what they gain. Typical boundaries:

- grep runs over file contents, file names or directory trees that an untrusted party controls
  (log scanners, CI jobs, code search, mail filters, `grep -r` run by root over users' homes);
- a service passes a partly untrusted pattern to grep (`-e`, `-f`, search boxes backed by grep);
- a script uses grep's exit status, `-c`, `-l`/`-L` or `-q` to make a security decision
  ("does this file contain X?").

## Components that matter most / least

- Most important: the Oniguruma FFI in `src/matcher.rs`. It passes raw start/end/range pointers
  into `onig_search`/`onig_match`, unwraps encoding callbacks, and implements `-w` word checks by
  decoding UTF-8 around a match. Inputs are arbitrary bytes, not valid UTF-8. Check every pointer
  and offset, especially where bounds are only enforced with `debug_assert!` (compiled out in
  release builds), and the `unsafe impl Send/Sync` on the regex wrapper.
- Bugs in the bundled Oniguruma C library (`onig_sys`) reachable through grep's usage count, but
  name the upstream component and version. Distinguish backtracking cost from memory corruption.
- Matching correctness that changes a decision: `-v`, `-w`, `-x`, `-i`, `-F` with multiple
  patterns, `-f` pattern files (empty lines, CRLF), `-z`, binary-file detection and
  `--binary-files`/`-a`/`-I`. A false "no match" when the line matches (or the reverse) matters.
- Recursive search in `src/searcher.rs` (`walkdir`): `-r` must not follow symlinks below the
  top level, `-R` loops, `--exclude`/`--include`/`--exclude-dir`, and `-D`/`--devices` handling
  of FIFOs and devices encountered under a tree.
- Output: file names printed with matches (`-H`, `-l`, `--null`), `--color` escape sequences, and
  `--label`; check whether names or contents can forge output lines that a consumer parses.
- Buffering in `src/line_buffer.rs` and `src/context_buffer.rs`: very long lines, `-A`/`-B`/`-C`
  context, `-m` with context, and memory growth on input without newlines.
- Out of scope: `fuzz/`, `benches/`, `tests/`, `util/`, and Windows-only code paths.

## How to exercise it

- The checkout is at `/src`. The binary is `target/debug/grep`.
- Rebuild offline with `cargo build --offline`; build `--release` too, because some bounds
  checks only exist as debug assertions and optimisation changes FFI behaviour.
- Integration tests are in `tests/test_grep.rs`: `cargo test --offline --test test_grep`.
  Unit tests live next to the code in `src/`.
- `fuzz/fuzz_targets/fuzz_grep.rs` shows how patterns and inputs are fed to the matcher; use it
  as a guide for reproducers. Feed invalid UTF-8, NUL bytes, and very long lines.
- The image runs as root, so tests that rely on permission denials can fail there. That is
  expected, not a finding.

## How you rate severity

- Critical: memory corruption (out-of-bounds write, use-after-free) in grep's FFI glue or in
  Oniguruma reachable from file contents alone, with a plausible path beyond a crash.
- High: memory corruption or out-of-bounds read reachable from an attacker-supplied pattern;
  disclosure of memory contents in output; `grep -r` run by a privileged user following a
  symlink it should not, so that it reads and prints files the attacker cannot read.
- Medium: wrong match results (false negatives or positives) from crafted input that defeat a
  filter or check; output forging through file names or escape sequences.
- Low: denial of service (catastrophic backtracking, unbounded memory, crash) from attacker input
  in an automated pipeline. Backtracking caused by a pattern the caller wrote themselves, on their
  own data, is a normal bug. A panic that only affects the caller's own invocation is not a
  vulnerability.

## Anything to leave alone

- A difference from GNU grep on its own is a compatibility bug, not a vulnerability; report it
  as a vulnerability only if it lets an attacker cross a boundary. See the next section.
- `-P` behaving like Oniguruma's Perl syntax rather than PCRE2 is a known difference.
- Panics, `unwrap`, or wrong exit codes with no safety impact (other than match/no-match status
  used for decisions, which is in scope).
- Proposed patches must keep GNU-compatible behaviour and must not be derived from GNU source code
  (GPL); write original code. A regression test in `tests/test_grep.rs` is appreciated.

## Compatibility differences from GNU grep

We also want to hear about behavioural differences from GNU grep, even when they have no security
impact. uutils aims to be a drop-in replacement, and these reports are valuable to the team. List
them in a separate section after any security findings, clearly marked as compatibility issues, and
do not assign them a security severity.

The GNU reference tools are installed in the image: `/usr/bin/grep` (GNU grep 3.11). Compare them
directly against `target/debug/grep` on the same input, in the same directory, with `LC_ALL=C` and
with `LC_ALL=en_US.UTF-8` when locale matters.

Areas worth comparing: BRE/ERE syntax and escapes, character classes and locales,
`-i`/`-w`/`-x`/`-v` interactions, `-o`/`-b`/`-n` offsets, context separators, binary-file messages,
`-r`/`-R` file selection and ordering, `--color` output, exit status (including with `-q` and `-s`)
and error messages.

Differences in `-P` (Oniguruma Perl syntax rather than PCRE2) are known; report them only when the
result is surprising for common patterns.

For each difference, give:

- the exact command line and a minimal input (inline, or a short script that creates the files);
- GNU's output, error messages and exit status, and ours;
- whether the existing test suite already covers it (name the test if a similar one exists);
- a suggested regression test, and a fix when it is small and clear.

Group differences that share a root cause, and skip pure formatting of `--help`/`--version` text.
