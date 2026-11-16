# Threat model

## What this project does and where untrusted input enters
TUICommander is a local desktop application (Tauri 2, Rust backend, SolidJS frontend) that runs terminals and AI coding
agents for one professional user on their own machine. The local OS user is the trust boundary: that user, the
repositories they open, and the plugins they install are trusted.

Untrusted input enters through:
- **PTY output.** Any program in a terminal (or a remote host reached over SSH) can write arbitrary bytes, escape
  sequences and OSC strings. They go through the patched `vte` and `alacritty_terminal` crates
  (`src-tauri/patches/`) and the agent output parsers (`src-tauri/crates/tuic-terminal`). A terminal stream must not
  be able to execute commands, write files, open URLs without a user action, or corrupt memory.
- **Network listeners.** The remote-access HTTP/WebSocket server (desktop app and the `tuic-remote` daemon) is
  reachable from the LAN. It requires a URL token, session cookie or Basic Auth, rejects foreign `Origin` and unknown
  `Host` headers, and rate-limits failed sign-ins. The relay transport carries end-to-end encrypted traffic through a
  third-party relay. A network attacker without credentials must not reach any API, terminal or file.
- **Web pages in a browser.** A website the user visits must not drive the local HTTP API (CSRF, DNS rebinding,
  CORS mistakes) or the `tuic://` deep-link handler into a harmful action.
- **Remote services.** Responses from GitHub, the update server, and remote `tuic-remote` daemons are parsed by the
  app. A malicious remote daemon must not gain code execution on the desktop that connects to it.
- **Content shown in previews.** Markdown, HTML and diffs from a repository are rendered in sandboxed iframes.

## Components that matter most / least
- Most: remote-access authentication and session handling (`src-tauri/src/mcp_http/`, `tuic-remote`), the relay
  pairing and encryption, deep-link handling, terminal escape-sequence parsing, the update/deploy path that copies
  binaries to remote hosts over SSH.
- Less: UI-only code paths, developer scripts (`scripts/`), benchmarks, the website (`website/`), docs.
- Out of scope: third-party code outside `src-tauri/patches/`; the `plugins/` content (installed and trusted by the user).

## How to exercise it
- Rust: `cd src-tauri && cargo nextest run --workspace --features dictation,test-fixtures` (offline, already built).
- Frontend: `pnpm exec vitest run`.
- Binaries: `/usr/local/bin/tuic-remote` (headless daemon with the HTTP API), `src-tauri/target/debug/tuic` (CLI),
  `src-tauri/target/debug/tuic-bridge` (MCP stdio to local socket bridge), `src-tauri/target/debug/tuicommander`
  (desktop app). `cargo test` re-links `target/debug/tuic-remote` as a stub that refuses to start; use the copy in
  `/usr/local/bin`.

## How you rate severity
- Critical: unauthenticated remote code execution or terminal/file access over the network listener or relay.
- High: authentication bypass on the HTTP API; a web page or deep link that runs a command or writes a file without
  user action; terminal output that leads to command execution; memory corruption in the terminal parsers.
- Medium: denial of service reachable from the network without credentials; information disclosure of secrets
  (tokens, passwords) to another local user or to the network.
- Low: denial of service that needs credentials or a local user action; crashes from malformed terminal output with
  no memory-safety impact.

## Anything to leave alone (intended design, do not report)
- The local MCP Unix socket / named pipe has no authentication: only the same OS user can reach it.
- Access to any local path the user can see (file browser, external file reads, opener scope `"**"`), including
  symlinks inside a repository that point outside it.
- The permissive Content-Security-Policy and `dangerousDisableAssetCspModification` in `tauri.conf.json`.
- Iframes use `sandbox="allow-scripts allow-same-origin"` on purpose.
- Plugins run in the same JavaScript realm as the host and are not isolated from each other; a plugin can use another
  plugin's id. This is known and documented.
- AI agents typing into terminals or full-screen TUIs without an extra approval step is a feature.
- `lazy_static` and other transitive dependency choices.
