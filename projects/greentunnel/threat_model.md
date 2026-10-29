# Threat model

## What this project does and where untrusted input enters
GreenTunnel is a local HTTP/HTTPS forward proxy that helps users in censored networks reach blocked sites. It
splits the TLS ClientHello so the SNI never appears whole in one packet, and it resolves hostnames over encrypted
DNS (DoH or DoT) so the ISP never sees the name in a plain DNS query. It ships as a CLI (`gt`, published to npm as
`green-tunnel`), a Docker image, and an Electron desktop app. Many users run it in places where being seen to
reach a blocked site has consequences, so the confidentiality of *which host is being visited* is a security
goal here, along with the usual memory and process safety.

Untrusted input enters at:
- **Proxy clients**: raw bytes on the listening socket: the request head (`CONNECT host:port`, or an
  absolute-form `GET http://…`), then whatever the client sends after it: a TLS ClientHello, or more HTTP
  requests on a keep-alive connection. Parsed in `packages/cli/src/core/proxy/connection.ts`, `http/head.ts`,
  `http/rewriter.ts` and `tls/fragment.ts`.
- **DNS answers**: DoH (HTTPS), DoT (TLS) and plain UDP/TCP responses, decoded in `core/dns/*.ts` (with
  `dns-packet`) and cached in `core/dns/resolver.ts`. Treat every answer as attacker-controlled: on a censored
  network, the path to the resolver is hostile.
- **Upstream servers**: response bytes relayed back to the client (`proxy/pipe.ts`, `proxy/plain-tunnel.ts`).
- **Desktop renderer → main process**: IPC messages from `apps/desktop/src/preload` to `apps/desktop/src/main/ipc.ts`.
  The renderer is sandboxed with context isolation; the main process must not trust anything it sends.
- **Files on disk the app reads back**: `settings.json` (`apps/desktop/src/main/settings.ts`, `json-store.ts`) and
  the system-proxy recovery snapshot (`core/system-proxy/recovery.ts`), whose values are later passed as
  arguments to `networksetup` (macOS), `gsettings` (Linux) or `reg.exe` (Windows) via `execFile`.

The proxy binds to `127.0.0.1` by default and has no authentication. The Docker image binds `0.0.0.0` because
the operator publishes the port themselves.

## Components that matter most / least
- Most: the engine in `packages/cli/src/core`: the request-head parser, the keep-alive HTTP rewriter (framing,
  `Content-Length`/chunked handling), ClientHello detection and fragmentation, DNS decoding, caching and
  fallback, and the system-proxy drivers that run OS commands.
- Next: the desktop main process (`apps/desktop/src/main`): IPC validation, `openExternal`'s allowlist, the log
  save dialog, settings persistence.
- Least: the CLI's banner and output (`packages/cli/src/ui.ts`), the renderer's styling, and build/release scripts.

## How to exercise it
- `npm run build` has already run: the CLI is `node packages/cli/dist/main.js` (source maps alongside) and the
  library entry point is `packages/cli/dist/index.js`.
- Start it offline without touching the OS proxy:
  `node packages/cli/dist/main.js --no-system-proxy --port 8000 --log-level trace`.
  There is no Internet in the scanner, so stand up local stand-ins with Node: a TCP or TLS server as the
  "upstream", and a fake resolver used via `--dns plain --dns-server 127.0.0.1` (or `--dns dot --dot-host
  127.0.0.1 --dot-port <n>`, or `--doh-url https://127.0.0.1:<n>/dns-query`) to feed crafted DNS answers.
- Unit tests: `npm test` (vitest; `*.test.ts` next to the code they test). Typecheck and lint: `npm run check`.
- The desktop app is built (`apps/desktop/out`) but the Electron binary is not downloaded; review its main and
  preload code statically.
- `CLAUDE.md` at the repository root documents the architecture, past bugs and the reasons behind design choices.

## How you rate severity
- **Critical**: code execution in the proxy process or the desktop main process from any input listed above;
  argument or command injection into `networksetup`/`gsettings`/`reg.exe` from data an attacker can influence.
- **High**: a default-configuration code path that silently defeats the tool's purpose, by sending the SNI
  unfragmented when fragmentation is on, or by resolving through plain DNS when DoH or DoT is selected without
  telling the user; acceptance of a forged DNS answer from a source other than the configured resolver;
  HTTP request smuggling or desync in the rewriter that sends a client's request to a host it did not ask for;
  a renderer → main escalation (bypassing the `openExternal` allowlist, writing arbitrary files, changing
  settings the UI does not allow).
- **Medium**: a single connection or a single DNS answer that crashes or hangs the whole proxy (an uncaught
  exception, an unbounded buffer, a missing timeout), or that leaves the OS proxy pointed at a dead port.
- **Low**: resource exhaustion that needs many connections from the local machine; sensitive data written to logs.

## Anything to leave alone
- It is an unauthenticated forward proxy by design. Reaching internal or loopback addresses through it, or
  using it as an open proxy when the operator binds it to a non-loopback address, is expected behaviour, not
  SSRF.
- Whether a particular DPI system can still detect or reassemble the fragmented ClientHello is a question of
  censorship-evasion effectiveness, not a vulnerability.
- Attacks that need the same OS user's access already (editing `settings.json`, attaching a debugger) are out of
  scope, unless crafted file contents cause the effects rated critical above.
- Bugs inside dependencies (`dns-packet`, `lru-cache`, Electron) only if GreenTunnel's own use makes them reachable.
- The v2 code that remains only in git history (`v2.*` tags) is unmaintained and out of scope.
