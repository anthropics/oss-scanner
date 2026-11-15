# Threat model

## What this project does and where untrusted input enters

RSSHub is an RSS feed generator. It is an HTTP server (Hono on Node.js, port 1200) with about 2,000 route
namespaces under `lib/routes/<namespace>/`. Each route fetches one or more third-party websites or APIs, scrapes or
parses what they return, and renders the result as RSS 2.0, Atom, JSON Feed or RSS3 (`lib/views/`). Operators run it
from the Docker image, the npm package or a Cloudflare Worker build, and many instances are public. Feed readers
poll it on their users' behalf.

Untrusted input:

- **Requests from anonymous clients.** Every route is public unless the operator sets `ACCESS_KEY`. Clients choose
  the route and its path parameters, and add query parameters that the shared middleware applies to every route
  (`lib/middleware/parameter.ts`): `filter*`/`filterout*` regular expressions, `filter_time`, `limit`, `sorted`,
  `mode=fulltext`, `opencc`, `brief`, `scihub`, `tgiv`, `format` and others. They also reach the non-feed endpoints:
  `/`, `/healthz`, `/metrics`, `/robots.txt`, `/api/*` and the static assets.
- **Everything fetched from upstream sites.** HTML, JSON, XML, JavaScript, cookies, headers and redirects all come
  from third parties. Many upstreams publish user-generated content (posts, comments, profiles), so assume an
  attacker can control what a route parses, including the item links that `mode=fulltext` fetches.
- **The cache.** Route output is cached in memory or Redis (`lib/middleware/cache.ts`, `lib/utils/cache/`) and
  served to later clients, so whatever one request stores, another request reads.

Trusted: the operator's environment and configuration (`lib/config.ts`), including the cookies and tokens for
upstream sites stored in environment variables, `USER_ROUTES_PATH`, `REMOTE_CONFIG`, proxy settings and the Redis
server.

## What must hold

- Neither requests nor upstream content may make the server execute code, read local files, or send requests to
  internal or private addresses or to hosts the route is not meant to fetch. User-supplied hosts and URLs are
  refused unless the operator sets `ALLOW_USER_SUPPLY_UNSAFE_DOMAIN` (see the routes that read it).
- Upstream content must not achieve code execution on the RSSHub host, whether it reaches a parser, a template, a
  regular expression, the in-process JavaScript sandbox some routes use, or a page opened in Chromium.
- The operator's upstream credentials and other secrets must never appear in responses, error pages, logs reachable
  by clients, or requests sent to hosts other than the service they belong to.
- `ACCESS_KEY` must protect every route except the documented exceptions in `lib/middleware/access-control.ts`.
- One client must not be able to change what the cache serves to other clients for a different request.
- Generated feeds must stay well-formed: text from upstream must not break out of the XML or JSON structure to add,
  replace or reorder items, links or enclosures.
- Nothing served from the instance's own origin as HTML (index, error pages, debug output, API responses) may run
  attacker-controlled script.

## Components that matter most / least

- Most: the shared code every request passes through. That is `lib/app-bootstrap.tsx` (middleware order),
  `lib/middleware/`, `lib/registry.ts`, `lib/api/`, `lib/views/`, `lib/errors/`, the HTTP client and request
  rewriter (`lib/utils/ofetch.ts`, `lib/utils/got.ts`, `lib/utils/request-rewriter/`), the cache, the Chromium
  helpers (`lib/utils/playwright*.ts`) and `lib/config.ts`.
- Next: routes that accept a user-supplied host, URL or arbitrary path segment (search for
  `ALLOW_USER_SUPPLY_UNSAFE_DOMAIN`, `isValidHost` and `:url`/`:domain` parameters), routes that send operator
  credentials, and routes that run upstream JavaScript.
- In scope but lower priority: individual scraping routes. A bug class repeated across many routes (for example, a
  path parameter concatenated into an upstream URL without encoding) belongs in one report that lists the affected
  routes, not one report per route.
- In scope: the Cloudflare Worker and container builds (`lib/worker.ts`, `lib/app.worker.tsx`, `lib/container.ts`,
  the `*.worker.ts` siblings), which reuse the same middleware.
- Out of scope: `scripts/`, `eslint-plugins/`, `.github/`, `assets/`, the test files (`*.test.ts`) and third-party
  dependencies (unless RSSHub uses them unsafely).

## How to exercise it

- The image has the checkout at `/src`, dependencies installed, the route registry built into `assets/build/` and
  the server bundle in `dist/`. Chromium for Patchright is under `/opt/ms-playwright`, and `redis-server` is
  installed.
- Start the server with `pnpm start` (production mode, port 1200) or `pnpm dev` (source with tsx). Upstream sites
  are unreachable offline, so routes that fetch them return 503. The `/test/*` routes (`lib/routes/test/`) need no
  network and are the easiest way to drive the middleware: `curl 'localhost:1200/test/1?format=json&limit=2'`.
- For anything that depends on upstream content, write a Vitest test that serves the upstream response with msw,
  following `lib/setup.test.ts`, or run a local HTTP server and point a test at it.
- Tests: `pnpm vitest run` for everything, `pnpm vitest run lib/middleware/parameter.test.ts` for one file. For the
  Redis cache, run `redis-server --daemonize yes` and set `CACHE_TYPE=redis REDIS_URL=redis://localhost:6379/`. A few
  tests visit real websites (httpbingo.org, example.org) and fail offline. That is expected.

## How you rate severity

- **Critical:** code execution on the RSSHub host, or reading local files, from a request or from upstream content
  in the default configuration; disclosure of the operator's upstream credentials or other environment secrets to an
  anonymous client.
- **High:** SSRF in the default configuration that lets an attacker choose the target (internal addresses, cloud
  metadata, arbitrary hosts) and read the response, whether the target comes from the request or from upstream
  content; bypassing `ACCESS_KEY`; operator credentials sent to a host other
  than their service (for example by following a redirect); cache poisoning that serves attacker-chosen content for
  someone else's request; script execution on the instance's own origin.
- **Medium:** blind SSRF, or SSRF limited to fixed hosts or ports; upstream text breaking the structure of a
  generated feed; CPU or memory exhaustion from a single small request with the default `re2` filter engine;
  disclosure of internal details such as file paths or stack traces in production mode.
- **Low:** anything that needs a non-default, documented-as-trusting option such as
  `ALLOW_USER_SUPPLY_UNSAFE_DOMAIN=true`, `ALLOW_USER_HOTLINK_TEMPLATE=true` or `FILTER_REGEX_ENGINE=regexp`;
  amplification where one request causes many upstream requests; information leaks that only reveal which public
  routes were requested.

## Anything to leave alone

- Routes that break, return wrong or partial data, or stop working after an upstream site changes. Those are
  functional bugs for the issue tracker.
- That RSSHub fetches third-party sites, follows their redirects, or rate-limits imperfectly. Fetching upstreams is
  its purpose. Denial of service that needs a large volume of requests is out of scope.
- HTML inside item descriptions passed through from upstream. Feed readers are expected to sanitize it; it is only a
  finding when RSSHub serves it as active HTML on its own origin or uses it to break the feed's structure.
- Behaviour that requires a malicious operator, a compromised Redis, attacker-controlled `USER_ROUTES_PATH` or
  `REMOTE_CONFIG`, or write access to the environment.
- Outdated dependencies without a reachable exploit path in RSSHub.

## How reports should look

Give the request (path and query) or the upstream response that triggers the issue, the code path it takes, and the
configuration it needs, stating whether that is the default. Prefer a reproducer that runs offline: a `/test/*`
request, or a Vitest test with msw handlers. Keep patches minimal, in TypeScript, and add a Vitest regression test
next to the affected code where feasible.
