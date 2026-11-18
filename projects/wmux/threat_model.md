# Threat model

wmux is a desktop terminal multiplexer for AI coding agents (Electron app plus
a background Node daemon). It owns panes and PTYs, renders terminal output,
drives browsers for agents over CDP, exposes an MCP server to agents, and can
serve panes to a phone and to the user's other PCs. The project's own security
model is `docs/SECURITY.md`; the cross-PC agent link is `docs/a2a-remote.md`.

## What this project does and where untrusted input enters

Trust line: the OS user running wmux and the user's own explicit grants in
the wmux UI are trusted. Everything below is untrusted.

- **Terminal output and escape sequences.** Any program in a pane can print
  arbitrary bytes. They reach the xterm-based renderer
  (`src/renderer/terminal/`, `src/renderer/hooks/useTerminal.ts`, its OSC and
  keyboard-protocol handlers), the daemon's output parsing and shell
  integration markers (`src/daemon/OutputInterpreter.ts`,
  `src/daemon/shell-integration.ts`, `src/daemon/sessionPipeMarkers.ts`), the
  snapshot backends, and the phone viewer (`src/renderer/web/viewerParser.ts`).
- **Web pages.** Pages loaded in browser panes and in agent-driven Chrome
  (`src/main/browser-session/`, `src/mcp/playwright/`) are hostile. Page
  content reaches agents through snapshots and extracted text, and pages may
  try to reach the app's IPC, privileged schemes or navigation
  (`src/main/security/navigationPolicy.ts`, `src/main/privilegedSchemes.ts`).
- **Cloned repositories.** File names, file contents, git metadata and
  per-project settings of repositories opened in panes or worktrees are
  attacker-controlled (`src/main/git/`, `src/main/project/`,
  `src/daemon/worktask/`, the phone git routes in `src/daemon/web/phoneGit*`).
- **Network peers.**
  - Browser/phone terminal server (`src/daemon/web/WebTerminalServer.ts`,
    `DeviceStore.ts`): pairing, device credentials, and the separately granted
    input, upload and git-write capabilities (`docs/SECURITY.md` §1.5).
  - LanLink (`src/daemon/lanlink/`): read-only messages from agents on other
    machines, with its own pairing.
  - Cross-PC A2A (`src/daemon/a2aRemote/`, `src/shared/a2aRemote.ts`): a TLS
    listener, a one-time invite with a pinned certificate fingerprint, peer
    credentials, per-peer exposure of panes, human-accepted pane-to-pane links,
    and message delivery into a linked pane.
- **Plugin bundles.** Plugins loaded through `src/main/plugins/` and their
  iframe host talk to the substrate over `pluginProtocol.ts` and must stay
  inside their declared permissions.
- **MCP requests.** Tool calls from agents into the MCP server (`src/mcp/`)
  and on to main and the daemon. Tool arguments never choose the workspace or
  pane a browser call acts on (`docs/SECURITY.md` §1.3.1); protected Chrome
  panes confine browser tools to an allowed host list and gate scripts,
  downloads and sign-in data behind operator consent (§1.3.2). Text that one
  agent sends another (A2A tasks, channels) is also untrusted data.

## Components that matter most / least

- **Most:** the daemon's RPC authentication (named pipe / Unix socket token,
  `src/daemon/DaemonPipeServer.ts`); the web/phone server and its credential
  and grant checks; the cross-PC A2A listener, pairing, pinning, exposure and
  link checks; LanLink pairing; MCP caller identity and workspace/pane claims;
  protected-pane enforcement and consent prompts; terminal escape-sequence
  handling (anything that turns printed bytes into input, clipboard writes,
  file access or IPC); Electron navigation and IPC exposure to web content;
  plugin permission enforcement.
- **Less:** renderer layout and styling, onboarding and settings UI that only
  the local user drives, telemetry and diagnostics formatting.
- **Out of scope:** build, packaging, release and benchmark scripts
  (`scripts/`, `bench/`, `forge.config.ts`, `.github/`), documentation
  (`docs/`, `*.md`), the test harnesses (`rig/`, `e2e/`), and third-party code
  under `node_modules/` and `patches/` except where wmux's own use of it
  creates the problem.

## How to exercise it

- `npm test` runs the unit tests (vitest; parallel lane plus the
  `*.runtime.test.ts` lane, which spawns real PTYs). Tests live next to the
  code in `__tests__/` folders; for example `src/daemon/web/__tests__/` and
  `src/daemon/a2aRemote/__tests__/` (which includes an in-process server rig,
  `a2aServerRig.ts`).
- The image builds the daemon to `dist/daemon-bundle/index.js` and the MCP
  server to `dist/mcp-bundle/index.js`. The Electron app itself is not
  launched in the image.

## How you rate severity

- **Critical:** code execution, or theft of a credential (daemon token, web or
  device credential, A2A peer credential, browser sign-in data), triggered by
  untrusted input: terminal output, a web page, a cloned repository, a network
  peer, a plugin bundle or an MCP request.
- **High or above:** bypassing authentication, the A2A certificate pin, the
  per-pane exposure or human link acceptance, a device grant (input, upload,
  git write), MCP workspace/pane identity, protected-pane consent, or plugin
  permissions. Unauthorized read of another pane's scrollback is high.
- **Listeners that are off by default** (web/phone server on a network bind,
  LanLink, cross-PC A2A) are rated as if the user had turned them on.
- **Medium:** denial of service, including crashes or hangs caused by
  untrusted input.
- **Out of scope:** an attacker who already runs code as the same OS user
  (`docs/SECURITY.md` §3): reading `~/.wmux/` or the token file directly,
  reaching the loopback CDP port, inspecting process memory, compromised
  plugins acting outside documented surfaces. What an agent decides to do with
  a message it received is governed by that agent's own permissions, not by
  wmux.

## Anything to leave alone

- Platform-specific behaviour the OS is documented to own (`docs/SECURITY.md`
  §2): disk encryption, swap and crash dumps, OS user isolation.
- Packaging fuse choices recorded as intentional in `docs/SECURITY.md` §1.4.
- Reports should include a reproducer (a unit test in the matching
  `__tests__/` folder is ideal) and a minimal patch in the surrounding code's
  style.
