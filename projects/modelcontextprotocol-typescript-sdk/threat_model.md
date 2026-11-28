<!--
The trust model below is condensed from the MCP security policy, which applies to every official SDK:
https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/SECURITY.md
The rules that matter for a scan are copied here. Follow this file.
-->
# Threat model: MCP TypeScript SDK

## What this project does and where untrusted input enters

Client and server libraries for the Model Context Protocol (JSON-RPC 2.0 over stdio, Streamable HTTP and SSE), with OAuth helpers. `main` is v2, the stable line. Untrusted input enters through HTTP requests to a server (body, headers, session ids, `Last-Event-ID`), through HTTP responses and event streams that a client reads, and through OAuth metadata, redirects and token responses.

## Components that matter most / least

- Most: `packages/server/src/server` (Streamable HTTP, `createMcpHandler`, request bodies and state, `middleware/`), `packages/client/src/client` (Streamable HTTP, SSE, `auth*.ts`, `crossAppAccess.ts`, `dpop.ts`, `responseCache.ts`), `packages/core/src` (the wire and OAuth schemas: `schemas.ts`, `auth.ts`), `packages/core-internal/src` (protocol, auth utilities, header and media-type parsing, URI templates, validators), `packages/server/src/ext` (the skills extension reads files), `packages/middleware/*`.
- In scope, lower priority: `packages/server-legacy` (frozen v1 code for migration: security fixes only).
- Least: `packages/codemod` (a developer tool that runs on the developer's own code).
- Out of scope: `examples/`, `docs/`, `scripts/`, `test/`, `skills/`, `common/`. A flaw in an example counts only if it shows a flaw in the packages.

## Trust model

- Clients trust the servers that a user or administrator configured them to use. A malicious server that only does what a server may do (return hostile tool descriptions, results or prompts) is not a vulnerability in the SDK.
- A local (stdio) server is trusted like any other installed program. The client starts it with the configured command, with the client's privileges. The stdio channel is not a sandbox.
- A server trusts the environment it runs in, and the application code that uses the SDK is trusted.
- Remote peers over HTTP are NOT trusted before authentication, and an authenticated peer is trusted only for its own identity, session and scopes. Anything on a network path, any web page in a user's browser, and any other client of the same server are untrusted.

## In scope

A flaw in this repository's code that a remote peer, a web page or another tenant can reach through the documented API, where the application uses the SDK as documented and has no documented way to prevent it. In particular:

- Authentication or authorization bypass: bearer token checks, scopes, audience/resource and issuer checks, OAuth metadata and discovery, client registration, redirect handling, PKCE and state, client authentication.
- Token or credential theft or leakage: sending a token to the wrong server or origin, mixing up authorization servers, credentials in logs or error messages that reach a peer.
- Session hijacking, and cross-session or cross-client leaks: one client receiving another's responses, notifications, event-store replay, cached results or request state.
- Host and Origin validation bypass where that protection is enabled or on by default (DNS rebinding).
- Injection into HTTP headers, server-sent events or JSON-RPC framing, and messages that the two ends parse differently with a security effect.
- Server-side request forgery in the client's OAuth discovery that goes beyond fetching the documented metadata URLs.
- Remote denial of service before authentication, or by one client against others: a crash of the process, unbounded memory or CPU out of proportion to the request, regular expressions with super-linear time on peer input, limits that can be bypassed.
- Prototype pollution, unsafe deserialization, path traversal or code execution from peer-controlled data.

## Not a vulnerability: please do not report

- Command execution through the stdio transport's configured command, arguments or environment. Starting that process is its purpose.
- One stdio peer crashing, hanging or exhausting the other. If the same code is reachable over a remote transport, report it for that transport.
- A tool, resource or prompt that does what the application's author wrote, an LLM that calls an unexpected tool, prompt injection, and tool descriptions that mislead a model.
- A problem that needs the application to do something the documentation says not to, for example to pass unvalidated peer data to a sink the application chose, or to turn a protection off.
- Volumetric denial of service: enough traffic to overload any server.
- A protection that the documentation describes as opt-in being off when the application did not enable it, unless the documented default says otherwise.
- Correctness or spec-conformance bugs that cross no security boundary.
- Vulnerabilities in dependencies that cannot be reached through this repository's code.
- Issues only in the `v1.x` branch, which is not what is checked out here.
## How we rate severity

- Critical: remote code execution, or a full authentication bypass, reachable by an unauthenticated remote peer in a default or documented configuration.
- High: theft of tokens or sessions, cross-tenant access, authorization bypass with real impact, bypass of Host or Origin validation that lets a web page drive a local server.
- Medium: an unauthenticated remote peer can crash the process or exhaust it with a small number of requests; a leak of limited information between clients; a high-impact issue that needs an uncommon but documented configuration.
- Low: hardening gaps with no direct impact. Please report these only with a concrete attack, and prefer one report per root cause.

Many MCP SDKs share the same design. If the cause is the MCP specification rather than this code, please say so.

## How to exercise it

- `pnpm -r --filter '!@modelcontextprotocol/test-e2e' test` runs the unit and integration tests (vitest); `pnpm --filter @modelcontextprotocol/test-e2e test` runs the end-to-end suite. Both work without a network; `test/integration/test/server/cloudflareWorkers.test.ts` runs `npm install` and depends on the npm cache in this image, so a failure there is not a regression.
- Every package is built, so `packages/*/dist` can be imported. `examples/` has small servers and clients to start from; most are run with `tsx`.
