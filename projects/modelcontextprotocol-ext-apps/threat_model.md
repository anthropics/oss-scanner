<!--
Based on the MCP Apps specification (specification/2026-01-26/apps.mdx, "Security Implications") and the MCP security
policy, https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/SECURITY.md. The rules that matter for a
scan are copied here. Follow this file.
-->
# Threat model: MCP Apps SDK (ext-apps)

## What this project does and where untrusted input enters

A library that lets MCP servers show HTML user interfaces ("Views") in host applications. The View runs in a sandboxed iframe and talks to the host with JSON-RPC over `postMessage`. Views, and the resource metadata a server sends (`_meta.ui`: CSP domains, permissions, visibility), may be hostile. The host application's own code is trusted, and so is a View's own code from the View's point of view; from a View, other frames and windows are untrusted.

## Components that matter most / least

- Most: `src/app-bridge.ts` (the host side), `src/app.ts` (the View side), `src/message-transport.ts`, `src/events.ts`, `src/legacy-handlers.ts`, `src/webmcp*.ts`, `src/types.ts`, `src/generated/`, `src/server/`, `src/react/`.
- Next: `examples/basic-host` (`src/sandbox.ts`, `serve.ts`, `src/implementation.ts`). It is the reference for how a host isolates Views and is copied by others, so a sandbox or CSP bypass there is in scope even though it is an example.
- Low: the other `examples/*` servers are demos. Report only code execution, or file access outside what the example documents (for example `pdf-server`'s allowed paths).
- Out of scope: `docs/`, `scripts/`, `tests/`, `plugins/`, `media/`.

## In scope

- A View, or a server's metadata, that escapes the sandbox, reads or changes the host page, or reaches host capabilities that the host did not grant.
- CSP or permission construction that a hostile domain list or permission value can widen (directive injection, dropped restrictions, wrong defaults).
- `postMessage` source or origin confusion in the library: a frame other than the expected peer having its messages accepted as that peer's, or private messages reaching a frame that is not the peer because of the library.
- Bypass of a check that this repository's code implements or documents that it performs on a View's requests (for example request handlers, capabilities and sandbox messages). Tool visibility is a check the specification puts on the host: a host application that leaves it out is out of scope, and a bypass of code here that performs it is in scope.
- Validation or parsing of peer messages that lets a peer pollute prototypes, confuse requests and responses, or crash the other side persistently.

## Not a vulnerability: please do not report

- Documented design: `postMessage` with target `"*"` between the known windows (receivers check the message source), and the sandbox proxy relaying every message that is not `ui/notifications/sandbox-*`.
- Hosts that skip what the specification requires of them, misleading or phishing content inside a View, and a View that consumes CPU or memory.
- A View contacting domains that its server declared and the host allowed.
- `basic-host` accepting only localhost embedders, using plain HTTP on localhost, or lacking user accounts: it is a development host.
- A server that returns a View that does what the server wants inside its sandbox; prompt injection.
- Flaws in browsers, the MCP SDKs or other dependencies; correctness bugs that cross no boundary.

## How we rate severity

- Critical: sandbox escape into the host's origin with no user action beyond showing the View.
- High: the same with ordinary user interaction, or a View using host capabilities that a check here should have refused.
- Medium: CSP or permission widening, a bypass of a visibility check here, or message spoofing between frames that needs a particular but documented layout.
- Low: limited information leaks and persistent denial of service of the host page by a View.

## How to exercise it

- `npm test` runs the unit tests with bun's test runner. The library is built in `dist/` and the examples are built under `examples/*/dist`.
- If the download worked, a headless Chromium is in `/opt/playwright`; `examples/basic-host` (ports 8080 and 8081) plus an example server on port 3001 runs entirely on localhost, and `tests/e2e` has Playwright drivers for it. `examples/qr-server` and `examples/say-server` are Python servers and cannot run in this image.
