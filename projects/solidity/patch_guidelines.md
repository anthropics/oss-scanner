# How we would like patches made

These rules follow the project's own `ReviewChecklist.md`, `CODING_STYLE.md` and the contributing guide (`docs/contributing.rst`).
Where this file is silent, follow those.

## Size and scope of a fix
- Fix the root cause, not the reproducer.
  If an optimizer step makes a wrong assumption, fix the assumption; do not special-case the input that exposed it.
- Fix the whole bug: check the variants the checklist lists (other types, data locations, construction time, inheritance, libraries, the ternary operator) and fix every one that has the same root cause.
- Keep the change as narrow as the root cause allows.
  No refactoring, renaming or reformatting of code the fix does not need to touch.
- Prefer a fix that does not change the bytecode of unaffected programs.
  If it does change bytecode or gas for programs that were correctly compiled before (for example by disabling an optimization in more cases than needed), say so and explain why.
- Do not "fix" a miscompilation by turning it into an error or an assertion, unless the input is genuinely invalid.
  An assertion is acceptable only for an invariant the compiler guarantees.
- Do not touch the code paths of the other pipeline unless it has the same bug: a fix in via-IR code generation should not change legacy output, and the reverse.
- Do not edit `docs/bugs.json` or `docs/bugs_by_version.json`; we add those entries at release.
- Do not modify vendored code under `deps/`.

## Code style
- Follow `CODING_STYLE.md` and match the surrounding code.
- Tabs for indentation only; any whitespace later on the line is spaces.
- Braces on their own lines; no braces around single-statement blocks unless needed for clarity.
- `m_` prefix for members, `_` prefix for parameters, camelCase names, PascalCase types.
- "East const": `T const&` and `T const*`, not `const T&`.
- Always initialize value types where they are defined.
- `.clang-format` is only approximate for this codebase.
  Do not run it over whole files; format the lines you change by hand.
  `scripts/check_style.sh` must pass.
- Use the project's error mechanisms: `solAssert` / `yulAssert` for internal invariants, and the `ErrorReporter` for errors and warnings shown to users.
- Few comments: only where the reason for the code is not obvious, for example why an optimization must not apply in some case.
- Use the C++ standard and dependencies the project already uses.
  No new dependencies.

## Tests
- Every fix comes with tests that reproduce the bug: they fail before the fix and pass after it.
  Run them both ways and state the result.
- Add the prominent variants of the reproducer as separate test cases, even those that did not trigger the bug.
- Pick the test type that matches the bug:
  - Code that compiles but behaves wrongly (miscompilation): a semantic test in the nearest subdirectory of `test/libsolidity/semanticTests/`.
  - A single Yul optimizer step: a test in `test/libyul/yulOptimizerTests/<step>/`, in addition to a semantic test when the bug is reachable from Solidity.
  - A program wrongly accepted or rejected: a syntax test in `test/libsolidity/syntaxTests/`.
    Do not mix code that compiles and code with errors in the same syntax test.
  - A compiler crash: a syntax test, or a `test/cmdlineTests/` case if it needs specific command-line options.
- Test files:
  - Name them after the behaviour they check, long and specific enough to guess the content; never after the report, and never by appending numbers to an existing name.
  - Place them in the right subdirectory.
  - Do not add a version pragma or SPDX comment to semantic and syntax tests.
  - For Standard JSON command-line tests, use `urls` and put the source in a separate file, not `content`.
- Generate the expectations after `// ----` with the tools rather than by hand, then review that they are correct and that the test still checks what it should:
  - `/src/build/test/tools/isoltest --testpath /src/test --enforce-gas-cost --accept-updates -t '<suite>/<dir>/*'`
  - when gas costs change, run it again with `--optimize`;
  - `test/cmdlineTests.sh --update` for command-line tests.
- Run the tests of the affected area only, e.g. `/src/build/test/soltest -t 'semanticTests/<dir>/*' -- --testpath /src/test`, and report the result.
  Do not run or update the whole suite.
- Do not change the expectations of existing tests unless the fix intentionally changes their output (for example gas costs or optimized code).
  If it does, list each changed test and why.

## Changelog
- Add one line to the unreleased section at the top of `Changelog.md`, following the style of the existing entries: `* <Component>: Fix <what was wrong>.`
- Miscompilations go under `Important Bugfixes:`, as in previous releases; add that heading at the top of the unreleased section if it is missing.
  Other fixes, including compiler crashes, go under `Bugfixes:`.
- Keep entries sorted alphabetically by component.
- For a miscompilation, say what was miscompiled and under which settings, but not how to exploit it.

## Branch and commit message
- Base the patch on the `develop` branch.
- Put the fix in its own commit, separate from any refactoring it needs.
- Commit subject in the form `<Component>: <what changed>`, e.g. `Yul Optimizer: Fix stale knowledge after variable reassignment`.
  Present tense, no trailing period.
- The commit body says *why* the change is made, not only what it does.
- Do not put an issue or report number in the commit message or branch name.
