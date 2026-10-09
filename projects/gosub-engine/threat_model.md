# Threat model

## What this project does and where untrusted input enters
Gosub is an embeddable browser engine written in Rust. Treat everything that comes from the web as hostile:
- HTML documents (`gosub_html5` tokenizer and tree builder, including shadow DOM)
- CSS stylesheets and inline styles (`gosub_css3`)
- Sub-resources found by the parser: images, web fonts, SVG (`gosub_svg`), and `data:` URLs
- Network responses, headers, redirects and cookies. These go through the external `gosub-sonar` crate, which is enrolled separately. In this repo, what matters is how the engine *uses* sonar's results.
- URLs and navigation requests from page content

The embedder (the application driving `GosubEngine` through `TabCommand`) is trusted. So are configuration (`gosub_config`) and local files the user opens on purpose.

## Components that matter most / least
Most important:
- `gosub_html5` and `gosub_css3`: parsers that take raw attacker bytes
- `gosub_render_pipeline`, `gosub_lattice` and `gosub_fontmanager`: layout, tables, text shaping and font loading driven by page content. Watch for integer overflow, huge allocations and unbounded recursion here.
- `gosub_sandbox` and `gosub_ipc`: process isolation (seccomp-BPF, network namespaces, rlimits on Linux) and shared-memory ring buffers between processes. These crates contain most of the project's `unsafe` code. A compromised renderer that escapes the sandbox, or that corrupts the parent through IPC/shared memory, is the worst case.
- `gosub_engine`: zone/tab isolation. A page reading cookies or storage from another zone is a security bug.

Lower priority but in scope: `gosub_renderer_*` backends, `gosub_web_platform` and `gosub_webinterop`.

Out of scope:
- `gosub_v8`, `gosub_jsapi` and `gosub_webexecutor`. They build, but JavaScript is not wired into the engine, so page content cannot reach them.
- `gosub_domjs`, a test-only QuickJS binding used for web-platform-tests
- `examples/`, `benches/`, `bin/gosub-wpt`, `crates/gosub_css3/tools/`, `wasm/` and `src/wasm*`
- The GUI shells (egui/gtk4/winit examples, `gosub-mini-browser`), except where they show an engine bug
- Third-party crates (Taffy, Skia, Vello, Cairo/Pango, etc.), unless gosub misuses them

## How to exercise it
- `cargo run --bin gosub-parser <file-or-url>` parses an HTML page.
- `cargo run --bin css3-parser <file>` and `cargo run --bin css-check <file>` parse CSS.
- `cargo run -p gosub-screenshot -- <url>` runs the full engine and render pipeline headless and writes a PNG.
- `cargo run --example hello-world` drives the engine headless.
- Fuzz targets live in `crates/gosub_html5/fuzz` (`html5_parser`, `tokenizer`) and `crates/gosub_css3/fuzz` (`css3_parser`). They need nightly.
- `cargo test --all` runs unit and integration tests. `crates/gosub_sandbox/tests` covers sandbox enforcement.

The scan runs without network access, so serve test pages from a local HTTP server on 127.0.0.1 or use `file://` paths.

## How you rate severity
- Critical: escaping the sandbox from a renderer/child process; memory corruption in the parent through IPC or shared memory; memory corruption reachable from web content that can be shown to lead to code execution.
- High: any other memory-safety bug (out-of-bounds, use-after-free, data races in `unsafe` code) reachable from web content; cookie, storage or data leaks between zones; a page reading local files or bypassing same-origin restrictions the engine enforces.
- Medium: a panic, unbounded allocation, stack overflow or infinite loop triggered by a crafted page (the engine is meant to survive hostile content, but this is a DoS); weaknesses in the sandbox policy that do not on their own allow an escape.
- Low: problems that need a malicious embedder or local configuration; info leaks with no practical impact.

## Anything to leave alone
- Do not report `unwrap`/`expect`/`panic` in tests, benches, examples or dev tools.
- Do not report missing JavaScript or Web API features. Scripting is not enabled.
- Do not report spec-conformance gaps (rendering differences, WPT failures) unless they have a security impact.
- The project is pre-1.0 and under heavy development. Report what is in the `main` branch.
