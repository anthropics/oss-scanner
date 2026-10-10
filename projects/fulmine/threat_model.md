# Threat model

## What this project does and where untrusted input enters
Fulmine.js is a drop-in replacement for Express 5 that runs on uWebSockets.js (µWS). An Express
application is meant to behave the same on it, only faster. It is an HTTP server framework, so every
byte of every request is untrusted: the path, the query string, headers, cookies, bodies (JSON,
urlencoded, raw, text, multipart), WebSocket messages, and anything a client can stream.

Untrusted input enters JavaScript of this project once µWS has parsed the request line and headers:

- **Routing**: `src/router.js`, `src/router-utils.js`, `src/route.js`, `src/walk.js`,
  `src/optimizer.js` (path matching, parameters, `app.param`, mounted apps and routers).
- **Request API**: `src/request.js`, `src/request-utils.js`, `src/parse-query.js` (query parsing,
  `req.ip`/`req.ips`/`req.hostname`/`req.protocol` under `trust proxy`, content negotiation).
- **Body parsers and middlewares**: `src/middlewares.js` (`express.json`, `urlencoded`, `raw`,
  `text`, `static`), `src/compression.js`.
- **Response API**: `src/response.js`, `src/response-utils.js` (`res.sendFile`, `res.download`,
  `res.redirect`, `res.cookie`, header handling).
- **Node compatibility layer**: `src/node-shim.js`, `src/lazy-readable.js`, `src/lazy-writable.js`,
  `src/socket.js`, which make µWS look like `http.IncomingMessage`/`ServerResponse` to middleware.
- **WebSockets and workers**: `src/websocket.js`, `src/cluster.js`, `src/worker.js`, `src/work.js`.

## Components that matter most / least
- Most: anything that lets a request reach a route or a file it must not reach (route matching,
  mounted paths, `express.static` / `res.sendFile` path traversal), state from one request leaking
  into another (pooled or reused request/response objects, headers or bodies of one request seen
  by the next, including on keep-alive and pipelined connections), and body or query parsing that
  crashes the process or pollutes prototypes.
- Less: `src/cli.js`, `src/testing.js`, `src/tracing.js`, `src/server-timing.js` (developer tools).
- Out of scope: `benchmark/`, `examples/`, `integrations/`, `site/`, `docs/`, `tools/`,
  `eslint-rules/` and `tests/`.
- Out of scope: **µWebSockets.js itself** (the HTTP parser, TLS, socket handling). If a bare µWS app
  (`require("uWebSockets.js").App().any("/*", (res) => res.end("ok"))`) answers the same request the
  same way, the bug belongs upstream at uNetworking/uWebSockets.js, not here.
- Out of scope: behaviour Fulmine reproduces faithfully from Express 5. Compatibility with Express is
  the product; where Express itself is wrong, the fix belongs upstream. A place where Fulmine answers
  *differently* from Express in a way an attacker can use is in scope.

## How to exercise it
- After the Docker build, dependencies are installed in `/src/node_modules`. There is no build step.
- `npm test` runs the comparison tests in `tests/tests/`: each registers the same app on Express and
  on Fulmine and compares the answers. This is the best template for a reproducer.
- `npm run test:unit` runs unit tests; `npm run test:express` runs Express's own test suite against
  Fulmine (the clone is already in `node_modules/express-suite-clone`).
- `npm run fuzz`, `npm run fuzz:wire`, `npm run fuzz:headers` and `npm run fuzz:session` are
  differential fuzzers against Express / node's HTTP parser; a divergence prints a replayable seed.

## How you rate severity
- Critical: remote code execution, or reading files outside the static root, reachable by an
  unauthenticated client against an app using default settings.
- High: a request reaching a route or middleware it must not reach (bypassing a mounted auth
  middleware), one request's headers, cookies, body or response leaking into another client's
  request, prototype pollution from request data, or a single ordinary-looking request that crashes
  the process or stops the server answering everyone else.
- Medium: `req.ip`/`req.hostname`/`req.protocol` reporting attacker-chosen values when the
  `trust proxy` settings say they should not; header injection or open redirect in the response
  API where Express would refuse; resource exhaustion needing sustained traffic.
- Low: information disclosure in error pages under non-default settings, issues that need the
  developer to opt in to documented-unsafe behaviour.

## Anything to leave alone
- `trust proxy protocol` is documented as unsafe on a public port and is off by default; using it
  there is not a vulnerability.
- Anything that needs the attacker to already run code in the process.
- The two documented exceptions in `fuzz:wire`: a pipelined request after `Connection: close`, and a
  framing value (a tab after `Content-Length`, a parameter after `chunked`) that µWS reads through
  where node refuses it. Both are decided by µWS before this project sees the request.
- Reports should include a minimal application and the request that triggers it, ideally as a
  comparison test in the style of `tests/tests/`, and a patch against `src/` where possible.
