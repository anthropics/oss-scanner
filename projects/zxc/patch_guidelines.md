# How we would like patches made

## Size and scope of a fix
- Fix the root cause with the narrowest change that closes it, and apply it to every SIMD variant and to both the fast and strict decoders when they share the defect.
- Prefer validating once at a boundary, such as a header or section parse, over adding checks to the decoder's hot loops. If a check in a hot path is unavoidable, say so in the patch description.
- Do not change the format. Format version 9 is frozen, and the files under `tests/conformance/` and `tests/format/` must not be regenerated or edited.
- Keep the public API and ABI backward compatible.

## Code style
- C17, ASCII only, formatted with the `.clang-format` at the repository root (Google base, 4 spaces, 100 columns).
- Keep comments few and explain why, not what.
- A new source file starts with the SPDX line and copyright notice described in `.github/CONTRIBUTING.md`.

## Tests
- Add a regression test to the matching `tests/unit/test_*.c` file and register it with a declaration in `test_common.h` and a `TEST_CASE` line in `test_main.c`.
- When the bug comes from a malformed archive, build the input in the test rather than adding a binary file.
- The fix must pass `ctest` in both a normal and an ASan + UBSan build.

## Branch and commit message
- Target `main`.
- Use a Conventional Commits subject, for example `fix(decompress): reject oversized literal section`.
- Commits need a `Signed-off-by` line (`git commit -s`), added by the person submitting the patch.
