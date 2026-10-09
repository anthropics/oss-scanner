# Merman threat model

## Project and exposure

Merman is a headless Rust implementation of Mermaid parsing, layout, and rendering,
distributed under MIT OR Apache-2.0. It returns typed models, SVG, terminal text,
PNG, JPEG, and PDF without starting a JavaScript runtime or browser.

Mingzhen Zhuang (GitHub: Latias94) is the sole core maintainer and primary security
contact. As of October 9, 2026, the repository has 580 GitHub stars; crates.io
reports 111,910 recent downloads and 119,745 all-time downloads for the merman
crate. Downloads are not counts of unique users. Zed has merged its Merman
integration: https://github.com/zed-industries/zed/pull/57644.

Editors and document tools can process attacker-controlled Mermaid source from
Markdown, repositories, and shared documents. Treat diagram text, frontmatter,
labels, links, and host-supplied IconifyJSON bytes as untrusted. Generated SVG
can cross another trust boundary when mounted in a browser or editor webview.

## Security goals and important components

- Inspect semantic parsing and configuration admission in crates/merman-core,
  and facade policy inheritance in crates/merman.
- Inspect layout algorithms for input-amplification CPU, memory, and stack
  exhaustion, including Dagre, ELK, Cytoscape, and family-specific paths.
- Inspect SVG serialization, entity decoding, sanitization, URL/CSS/namespace
  handling, and immutable icon registry admission in crates/merman-render.
- Inspect the terminal resvg-safe pipeline and bounded raster/PDF export in
  crates/merman-export. Non-navigation rendering resources must be closed under
  the documented export policy.
- Inspect native ABI token ownership, concurrent operations, close/free behavior,
  callbacks, and panic boundaries in crates/merman-ffi and bindings-core.
- Inspect the Tree-sitter grammar and external scanner in
  distribution/tree-sitter-mermaid, including incremental edits.
- Browser DOM admission and mount checks in platforms/web and editor integrations
  are relevant source-review targets, although this initial image builds native
  Rust and C components rather than the JavaScript/browser tooling.

See docs/security/RENDERING_SECURITY.md and docs/integration/RESOURCE_POLICY.md
for the authoritative guarantees and host responsibilities. Follow their actual
contracts rather than assuming browser Mermaid behavior or a universal sandbox.

## Trust boundaries and severity

Default/strict behavior must maintain its documented sanitization and resource
boundaries. Source-controlled configuration must not bypass explicit host policy.
Demonstrate the exact entry point, effective options, and consumer behavior.

Mermaid loose mode is intentional trusted-input behavior. Merman's sandbox
security setting does not create an iframe or process isolation. Trusted host
callbacks and custom postprocessors are executable host capabilities, not
attacker-supplied code execution features. Raw SVG insertion that bypasses the
documented browser admission helpers is a host trust decision. Still report
bypasses of the guarantees that those helpers or strict/export policies make.

Configurable work limits and cooperative cancellation do not promise a hard RSS
cap or forced interruption of synchronous host callbacks. Hosts own scheduling
and process quotas. Report practical amplification or limit bypasses under finite
supported policies with input size, elapsed time, memory/stack behavior, and a
baseline; do not classify ordinary work within documented limits as a bypass.
Explicit unbounded_for_trusted_input behavior is not itself a vulnerability.

Native callers must satisfy documented pointer validity, allocation, lifetime,
and callback contracts. An invalid arbitrary pointer passed to an unsafe C ABI is
not by itself a library vulnerability. Memory corruption, races, or use-after-free
reachable through contract-compliant calls are security-relevant.

Rate findings by demonstrated reachability and impact. Code execution through
untrusted input deserves highest priority. Browser script execution needs an
actual supported mount path and security context. Reliable process termination
or resource exhaustion can be important in editors and services, but do not
automatically label every panic or slow diagram critical. Visual parity defects
without a security consequence are ordinary bugs.

## Build and reproduction

The checkout is /src. The Dockerfile fetches the workspace and fuzz dependencies,
builds native entry points, compiles selected tests, and runs a security-focused
subset. Rust builds retain debug information and frame pointers. Core diagram
families, SVG, optional layout/math engines, ASCII, PNG/JPEG/PDF, analysis, and
the native ABI are enabled through MERMAN_SCAN_FEATURES.

Run the compiled native suites offline with:

```sh
cargo nextest run --offline --locked \
  -p merman -p merman-core -p merman-render -p merman-export \
  -p merman-ffi -p tree-sitter-mermaid \
  --features "$MERMAN_SCAN_FEATURES"
```

target/debug/merman-cli and target/debug/merman-lsp provide CLI and LSP entry points;
use --help or the corresponding crate README for invocation details. Rust
embedding examples live in crates/merman/examples. fixtures/ and the crate test
suites contain regression inputs. Existing fuzz harnesses are in
fuzz/fuzz_targets for parsing, rendering, SVG pipeline, FFI, and Tree-sitter.
Fuzz dependencies are cached, but running libFuzzer needs an additional nightly
toolchain and cargo-fuzz; these are not installed by this initial image.

Historical copies in repo-ref/ and generated upstream comparison artifacts are
reference material, not shipped Merman runtime implementations. Third-party
dependency defects should be identified separately from Merman-owned defects.

## Reports and patches

Send reports to superfrankie621@gmail.com. Provide a self-contained reproducer,
affected revision, exact API/options, expected guarantee, observed impact, and
commands that run offline. Distinguish current main from published releases.
Group findings with the same root cause. Candidate patches should preserve
Mermaid semantics where safe and include a focused regression test; prefer fixes
at the owning boundary rather than fixture-specific tuning or a new audit
framework. The maintainer will independently verify findings and patches.
