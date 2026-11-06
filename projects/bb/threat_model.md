# Threat model

## What bb is

bb is an agentic IDE written in TypeScript (pnpm + Turbo monorepo). A user runs
a bb **server** (`apps/server`, Hono + SQLite) and one or more **host daemons**
(`apps/host-daemon`) that run coding agents (Claude Code, Codex, ACP providers)
in git worktrees on the user's machines. The web/desktop **app** (`apps/app`,
`apps/desktop` Electron), the **CLI** (`apps/cli`) and plugins drive the server
over HTTP and WebSocket. **bb connect** (`apps/connect`, Cloudflare Workers)
tunnels a server to a `getbb.app` URL gated by the owner's account session.

## Trust boundaries and where untrusted input enters

The server binds to loopback by default, and its HTTP API is unauthenticated
by design: anyone who can reach it can run commands and read files on the
host. A local process, or a peer the user deliberately exposed the server to
(`--server-bind-host 0.0.0.0`, Tailscale), is trusted. Findings that only
restate this are out of scope.

Treat these as adversarial:

- **Web pages in the user's browser**: cross-origin requests, DNS rebinding,
  WebSocket hijacking or CSRF against the loopback server, the host daemon's
  local HTTP API, or the desktop app's local helpers.
- **bb connect**: requests to `getbb.app` / the connect Worker from anyone who
  is not the paired account owner; session, pairing-code and tunnel handling;
  one account reaching another's server.
- **Remote host enrollment**: the server–daemon WebSocket and host RPC
  (`packages/host-daemon-contract`); a machine or network peer impersonating a
  daemon or server.
- **Repository and agent content**: files in a cloned repository, git refs,
  branch names, worktree paths, attachments, and agent/tool output rendered in
  the app (XSS, path traversal out of the workspace, argument or shell
  injection into git and other spawned commands).
- **Plugins from the marketplace**: escaping the documented plugin
  permissions, or a plugin's UI reaching core state it was not granted.
- **Electron**: renderer-to-main escalation, unsafe `shell.openExternal`,
  navigation to untrusted origins.

## Components that matter most / least

Most: `apps/server`, `apps/host-daemon`, `apps/connect`,
`packages/connect-client`, `packages/tunnel-*`, `packages/host-workspace`,
`packages/host-daemon-contract`, `packages/server-contract`,
`packages/secret-storage`, `apps/desktop`, `packages/plugin-*`.

Less: `apps/web` (marketing site), `apps/demo-server`, `apps/mobile`,
`examples/`, `qa/`, `scripts/`, tests, and `patches/` (third-party).

## How to exercise it

The image has dependencies installed and the workspace built.
`pnpm exec turbo run test --filter=<package>` runs a package's Vitest suite
offline (tests use real SQLite databases). `node packages/bb-app/dist/bb-app.js`
starts a server; `pnpm exec turbo run smoke:boot --filter=bb-app` boots it.

## How we rate severity

- **Critical**: unauthenticated remote code execution or file read on a user's
  machine from the internet or a web page, or one bb connect account reaching
  another's server.
- **High**: code execution or secret disclosure that needs one ordinary user
  action (opening a repository, viewing a thread, installing a marketplace
  plugin within its stated permissions); escaping a workspace to write
  arbitrary files.
- **Medium**: XSS in the app without a demonstrated path to code execution;
  information leaks that need unusual configuration.
- **Low**: denial of service, crashes, and hardening issues.

## Reports and patches

Include a minimal reproduction against a locally started server where you
can. Patches should be minimal and follow `AGENTS.md`. Deduplicate by root
cause, not by every route that reaches it.

## Leave alone

- That the loopback API is unauthenticated, or that a user who binds it to
  `0.0.0.0` exposes it.
- That agents the user started can run commands and edit files in their
  workspace; that is the product.
- Vulnerabilities in dependencies unless bb uses them unsafely.
