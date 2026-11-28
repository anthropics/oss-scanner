# Threat model

This follows webpack's published threat model,
<https://github.com/webpack/security-wg/blob/main/docs/threat-model.md>.

## What this project does and where untrusted input enters

webpack-dev-server is a development HTTP server for webpack. A developer starts it on their own machine,
with their own privileges, through `webpack serve` (webpack-cli), `bin/webpack-dev-server.js`, or the
`Server` class exported by `lib/Server.js`. It compiles the project in memory through webpack-dev-middleware,
serves the bundle and any `static` directories over HTTP, HTTPS or HTTP/2, and pushes rebuild and reload
messages to open pages over a WebSocket (or Server-Sent Events). The browser runtime, the error overlay and
the hot transports now live in webpack-dev-middleware; this repository builds `client/` as thin
re-exports of them (`scripts/build-client.mjs`) and keeps the policy for who may talk to the server.

webpack trusts the developer and their machine, and everything they configure or install:
- `webpack.config.js` and the `devServer` options (`setupMiddlewares`, `headers`, `server`, `webSocketServer`, ...)
- CLI flags and environment variables
- loaders, plugins and everything in `node_modules`
- the project's own source files and assets
- network resources the developer configured, such as `proxy` targets.

A finding that needs control of any of these is not a vulnerability.

What webpack does not trust is network data reaching the dev server, and the clients that send it. That
includes requests from outside the intended developer environment: a web page open in the developer's
browser (cross-origin requests, DNS rebinding), or a machine on the same network when the server is reachable
from it. Untrusted input enters through:

- **HTTP requests.** Every request passes the `host-header-check` and `cross-origin-header-check`
  middlewares set up in `setupMiddlewares()`. They read `Host`/`:authority`, `Origin`, `Referer` and the
  `Sec-Fetch-*` headers and decide, with `allowedHosts` and `allowedOrigins`, whether the request is
  answered and which CORS and `Cross-Origin-Resource-Policy` headers it gets (`isValidHost`,
  `isHostAllowed`, `isSameOrigin`, `#isSameOriginRequest`, `#isOriginAllowed`, `#isListedOrSameOrigin`,
  `#parseOrigin`, `#checkCrossOriginRequest`, `#answerPreflight`). The defaults are `allowedHosts: "auto"`
  (loopback, IP literals, `*.localhost`, the configured `host`) and `allowedOrigins: "auto"`.
- **Built-in routes.** `/webpack-dev-server/invalidate` triggers a rebuild, `/webpack-dev-server/open-editor`
  passes its `fileName` query to `launch-editor` and so starts a process on the developer's machine, and
  `/webpack-dev-server` renders an HTML assets report. The first two are guarded only by
  `#isSameOriginRequest`.
- **The hot socket.** WebSocket upgrades and SSE connections to the hot endpoint are judged in
  `guardHotEndpoint()`: `Host` must pass `isValidHost`, and the `Origin` must be allowed or the connection
  must carry the per-run token (`#isHotTokenValid`). A page that connects receives build stats, including
  file paths and error messages with source excerpts. Messages a client sends back are also input.
- **Paths mapped to the file system.** `static` directories are served by `express.static` under each
  `publicPath`, optionally behind `static.deny` (`segmentPatternToRegExp`, `isPathDenied`, the
  `DEFAULT_STATIC_DENY` list) and with `serve-index` listings. `historyApiFallback` rewrites paths, and the
  in-memory bundle is served by webpack-dev-middleware. Nothing outside a configured directory or the
  output file system should be readable through a request.
- **Proxied WebSocket upgrades.** `proxy` targets are trusted, but the clients reaching them are not.
  HTTP requests to a proxy go through the same host and origin checks, and WebSocket upgrades for
  `ws: true` proxies are dispatched from the raw server's `upgrade` event, which re-applies the checks
  itself before forwarding.

## Components that matter most / least

- Most: `lib/Server.js`, in particular `setupMiddlewares()` and the host, origin, CORS and token checks it
  installs, the built-in routes, `guardHotEndpoint()`, the WebSocket proxy `upgrade` handler, and static
  serving with `static.deny`.
- Also in scope: `lib/hotOptions.js` (how this server's options are mapped onto webpack-dev-middleware's,
  including the overlay's open-editor endpoint), `lib/servers/BaseServer.js`, `lib/options.json` and the
  generated `client/` shims.
- Least: `types/` (generated declarations), `dist/` (Babel output of `lib/`), `lib/getPort.js`, the
  self-signed certificate and IPC socket setup (local files on the developer's trusted machine), and CLI
  argument parsing, which is webpack-cli's.
- Out of scope: `test/`, `examples/`, `scripts/`, `.github/`, `.changeset/` and the migration guides. These
  are tests, documentation and repository tooling.
- Out of scope: sibling projects published from their own repositories, including webpack,
  webpack-dev-middleware (which now owns the browser runtime, the overlay and the hot transports),
  webpack-cli, and dependencies such as `express`, `ws`, `http-proxy-middleware`, `serve-index`,
  `connect-history-api-fallback`, `launch-editor`, `selfsigned`, `chokidar` and `bonjour-service`. A bug in
  one of them is in scope only when webpack-dev-server's own code makes it reachable from the network in a way
  the dependency does not already document, for example by forwarding a request its checks should have
  refused.

## How you rate severity

These levels follow the advisories webpack has published for this package. The scenarios assume default or
documented options and no compromise of trusted elements. A documented, non-default option such as `proxy`
or a custom `publicPath` does not by itself lower the rating. An explicit opt-out such as
`allowedHosts: "all"` does make the issue not a vulnerability.

- **Critical:** a request from a foreign origin or another machine that executes code or starts an
  arbitrary process on the developer's machine. For example, reaching `/webpack-dev-server/open-editor`
  with a `fileName` that makes `launch-editor` run something other than the developer's editor.
- **High:** path traversal or arbitrary file read outside the configured static roots and the build output;
  a `static.deny` bypass that serves a denied file; a foreign origin hijacking the hot socket or a
  `ws: true` proxied WebSocket, enough to read or inject HMR control messages.
- **Medium:**
  - a bypass of `allowedHosts` or `allowedOrigins` (DNS rebinding through a crafted `Host`, an `Origin`
    parsed differently from the browser's serialization, a handshake let through without a valid origin
    or token) that lets a foreign page read the bundle, source maps or build stats;
  - cross-site request forgery against `/webpack-dev-server/invalidate` or another internal endpoint;
  - information disclosure through `/webpack-dev-server/open-editor`;
  - one unauthenticated request or handshake (for example a malformed `Host` or `Origin`) that crashes the
    server, blocks its event loop or exhausts its memory;
  - CORS or credential headers granted more widely than the options say.
- **Low:** issues that need an unusual network position or a narrow timing window, and leaks of paths or
  build metadata to a client that already passed the host and origin checks.
- Not a vulnerability:
  - anything that needs control of configuration, CLI flags, environment variables, `setupMiddlewares`,
    a proxy target, `headers`, a custom server or transport module, a loader, a plugin, `node_modules`, or
    the project's source files and assets;
  - behavior after the developer opts out with `allowedHosts: "all"` or `allowedOrigins: "all"`;
  - the server being exposed to the public internet or used in production (an operational
    misconfiguration);
  - the server being reachable from the local network because no `host` was set (documented);
  - `static.deny` being off by default, or the self-signed certificate not being trusted by browsers;
  - webpack-cli being installed after the developer answers "yes" to the prompt in
    `bin/webpack-dev-server.js`;
  - bugs in the application being served;
  - Node.js or OS bugs.

## How to exercise it

- The image has the repository at `/src` with dependencies installed, `npm run build` already run (so
  `dist/`, `client/` and `types/` exist), Chromium available for Puppeteer, and the package linked into its
  own `node_modules`, so both `import Server from "/src/lib/Server.js"` and `import "webpack-dev-server"`
  work. `node /src/bin/webpack-dev-server.js --config <dir>/webpack.config.js` starts the CLI.
- A reproducer is usually a small ES module that builds a `webpack(config)` compiler, starts
  `new Server({ port, ...options }, compiler)` and sends raw requests with `supertest`, `node:http` or
  `ws`, then calls `server.stop()`. These are the best templates:
  - `test/server/host-header-validation.test.js`
  - `test/e2e/allowed-hosts.test.js`, `test/e2e/allowed-origins.test.js`
  - `test/e2e/cross-origin-request.test.js`, `test/e2e/proxy-web-socket-origin.test.js`
  - `test/e2e/static-deny.test.js`, `test/e2e/built-in-routes.test.js`

  `test/fixtures/simple-config/webpack.config.js` and `test/fixtures/client-config/webpack.config.js`
  provide a ready compiler configuration, and `test/ports-map.js` assigns ports.
- Run one test file the way `scripts/run-tests.mjs` does:
  `node --import ./scripts/node-test-setup.mjs --experimental-test-module-mocks --test --test-force-exit
  test/server/host-header-validation.test.js`.
  - `npm run test:only` runs everything (`test/*.test.js`, `test/cli`, `test/server`, `test/e2e`) and is
    slow.
  - The `test/e2e` suites launch headless Chromium through `test/helpers/run-browser.js`.
  - Avoid plain `npm test`, which runs the linters first.
- The scan runs with no network, where the container has only a loopback interface. Most suites pass
  offline (about 1250 of 1320 tests). These fail there for that reason alone and are not evidence of a bug:
  - the `test/cli` snapshot tests, which expect "On Your Network" lines;
  - the tests for `host: "local-ip"`, `"local-ipv4"` and IPv4 hosts;
  - the tests for proxied WebSocket URLs.

## Anything to leave alone

- Dependency CVEs that do not reach a webpack-dev-server code path. Report those upstream.
- The browser runtime, overlay and hot transports: they are webpack-dev-middleware's, and `client/` only
  re-exports them. Report issues there unless this server's options are mapped into them wrongly in
  `lib/hotOptions.js`.
- Content of the build (asset names, chunk names, error text) rendered by the server: it comes from the
  project's sources, loaders and plugins, which are trusted.
- Deprecated behavior that is documented as such and warned about at run time:
  - `allowedHosts: "all"` also allowing every origin;
  - an `Access-Control-Allow-Origin: *` entry in `headers` turning off `Cross-Origin-Resource-Policy`;
  - `client.webSocketURL.hostname` being accepted as a host.
- Test fixtures under `test/fixtures/` contain deliberately permissive configuration and self-signed keys
  (`test/fixtures/https-certificate`, `test/fixtures/ssl`); they are not shipped.

## How reports should look

Name the attacker's position (a page on another origin, a rebound DNS name, another host on the network),
the request or handshake it sends, and the code path in `lib/Server.js` that should have refused it. Give a
reproducer that starts the server from `/src/lib/Server.js` with the smallest options needed, states which
options differ from the defaults, and shows the raw request and the response or socket messages that
demonstrate the issue. A proposed patch against `lib/` is welcome, ideally with a test modeled on the
`test/server/` or `test/e2e/` file closest to the bug. Plain text or Markdown.
