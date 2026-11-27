# How we would like patches made

## Size and scope of a fix
- Fix the root cause, where the invalid state is created, rather than adding a check at the place where it is
  noticed. If the same mistake exists at sibling call sites, fix them in the same patch.
- No unrelated refactoring and no reformatting of untouched code.
- Validate untrusted input and throw an exception with a meaningful error code (for example `INCORRECT_DATA`,
  `CANNOT_PARSE_INPUT_ASSERTION_FAILED`, `TOO_LARGE_ARRAY_SIZE`, `ACCESS_DENIED`) instead of using `assert` or
  `chassert`, which do nothing in release builds. Use `LOGICAL_ERROR` only for states that untrusted input cannot reach.
- Do not add fallback paths that silently substitute a default value: let the error propagate.
- Never use `sleep` to fix a race condition. Never add spinlocks or busy-wait loops.

## Code style
- C++ with Allman-style braces (the opening brace on its own line), four-space indentation, following the style of
  the surrounding code. See `/src/.clang-format` and `/src/.clang-tidy`.
- Few comments: only where the code is not obvious, explaining why rather than what.

## Tests
- Add a regression test as a new SQL or shell test under `/src/tests/queries/0_stateless/`, created with
  `/src/tests/queries/0_stateless/add-test <name>` (or `<name>.sh`), with its `.reference` file. Prefer a new test over
  extending an existing one, and a functional test over a unit (gtest) test.
- Crafted binary input belongs in a shell test that generates it, or in a small file under
  `/src/tests/queries/0_stateless/data_*`.
- Do not add `no-*` tags to the test unless strictly necessary.

## Branch and commit message
- Against the `master` branch.
- A short subject line describing the change, without a component prefix; a body that explains the root cause.
  Wrap names of functions, settings and classes in inline code.
