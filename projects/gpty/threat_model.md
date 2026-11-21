# gPTY threat model

## What this project is

gPTY is a multi-terminal emulator: a Rust PTY backend (`crates/gpty-core`) behind a Godot 4 GUI
(`godot/`), joined by a GDExtension (`crates/gpty-gdext`), a JSON-RPC control surface over a local
socket (`crates/gpty-ipc`) exposed as a CLI and an MCP server (`crates/gpty-cli`), and a media pane
that demuxes and decodes with a pinned FFmpeg (`crates/gpty-media`). The shipped artifact is the GUI
plus the `gpty` CLI; both run as the user.

## The trust boundary that matters

Same-UID is trusted by design (`SECURITY.md`). A process running as the same user can already read
the user's files, attach to their terminals and drive the control socket, so "a same-UID process can
control the workspace" by itself is not a vulnerability and should not be reported.

Everything reachable from outside that boundary is in scope:

- A program running inside a pane, when the user has set `GPTY_SECRET` (the GUI and CLI call
  `gpty_core::hardening::harden_process()`: `PR_SET_DUMPABLE 0` on Linux, a process DACL without
  `PROCESS_VM_READ` on Windows).
- Another local user on a shared host.
- Files the user opens: media files, vault notes, profiles/layouts/concepts/settings JSON, plugin
  manifests.
- Bytes produced by programs the user runs: terminal output, OMP event frames, AI backend output.
- Network input only insofar as a pane program fetches it and writes it to its terminal.

## Where untrusted input enters, highest value first

1. `crates/gpty-core/src/parser.rs` - the vte/ANSI parser: OSC/DCS/CSI, malformed UTF-8, huge
   output, resize storms, alt-screen switching. `osc_dispatch` interprets exactly one sequence,
   `gpty_state`, and strips every other OSC payload (titles included); there is no OSC 52 clipboard
   path. The grid is `term.rs` plus the alacritty terminal crate.
2. `crates/gpty-ipc/src/server.rs` - newline-framed JSON-RPC over a Unix socket or named pipe, with
   `MAX_REQUEST_LEN` (64 KiB) per frame and a read timeout; `peer_uid_matches` is the gate and fails
   closed. `transport::validate_socket_path` and the `GPTY_SECRET` checks are security-critical.
3. `crates/gpty-gdext` - the Rust/Godot FFI and the Variant marshalling for every pane;
   `omp_events.rs::ALLOWED_FIELDS` and its caps (ids <= 128 B, text <= 8 KiB) are the boundary that
   stops agent metadata from carrying prompts, answers or tool payloads.
4. `godot/scenes/terminal/` - keyboard and paste input; `_paste_text` is the single paste filter
   (C0 except newline and tab, plus DEL, dropped; ESC dropped so `ESC[201~` cannot break out of a
   bracketed paste).
5. `crates/gpty-core/src/concept.rs` and `engine.rs` - user-authored concept triggers matched against
   terminal output; the standard Rust `regex` crate only (no back-tracking engine; ReDoS is a
   defect).
6. `crates/gpty-media/src/lib.rs` - FFmpeg demux/decode of user-opened files, with demuxer and codec
   allowlists checked after open (defense in depth over the pinned build).
7. `crates/gpty-core/src/vault.rs`, `links.rs`, `store.rs`, `history.rs` - note files, wikilinks, the
   SQLite scrollback database, and the 0600/0700 store permissions.
8. `crates/gpty-plugin` and the plugin-manifest handling in `godot/` - installed plugin paths and
   the profile trust anchor (`PaneTypes.ALL`).

## How to exercise it

The image has the workspace built, its crates fetched, the pinned FFmpeg prefix and the pinned Godot
4.7.2 editor:

- `cargo test --workspace` (the Rust suite; add `-- --test-threads=1` when a test is suspected of
  shared state).
- `./scripts/gut-check` (headless GUT suite; the script owns the command and judges the run).
- `(cd extensions/gpty-omp-events && node --test)`.
- `fuzz/target/x86_64-unknown-linux-gnu/release/<target>` for the seven prebuilt libFuzzer targets
  (`line_parser`, `grid_feed`, `ipc_request`, `markdown`, `vault_links`, `media_probe`, `ai_frame`);
  run one with `-runs=N` and a corpus, or rebuild with `cd fuzz && cargo fuzz build`.
- `python3 scripts/smoke_pane_api.py` boots the GUI headless and drives the CLI against it.
- `godot --headless --path godot` starts the GUI with no display; `./target/debug/gpty` is the CLI
  (`gpty schema`, `gpty mcp`, `gpty new-pane`, ...).

## How to rate severity

- Critical: code execution, arbitrary file read/write/delete, or a privilege change reachable from a
  pane program, a parsed escape sequence, an opened media file, a vault note or an IPC request.
- High: memory corruption or a sanitizer finding in our Rust or FFI code; a cross-user socket or
  secret bypass; an allowlist escape (media demuxer/codec, paste filter, plugin path); unbounded
  memory growth that persists after the input stops.
- Medium: a single-pane denial of service that ends when the pane is closed; a leak of same-UID
  metadata; a file mode laxer than 0600/0700 with no demonstrated reader.
- Low: cosmetic or hardening-only issues with no demonstrated impact.

Same-UID issues, and anything reachable only by editing your own configuration to run your own
program, are not vulnerabilities. Dependency advisories are covered by `cargo audit` and
`cargo deny` in CI; do not spend reports on them unless gPTY's own code makes the advisory
reachable, and then report that code path.

## Leave alone

- The Godot engine, the alacritty terminal crate, FFmpeg internals and the OMP/LLM backend are
  third-party; report only gPTY code that misuses them.
- `godot/addons/gut/` is a vendored test framework.
- Windows- and macOS-specific code cannot be executed in this Linux image; report what can be proved
  by reading it, and say that it was not run.
