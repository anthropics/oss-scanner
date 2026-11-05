# Threat model

## What this project does and where untrusted input enters

uutils diffutils is a Rust reimplementation of GNU diffutils. It currently implements `diff`
(normal, context, unified, ed and side-by-side output) and `cmp`. There is no `patch`, `diff3` or
`sdiff` binary yet, and `diff -r` (recursive directory comparison) is not implemented. The tools
are local command-line programs with no network service.

A finding is a vulnerability only if it crosses a trust boundary. Name the attacker, what they
control, and what they gain. Typical boundaries:

- a CI job, code-review bot, package build or backup/integrity check runs `diff` or `cmp` on file
  contents or file names that an untrusted party controls;
- the output of `diff` is consumed by another program: `patch`, `ed` (for `diff -e` scripts), a
  web UI, or a script that parses `cmp`'s byte/line offsets or exit status to decide whether two
  files are identical.

## Components that matter most / least

- Most important: output that a downstream consumer interprets.
  - `src/ed_diff.rs`: `diff -e` emits an `ed` script. Attacker-controlled lines must never be able
    to terminate an append block early and smuggle `ed` commands (including `!command`) into the
    script. Check the handling of lines consisting of a single `.` and of missing trailing
    newlines.
  - `src/unified_diff.rs`, `src/context_diff.rs`, `src/normal_diff.rs`: hunk headers and line
    counts must match the emitted lines, so that `patch` applies exactly what `diff` showed.
    File names and labels are printed in the `---`/`+++`/`***` headers; check names containing
    newlines, tabs or control characters.
  - `cmp` exit status and reported offsets: a wrong "identical" answer (exit 0) for differing
    files, for example with `--ignore-initial`, `--bytes` or very large offsets, defeats
    integrity checks.
- `src/cmp.rs` and `src/utils.rs` contain the only `unsafe` code (`from_raw_fd` on stdout and
  `from_utf8_unchecked` in the byte formatters); check that the invariants claimed in the
  `SAFETY` comments hold for every byte value.
- Resource use: the diff algorithm and `side_diff.rs` on large or adversarial inputs (every line
  different, very long lines, huge numbers of lines). Report it only when cost is clearly
  disproportionate to input size, not merely proportional.
- Argument parsing in `src/params.rs` (combined short options, `-U`/`-C` numbers, `--width`,
  `--tabsize`), when an automated caller forwards partly untrusted options.
- Out of scope: `fuzz/`, `benches/`, `tests/`, `util/`, and Windows-only code paths.

## How to exercise it

- The checkout is at `/src`. The multicall binary is `target/debug/diffutils`; run
  `target/debug/diffutils diff a b` or `target/debug/diffutils cmp a b`.
- Rebuild offline with `cargo build --offline`; build `--release` too when a finding depends on
  overflow checks or optimisation.
- Integration tests are in `tests/by-util/test_diff.rs` and `tests/by-util/test_cmp.rs`, run
  with `cargo test --offline -- test_diff:: test_cmp::`. Unit tests are next to the code in
  `src/`.
- `fuzz/fuzz_targets/` shows how the formatters are expected to round-trip (for example
  `fuzz_patch.rs` and `fuzz_ed.rs` feed `diff` output back to `patch`/`ed`); use them as a guide
  for reproducers. GNU `patch` and `ed` may not be installed in the image.
- The image runs as root, so tests that rely on permission denials can fail there. That is
  expected, not a finding.

## How you rate severity

- Critical: attacker-controlled file contents or names make `diff -e` output execute commands
  when the script is run with `ed`, or make `patch` write outside the files that `diff` named.
- High: `diff` output that `patch` applies differently from what was displayed (hidden or
  altered lines that a reviewer would not see); `cmp` reporting identical files as identical when
  they differ; memory-safety bugs in `unsafe` code reachable from file contents.
- Medium: header injection through file names that misleads tools or reviewers parsing the
  output, without changing what gets applied.
- Low: denial of service (hang, excessive memory, crash) from attacker-controlled files processed
  by an automated pipeline. A panic that only affects the caller's own invocation on their own
  data is a normal bug, not a vulnerability.

## Anything to leave alone

- A difference from GNU diffutils on its own is a compatibility bug, not a vulnerability; report it
  as a vulnerability only if it lets an attacker cross a boundary. See the next section.
- Missing features (`patch`, `diff3`, `sdiff`, `diff -r`) are not findings.
- Panics, `unwrap`, or wrong exit codes with no safety impact (other than `cmp`'s identical/
  different status, which is in scope).
- Proposed patches must keep GNU-compatible behaviour and must not be derived from GNU source code
  (GPL); write original code. A regression test in `tests/by-util/` is appreciated.

## Compatibility differences from GNU diffutils

We also want to hear about behavioural differences from GNU diffutils, even when they have no
security impact. uutils aims to be a drop-in replacement, and these reports are valuable to the
team. List them in a separate section after any security findings, clearly marked as compatibility
issues, and do not assign them a security severity.

The GNU reference tools are installed in the image: `/usr/bin/diff` and `/usr/bin/cmp` (GNU
diffutils 3.10). Compare them directly against `target/debug/diffutils diff` /
`target/debug/diffutils cmp` on the same input, in the same directory, with `LC_ALL=C` and with
`LC_ALL=en_US.UTF-8` when locale matters.

Areas worth comparing: output formats (`-e`, `-c`, `-u`, `-y`, `--normal`), hunk boundaries, headers
and timestamps, `--label`, `-i`/`-w`/`-b`/`-B` and other ignore options, `--width`/`--tabsize` in
side-by-side output, binary-file detection, `cmp -l`/`-b`/`--ignore-initial` output, exit status and
error messages.

Not yet implemented utilities and options (`patch`, `diff3`, `sdiff`, `diff -r`) are known gaps;
list a missing option only if you came across it while testing.

For each difference, give:

- the exact command line and a minimal input (inline, or a short script that creates the files);
- GNU's output, error messages and exit status, and ours;
- whether the existing test suite already covers it (name the test if a similar one exists);
- a suggested regression test, and a fix when it is small and clear.

Group differences that share a root cause, and skip pure formatting of `--help`/`--version` text.
