# Threat model: Fiber

## Start here

Fiber is mature, and it has just been through a concentrated hardening cycle: in the three months before this file was written (July to October 2026), 360 of the 885 non-merge commits to `main` mention a bug or a fix, and many of them close a gap between how the router, a middleware and some downstream parser read the same request. A simple form of most classic web-framework bugs was run against this commit and held (see "Already tried"). Spend your time where bugs are still likely, in this order:

1. **Variants of recent fixes.** The full history is in `/src/.git` (7,473 commits, 149 tags). For each class in "Bug classes seen here", state the invariant the fix restored, then look for a sibling that does not enforce it. This has the best yield per hour.
2. **Differentials.** Run the lab (see "How to exercise it"), then extend it with a consumer, a configuration or a downstream parser it does not cover. A request must mean the same thing to the router, to every middleware, and to whatever receives what Fiber emits.
3. **Code rewritten for speed or parsed by hand.** The flat route index and its filters in `router_filter.go`, the SWAR path and header scanners, `internal/{wiretarget,urlnorm,fspath,origin,schemehost,headerlist,byterange,etag,mediatype,idnafold,quotedstring,fieldname,headerlookup}`, `extractors/`, the session store, and the redirect-rule ranking in `middleware/redirect`. Read them line by line, with the tests that pin their behavior beside them.
4. **Request ownership under concurrency**, with `-race`.
5. **State and key scoping**: anything stored under a key a client can influence.

If you can run workers in parallel, give each one area and have it read its files completely: (a) `path.go`, `router*.go`, `constraint.go`, `domain.go`, `mount.go`, `group.go`, `middleware/static`, `internal/{wiretarget,urlnorm,fspath}`; (b) `middleware/proxy`, `middleware/adaptor`, `client/`, `redirect.go`, `middleware/{redirect,rewrite}`; (c) `req.go`, `res.go`, `ctx.go`, `helpers.go`, `binder/`, `bind.go`; (d) `middleware/{session,csrf,cors,hostauthorization,basicauth,keyauth,encryptcookie,limiter,idempotency}`, `extractors/`, `internal/{origin,schemehost,cookie}`; (e) `middleware/{cache,compress,etag,timeout,sse,earlydata,logger}` and the lifetime of pooled objects.

Working rules. Give a hypothesis about fifteen minutes; without a lead, move on. Once a root cause has a reproducer and a patch, stop and write it up rather than listing variants. Read the tests for what they pin, not in full (`ctx_test.go` alone is 400 KB): a test that asserts a behavior marks it as deliberate. Skip `*_gen.go`, `*_msgp.go`, `.github/`, and the `docs/` pages of components you are not on.

## What this project does and where untrusted input enters

Fiber (`github.com/gofiber/fiber/v3`, the `main` branch) is an Express-style web framework for Go, built on fasthttp. It is a library: an application imports it, registers routes and middleware, and calls `app.Listen`. You are auditing the framework, not an application. The module has one `go.mod`, about 49,000 lines of non-test Go outside generated files (the tests are 130,000), no cgo, and no build tags other than two platform variants. fasthttp parses HTTP/1.x inside the process; HTTP/2 and HTTP/3 are expected to be terminated by a reverse proxy (`docs/guide/reverse-proxy.md`). v1 and v2 are other lines and are not scanned.

A network client of an application built on Fiber is the attacker, usually before the application has authenticated anything. Treat all of the following as attacker-controlled:

- **The request target**: the raw request line, percent-escapes, `.` and `..` segments, repeated or escaped slashes (`%2F`), backslashes, a stray `%`, `;` path parameters, the query string, and the unusual forms (`OPTIONS *`, absolute-form, authority-form, no leading slash).
- **Request headers**: `Host`, `X-Forwarded-*`, `Forwarded`, `X-Real-IP` and whichever header `Config.ProxyHeader` names, `Authorization`, `Cookie`, `Origin`, `Referer`, `Sec-Fetch-*`, `Content-Encoding`, `Accept-*`, `Range`, `If-*`, `Cache-Control`, `X-Idempotency-Key`, `X-Request-ID`, `Connection`, `Upgrade`. Repeated header lines, names in unusual case (under `DisableHeaderNormalizing`) and list syntax inside values are inputs too.
- **Request bodies**: raw, url-encoded and multipart bodies, and the decoders in `binder/` and `bind.go`: JSON, XML, CBOR and MessagePack (the last two through an application-supplied codec), plus query, header, cookie and URI binding through `github.com/gofiber/schema`. `Ctx.Body()` inflates `gzip`, `br`, `deflate` and `zstd` bodies.
- **Cookies that Fiber reads and acts on itself**: `fiber_flash` (decoded by a generated MessagePack decoder, `redirect_msgp.go`, on every request that carries it unless `DisableFlashMessages` is set), and the session, CSRF and `encryptcookie` cookies.
- **Values read back from a `Storage`**: session, limiter, cache and idempotency entries are decoded with `gob` or generated MessagePack code. The storage is trusted, but its keys are built from the request (session IDs, CSRF tokens, rate-limit and cache keys, idempotency keys), so look for key confusion between middleware that share one storage, and for entries one client can read or pre-empt for another.
- **The far end of outbound connections**: `client` and `middleware/proxy` talk to servers that may be hostile (response headers, `Set-Cookie`, redirects, bodies).
- **File names**: `middleware/static`, `SendFile`, `Download` and `Attachment` turn a request-derived name into an open file.

Trusted: application code and handlers, `fiber.Config` and every middleware `Config`, the `Storage` backend, template engines and templates, a reverse proxy that `TrustProxyConfig` lists, and whatever directory tree the application chose to serve.

The defaults decide severity, so know them. `BodyLimit` 4 MiB (also applied after decompression), `ReadBufferSize` 8 KiB (which caps the header size), `Concurrency` 262144, `MaxRanges` 16. `TrustProxy` off, so forwarded headers are ignored. No read, write or idle timeout. Panics are **not** recovered (`docs/guide/error-handling.md`), so one escaping a handler ends the process unless the application mounts `middleware/recover`. `Immutable` off, `UnescapePath` off, routing is case-insensitive and non-strict.

## What Fiber promises (a violation is a finding)

Each promise ends with the check that tests it.

1. **One path.** Before matching, the router normalizes the path as RFC 3986 section 6.2.2 describes (`docs/guide/routing.md`, "Path normalization"): unreserved escapes are decoded exactly once, other escapes stay encoded in upper case, dot segments are resolved, a stray `%` cannot forge an escape. Middleware mounted on a prefix therefore sees every spelling of any path below it. The middleware that acts on a request path (`static`, `proxy`, `rewrite`, `adaptor`) acts on the path the router matched (`c.Path()`), never on the raw target, so that no other spelling reaches what a prefix's middleware guards. `c.OriginalURL()` is the one accessor that keeps the raw target. *Check:* put a guard that always answers 401 on `/admin` and the content behind it in each consumer; no spelling of any request may return that content (the lab's `TestPathMatrix`).
2. **Proxy trust.** `IP()`, `Host()`, `Hostname()`, `Scheme()`, `BaseURL()` and `Subdomains()` use forwarded headers only when the TCP peer is in `TrustProxyConfig`. `Protocol()` never comes from a header. `EnableIPValidation` walks `X-Forwarded-For` right to left past trusted proxies. *Check:* from an untrusted peer, add each forwarding or override header you can think of; no response may change.
3. **Request ownership.** Strings and byte slices from `Ctx` alias fasthttp's buffers, and `Ctx`, `client.Request` and `client.Response` come from pools. That is documented ("Zero Allocation") and is the application's concern. Fiber's own code must not keep such a view, or a pooled object, past the end of the request: not in a cache or storage write, a goroutine, a hook, the `timeout` middleware's abandon-and-reclaim protocol (`ScheduleReclaim`, `ReleaseCtx`), or a stale `Close()` on a reused object. *Check:* reuse one `fasthttp.RequestCtx` for many requests, as the server does per connection, with a `Storage` that records keys and values uncopied and compares them with a copy made at the same moment; and run concurrent requests with a unique marker in every input, under `-race`.
4. **Bounds.** Body, header, range, upstream-response and storage-key sizes stay within `BodyLimit`, `ReadBufferSize`, `MaxRanges`, `MaxResponseBodySize` and the limits each middleware documents, including after decompression. *Check:* time and allocation per request at the maximum size, then at double.
5. **Secure defaults.** `proxy` refuses loopback, private, link-local (cloud metadata), CGNAT and IPv6-transition upstreams, re-checking at dial time; refuses non-http(s) schemes and HTTPS-to-HTTP redirects; strips hop-by-hop headers, and credentials when a redirect crosses to another host; refuses a routed path that an upstream could read differently (`%2F`, `//`, `\`, `..;`). `cors` refuses a wildcard origin with credentials. `csrf` checks `Origin` or `Referer` before the token. *Check:* the SSRF address spellings in "Bug classes seen here", and hostile `Origin` and `Host` spellings (userinfo, delimiters, suffix tricks, Unicode look-alikes) against the CORS list, `hostauthorization` and `Domain` routing.

`docs/` is the maintainers' statement of intended behavior. When it says a behavior is intended, a caveat, or something the application must do, that is not a finding. When the code contradicts it, that is.

## Components that matter most / least

Most important, in this order. The count after each is its non-merge commits since 1 July, test files excluded (a rough measure of how new the code is).

1. **Routing and path handling** (`router.go` 67, `path.go` 37, `router_filter.go`, `router_skip.go`, `constraint.go`, `domain.go` 19, `mount.go` 25, `group.go`, `register.go`, `internal/{urlnorm,wiretarget,paramdelim}`). A mistake here skips middleware, which is the most severe outcome this framework has.
2. **Request and response accessors** (`req.go` 56, `res.go` 71, `ctx.go` 52, `helpers.go` 48, `redirect.go`, `app.go` 69, `listen.go`, `prefork.go`, `internal/{cookie,headerlist,mediatype,byterange,etag}`).
3. **Middleware that forwards, serves or stores what a request names**: `proxy` (38, 18 of them in `security.go`), `static` (30, with `internal/fspath`), `adaptor` (29), `redirect` (57) and `rewrite` (with `internal/{rulematch,crosshost}`), `cache` (43), `compress`, `timeout`, `sse`.
4. **Authentication and request-origin middleware**: `session`, `csrf`, `cors`, `hostauthorization`, `basicauth`, `keyauth`, `encryptcookie`, `limiter`, `idempotency`, `earlydata`, `helmet`, with `extractors/` (39), `internal/{origin,schemehost,redact}`.
5. **`binder/`, `bind.go`, `client/`** (redirects, cookie jar, path-parameter substitution, hooks), `internal/{memory,storage/memory}`, and the generated decoders (`*_msgp.go`).

Less important, still in scope: `log/`, `middleware/logger`, `requestid`, `responsetime`, `favicon`, `healthcheck`, `paginate`, `skip`, `etag`, `pprof`, `expvar`, `envvar`, `addon/retry`.

Out of scope: `_test.go` files, `internal/clocktest`, `internal/loggertest`, `internal/tlstest`, `docs/`, `.github/`, benchmarks, and the generated interface files `ctx_interface_gen.go`, `req_interface_gen.go` and `res_interface_gen.go`.

Dependencies. fasthttp (`github.com/valyala/fasthttp`) is the HTTP parser, server and client underneath. Fiber's use of it is in scope: the options Fiber sets, what Fiber does with the values fasthttp hands it, and any difference between how fasthttp and Fiber read the same bytes. A flaw that lies wholly inside fasthttp or another third-party module (`golang.org/x/net`, `golang.org/x/crypto`, `klauspost/compress`, `fxamacker/cbor`, `shamaton/msgpack`, `tinylib/msgp`) belongs to its maintainers: report it here only when a default Fiber application is exposed, say which module holds the fix, and give the reproducer as a Fiber application. `gofiber/utils/v2` and `gofiber/schema` are maintained by the Fiber team and are in scope wherever Fiber's API reaches them. Module sources are in the module cache (`go list -m -f '{{.Dir}}' github.com/valyala/fasthttp`).

## Bug classes seen here (hunt for variants)

Numbers like #4695 are pull requests and appear in merge commits (`git log --grep '#4695'`); short hashes are commits. For each class: the fixes, then the siblings worth checking.

1. **A path-scoped middleware is skipped because the path is spelled differently.** #4695, #4719, #4712, #4720, #4728, #4722, #4778, #4772, `fceb2d17`, `db6c1a02`, `c52b7335`. Siblings: prefix arithmetic in `Mount`, `Group` and `Domain` (`mount.go`, `group.go`, `domain.go`); `Use` with parameters or wildcards; `Next` and `Skip` predicates that compare paths; `pprof`, `expvar`, `favicon`, `healthcheck`, `skip`; `GetRouteURL` and `Redirect().Route`; `HEAD`, `OPTIONS`, `*`, `CONNECT`, absolute-form targets and HTTP/1.0 without `Host`.
2. **Decoded twice, or decoded differently from the router.** #4719 (`SendFile`), #4695 and `737bb77c` (static), #4626 (extractors), #4625 and `4a3376fb` (client path parameters). Siblings: any `url.PathUnescape`, `QueryUnescape` or fasthttp decode of a value Fiber already decoded; every behavior under `UnescapePath` on and off.
3. **Same bytes, different parser downstream.** The adaptor to `net/http` (`abc82078`, `3a8b07a7`, `01f3f07d`), the proxy to an upstream (`a1d5ad63` backslash and `..;`, `84fd7c6a` `%2F` and `//`, `a855e889` forged escapes, `163ba8b1` routed path), redirect rules (#4584). Siblings: every value Fiber re-emits (`Location`, `Link`, `Content-Disposition`, `Set-Cookie`, `Vary`, SSE frames, log lines, forwarded headers) and every parser Fiber hands bytes to. Model the receiver: Node and WHATWG (`\` is `/`), IIS, Tomcat and Jetty (`;` parameters), nginx (merged slashes), Spring (suffix patterns), Envoy.
4. **Trust and header parsing.** #4568 and #4735 (repeated and tabbed `X-Forwarded-For`), #4725 and #4745 (`X-Real-IP`, the `Connection` listing), #4738 (repeated `Authorization`), #4708 (repeated `Accept-Encoding` and `Cache-Control`), `5d8b1014` and `73df8412` (header names matched as a recipient does), #4693 (idempotency replay under `EnableSplittingOnParsers`). Siblings: each place that reads a header once instead of as the joined list; `DisableHeaderNormalizing`; underscores, whitespace, obs-fold, case.
5. **The SSRF guard misses an address.** #4405 (`SecurityPolicy`), #4518 (DNS rebinding), #4553, `4991e877`, `04350120`, `84cc15ab` (IPv6 transition addresses), `8a3d770c` and `034d8d87` (installing the guard on clients). Siblings: other spellings of an internal address (decimal, octal, hex and short IPv4; mapped and compatible IPv6; zone IDs; trailing dots; userinfo; IDNA mappings; `0.0.0.0`; `::`), redirects (is the guard re-run per hop?), a `fasthttp.Client` the application passes per call, `LBClient`, `DomainForward` hostnames resolved at construction.
6. **Forged or fixed credentials.** GHSA-98j2-3j3p-fw2v (session IDs chosen by the client), GHSA-94w9-97p3-p368 (CSRF token injection), #4726 (basicauth timing), #4631 (challenge quoting), #4679 and `a17178a3` (session write-back holes and extractor provenance). Siblings: the rewritten session store and every extractor source, `Reset`, `Regenerate` and `Destroy`, timeouts, cookie attributes, `SingleUseToken`, CSRF `Session` mode, `keyauth` taking a key from the query string.
7. **Precedence that depended on map order.** #4621 and #4633 (redirect rules). Siblings: any security decision made while ranging over a Go map; grep `range` over maps in `middleware/` and in configuration handling.
8. **A pooled object outlives its request.** #4659 (a client `Response` released a reused `Request`), #4359 and `ctx_reclaim_test.go` (timeout reclaim), `519e298a` (`Locals` of a custom Ctx), #4656 (`SendFile` over a function-backed `fs.FS` added a handler per call). Siblings: every `sync.Pool`, `bytebufferpool` and `Acquire`/`Release` pair; every `utils.UnsafeString` or `UnsafeBytes` result that is stored, sent on a channel or captured by a goroutine; hooks; `Context()`.
9. **A panic from a structural limit.** GHSA-mrq8-rjmw-wpq3 (more than 30 route parameters; `maxParams`), #4717 (a trailing escape in a route), #4620 (a nested mount, nil dereference), #4662 (typed-nil view engine). Siblings: every fixed-size array indexed by a count (`[maxParams]string`), every slice indexed by a parsed number, and construction that runs at the first request instead of at startup.
10. **Super-linear cost.** #4658 (`Set-Cookie` attribute parsing), #4677 (rate-limit key size), `67750d2c` and `786eaf2a` (buffering streams for HTTP/1.0 clients). Siblings: parsers fed a repeated token (cookies, `Accept*`, `Link`, `Vary`, `Forwarded`), multipart parts, form keys, regexes built from request data.
11. **Output injection and open redirects.** #4570 and `f354b065` (log injection), #4586 (JSONP callback), #4584 (composed route URLs and redirect rules), #4629 and #4721 (route URL parameters), #4529 (`Redirect.Route` query). Siblings: every header or cookie Fiber writes from request data; SSE (`Test_SSE_EventRejectsFieldInjection` covers one case); `Attachment`, `Links`, `Location`.
12. **A speed-up changed what is accepted.** #4558, #4517, #4655, #4688, #4705 (router filters), the SWAR scanners (`a4879b72`, `7d774759`, `80b7e9af`). Each commit says it was checked against a simple reference; look for the inputs the reference was not run on.

## Hypotheses worth testing

Each is a test with an oracle. Skip one if the lab or the tests already cover it at the depth you would reach.

1. **A new consumer or a second-order spelling in the path matrix.** Consumers it does not have: `rewrite` and `redirect` rules, `Domain` plus `Mount`, `skip`, `healthcheck`, `pprof`, `expvar`, `favicon`, a `Next` predicate comparing `c.Path()`, `static` with `Browse` and `Download`, `SendFile` with an `fs.FS`. Spellings it does not have: two layers at once (an encoded slash inside a mounted prefix under `UnescapePath`), long prefixes, Unicode, overlong UTF-8, `%u` forms.
2. **More downstream models for the proxy.** The lab models `net/http`, WHATWG and Tomcat/Jetty. Add nginx (merged slashes, normalized dot segments), Envoy, Spring suffix patterns, and Apache `AllowEncodedSlashes`. The oracle is the same: an upstream reads the forwarded target as under `/admin` while Fiber's guard did not match.
3. **Prefix arithmetic.** Register the same routes flat and nested (`Group`, `Mount`, `Domain`, with parameters, trailing slashes, `StrictRouting`); every request must reach the same handler, with the same `Params`, in both.
4. **Router differential.** For random sets of eight or more routes sharing a prefix (that engages `filterMinBucket` and the fingerprints), random paths, and every combination of `CaseSensitive`, `StrictRouting` and `UnescapePath`, the router must pick the first route that `fiber.RoutePatternMatch(path, pattern, cfg)` accepts. Also compare an app with `SkipUnmatchedRoutes` against one without: the route handler must be the same. Grow the grammar: `\:` escapes, `regex(...)` and custom constraints, `+` and `*` mixes, long static segments, Unicode.
5. **Configuration cross-product.** Run every lab test under the combinations of `UnescapePath`, `CaseSensitive`, `StrictRouting`, `DisableHeaderNormalizing`, `SkipUnmatchedRoutes`, `Immutable`, `StreamRequestBody` and `EnableSplittingOnParsers`. Behavior that diverges only under one option is where the untested code is.
6. **Connection-level behavior on a real listener.** Pipelined requests where the first is refused early (`BodyLimit`, malformed target), `Expect: 100-continue`, `Connection: close` after an error, chunked trailers, HTTP/1.0 keep-alive, `Content-Length` with `Transfer-Encoding`. Use a Python socket against `app.Listen("127.0.0.1:...")`. The lab parses one request at a time and cannot see desynchronization.
7. **`StreamRequestBody` and multipart.** Handlers run before the whole body arrives: `c.Body()`, binders and the CSRF form extractor under streaming; `BodyLimit` while streaming; temp-file cleanup on every error path; part count and size.
8. **Key scoping.** For every middleware that stores state or a response under a key a client can influence (`session`, `csrf`, `cache`, `limiter`, `idempotency`, anything over `Storage`), ask who else can present the key and what it is bound to (principal, method, path, body, host, scheme). Oracle: two clients, same key, compare the responses; and one client trying to pre-empt a key another will use.
9. **State machines against a model, with an injected clock.** Session idle and absolute timeouts, `Regenerate`, `Reset` and `Destroy` followed by use of the old ID; CSRF expiry and single-use tokens; limiter windows (never above `Max`, no negative remainder, no overflow at large values); idempotency locks.
10. **The client against a hostile server.** Fuzz raw responses through `fasthttputil.NewInmemoryListener` into `client.Get`; redirect chains and loops; cookie-jar domain and path rules; credentials on redirects; response size with no cap; slow responses.
11. **Complexity probes.** For each parser, time it at sizes n, 2n and 4n, within `ReadBufferSize` for headers and `BodyLimit` for bodies; flag a ratio above 3 per doubling.
12. **Coverage as a map of untested code.** `go test -coverprofile=/tmp/c.out ./... && go tool cover -func=/tmp/c.out | sort -k3 -n | head -60`, then read the uncovered branches of the files under "Components that matter most". Coverage is already high (`static` is at 96%), so the value is in the few branches left, not in broad gaps.

## Already tried

At commit `4515676` (2026-10-19) each of these was run and found nothing; where a clean result could be vacuous (the path, ownership and cache checks), a control confirmed that the check can fail. Treat them as covered at that depth; a finding here needs a new angle.

- A larger version of the lab's path matrix (about 1,700 spellings, three mount prefixes, four routing configurations) against `static` mounted at `/`, at a prefix and over an `fs.FS`, `net/http`'s `FileServer` through the adaptor, a mounted sub-app and a `Group`: no guard bypassed. The proxy against the three upstream models is where differences are most likely to remain.
- The router against `RoutePatternMatch`: 800,000 (route set, path) pairs, 57% of them with a matching route, five configurations; `SkipUnmatchedRoutes` against the default router: 60,000 requests. No disagreement.
- Fuzzing raw requests through about 35 accessors, the common middleware, `static` with ranges, listings and compression, the proxy, the adaptor, `SendFile` and `Download`: about 4 million executions, no panic.
- Ownership: concurrent keep-alive requests through cache, session, compress, timeout, proxy and adaptor, with the `timeout` middleware firing on about a third of them while the abandoned handler keeps using its context, under `-race`: no leak and no race. A recording `Storage` on a reused `RequestCtx`: no key or value aliased across session, CSRF, idempotency, limiter and cache.
- Credentials: a double-submit CSRF token chosen by the attacker is refused; a session ID presented by the client is never adopted, through a cookie, a header, the query string or a chain; a forged, truncated or moved `encryptcookie` value is dropped.
- Cross-client replay: 252 orderings of `cache`, `cors`, `compress`, `etag`, `session`, `limiter` and `helmet` never gave one client another's `Access-Control-Allow-Origin`, `Content-Encoding` or `Set-Cookie`; a response that sets a cookie is not cached; a partial `206` is not cached.
- Forwarding headers: 31 forwarding and override headers (`X-Forwarded-*`, `Forwarded`, `X-Original-URL`, `X-HTTP-Method-Override`, `True-Client-IP` and others) from an untrusted peer changed nothing in `IP()`, `Host()`, `Scheme()`, `BaseURL()`, cookies, CORS, redirects or helmet.
- Host and origin: 81 spellings of `Host` (userinfo, delimiters, Unicode look-alikes, duplicates, absolute-form conflicts), each in seven request forms, against `hostauthorization`, `Domain` routing and `BaseURL()`; 56 spellings of `Origin`, each in four forms, against a wildcard CORS list. Nothing outside the allowed names passed, apart from names that fold to an allowed one (Unicode compatibility mapping, in `Host`) and labels with a leading hyphen or an underscore under an allowed suffix (in `Origin`).
- Injection: CR and LF in header, cookie, `Link`, `Location` and `Content-Disposition` values are neutralized; the JSONP callback is sanitized; redirect rules and `Back()` cannot leave the site; directory listings escape file names; the logger escapes CR and LF; the route-parameter limit is enforced across groups, mounts, wildcards and optionals.
- `Range`: 50,000 headers against `net/http`, never out of bounds up to `MaxInt64`, and either equal or stricter (Fiber rejects `+1` and `-0`).
- Cost: the largest header payloads cost up to 1.7 ms (about 40 times a bare request, linear); a sparse form index such as `b[999999999]` is capped; deeply nested JSON and XML neither crash nor blow up.
- The client keeps credentials on same-origin and same-host redirects (the port is ignored, as in `net/http`) and drops them for another host name.

## How to exercise it

The image has the checkout at `/src` with its full git history, Go 1.27, every module in the module cache, the library and all of its test binaries already compiled (plain and with `-race`), `GOPROXY=off` and `GOTOOLCHAIN=local`. `/src/.oss-scanner/` is the scanner's own untracked copy of the Dockerfile; keep it out of patches. `curl`, `nc`, `python3`, `gdb`, `strace` and `valgrind` are installed, only loopback is reachable, and the shell has two CPUs and 8 GB.

- **Tests**: the whole suite passes here with no network. `go test -race -count=1 ./...` takes about three minutes, the slowest packages (the root package, `idempotency`, `limiter`, `client`) 30 to 45 seconds each, so while you iterate run a package or a `-run` pattern. The `make` targets `lint`, `test`, `audit`, `format` and `generate` fetch tools with `@latest` and need the network; use `go test`, `go vet ./...` and `gofmt -l .` instead.
- **History**: `git log --no-merges --since=2026-07-01 --format='%h %ad %s' --date=short -- path.go router.go middleware/static | head -40` lists recent fixes to a file. `git log -S'<text>' -- <file>` finds when a line appeared. Merge commits carry the PR number.
- **A server to attack**: put a throwaway `main` package in a new directory inside the checkout, such as `/src/poc/main.go`, written from the Quickstart in `README.md`, and run it with `go run ./poc` on `127.0.0.1`. Delete the directory before you write a patch. Send requests with `curl --path-as-is` (otherwise curl resolves `..` itself), or as raw bytes, which is the faithful way to test anything that depends on the exact request line: `printf 'GET /a/%%2e%%2e/admin/b HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n' | nc 127.0.0.1 3000` (write `%%` because `printf` reads `%2e` as a format).
- **In process**: `app.Test(req)` takes a `*net/http.Request`, and `net/http` refuses or reads differently some targets. To hand Fiber a raw target, parse the bytes with fasthttp and run the handler, as the lab's `serve` does. If you build the request by hand instead, set the host with `req.Header.SetHost("example.com")`, which is how a socket delivers it: `req.SetHost` makes fasthttp read a target that begins with `//` as an authority, so `//admin/x` is routed as `/x`; on the wire that happens only to an HTTP/1.0 request with no `Host` header.
- **Fuzzing** works offline: `go test -run '^$' -fuzz FuzzRequest -fuzztime 5m -parallel 2 ./poc` for the lab's target, or the repository's own, for example `go test -run '^$' -fuzz FuzzValidateUpstream -fuzztime 60s ./middleware/proxy/`.
- **Races and pooling**: `go test -race -count=20 -run <test> ./<package>`, and `ctx_reclaim_test.go` for the abandon-and-reclaim protocol. The `timeout` middleware answers a timeout with 503.
- **Generated code**: `*_msgp.go` and `*_gen.go` come from `msgp` and `ifacemaker`, which are not in the image. If a fix needs generated code, change the source and the generated file by hand and say so.

### The lab

Save as `/src/poc/lab_test.go` and run `go test -count=1 -run TestPathMatrix ./poc` and `go test -run '^$' -fuzz FuzzRequest -fuzztime 2m ./poc`. It was written against `main` at the commit named under "Already tried"; if the API has moved, the compile errors are mechanical. Add a consumer to `TestPathMatrix`, a middleware or route to `FuzzRequest`, or a downstream model to `upstreamReads`. `spellings(pre)` spells the whole path of a consumer mounted at `pre`, so the mount prefix is encoded too and the request-target forms keep their authority in front of it; add a prefix to the list in `TestPathMatrix` for a consumer mounted elsewhere. Two things it relies on: every consumer has a control request that must return exactly the expected body (otherwise a clean run proves nothing, as it would for `proxy.Forward(addr)`, which sends every request to one fixed URL), and the guard answers 401 for everything, so any response containing the payload is a bypass.

```go
package poc

import (
	"bufio"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/gofiber/fiber/v3"
	"github.com/gofiber/fiber/v3/middleware/adaptor"
	"github.com/gofiber/fiber/v3/middleware/logger"
	"github.com/gofiber/fiber/v3/middleware/proxy"
	"github.com/gofiber/fiber/v3/middleware/session"
	"github.com/gofiber/fiber/v3/middleware/static"
	"github.com/valyala/fasthttp"
)

// serve parses raw request bytes the way the server does, then runs the handler. -1 means the HTTP parser refused them.
func serve(h fasthttp.RequestHandler, raw string) (int, string) {
	var req fasthttp.Request
	if req.Read(bufio.NewReaderSize(strings.NewReader(raw), 8192)) != nil {
		return -1, ""
	}
	ctx := &fasthttp.RequestCtx{}
	ctx.Init(&req, nil, nil)
	h(ctx)
	return ctx.Response.StatusCode(), string(ctx.Response.Body())
}

// spellings of pre+"/admin/secret.txt" (pre is where a consumer is mounted): every byte encoded, every slash replaced, dot segments, extra prefixes and
// suffixes, case, forged escapes, and the request-target forms, with the authority in front of the mount prefix.
func spellings(pre string) (out []string) {
	canon, set := pre+"/admin/secret.txt", map[string]bool{}
	for i := range canon {
		for _, f := range []string{"%%%02X", "%%%02x", "%%25%02X"} {
			set[canon[:i]+fmt.Sprintf(f, canon[i])+canon[i+1:]] = true
		}
		for _, s := range []string{"%", "%%", "%2", ";", "%00"} {
			set[canon[:i]+s+canon[i:]] = true
		}
		if canon[i] == '/' {
			for _, s := range []string{"%2F", `\`, "%5C", "//", "/./", "/x/../", "/;/", "/..;/", "/%2e/", "%C0%AF", "%252F"} {
				set[canon[:i]+s+canon[i+1:]] = true
			}
		}
	}
	for _, p := range []string{"//", "/./", "/x/../", "/%2e%2e/", `/\`} {
		set[p+canon[1:]] = true
	}
	for _, s := range []string{"/", "//", "/.", "%00", ";a=b", "?", "#", "%23"} {
		set[canon+s] = true
	}
	for _, s := range []string{"/admin/secret.txt", "/ADMIN/secret.txt", "/%61dmin/secret.txt", "/%%61dmin/secret.txt", "/admin/../admin/secret.txt", "/admin//secret.txt"} {
		set[pre+s] = true
		set[strings.ToUpper(pre)+s] = true
	}
	for _, authority := range []string{"http://x", "//x"} {
		set[authority+canon] = true
	}
	if pre == "" {
		set["admin/secret.txt"], set["*"] = true, true
	}
	for s := range set {
		out = append(out, s)
	}
	return out
}

// upstreamReads: what upstreams with different path parsers would serve for a raw target (net/http, WHATWG/IIS, Tomcat/Jetty).
func upstreamReads(raw string) (out []string) {
	p := strings.SplitN(strings.SplitN(raw, "?", 2)[0], "#", 2)[0]
	if u, err := url.ParseRequestURI(raw); err == nil {
		out = append(out, path.Clean("/"+u.Path))
	}
	if d, err := url.PathUnescape(strings.ReplaceAll(p, `\`, "/")); err == nil {
		out = append(out, path.Clean("/"+d))
	}
	segs := strings.Split(p, "/")
	for i, s := range segs {
		segs[i], _, _ = strings.Cut(s, ";")
	}
	if d, err := url.PathUnescape(strings.Join(segs, "/")); err == nil {
		out = append(out, path.Clean("/"+d))
	}
	return out
}

// TestPathMatrix: a guard on /admin always answers 401, so no spelling of any request may ever return the payload.
func TestPathMatrix(t *testing.T) {
	const payload = "PAYLOAD-7f3a"
	dir := t.TempDir()
	_ = os.MkdirAll(filepath.Join(dir, "admin"), 0o755)
	_ = os.MkdirAll(filepath.Join(dir, "pub"), 0o755)
	_ = os.WriteFile(filepath.Join(dir, "admin", "secret.txt"), []byte(payload), 0o644)
	_ = os.WriteFile(filepath.Join(dir, "pub", "ok.txt"), []byte("OK"), 0o644)
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		for _, p := range upstreamReads(r.RequestURI) {
			if strings.HasPrefix(p, "/admin/") {
				_, _ = w.Write([]byte(payload))
				return
			}
		}
		_, _ = w.Write([]byte("OK:" + r.RequestURI))
	}))
	defer up.Close()
	pol := proxy.DefaultSecurityPolicy()
	pol.AllowPrivateIPs = true            // the upstream is on loopback
	prev := proxy.WithSecurityPolicy(pol) // the policy is process-wide: put the old one back when the test ends
	defer proxy.WithSecurityPolicy(prev)

	sub := fiber.New() // a sub-app that knows nothing about the parent's guard
	sub.Get("/admin/*", func(c fiber.Ctx) error { return c.SendString(payload) })
	sub.Get("/pub/*", func(c fiber.Ctx) error { return c.SendString("OK") })
	deny := func(c fiber.Ctx) error { return c.SendStatus(fiber.StatusUnauthorized) }
	consumers := []struct {
		name          string
		mount         func(*fiber.App)
		control, want string // a request that must work, and the body that proves the consumer really serves paths
	}{
		{"static at /", func(a *fiber.App) { a.Use("/admin", deny); a.Use(static.New(dir)) }, "/pub/ok.txt", "OK"},
		{"static at /files", func(a *fiber.App) { a.Use("/files/admin", deny); a.Use("/files", static.New(dir)) }, "/files/pub/ok.txt", "OK"},
		{"net/http FileServer", func(a *fiber.App) { a.Use("/admin", deny); a.Use(adaptor.HTTPHandler(http.FileServer(http.Dir(dir)))) }, "/pub/ok.txt", "OK"},
		{"proxy.Balancer", func(a *fiber.App) {
			a.Use("/admin", deny)
			a.Use(proxy.Balancer(proxy.Config{Servers: []string{up.URL}}))
		}, "/pub/ok.txt", "OK:/pub/ok.txt"},
		{"mounted sub-app", func(a *fiber.App) { a.Use("/files/admin", deny); a.Use("/files", sub) }, "/files/pub/x", "OK"},
	}
	for name, cfg := range map[string]fiber.Config{"default": {}, "UnescapePath": {UnescapePath: true}, "CaseSensitive+Strict": {CaseSensitive: true, StrictRouting: true}} {
		for _, c := range consumers {
			app := fiber.New(cfg)
			c.mount(app)
			h := app.Handler()
			if st, body := serve(h, "GET "+c.control+" HTTP/1.1\r\nHost: x\r\n\r\n"); st != 200 || body != c.want {
				t.Fatalf("[%s/%s] control request returned %d %q: the consumer is not serving, so a clean result would mean nothing", name, c.name, st, body)
			}
			for _, pre := range []string{"", "/files"} {
				for _, s := range spellings(pre) {
					if _, body := serve(h, "GET "+s+" HTTP/1.1\r\nHost: x\r\n\r\n"); strings.Contains(body, payload) {
						t.Errorf("[%s/%s] GUARD BYPASSED by %q", name, c.name, s)
					}
				}
			}
		}
	}
}

// touch calls request accessors and response helpers that take request data, so one fuzz target reaches many parsers.
func touch(c fiber.Ctx) error {
	_, _ = c.Range(1000)
	_, _ = c.MultipartForm()
	_, _ = c.Authorization()
	_, _ = c.IfModifiedSince()
	var v struct {
		A string            `query:"a" form:"a" json:"a" header:"a" cookie:"a" xml:"a"`
		B []int             `query:"b" form:"b" json:"b"`
		C map[string]string `query:"c" form:"c" json:"c"`
	}
	b := c.Bind()
	_, _, _, _, _ = b.Query(&v), b.Header(&v), b.Cookie(&v), b.Body(&v), b.All(&v)
	_ = []any{c.Accepts("text/html", "application/json"), c.AcceptsEncodings("gzip", "br"), c.AcceptsLanguages("en"), c.BaseURL(), c.Body(), c.FullURL(), c.Origin(),
		c.Cookies("a"), c.AllCookies(), c.FormValue("a"), c.Fresh(), c.Stale(), c.IfNoneMatch(), c.GetHeaders(), c.Bearer(), c.Hostname(), c.IP(), c.IPs(), c.Is("json"),
		c.Method(), c.Path(), c.Params("*"), c.Scheme(), c.Queries(), c.Subdomains(), c.IsProxyTrusted(), c.MediaType(), c.Charset()}
	c.Cookie(&fiber.Cookie{Name: c.Query("n"), Value: c.Query("v"), Domain: c.Query("d"), Path: c.Query("p")})
	c.Set(c.Query("k"), c.Query("v"))
	c.Attachment(c.Query("f"))
	c.Links(c.Query("l"), "next")
	if s := session.FromContext(c); s != nil {
		s.Set("a", c.Query("a"))
	}
	if c.Query("jsonp") != "" {
		return c.JSONP(fiber.Map{"a": 1}, c.Query("cb"))
	}
	return c.SendString("ok")
}

// FuzzRequest feeds arbitrary bytes through fasthttp's parser into an app with the usual middleware. Fiber does not
// recover panics, so any panic here is a bug that kills a real server. Add the middleware and routes you want covered.
func FuzzRequest(f *testing.F) {
	app := fiber.New(fiber.Config{TrustProxy: true, ProxyHeader: fiber.HeaderXForwardedFor, EnableIPValidation: true, TrustProxyConfig: fiber.TrustProxyConfig{Loopback: true}})
	// Fuzz inputs carry no valid session cookie, so each one creates a session. A short idle timeout keeps the store from growing with the run.
	app.Use(logger.New(logger.Config{Stream: io.Discard}), session.New(session.Config{IdleTimeout: time.Second}))
	app.All("/*", touch)
	h := app.Handler()
	f.Add([]byte("GET /x?a=1&b=2&c[k]=v HTTP/1.1\r\nHost: a\r\nCookie: a=1\r\nRange: bytes=0-5,7-\r\nX-Forwarded-For: 1.2.3.4, 127.0.0.1\r\nAccept-Encoding: gzip\r\n\r\n"))
	const body = `{"a":"x","b":[1]}`
	f.Add([]byte(fmt.Sprintf("POST / HTTP/1.1\r\nHost: a\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n%s", len(body), body)))
	for _, pre := range []string{"", "/files"} {
		for _, s := range spellings(pre) {
			f.Add([]byte("GET " + s + " HTTP/1.1\r\nHost: a\r\n\r\n"))
		}
	}
	f.Fuzz(func(t *testing.T, data []byte) {
		var req fasthttp.Request
		if req.Read(bufio.NewReaderSize(strings.NewReader(string(data)), 8192)) != nil {
			return
		}
		ctx := &fasthttp.RequestCtx{}
		ctx.Init(&req, nil, nil)
		h(ctx)
	})
}
```

Notes for extending it. The oracles above come from these ideas, all cheap to build: **spoof invariance** (for an untrusted peer, adding forwarding headers must not change the response; mask random cookie values first); **a recording `Storage`** that keeps keys and values uncopied beside a copy, with one `RequestCtx` reused for many requests, plus a deliberately buggy handler as a control; **a metamorphic cross-client check** (the second client's response must not carry the first client's Vary-governed headers or cookies, for every ordering of the middleware); **a virtual file** (a `Read`/`Seek` type with no memory behind it) so `Range` can be compared with `http.ServeContent` at sizes up to `MaxInt64`. A host matrix needs the RFC 9112 reading of the target: an absolute-form target's host wins over `Host`, and fasthttp drops userinfo from `Host`.

## How you rate severity

A finding counts when a network client of an application that uses Fiber as its documentation describes can make it misbehave. State the `fiber.Config` and middleware configuration the reproducer needs. A finding against the defaults, or against the configuration that `docs/guide/reverse-proxy.md` and the middleware docs recommend, weighs more than one that needs an unusual option. The maintainers have published advisories for client-chosen session IDs, CSRF token injection and a route with too many parameters panicking, so rate these classes seriously even when the trigger looks small.

- **Critical**: remote code execution, or memory corruption reachable from the network, including a data race on a string, slice or interface value, which Go can turn into one (Fiber converts between strings and byte slices with `unsafe`, and `readonly.go` uses `go:linkname`). A request that reaches a handler, a file or an upstream below a path prefix without running the middleware mounted on that prefix, through any spelling of the path, under the default routing options. Data from one request delivered to another: a response, header, cookie, session, body, `Locals` value or pooled object attributed to the wrong request. A session ID, CSRF token or `encryptcookie` value that can be forged, predicted or fixed, or `basicauth` or `keyauth` accepting a wrong credential, in the documented configuration.
- **High**: a panic or fatal error (nil dereference, index out of range, concurrent map access, unbounded recursion, out-of-memory) that one unauthenticated request triggers in core code, or in a middleware under its default configuration, because the process exits. A bypass of a defense listed under "What Fiber promises": the `proxy` SSRF guard, `TrustProxyConfig` in an application configured as the guide says, `csrf` origin or token checks, `cors` origin matching, `hostauthorization`. Reading a file outside the root or `fs.FS` that `static` was given, or one that path-scoped middleware was meant to guard. Memory or CPU growth from small unauthenticated requests beyond the documented bounds, including through compression, unbounded storage keys, super-linear route, constraint, header-list or multipart parsing, or a goroutine or pooled object leaked per request. `client` or `proxy` sending `Authorization` or `Cookie` to a host they do not belong to. Response splitting, header or cookie-attribute injection, or an open redirect that Fiber's own helpers produce from inputs its docs call safe.
- **Medium**: the High denial-of-service and panic classes when they need a non-default option or a non-default middleware configuration. One client receiving, replaying or pre-empting another's stored state or response through a shared key (`cache`, `idempotency`, `session`, `limiter`, `csrf`), a wrong `Vary` or `Cache-Control` that lets a shared cache mix users, or a `limiter` bypass, each needing an unusual key configuration or knowledge of the key. A parsing difference between Fiber and fasthttp, `net/http` or a common upstream (header lists, `Content-Encoding`, `Range`, `Accept`, `Host`, path parameters) that changes an authorization or routing decision only on a path the application must opt into. A credential or token comparison that is not constant-time where the code means it to be (`basicauth` and `csrf` use `crypto/subtle`). Disclosure beyond what the docs describe: stack traces, internal addresses, file paths, environment values.
- **Low**: log injection that needs a non-default logger format. A hardening gap in documentation or examples. A crash that only the application's own handler or configuration can cause.

When a finding sits between two levels, choose the lower and say what would raise it. A deviation from RFC 9110 or 9112 with no security consequence is a bug and not a vulnerability; do not report it.

## How to report

Verify before you report. A finding needs all of these:

1. A reproducer that runs in this image, from a clean checkout: a Go test in the package concerned, or a small `main` plus the exact bytes or `curl` command sent, the `fiber.Config` and middleware configuration, and what you observed against what the documentation promises. For resource exhaustion, give the measured memory or time against the configured limit, at two sizes.
2. A check that it is not intended: search `docs/` and the tests (`grep -rn '<behavior>' --include='*_test.go' .`; `git log -S'<text>'`). A test that pins the behavior, or a doc that describes it, usually means it is deliberate.
3. A check that it is present on `main` now (`git log --oneline -5 -- <file>`).
4. A minimal patch against `main` with a regression test written as the repository writes them: `t.Parallel()` first in every test and subtest (except tests that call `testing.AllocsPerRun`), `testify/require`, and `github.com/gofiber/utils/v2` helpers where they fit. Handle every returned error and type assertion (the `errcheck` settings in `.golangci.yml` reject `_ =`). The test must fail before the patch and pass after it, with `go test -race` on the package. Update `docs/` when a documented contract changes.

Report one root cause once, listing each API it reaches. Say plainly when a finding depends on a Windows path rule (`internal/fspath` documents several) or any other behavior this Linux image cannot reproduce, and what you checked instead. Do not report best-practice gaps without a concrete request that misbehaves.

## Anything to leave alone

- Values from `Ctx` (`Params`, `Query`, `Body`, `Get`, `Cookies`, and so on) are reused after the handler returns unless `Immutable` is set. An application that keeps them is the application's bug. Only Fiber's own retention counts.
- The defaults are unlimited timeouts, no panic recovery, no TLS, no authentication and no rate limiting. A slow client, a connection held open, or a panic that the application's own handler raises against a server with those defaults is not a finding. A panic that Fiber raises on network input is (see High).
- `ProxyHeader` and `X-Forwarded-*` are spoofable when `TrustProxy` is off or `TrustProxyConfig` lists no proxy, as `docs/guide/reverse-proxy.md` says. So is `c.IP()` when `Private`, `Loopback` or `LinkLocal` is set and clients connect from those ranges, and when the proxy passes client-supplied forwarding headers through. Report a bypass of the documented setup, not the documented risk.
- `DefaultErrorHandler` writes `err.Error()` for errors that are not `*fiber.Error`, and `middleware/recover` writes the panic message, unless the application sets `ErrorHandler` or `PanicHandler`. This is documented.
- `cors.New()` allows any origin without credentials by default, and CORS is not an access-control mechanism. `csrf.NewCrossOriginProtection` is tokenless by design and checks neither tokens nor `Referer`. Attacks that `docs/middleware/csrf.md` places outside its model are not findings.
- `pprof`, `expvar`, `envvar`, `healthcheck` and `static` with `Browse` expose data by design when an application mounts them without authentication. `static` serves dotfiles inside the directory the application chose, like `net/http.FileServer`. Report only an exposure beyond what the middleware's docs and `Config` say, such as an `envvar` variable that is not in `ExportVars`.
- Middleware constructors panic at startup on a contradictory or unsafe configuration (`cors` with a wildcard origin and credentials, a `proxy.Balancer` server with a path, `redirect` with both `Rules` and `RuleList`, an `encryptcookie` without a key or a `basicauth` user with a plaintext password). That is deliberate; it is how a bad configuration is refused.
- The router keeps empty path segments, so `/dl//admin` is not under `/dl/admin`. An application that then collapses the slashes itself (`filepath.Join`, `path.Clean`) bypasses its own prefix guard; Fiber's own consumers (`static`, the proxy, the adaptor) refuse empty segments instead. That is the application's concern.
- An absolute-form target's host wins over the `Host` header (RFC 9112 section 3.2.2); fasthttp drops userinfo from `Host`; `hostauthorization`, `DomainForward` and CORS fold Unicode host names to Punycode. A host that folds to an allowed name passing is not a finding unless two Fiber components disagree in a way that grants access.
- Linear amplification bounded by `BodyLimit` or `ReadBufferSize`: a body of commas under `EnableSplittingOnParsers` allocates roughly 200 times its size, a JSON array about 20 times, a maximal `Cookie` header costs about 1.7 ms. Report super-linear growth, or amplification that escapes the documented limits.
- An application that passes request data to `Redirect().To`, `Location`, `SendFile`, `Download`, a view name or a header value where Fiber's docs do not promise it is safe.
- Findings that exist only in the v1 or v2 lines, in `gofiber/contrib`, `gofiber/template` or `gofiber/storage` (separate modules, not in this module graph), or only in `_test.go` files, `docs/` and `.github/`.
