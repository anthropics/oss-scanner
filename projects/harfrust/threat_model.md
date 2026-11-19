# HarfRust threat model

## Purpose and trust boundaries

HarfRust is a Rust port of HarfBuzz's text shaping engine. It accepts font data
and Unicode text and returns positioned glyphs. The workspace contains the
`harfrust` library, the `hr-shape` command-line tool, the `harfrust_capi` C ABI,
and an OSS-Fuzz shaping harness. The optional C API drawing and painting features
delegate to Skrifa, and subsetting delegates to Skera.

Treat fonts and text as attacker-controlled, including web fonts and fonts
embedded in documents. Malformed or truncated font tables, collections, invalid
offsets/counts, overlapping data, cyclic lookups, extreme variation coordinates,
and adversarial text/feature combinations are in scope. Do not assume that a font
was sanitized before reaching HarfRust. Invalid font data may be rejected safely.

The core Rust crate forbids unsafe code. The C API contains unsafe pointer,
ownership and callback glue and must be audited separately. Safe Rust callers
should not be able to trigger memory unsafety or a process-wide failure through
ordinary supported calls. For the C API, callers must supply accessible buffers
with truthful lengths, valid object lifetimes and valid callbacks, and obey the
documented threading and ownership rules. A reproducer requiring the caller to
violate those preconditions is not sufficient. A hostile font causing HarfRust
to violate them internally is in scope.

## Audit priorities and scope

- OpenType and AAT shaping in `harfrust/src/ot/`, `harfrust/src/aat/` and script
  shaping code. Examine contextual lookups, state machines, recursion, glyph
  expansion, buffer mutation, arithmetic and work limits for small hostile inputs.
- Font creation, eager/lazy table loading, caching and variation handling in
  `harfrust/src/shaper_font.rs` and its font dependencies. Check whether eager
  parsing or cache construction defeats limits enforced during shaping.
- Buffer and Unicode processing, feature ranges, custom font functions and
  optional tracing callbacks, including resource amplification from snapshots.
- C API reference counting, blobs, faces, buffers, fonts, user data, borrowed
  pointers and callbacks in `harfrust_capi/src/`. Pay particular attention to
  lifetimes, callback reentrancy, error/panic handling and conversions between
  C sizes and Rust slices. Supported callback behavior belongs in scope.
- The optional subset, draw and paint wrappers, including assembly of callback
  font tables, output ownership and traversal of color glyphs. Image decoding or
  rendering performed by an application's callback belongs to that application.

Focus on HarfRust's own root causes. `read-fonts`, Skrifa, Skera, ICU4X, the Rust
standard library and the HarfBuzz reference used by tests are dependencies, not
separate audit targets. HarfRust's misuse of their APIs remains in scope. External
font corpora contain test inputs only. Developer generators and benchmarks are
lower priority than code reachable through the public Rust or C APIs.

HarfRust is not a complete HarfBuzz implementation. Do not report unsupported
backends or ordinary glyph differences as security vulnerabilities. Consult
`HARFBUZZ.md` for known conformance differences before reporting a mismatch.

## Build and reproduction environment

The checkout is at `/src`. Stable Rust, nightly Rust, `cargo-fuzz`, a generated
`Cargo.lock`, crate/git dependency caches and test fonts are retained in the
image. `CARGO_NET_OFFLINE=true` prevents registry access during the audit.

Debug and release workspace builds include all optional features: ICU4X Unicode
data, tracing, and C API subsetting, drawing and painting. Release binaries retain
debug information and frame pointers, with stripping and LTO disabled. Release
overflow checks retain the upstream setting; debug builds and the sanitizer
fuzzer enable debug assertions and overflow checks. A separate `target/no-std/`
build exercises the core library with `libm,tracing` and default features
disabled on the Linux host; it is not a bare-metal target.

From `/src`, rebuild and run the tests without network access:

```sh
cargo build --locked --offline --workspace --all-features
cargo test --locked --offline --workspace
cargo test --locked --offline --workspace --all-features
cargo test --locked --offline --release --workspace --all-features
cargo build --locked --offline -p harfrust --no-default-features \
  --features libm,tracing --target-dir target/no-std
```

`target/debug/hr-shape` and `target/release/hr-shape` accept a font filename and
text. The shared/static C libraries are `target/{debug,release}/libharfrust_c.*`,
and the committed public headers are in `harfrust_capi/include/`. Small C
consumers are provided at `target/debug/hr-shape-c`, `hr-subset-c` and
`hr-rendering-c`. For example:

```sh
target/debug/hr-shape harfrust/tests/fonts/rb_custom/PT_Sans-Caption-Web-Regular.ttf abc
target/debug/hr-shape-c harfrust/tests/fonts/rb_custom/PT_Sans-Caption-Web-Regular.ttf abc
target/debug/hr-subset-c harfrust/tests/fonts/rb_custom/PT_Sans-Caption-Web-Regular.ttf
target/debug/hr-rendering-c harfrust_capi/tests/fonts/Rendering.ttf
```

The AddressSanitizer libFuzzer binary is
`target/x86_64-unknown-linux-gnu/release/fuzz_shape`. Rebuild it with
`cargo +nightly fuzz build -O --debug-assertions`. Run a saved input directly:

```sh
target/x86_64-unknown-linux-gnu/release/fuzz_shape \
  -runs=1 harfrust/tests/fonts/rb_custom/PT_Sans-Caption-Web-Regular.ttf
```

For a bounded fuzzing session:

```sh
cargo +nightly fuzz run fuzz_shape -O --debug-assertions -- \
  -max_total_time=60 -timeout=10 -rss_limit_mb=2048
```

The upstream seed corpus is
`fuzz/corpus/fuzz_shape/`; additional fonts from text-rendering-tests, color-fonts
and HarfBuzz are in `/opt/font-corpus/`. The harness selects a collection face,
derives variation coordinates and Unicode codepoints from trailing input bytes,
and also shapes fixed text. It does not cover every C API or arbitrary text/feature
combination. Prefer a direct Rust/C API reproducer when a harness limitation
matters. Font regressions are also under `harfrust/tests/fonts/` and
`harfrust_capi/tests/fonts/`.

## Severity and report expectations

- Critical: demonstrated arbitrary code execution or a comparable compromise
  through hostile font/text input and supported APIs.
- High: attacker-reachable memory corruption in HarfRust or its FFI glue, or
  demonstrated sensitive memory disclosure. Safe Rust in the core does not rule
  out bugs at the C boundary.
- Medium: a reproducible abort, uncaught panic, stack exhaustion, infinite loop,
  or disproportionate CPU/memory consumption from reasonably sized hostile input.
  Explain how a Rust panic reaches a process or service boundary; an embedding
  application may catch a panic, while a panic crossing a C ABI can abort.
- Low or correctness-only: ordinary shaping/conformance differences, safe font
  rejection, bounded costs proportional to input, or debug-only assertions with
  no demonstrated release security effect.

Check candidate panics and arithmetic issues in the release build as well as the
debug/sanitizer configuration. Measure resource amplification, account for
existing work limits, and distinguish a checked overflow from memory corruption.
Deduplicate findings sharing the same root cause.

Reports should include the tested commit and Cargo features/profile, a minimized
font/text or deterministic generator, exact offline reproduction commands,
backtrace or sanitizer output, and observed impact. Explain which trust boundary
is crossed and distinguish demonstrated behavior from exploitation hypotheses.
Prefer a focused fix preserving the public API/ABI with a regression test in the
existing suite. Report privately to the enrollment's primary security contact;
do not publish undisclosed vulnerabilities as GitHub issues.
