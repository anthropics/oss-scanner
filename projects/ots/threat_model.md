# OpenType Sanitizer threat model

OpenType Sanitizer (OTS) validates and rewrites OpenType (TTF/OTF), TrueType
Collection (TTC), WOFF and WOFF2 fonts. Browsers including Chromium and Firefox
use it at the boundary between untrusted font bytes and font consumers. Assume
an attacker controls every byte of an input font, including table directories,
compressed streams, offsets, lengths, counts and cross-table references.

## Security goals and scope

Parsing and serialization must remain memory safe for malformed, truncated and
internally inconsistent fonts. Rejecting an unsupported or invalid font is
expected. Accepted fonts should not preserve malformed structures that defeat
the sanitization OTS promises for the affected table. A sanitizer bypass needs
a concrete unsafe output or downstream security consequence; accepting a font
that differs from a specification is not by itself a vulnerability.

Prioritize the public `ots::OTSContext::Process()` entry point in `src/ots.cc`,
shared buffer and stream helpers, and table parsers and serializers in `src/`.
Pay attention to:

- Directory and collection parsing, offset arithmetic, table overlap, output
  sizes, checksums, alignment, decompression and resource limits.
- TrueType outlines and composite glyphs; CFF/CFF2 dictionaries, indices and
  charstrings; recursion, stacks and glyph/table dependencies.
- OpenType layout (GSUB, GPOS, GDEF), variable-font data (including `gvar`,
  CFF2 and variation stores), COLR paint graphs and color palettes.
- Graphite tables and their compressed data. Graphite sanitization is enabled
  in both prepared builds, as it is by default upstream.
- Error paths, partial parsing and serialization, allocation failure, and
  processing multiple fonts in a collection.

The embedding application must provide valid pointers, the actual input buffer
length, a valid output stream and callbacks, and object lifetimes consistent
with the API. Caller violations alone are not OTS vulnerabilities. Custom table
actions can deliberately pass tables through without sanitizing them; distinguish
that documented policy from failures in tables OTS is asked to sanitize.

The `ots-sanitize` command is a useful reproduction entry point. Other developer
utilities, test drivers and benchmarks are lower priority. FreeType, WOFF2,
Brotli, zlib, LZ4 and GoogleTest are dependencies: attribute bugs to the component
with the root cause, while keeping OTS's use of them in scope.

## Prepared build and fuzzing environment

The checkout is at `/src`. Build tools are installed in `/opt/venv`, which is on
`PATH`. Meson fetches bundled dependencies during the image build, so rebuilding
and running tests require no network access.

- `/src/build`: Clang, debug information, assertions, static library, standalone
  `ots-fuzzer`, `ots-sanitize`, FreeType-based utilities and regression tests.
- `/src/build-fuzz`: the same targets and dependencies with AddressSanitizer,
  UndefinedBehaviorSanitizer and coverage instrumentation. `ots-fuzzer` links
  libFuzzer through upstream's `fuzzer_ldflags` option.
- `/src/fuzzer_corpus`: the contents of `tests/fonts`, named by content hashes,
  matching the seed source used by OSS-Fuzz. Inputs include valid, invalid and
  historical regression fonts.

Run the tests with:

```
meson test -C build --print-errorlogs
ASAN_OPTIONS="$ASAN_OPTIONS:detect_leaks=0:alloc_dealloc_mismatch=0" \
  meson test -C build-fuzz --print-errorlogs
```

The sanitizer test command follows OSS-Fuzz's `run_tests.sh`. Its leak and
allocation-mismatch suppressions apply only to regression replay; the image's
default sanitizer settings keep both checks enabled for the audit and fuzzing.
Logs remain in each build's `meson-logs/testlog.txt`.
Meson tests include CFF charstrings, table passthrough,
rejection of bad fonts, idempotence for good fonts and replay of fuzzing seeds.

Start mutation fuzzing with:

```
build-fuzz/ots-fuzzer -max_len=1000000 fuzzer_corpus
```

Replay a single font with `build-fuzz/ots-fuzzer -runs=1 /path/to/font`, or use
`build/ots-fuzzer /path/to/font` without sanitizers. The fuzzer calls `Process()`
with an expanding memory stream and, after successful collection processing,
also processes individual TTC faces. Its output limit is eight times the input
size; investigate larger-output paths with a suitable stream or `ots-sanitize`
when needed. Custom table-action callbacks and custom streams need dedicated
harnesses. Windows and macOS integrations and 32-bit builds are not supplied by
this image; identify any required platform or configuration in a report.

## Severity and useful reports

- Critical: demonstrate a credible code-execution or sandbox-escape consequence
  from attacker-controlled fonts in a typical embedding application.
- High: reachable memory corruption, out-of-bounds access, use-after-free, or a
  sanitizer bypass with a demonstrated serious downstream security impact.
- Medium: practical denial of service from small inputs, such as excessive CPU,
  recursion or memory amplification. Include input size, runtime and memory use.
- Low: a security issue with limited practical impact. Specification differences,
  ordinary font rejection, diagnostic differences and test-only failures without
  a security consequence are correctness issues rather than vulnerabilities.

Distinguish debug assertions from release-build behavior and demonstrate
reachability through a supported API. A non-default supported configuration is
not automatically low severity. Report allocation failures that lead to memory
corruption; resource exhaustion caused only by enormous inputs or the harness's
own allocations needs evidence of a practical attack.

Include a minimized font, exact build and command, sanitizer output and the
affected input/table path. Prefer focused fixes that preserve the public API,
with regression coverage in `tests/` or a minimized input in
`tests/fonts/fuzzing/`. Run both prepared test suites after a patch.
