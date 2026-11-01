# Ruffle security review

Ruffle is a Flash Player emulator written in Rust, used as a native desktop
player and as WebAssembly embedded in web pages and browser extensions. Treat
SWFs and the ActionScript programs they contain as attacker controlled, along
with media, fonts, URLs, network responses and serialized data loaded by them.
The embedding application's configuration and explicit user permission grants
are trusted inputs; a movie must not be able to grant itself those permissions.

## Review priorities

- `swf/` and `flv/`: parsing, decompression, length arithmetic and allocations.
- `core/src/avm1/` and `core/src/avm2/`: bytecode decoding and execution, malformed
  objects, garbage collection, reentrancy, native bindings and serialization.
- `render/` and `video/`: shader translation, image/audio/video decoding and
  unsafe or native dependency boundaries reached from movie content.
- `desktop/src/backends/` and `frontend-utils/`: filesystem paths, shared-object
  persistence, bundle handling, socket permissions, URL opening and redirects.
- `web/src/` and `web/packages/`: JavaScript and ExternalInterface interactions,
  origin handling, script access and networking configuration. Browser sandbox
  protections are part of the environment, but do not excuse bypassing Ruffle's
  own configured restrictions.

Follow each proposed exploit through the actual frontend and its configuration.
Desktop and web have different capabilities; do not assume identical Flash
sandbox semantics. Distinguish a permission bypass from an action the user or
embedding page explicitly allowed. Compatibility stubs and differences from
Adobe Flash behavior need a concrete security consequence to be vulnerabilities.

## Impact and reporting guidance

Prioritize host code execution, memory corruption, unauthorized file access,
credential or private data disclosure, and bypasses of script or networking
restrictions. Show the affected frontend, required settings, user interaction,
attacker control and reachable call chain. Evaluate crashes and resource
exhaustion by their demonstrated effect: a movie terminating its own player has
different impact from compromising the embedding page or host. Treat severity
as a proposal for maintainer review, based on the demonstrated impact rather
than a hypothetical exploit chain.

Include a minimal SWF, bytecode or media sample, exact commands and observed
behavior. Prefer a regression test and a focused patch. Existing fixtures are
under `tests/tests/swfs/`; see `tests/README.md` for their format. Tests and fuzz
corpora are intentionally malformed in places and are not production entry
points on their own. Dependency findings should show reachability from Ruffle.

## Scanner environment and commands

The checkout is `/src`, the native player is `/src/target/debug/ruffle`, and Cargo
dependencies and the stable Rust toolchain remain installed under `/opt`.
Java and the checked-in `tools/asc/asc.jar` support ActionScript compilation.
From `/src`, run:

```sh
cargo test --offline --locked -p swf -p flv-rs -p naga-agal
cargo test --offline --locked -p tests --features lzma,jpegxr,freetype
cargo test --offline --locked -p tests --features lzma,jpegxr,freetype -- avm2
cargo build --offline --locked -p ruffle_desktop
```

The regression harness runs SWFs headlessly. GPU image comparisons are not
enabled in this image; launching the desktop GUI requires a display and audio
may require a host device. The web frontend is available for source review but
this image does not install Node, browser automation or the Wasm build toolchain.
The separate `fuzz/` workspace is documented in `fuzz/README.md`; its nightly
toolchain, engines and dependencies are not provisioned here. Reproduce parser
findings with the native tests when possible. Do not assume builds with new
features or additional workspaces have cached dependencies offline.
