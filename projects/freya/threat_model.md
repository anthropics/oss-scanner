# Threat model

## What this project does

Freya is a native GUI library for Rust applications. It provides rendering, layout,
text editing, components, accessibility, and optional integrations such as HTML,
Markdown, remote assets, video, and terminals.

Application code and its dependencies are trusted. Freya is not a sandbox for
application code, plugins, terminal commands, or embedded web content.

## Inputs and boundaries to investigate

- Untrusted text, images, SVG, fonts, Markdown, and HTML passed to Freya APIs.
- Remote asset URLs and responses, where an application enables these features.
- Terminal output from a child process, including control and escape sequences.
- Text editing indices, selections, Unicode handling, and clipboard content.
- Unsafe code and native graphics or platform integrations reached by these inputs.

Prioritize memory safety defects, unintended command execution, unintended file
access, and disclosure of application data across a demonstrated trust boundary.
Explain which application API accepts attacker-controlled input and what capability
the attacker gains. Distinguish Freya defects from defects in third-party libraries.

Application policy matters. Loading a URL supplied by trusted application code or
running a command explicitly configured by the application is not itself a defect.
Do not assume that Freya promises browser-style origin isolation or HTML sandboxing.
Treat crashes or excessive resource consumption as availability issues rather than
code execution without evidence of a stronger impact.

## How to exercise it

The checkout is at `/src`. Rust uses the repository's `rust-toolchain.toml`.
The image builds the workspace with `freya/all-debug`, builds
`freya` with `devtools`, and compiles the workspace tests with `all-tests`.
Cargo dependencies, native build outputs, and debug artifacts remain in the image.
Cargo is configured to operate offline.

Use focused tests to reproduce findings, for example:

```sh
cargo test --locked --package torin
cargo test --locked --package freya-core --features all-tests
cargo test --locked --package freya-components --features all-tests
```

Use `freya-testing` for headless component reproductions. Native windows, camera,
audio, and GPU examples may require hardware or a display unavailable in the scanner.
Tests or examples that contact external services need local fixtures when run offline.

## Reports

Include the affected crate, attacker-controlled input, necessary application setup,
and a minimal reproducer or focused regression test. State whether the affected
feature is enabled by default or requires an optional integration.
