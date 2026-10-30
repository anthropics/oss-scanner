# GNU FriBidi: threat model and severity guide

GNU FriBidi is a C implementation of the Unicode Bidirectional Algorithm (UAX #9). It computes
embedding levels and reorders text for display, and also provides Arabic joining/shaping, mirroring
and character-set conversion. It is embedded in Pango/GTK, terminals, media players and other text
stacks, where the text being displayed can be attacker-controlled (filenames, messages, document
contents, web text). Assume every code point and length passed to the library is untrusted.

## What this project does and where untrusted input enters

- **Bidi levels and reordering** are the main surface. `fribidi_get_bidi_types()`
  (`lib/fribidi-bidi-types.c`), `fribidi_get_bracket_types()` (`lib/fribidi-brackets.c`), and
  `fribidi_get_par_embedding_levels_ex()` / `fribidi_reorder_line()` (`lib/fribidi-bidi.c`)
  consume UTF-32 text (`FriBidiChar`, `uint32_t`) of a caller-supplied `FriBidiStrIndex` length.
  They implement explicit levels, overrides, isolates, bracket pairs (BD16), weak/neutral
  resolution and line reordering. `fribidi_log2vis()` (`lib/fribidi.c`) wraps the common pipeline.
- **Character-set conversion**: `lib/fribidi-char-sets*.c` converts byte strings in UTF-8,
  ISO8859-6, ISO8859-8, CP1255, CP1256 and CapRTL to/from UTF-32
  (`fribidi_charset_to_unicode()`, `fribidi_unicode_to_charset()`). The `fribidi` CLI uses it, and
  embedders may feed it untrusted bytes.
- **Arabic and shaping**: `lib/fribidi-joining.c`, `lib/fribidi-joining-types.c`,
  `lib/fribidi-arabic.c`, `lib/fribidi-shape.c` and `lib/fribidi-mirroring.c` implement joining
  types, Arabic shaping and mirrored characters (`fribidi_shape()`, `fribidi_shape_arabic()`,
  `fribidi_get_mirror_char()`).
- **Run-level compression**: `lib/fribidi-run.c` groups runs of equal embedding levels.
- **Deprecated API**: `lib/fribidi-deprecated.c` is built (`-Ddeprecated=true`) and callable by
  embedders; it is lower priority but in scope.
- **CLI**: `bin/fribidi-main.c` processes command-line options and files; lower priority.

Generated Unicode tables (`gen.tab/`, producing `bidi-type.tab.i`, `brackets*.tab.i`,
`joining-type.tab.i`, `arabic-shaping.tab.i`, `mirroring.tab.i` and
`fribidi-unicode-version.h`) are data, not hand-written code. Report memory-safety bugs in how
they are consumed, not table-content differences.

## API contract

Most functions take a `len` and caller-allocated output arrays, with no capacity argument. A
finding that depends on the caller passing a `len` longer than the real input, or an output buffer
smaller than the documented requirement, is API misuse rather than a library vulnerability.
`fribidi_unicode_to_charset()` can emit up to four bytes per input character for UTF-8, so the
caller must size the output buffer accordingly. `FriBidiStrIndex` is a signed `int`, so lengths and
offsets near `INT_MAX` are worth checking for overflow, but callers are expected to pass real
buffer sizes.

## Fuzzer coverage

The bundled fuzzer (`bin/fribidi-fuzzer.c`) treats the input as native-endian UTF-32
(`size / 4` code points; little-endian on x86-64) and calls only:

- `fribidi_get_bidi_types()`
- `fribidi_get_bracket_types()`
- `fribidi_get_par_embedding_levels_ex()`

It does **not** exercise `fribidi_reorder_line()`, `fribidi_log2vis()`, `fribidi_shape()` /
Arabic shaping, mirroring, charset conversion, run-level compression or the CLI. Write a small
harness for those paths against the built library, or drive the `fribidi` CLI, and add a minimized
input to `test/fuzzing/` when fixing a crash there.

## Components that matter most / least

- Most important: `lib/fribidi-bidi.c` (levels, isolates, overrides, bracket stack),
  `lib/fribidi-brackets.c`, `lib/fribidi-run.c`, the Arabic/joining/shaping files, the charset
  conversion files and the public API implementations in `lib/fribidi.c`.
- Lower priority: `bin/` (CLI and the vendored GNU `getopt` files), `test/`, `doc/` and `gen.tab/`.
- There are no external runtime dependencies. The vendored getopt is third-party; report only a
  FriBidi-specific misuse of it.

## How to exercise it

Two builds are prepared:

- `/src/build`: gcc, debugoptimized, static library, CLI and tests. Run the upstream suite with
  `meson test -C /src/build --print-errorlogs`. It includes the input/reference tests, the
  `reorder-nsm` and `par-direction` API tests, and the `BidiTest` / `BidiCharacterTest` Unicode
  conformance suites.
- `/src/build-asan`: clang, ASan + UBSan, and the libFuzzer-linked
  `/src/build-asan/bin/fribidi-fuzzer`. `meson test -C /src/build-asan --print-errorlogs` also
  runs the two `test/fuzzing/crash-*` regression seeds through the fuzzer. Fuzz the prepared
  corpus with:

  ```
  /src/build-asan/bin/fribidi-fuzzer /src/fuzzer_corpus
  ```

- Reproduce a finding with a single input:
  `/src/build-asan/bin/fribidi-fuzzer -runs=1 /src/fuzzer_corpus/<file>`.
- The CLI is `/src/build/bin/fribidi`; `fribidi --help` lists the character sets and options.
  Fuzzer inputs are raw UTF-32, while the CLI defaults to UTF-8, so convert inputs or use the
  matching `--charset` when reproducing at the CLI level.

## How we rate severity

- **Critical**: memory corruption in the bidi, bracket, joining or charset paths reachable from
  untrusted text in a default build, with a plausible path to code execution or sandbox escape in
  a typical embedder.
- **High**: out-of-bounds read/write, use-after-free, double free or uninitialized use reachable
  from untrusted input; integer overflow leading to a short allocation; or stack/heap exhaustion
  that crashes the process from a small input.
- **Medium**: denial of service with small inputs (quadratic or exponential behavior, large memory
  amplification), or memory-safety bugs that require non-default API use or documented-buffer
  misuse.
- **Low**: issues confined to `bin/` argument handling, tests, docs or table generators;
  debug-only `assert()` failures that a release build compiles out and that do not precede memory
  corruption; and conformance deviations with no memory-safety or security impact (report those as
  correctness bugs).

## Please avoid reporting

- Findings that require a `len` longer than the actual input buffer, or an output buffer smaller
  than the API requires.
- Safe handling of invalid UTF-32 values (surrogates, values above U+10FFFF); treat them as input
  data, not a vulnerability by themselves.
- Pure differences from `BidiTest.txt` / `BidiCharacterTest.txt` without memory-safety or security
  impact.
- Issues in the vendored `getopt`, generated tables, tests, docs or CLI option parsing.
- Style, portability or build warnings, missing tests or missing documentation.

## Allocation failures and OOM

FriBidi returns 0/error from the level and reorder APIs on allocation failure; best-effort output
is acceptable as long as there is no crash, out-of-bounds access or memory corruption. The fuzzer
harness allocates arrays proportional to the input and does not check `calloc()`, so findings that
require a multi-gigabyte input are harness limitations, not library vulnerabilities. Keep
reproducers small.

## Patches and reproducers

- Reproduce first and include the exact command plus the full ASan/UBSan report.
- Prefer a minimal patch and add a regression test under `test/` or a minimized input under
  `test/fuzzing/`.
- Preserve the public API/ABI and the `FRIBIDI_NO_DEPRECATED` guards: a patch must still compile
  with `-Ddeprecated=false`, even though this build enables deprecated APIs.
- Do not hand-edit generated tables; update `gen.tab/` and regenerate.
- Run `meson test -C /src/build` and the matching ASan suite; for bidi changes, the conformance
  tests (`BidiTest`, `BidiCharacterTest`) are the minimum correctness bar.
- FriBidi is portable C built on Linux, macOS and Windows/MSVC; avoid GCC-only or little-endian
  assumptions in patches.
