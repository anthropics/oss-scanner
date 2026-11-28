# Threat model

This follows webpack's published threat model,
<https://github.com/webpack/security-wg/blob/main/docs/threat-model.md>.

## What this project does and where untrusted input enters

webpack-dev-middleware is a development server component. It wraps a webpack compiler in watch mode,
keeps the emitted assets in memory (`memfs`) or on disk (`writeToDisk`), and serves them over HTTP from
inside the developer's own server: Express, Connect, Koa, Hapi, Fastify, Hono or a plain `http` server
(`src/index.js`). With the `hot` option it also serves a Hot Module Replacement endpoint over Server-Sent
Events or a WebSocket (`src/hot.js`, `src/servers/`) and injects a browser client (`client-src/`, built
to `client/`) that applies updates and shows build errors in an overlay. webpack-dev-server is built on
it. It runs on a developer's machine, with that developer's privileges, and is not meant for production.

webpack trusts the developer and their machine, and everything they configure or install. That includes:
- `webpack.config.js` and the middleware options, among them `headers`, `modifyResponseData`,
  `writeToDisk` and `outputFileSystem` functions, `hot.transport` factories, `hot.cors` functions and the
  overlay filter functions serialized into the client;
- CLI flags and environment variables;
- loaders, plugins and everything in `node_modules`;
- the project's own source files and assets.

The build output, including module names and the text of build errors and warnings, comes from these, so it
is trusted too. A finding that needs control of any of them is not a vulnerability.

What webpack does not trust is network data reaching the middleware, and the clients that send it. The
attacker is a web page open in the developer's browser, or a host on the same network when the server is
reachable from it. Untrusted input enters here:

- **HTTP requests to the asset handler** (`src/middleware.js`). `getFilenameFromUrl` decodes the request
  URL, strips the `publicPath` prefix and maps what is left to a file under `output.path`. Its `..`, null
  byte and `path.relative` checks are what keep a request inside the output directory. That holds on the
  in-memory file system and, with `writeToDisk` or a disk `outputFileSystem`, on the real one.

  Request headers drive conditional and partial responses:
  - `Range` (`range-parser`, merged ranges and `multipart/byteranges` bodies);
  - `If-None-Match`, `If-Modified-Since`, `If-Match`, `If-Unmodified-Since` and `If-Range`;
  - `Cache-Control`, and the method.

  The HTML error page escapes its content (`escapeHtml` in `src/utils.js`) and sets
  `Content-Security-Policy: default-src 'none'`.
- **The hot endpoint** (`hot.path`, default `/__webpack_hmr`). `src/servers/EventSourceServer.js` and
  `src/servers/WebSocketServer.js` accept connections, and `src/utils.js` decides who may use them:
  - `hot.cors` against the `Origin` header (`resolveCors`, `matchOrigin`, `applyCors`, `isSameOrigin`
    against `Host`, `isUpgradeAllowed`);
  - `hot.token` against the `token` query parameter (`resolveToken`, `isTokenValid`).

  Payloads carry module paths and source frames from build errors, so a foreign origin reading the stream
  leaks source. Messages a client sends back over the WebSocket are also input.
- **HMR control messages in the browser client.** `client-src/process-update.js` and `client-src/index.js`
  decide from a message whether to apply an update or reload the page. Only the server the page was
  served by, over a connection the checks allowed, should be able to send them.
- **The page URL.** The client reads the page's own `location.search` for the `<pageParamPrefix>-apply`,
  `-hot` and `-live-reload` overrides (`urlOverride` in `client-src/index.js`), and builds the socket URL
  from `location` (`client-src/utils/socket-url.js`). Any site can link the developer to such a URL. The
  client's own resource query is written by the middleware at build time (`clientQuery` and
  `injectHotClient` in `src/utils.js`) and is trusted. File references in the overlay are sent to
  `openEditorEndpoint` (`client-src/utils/open-editor-url.js`), and the token must never go to another
  server.

## Components that matter most / least

- Most:
  - `getFilenameFromUrl` and the response logic in `src/middleware.js`: path traversal, range and
    conditional-request handling, the error page;
  - the CORS and token checks in `src/utils.js`, and how `src/servers/EventSourceServer.js` and
    `src/servers/WebSocketServer.js` use them;
  - message handling and URL overrides in `client-src/index.js` and `client-src/process-update.js`;
  - `client-src/utils/open-editor-url.js` and `client-src/utils/socket-url.js`.
- In scope: `src/`, `client-src/` (and the built `client/` and `dist/` it ships), `src/options.json`
  and `types/`. The framework wrappers in `src/index.js` (`koaWrapper`, `hapiWrapper`, `honoWrapper`)
  must enforce the same checks as the Express path.
- Less: the overlay's rendering of build output (`client-src/overlay.js`, `client-src/utils/ansi-html.js`),
  whose input is trusted; `client-src/indicator.js` and `client-src/theme.js` (cosmetic); logging; the
  deprecated `hot.progress` and `hot.statsOptions` paths.
- Out of scope: `test/`, `examples/`, `scripts/`, `.github/`, `.changeset/` and
  `migration-from-webpack-hot-middleware.md`. These are tests, documentation and repository tooling.
- Out of scope: other repositories and dependencies.
  - webpack itself, `webpack-dev-server`, `webpack-cli` and other webpack-org repositories;
  - this package's dependencies (`memfs`, `mime-db`, `range-parser`, `schema-utils`, `ws`).

  A bug in one of them is in scope only when this package's own code makes it reachable from the network
  in a way the dependency does not already document.

## How to exercise it

- The image has the repository at `/src` with dependencies installed and the package built (`dist/`,
  `client/`, `types/`), so `require("/src")` gives the middleware and `webpack` is in
  `/src/node_modules`.
- A reproducer is a small Node script:
  1. Build a compiler from a `webpack.config.js` and a few source files.
  2. Mount `middleware(compiler, options)` on `http.createServer` or Express (`express` and `connect` are
     installed).
  3. Listen on `127.0.0.1` and send the crafted request with `http.request` or `supertest`.

  Use raw `http.request` (or a socket) for paths the WHATWG URL parser would normalize away, such as `..`
  and `%2e%2e`.
- `test/middleware.test.js` (request handling, ranges, caching, every supported framework) is the best
  template for asset-handler reproducers, with `test/helpers/getCompiler.js` and the configs in
  `test/fixtures/`. `test/hot.test.js` and `test/instance-hot-api.test.js` cover the hot endpoint,
  CORS and token over both transports.
- `npm run test:only -- --ci` runs the Jest suites outside `test/e2e/` (about two minutes).
  - `npm run test:only -- --ci test/middleware.test.js` runs one file.
  - Two tests in `test/logging.test.js` expect a `mkdir` permission error and fail when run as root, as in
    this image.
  - Avoid plain `npm test`, which runs the linters first.
- `npm run test:e2e -- --ci` runs the browser suites in `test/e2e/` against the Chrome that puppeteer
  installed under `/opt/puppeteer`. `test/e2e/cors.test.js` and `test/e2e/overlay.test.js` are the templates
  for a browser-side reproducer. Run one file with `npm run test:e2e -- --ci test/e2e/cors.test.js`.
- `examples/hot` is a complete server with `hot: true` and shows the normal setup.

## How you rate severity

These levels follow the advisories webpack has published for this package. The scenarios assume default or
documented options and no compromise of trusted elements. A documented, non-default option does not by
itself lower the rating. Path traversal through a non-slash-terminated `publicPath` was rated High.

- **Critical:** a request from a foreign origin or another machine that executes code on the developer's
  machine.
- **High:**
  - path traversal or arbitrary file read outside `output.path` through a request to the asset handler;
  - a request causing a file to be written, overwritten or deleted on disk;
  - a foreign origin hijacking the hot endpoint, enough to inject control messages that make the client
    apply an update or run script;
  - a framework wrapper skipping a check the Express path applies, when it leads to one of these;
  - the token being sent to a server other than the page's own.
- **Medium:**
  - a foreign origin reading the hot stream (build errors, source frames, module paths) when `hot.cors` is
    narrowed or `hot.token` is on, or upgrading a WebSocket that the local-origins default should refuse;
  - script execution in the developer's page from the page's own URL parameters;
  - response splitting or header injection from a request;
  - one unauthenticated request, `Range` header or WebSocket frame that crashes the server, blocks its
    event loop or exhausts its memory.
- **Low:** issues that need an unusual network position or a narrow timing window; information in error
  responses beyond what the build already exposes.
- Not a vulnerability:
  - anything that needs control of configuration, options, CLI flags, environment variables, a loader, a
    plugin, `node_modules`, or the project's source files and assets;
  - in particular, content from the build (module names, error and warning text) rendered by the
    overlay;
  - the documented defaults (`hot.cors: true` for `'sse'`, `hot.token: false`);
  - assets being readable cross-origin through `<script>`, or DNS rebinding through `Host`. The README's
    Security section assigns both to the developer's server (`Cross-Origin-Resource-Policy`, a `Host`
    allowlist), as it does the checks inside an `openEditorEndpoint` route;
  - the local-origins set trusting other servers on `localhost`;
  - Fetch Metadata and `Origin` being absent over plain `http` to a non-`localhost` address;
  - the token being readable by anything that can already read the bundle;
  - the middleware being exposed to the internet or used in production (an operational misconfiguration);
  - bugs in the application being served, and Node.js or OS bugs.

## Anything to leave alone

- Dependency CVEs that do not reach a code path in this package. Report those upstream.
- webpack-dev-server's own checks (`allowedHosts`, its proxy, its static file serving). They live in its
  repository, even when webpack-dev-server is the usual way this middleware is run.
- `new Function` in `client-src/index.js` (`decodeOverlayOptions`) and `isExpression` in `src/utils.js`
  build overlay filters from functions in the developer's options, carried in the client's resource
  query that the middleware writes. That is configuration, not input.
- Test fixtures under `test/fixtures/` contain deliberately broken code and configuration.
- The ES5 and legacy-browser paths of the client when the issue exists only in a browser that has no
  security support.

## How reports should look

Name the attacker's position (a page on another origin, another host on the network, a link the developer
follows), the request, header, `Origin` or page URL it controls, the code path in `src/` or `client-src/`
that consumes it, and the options in force. Give a reproducer that runs in the image against `/src`: a Node
script that starts the middleware on `127.0.0.1` and sends the request, or a test modeled on
`test/middleware.test.js` or a `test/e2e/` suite for browser-side issues. Show the response or the browser
behavior that demonstrates the issue. A proposed patch against `src/` or `client-src/` is welcome, ideally
with a test in the matching file under `test/`. Plain text or Markdown.
