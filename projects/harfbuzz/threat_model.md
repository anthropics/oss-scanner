# HarfBuzz threat model

## Purpose and trust boundaries

HarfBuzz is a text shaping engine embedded in browsers, document readers, GUI
toolkits and other applications. It parses font tables, turns Unicode text into
positioned glyphs, exposes font metadata and outlines, and provides font
subsetting, variable-font instancing, rasterization, vector output and GPU data
preparation libraries.

Treat font bytes and text as attacker-controlled, including fonts embedded in
documents or supplied as web fonts. Do not assume a font has passed through
OpenType Sanitizer or FreeType before reaching HarfBuzz. Malformed, truncated,
overlapping, cyclic and internally inconsistent font tables are in scope.
Also consider attacker-influenced glyph selections, feature settings, variation
coordinates and buffer contents passed through otherwise valid public API calls.

The embedding application supplies valid pointers, allocation lengths, object
lifetimes and callbacks according to the API contract. Crashes that require a
caller to lie about an accessible buffer's length, use a destroyed object, install
an invalid callback, or mutate an object concurrently in violation of its API
contract are not security findings by themselves. A malformed font or text that
causes HarfBuzz to violate these rules internally is in scope. Allocation failure
must not cause memory corruption; safe early failure or incomplete output is
acceptable.

## Audit priorities

- Font sanitization and table access in `src/hb-open-type.hh`, `src/hb-open-file.hh`,
  `src/hb-ot-*.hh`, `src/OT/` and the AAT parsers in `src/hb-aat-*`. Pay particular
  attention to offsets, lengths, counts, integer arithmetic, recursive structures,
  glyph outlines, variation data, color glyphs and embedded images.
- OpenType and AAT shaping, Unicode processing, buffer growth, lookup application,
  caches and work limits. Both hostile fonts and hostile text paired with a valid
  font can reach this code.
- Buffer deserialization through `hb_buffer_deserialize_glyphs()` and
  `hb_buffer_deserialize_unicode()`, including JSON/text syntax, lengths, numeric
  fields and partially parsed inputs. These are public parsers for untrusted data.
- Subsetting, instancing, dependency analysis, serialization and graph repacking
  in `src/hb-subset*`, `src/hb-serialize.hh` and `src/graph/`. Check malformed input
  as well as the validity and safety of emitted fonts.
- Drawing and painting callbacks, raster and vector libraries, SVG handling, and
  the CPU-side preparation of GPU data in `src/hb-draw*`, `src/hb-paint*`,
  `src/hb-raster*`, `src/hb-vector*` and `src/hb-gpu*`. Experimental APIs are in
  scope; identify the required feature or build setting in the report.
- Shared containers, allocation/error paths, reference counting and lazy
  initialization when reachable through supported public APIs.

Prioritize library bugs reachable by consumers. Command-line utilities in `util/`
are useful entry points, and their handling of hostile fonts and text is also in
scope. Developer generators, benchmarks, documentation and test-only drivers are
lower priority; a crash confined to a test harness is not a library vulnerability.
Third-party dependencies are outside this project's scope, but HarfBuzz's use of
them is in scope. Attribute a finding to the component containing its root cause.

Supported reduced-feature and 32-bit configurations remain in scope. State the
required configuration and demonstrate reachability; a non-default configuration
alone does not establish a lower severity. This image supplies an x86-64 Linux
environment, not a complete 32-bit or platform-specific toolchain.

## Build and reproduction environment

The checkout is at `/src`. Dependencies, including the Python environment in
`/opt/venv`, are installed during the image build; rebuilding and testing need no
network access. Three Clang build trees are available:

- `/src/build`: optimized with debug information, assertions and frame pointers.
- `/src/build-asan`: AddressSanitizer and UndefinedBehaviorSanitizer, with the same
  features plus `experimental_api=true`.
- `/src/build-fuzz`: static ASan/UBSan libraries with sanitizer coverage, libFuzzer,
  experimental APIs and allocation-failure injection. Only the seven security
  fuzz targets are built in this tree; use the other trees for Meson tests.

Both replay builds include GLib, GObject, FreeType, Cairo, ICU and Graphite2
integration, plus subsetting, raster, vector and GPU libraries. The interactive
GPU demo is disabled; CPU-side GPU encoding tests and fuzz drivers run without a
GPU or display.
Platform backends for Windows and macOS, WebAssembly shaping, and the optional
Rust and kbts backends are not built in this Linux image. A finding in an unbuilt
backend needs its configuration and reachability explained.

UBSan diagnostics stop execution and print a stack trace. ASan permits allocator
failure and retains leak detection. These settings apply to direct CLI and fuzz
driver invocations as well as test runs.

From `/src`, rebuild and run tests with:

```sh
meson compile -C build -j 2
meson test -C build --print-errorlogs --num-processes 2
meson test -C build-asan --print-errorlogs --num-processes 2
```

Use `--suite api`, `--suite shape`, `--suite subset`, `--suite vector` or
`--suite fuzzing` to narrow a test run. Logs are in each tree's
`meson-logs/testlog.txt`. The sanitizer build can fail `check-symbols` because
instrumentation exposes extra symbols, including `__start_asan_globals` and
`__stop_asan_globals`, and additional C++ template symbols. Use the normal build
for this exported-ABI check; these extra symbols alone are not a security finding.

Command-line tools live in `build/util/` and
`build-asan/util/`, including `hb-shape`, `hb-subset`, `hb-view`, `hb-info`,
`hb-raster` and `hb-vector`. For example:

```sh
build-asan/util/hb-shape test/api/fonts/Roboto-Regular.abc.ttf abc
build-asan/util/hb-subset test/api/fonts/Roboto-Regular.abc.ttf \
  --text=abc --output-file=/tmp/subset.ttf
build-asan/test/fuzzing/hb-shape-fuzzer test/api/fonts/Roboto-Regular.abc.ttf
```

`build-asan/test/fuzzing/` also contains standalone subset, repacker, raster,
vector, GPU and dependency fuzz drivers. These take input filenames and exit;
they are not libFuzzer engines. See `test/fuzzing/meson.build` and the harness
sources for input formats and any harness-specific behavior. Font corpora and
regressions are under `test/fuzzing/fonts/`, `test/api/fonts/`,
`test/shape/data/` and `test/subset/data/`; repacker inputs are in
`test/fuzzing/graphs/`. Prefer a public API or command-line reproducer when a
harness failure may depend on synthetic state or allocation-failure injection.

The mutation engines in `build-fuzz/test/fuzzing/` are `hb-shape-fuzzer`,
`hb-subset-fuzzer`, `hb-raster-fuzzer`, `hb-vector-fuzzer`, `hb-gpu-fuzzer`,
`hb-repacker-fuzzer` and `hb-depend-fuzzer`. Rebuild those named targets with
`meson compile -C build-fuzz -j 2 <target>`. Font inputs from the existing test and
performance trees are combined in `/src/fuzzer_corpus/fonts/`, and repacker
graphs are in `/src/fuzzer_corpus/graphs/`. Content-hash filenames preserve
distinct inputs with the same original name and deduplicate identical bytes.

For a bounded mutation run, use a writable working corpus followed by the seeds:

```sh
mkdir -p /tmp/hb-shape-corpus
build-fuzz/test/fuzzing/hb-shape-fuzzer -max_total_time=60 \
  -timeout=10 -rss_limit_mb=2048 /tmp/hb-shape-corpus fuzzer_corpus/fonts
```

Use `fuzzer_corpus/graphs` for the repacker. Replay a saved input with
`build-fuzz/test/fuzzing/hb-shape-fuzzer -runs=1 /path/to/input`. The image build
checks all seven engines on small seeds with injection enabled and disabled;
these smoke checks do not constitute an exhaustive fuzzing campaign. For input
reduction and regression recording, see `test/fuzzing/hb_fuzzing_tools.py` and
`test/fuzzing/record-test.py`.

To check behavior without optional system backends, create a separate tree:

```sh
meson setup build-min --wrap-mode=nofallback --auto-features=disabled \
  -Dtests=enabled -Dutilities=disabled
meson compile -C build-min -j 2
meson test -C build-min --print-errorlogs --num-processes 2
```

## Allocation-failure injection

Only `build-fuzz` enables `HB_CUSTOM_MALLOC` and links `src/failing-alloc.c`.
The harness enables its deterministic failing allocator when the final input
byte is at least `0x80`; the allocator then returns NULL for roughly one in
sixteen allocation attempts. The regular and sanitizer replay trees use normal
allocation and do not inject failures.

Memory corruption, crashes and invalid internal state after allocation failure
are in scope. Safe early failure, incomplete rendering or discarded partial
output are acceptable, including in experimental raster, vector and GPU code.
A leak needs a concrete resource-exhaustion impact to qualify as a security
finding. Explain the allocation failure and externally observable effect; do not
infer a security bug solely from OOM simulation or a differing output.

Reproduce an OOM finding with `build-fuzz` and retain the complete input,
including its trailing allocator-control byte. The prepared input
`/tmp/hb-fuzz-smoke/shape-oom` enables injection, while `shape-normal` disables it.
Apply the same severity rubric as for other inputs, and prefer a direct
public-API reproducer where practical.

## Severity and report expectations

- Critical: demonstrated arbitrary code execution or comparably severe compromise
  from hostile font or text input. Do not infer this solely from a sanitizer crash.
- High: attacker-reachable memory corruption, such as an out-of-bounds write,
  use-after-free or double free; or a demonstrated disclosure of sensitive memory.
  Explain the degree of attacker control and any consumer-specific prerequisites.
- Medium: reliably triggered process crashes, stack exhaustion, unbounded loops,
  or disproportionate CPU/memory use from reasonably sized hostile inputs;
  out-of-bounds reads without demonstrated sensitive disclosure generally belong
  here. Measure resource amplification and account for existing work limits.
- Low or correctness-only: incorrect glyph selection, positioning or rendering,
  harmless rejection of malformed fonts, bounded resource use proportional to
  input size, or sanitizer warnings without an established security impact.

An assertion failure or undefined-behavior diagnostic alone does not establish
exploitability. Explain the externally observable effect and, where relevant,
whether it persists with assertions disabled in a release build. Treat different
inputs reaching the same root cause as one finding.

Reports should include the tested commit, build options, affected source locations,
a minimized font/text or small deterministic input generator, exact offline
reproduction commands, sanitizer output or a backtrace, and a concrete impact
analysis. Separate observed behavior from exploitation hypotheses. Prefer a small
patch that fixes the root cause without changing public API/ABI, plus a regression
test in the relevant existing suite. Follow `SECURITY.md` for private reporting;
do not open public issues containing undisclosed vulnerabilities.
