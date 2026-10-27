# Fontations threat model

## Purpose and trust boundaries

Fontations is a collection of Rust libraries for reading, inspecting, scaling,
modifying, subsetting and writing OpenType fonts, and applying Incremental Font
Transfer (IFT) patches. Consumers include browsers, graphics libraries and font
engineering tools.

Treat font bytes, font collections and IFT patch data as attacker-controlled,
including fonts delivered over the web or embedded in documents. Do not assume
that a sanitizer or another font library has validated the input first.
Malformed, truncated, overlapping, cyclic and internally inconsistent tables
are in scope. Also consider attacker-influenced glyph selections, Unicode text,
variation coordinates, sizes, feature settings and subset requests supplied
through supported public APIs.

Callers must respect Rust's memory-safety contracts and documented unsafe API
preconditions. A finding that requires a caller to construct an invalid slice,
violate lifetimes or introduce a data race is not a library vulnerability by
itself. Safe public APIs must handle malformed input without memory corruption.
Rust bounds checks and `forbid(unsafe_code)` do not rule out denial of service,
integer-arithmetic problems, or incorrect use of unsafe dependencies and FFI.

## Audit priorities

- `read-fonts/src/`, `read-fonts/generated/` and `font-types/src/`: font and
  collection directories, offsets, counts, integer arithmetic, table access,
  iterators, recursive structures and typed views of untrusted bytes. Include
  TrueType, CFF/CFF2 and Type 1 parsing, layout tables, variation data, color
  tables, embedded bitmap metadata and the experimental font API.
- `skrifa/src/`: character mapping, metrics, naming, variation normalization,
  outlines, composite glyphs and VARC, TrueType hinting, CFF/CFF2 interpretation,
  autohinting and color paint traversal. Check recursion and work limits, stack
  behavior, scratch-buffer sizing and validation before indexing or allocation.
- `write-fonts/src/` and `write-fonts/generated/`: conversion from borrowed to
  owned data, serialization, offset resolution and overflow handling. Check
  malformed input and the structural validity of emitted fonts. A malformed
  output font needs a concrete security consequence to be a security finding.
- `skera/src/`: glyph and layout closure, recursive dependencies, table
  subsetting, variation data, serialization and graph repacking. Hostile fonts
  and otherwise valid subset requests can both reach this code.
- `incremental-font-transfer/src/`: patch mapping, subset matching, URL template
  expansion, patch selection, table-keyed and glyph-keyed patch application,
  compatibility checks, output sizing and decompression limits. Fonts and patches
  may be inconsistent with each other. URL generation is in scope; network
  fetching policy belongs to the caller unless the library performs the fetch.
- `shared-brotli-patch-decoder/src/`: Rust/C FFI, shared dictionary lifetimes,
  input/output lengths, decompression limits, error handling and both the C and
  Rust Brotli backends. Attribute bugs in an external decoder to that dependency;
  Fontations' integration remains in scope.
- Shared collections in `read-fonts/src/collections/`, including sparse bit set
  decoding, integer sets and range sets, when reachable from font or patch data.

Prioritize library bugs reachable by real consumers. The `skera`, `ift_extend`
and `ift_graph` command-line tools are useful reproduction entry points and
their handling of hostile input is also in scope. `font-codegen`, benchmarks,
test-data generators and the FreeType comparison tool `fauntlet` are lower
priority. Third-party dependencies are outside this project's scope except for
Fontations-specific misuse of them. Test-harness failures need demonstrated
reachability in a library or supported tool.

Generated Rust is checked in. Fix the corresponding schema or generator in
`resources/codegen_inputs/` or `font-codegen/` when appropriate, then regenerate
with `cargo run --locked --bin codegen resources/codegen_plan.toml`; do not leave
generated code inconsistent with its source.

## Build and reproduction environment

The checkout is at `/src`. Stable Rust builds the workspace libraries and CLI
tools with all features; optimized binaries with debug information are
in `target/release/`. Default-feature and all-feature workspace tests are run
during the image build, excluding the separate `fuzz` package. Additional tests
cover `write-fonts` without default features and the Rust Brotli backend in both
the decoder wrapper and IFT library. Ignored slow integration tests and
benchmarks are not run by default.

Cargo's registry cache, the generated `Cargo.lock`, stable and nightly toolchains,
`cargo-fuzz`, and the Python environment at `/opt/venv` remain available offline.
The Python environment includes the FontTools version from upstream's Skera CI
requirements. A local Git mirror at `/opt/brotli.git` and a system Git URL rewrite
satisfy the decoder build script's Brotli clones, including for new build
configurations, without network access. Do not delete this mirror when cleaning
Cargo output. Native code and Rust builds retain frame pointers; release LTO is
disabled to simplify rebuilds and debugging.

From `/src`, rebuild and test with:

```sh
cargo build --locked --release --workspace --exclude fuzz --all-features
cargo test --locked --workspace --exclude fuzz
cargo test --locked --workspace --exclude fuzz --all-features
cargo test --locked -p shared-brotli-patch-decoder --no-default-features --features rust-brotli
cargo test --locked -p incremental-font-transfer --no-default-features --features rust-brotli
target/release/skera --help
target/release/ift_extend --help
```

Use `-p read-fonts`, `-p skrifa`, `-p write-fonts`, `-p skera` or
`-p incremental-font-transfer` to narrow tests. Regression fixtures live under
`font-test-data/test_data/`, `skera/test-data/`, `fauntlet/test_fonts/` and
`incremental-font-transfer/resources/testdata/`. This is an x86-64 Linux image;
32-bit, WebAssembly, no-std and platform-specific consumers are not built here.
Findings requiring those configurations must explain reachability and the
required setup.

## Fuzzer coverage and limitations

The image follows the upstream OSS-Fuzz build: nightly Rust, optimized libFuzzer
engines, AddressSanitizer and debug assertions. The C Brotli build is also
compiled with ASan. Engines are in
`target/x86_64-unknown-linux-gnu/release/`. Rebuild with:

```sh
CFLAGS="-g -fno-omit-frame-pointer -fsanitize=address" \
CXXFLAGS="-g -fno-omit-frame-pointer -fsanitize=address" \
cargo +nightly fuzz build -O --debug-assertions
```

Font inputs exercise `fuzz_basic_metadata`, `fuzz_name`,
`fuzz_skrifa_charmap`, `fuzz_skrifa_outline` and `fuzz_skrifa_color`.
`fuzz_int_set`, `fuzz_range_set`, `fuzz_sparse_bit_set_encode` and
`fuzz_sparse_bit_set_decode` consume operation streams or structured data, not
complete fonts. Consult their sources for encoding and operation limits.
`fuzz_ift_patch_group` uses `arbitrary` to construct font tables and patch state;
it substitutes `NoopBrotliDecoder`, so it does not exercise real Brotli decoding.
The fuzz crate uses its own dependency feature selection; it does not inherit
the stable workspace build's all-feature coverage.

Font seeds from upstream regression fixtures, text-rendering-tests, color-fonts
and HarfBuzz are combined in `/src/fuzzer_corpus/fonts/`. Content-hash filenames
avoid collisions and deduplicate identical bytes. For a bounded mutation run:

```sh
mkdir -p /tmp/fontations-charmap-corpus
target/x86_64-unknown-linux-gnu/release/fuzz_skrifa_charmap \
  -max_total_time=60 -timeout=10 -rss_limit_mb=2048 \
  /tmp/fontations-charmap-corpus fuzzer_corpus/fonts
```

Replay an input with the relevant engine and `-runs=1 /path/to/input`. The image
smoke-tests every declared engine on a small seed; these checks are not an
exhaustive fuzzing campaign. The outline harness deliberately explores a cross
product of sizes, variation locations and hinting modes; distinguish that work
from amplification in a single public API call. Set/range harnesses also assert
correctness properties; a mismatch alone does not establish a security impact.

Existing engines do not cover every parser, subsetting, serialization or real
IFT decompression path. Use library tests, a small public-API harness or the CLI
tools for gaps. Preserve the complete harness input, including any bytes used
to select collection indices or operations.

## Severity and report expectations

- Critical: demonstrated arbitrary code execution or comparably severe
  compromise from hostile font or patch data. Do not infer this solely from an
  ASan report or Rust panic.
- High: attacker-reachable memory corruption, such as an out-of-bounds write,
  use-after-free or double free, or demonstrated disclosure of sensitive memory.
  Explain attacker control and any consumer-specific prerequisites.
- Medium: reliably triggered process crashes, stack exhaustion, unbounded loops
  or disproportionate CPU/memory use from reasonably sized hostile inputs.
  A panic can qualify when it causes denial of service in a realistic consumer;
  explain whether that consumer catches unwinding or aborts the process.
- Low or correctness-only: incorrect glyph selection, metrics, outlines or
  subset output without a security consequence; harmless rejection of malformed
  data; bounded resource use proportional to input size; or diagnostic failures
  without an established impact.

Measure resource amplification and account for existing limits. A debug-only
arithmetic panic or assertion needs an impact analysis for an ordinary release
consumer. Safe allocation failure or early rejection is acceptable; allocation
failure must not cause memory corruption. A huge input exhausting its own
proportional allocation, a rendering difference from FreeType, or a failed
harness correctness assertion is insufficient on its own.

Reports should include the tested commit, toolchain and features, affected source
locations, a minimized font/patch or deterministic input generator, exact offline
reproduction commands, a backtrace or sanitizer output, and a concrete impact
analysis. Separate observed behavior from exploitation hypotheses and combine
inputs reaching the same root cause. Prefer a small root-cause fix preserving
public APIs, with a regression test in the affected crate. Keep undisclosed
vulnerabilities in private reports to the configured contacts.
