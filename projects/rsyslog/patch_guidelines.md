# How we would like patches made

## Size and scope of a fix
- Fix the root cause, as narrowly as practical. If the same faulty pattern
  exists in a shared helper used by several modules, fix the helper rather
  than one call site.
- No unrelated refactoring, renames or style changes in the same patch.
- Do not edit the ChangeLog file.

## Code style
- C code must be formatted with clang-format-18 using the .clang-format file
  at the repository root (devtools/format-code.sh does this).
- Follow the surrounding code: rsyslog's DEFiRet / CHKiRet / FINALIZE
  error-handling macros, and free resources on every error path.
- Comment only non-obvious invariants, such as a size calculation.

## Tests
- Add a regression test under tests/ that fails without the fix, as a shell
  test using tests/diag.sh, and register it in tests/Makefile.am. Start the
  test with a short comment that says what it checks and how it decides pass
  or fail.
- For parser or framing bugs, a seed for tests/fuzz/corpus is welcome too.

## Branch and commit message
- Against the main branch.
- Subject line in the form "module: what changed", for example
  "imtcp: bound octet-count length before allocation". The body explains the
  root cause and the fix in plain words.
