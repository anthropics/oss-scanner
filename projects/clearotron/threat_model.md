# Threat model: Clearotron

## What this project does and where untrusted input enters

Clearotron is a trademark clearance engine. Given a proposed name, it searches trademark registers and
the open web, has a model rate the conflicts, and writes a report that a lawyer reviews. A deployment
runs it as a network service: a web portal and a remote MCP server that people at a law firm, and the
firm's clients, sign in to. The data it holds is confidential by nature. It includes names a company
has not yet announced or filed, and the reports written about them.

Untrusted input enters at these points:

- **The remote MCP server** (`mcp-server/http-server.mjs`, and the client-facing
  `mcp-server/http-server-client.mjs`): every request, header, session id, and token. A request is
  authenticated by a JWT from a fronting auth proxy or by a scoped access key. Every tool call is then
  authorized at one chokepoint (`authorize()` in `shared/scope.mjs`).
- **The portal** (`driver/portal-service.mjs`, with `driver/portal-access.mjs` as its access boundary):
  every HTTP request a signed-in person makes.
- **Register and web content.** Records returned by register APIs (`providers/`) and pages and results
  from web search are attacker-controllable. They pass through model stages into reports that are
  rendered in the portal, delivered as files, and returned through MCP tools.
- **Model output.** Each pipeline stage's output is checked by validators, never trusted on the
  model's own say-so.
- **Names and paths a caller supplies:** run ids, artifact names, and resource URIs, which reach file
  reads under the run and pool directories.

The access model, including the principal kinds, what each may read, and how tokens are minted and
revoked, is stated once in [`docs/SECURITY.md`](https://github.com/CordilleraSarl/clearotron/blob/main/docs/SECURITY.md).
Read it rather than this summary when judging whether a behaviour is a hole.

## Components that matter most / least

Most:

- **The engine boundary.** Each pipeline stage is a headless turn of Claude Code or the Codex CLI
  (`driver/engine/`). It starts with a named list of settings rather than the whole environment, so the
  key that signs access tokens never reaches it (`driver/engine/engine-env.mjs`). Its folder access is
  scoped to its run. A stage on Claude is offered no tool that runs a command, and a stage on Codex
  runs its commands inside Codex's own sandbox. These stages read register records and web pages, so
  content that steers a stage across any of these lines is the injection case we care about most.
- **The authorization boundary.** A `user` key is read-only and pinned to exactly one run. An `account`
  principal sees only the companies its guest-list entry grants. Two organisations must stay invisible
  to each other.
- **Fail-closed construction.** The HTTP server refuses to start without an audience, an issuer, and an
  identity gate. Its access-key mode requires a loopback bind and an allowed-hosts list.
- **Path handling** for artifacts, pools, and run directories.
- **Report rendering.** This covers any register or web content that ends up executing as script or
  markup in the portal or in a delivered report.
- **Company-facing output that leaks internals**, such as setting names, internal paths, or stack traces.

Least:

- The stdio MCP server (`mcp-server/server.mjs`), which is trusted by construction and guarded by the
  operating-system user it runs as.
- The development portal (`driver/dev-portal.mjs`). Only its refusal of every non-loopback host
  matters.
- `vendor/`, which is third-party code, and the synthetic demo data.

## How to exercise it

- `npm test -w mcp-server` runs the MCP server's suite, including authentication and scope
  (`mcp-server/test/security.test.mjs`). Run the suites as the image's `node` user, not root: some
  tests make a file unreadable and expect that to hold.
- `node bin/example.mjs` is the same as `npx clearotron demo`. It replays a finished, synthetic
  clearance into `~/trademark-demo/pool`. It then starts the portal at `http://127.0.0.1:18860/portal`
  (local sign-in) and the staff MCP server at `http://127.0.0.1:18861/mcp` (access key). It needs no
  model, no register account, and no network. Both servers refuse an unauthenticated request.
- `mcp-server/mint-token.mjs` mints `ops`, `user`, and `account` tokens for testing the boundary.

## How you rate severity

- **Critical:** reading or changing another organisation's, company's, or run's data; a `user` key
  reaching beyond its one run; any request served with authentication silently absent; remote code
  execution; register or web content that makes a stage read a secret, run a command, or write outside
  its run.
- **High:** exposing a company's unfiled name, a report, or a credential to someone not granted it; path
  traversal outside the run and pool directories; script injected into the portal or a delivered report
  from register or web content; an `ops` token reaching a tool outside the verbs it names, or running a
  what-if over HTTP.
- **Medium:** internals in company-facing output; a single unauthenticated request that takes the
  service down.
- **Low:** misuse that stays within what an authenticated `ops` token's named verbs allow.

## Anything to leave alone

- A deployment's own configuration: its auth proxy, TLS, firewall, and API keys.
- The development mode in which authentication is off. It needs two explicit flags and a loopback
  listener, by design.
- The absence of a rate limit on the local stdio server.
- Vendor APIs this project calls. Those belong to the vendor.
