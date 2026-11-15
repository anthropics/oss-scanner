# Threat model: fasthttp

## Project and trust boundaries

fasthttp is a performance-oriented HTTP/1.x server and client library for Go.
Audit the `master` branch of `github.com/valyala/fasthttp`, including its public
subpackages. Applications, their handlers, configuration and chosen upstream
URLs are trusted; remote clients and remote HTTP servers can be hostile.

Untrusted input includes request and response start lines, headers, trailers,
cookies, request targets, paths, query strings, multipart forms, compressed
bodies and connection timing. Follow these inputs through parsing, accessors,
serialization, streaming and connection reuse, rather than testing only an
isolated parser helper.

## Areas to prioritize

- HTTP message framing in `header.go`, `headerscanner.go`, `http.go` and
  `server.go`: ambiguous Content-Length/Transfer-Encoding combinations,
  repeated headers, chunked encoding, trailers, early errors, upgrades and
  bytes left for the next message on a persistent connection. Demonstrate
  request smuggling with a concrete peer/proxy interpretation and the actual
  bytes sent and consumed.
- URI, path, query and cookie handling in `uri.go`, `args.go`, `cookie.go` and
  `bytesconv.go`: inconsistent decoding, normalization, header injection and
  values that change meaning when forwarded or serialized.
- Server, client and `PipelineClient` connection lifecycle: timeouts,
  cancellation, retries, body streaming, connection pooling and response
  association. Check error paths as well as successful round trips.
- Pooled requests, responses, contexts, headers and compression state: reset,
  copy and reuse must not leak one request's data into another. Check the
  library's own retained references and concurrent use with the race detector.
- Static file serving (`fs.go`), `fasthttpadaptor`, `fasthttpproxy`, and
  compression helpers: path traversal, translation to/from net/http, boundary
  checks and enforcement of explicitly configured limits.

The examples and tests are useful drivers. A vulnerability in an example or a
third-party dependency should identify that component and explain whether a
supported fasthttp API exposes it. Do not attribute an application's missing
authentication, URL allowlist or proxy trust policy to the HTTP library.

## Intended behavior and limits

Read the API comments and README before classifying a behavior as a bug.
fasthttp intentionally differs from net/http in some places; a parser
difference alone needs a demonstrated security consequence.

- The server's default buffered request body limit is 4 MiB. Header size is
  bounded by the read buffer (4 KiB by default). Check configured limits and
  defaults through the real server/client call sequence.
- Read, write and idle timeouts are not enabled by default. Applications are
  responsible for choosing deployment-appropriate deadlines and connection
  limits. Distinguish these documented defaults from bypassing an enabled
  limit or leaking resources after a connection closes.
- `StreamRequestBody` deliberately permits bodies larger than the buffered
  request limit. `RequestBodyStream` allows bounded-memory processing;
  `PostBody` and `Request.Body` materialize the remaining stream in memory.
- Decompression APIs without a limit, and variants whose limit is nonpositive,
  deliberately allow unbounded output. A compression bomb using such an API
  alone is not a limit bypass. Investigate bounded variants and unexpected
  decoding through other accessors separately.
- Many returned byte slices alias internal buffers and are valid only until
  the next relevant operation or handler return. Callers must copy data they
  retain and must not access released pooled objects. Misuse of those
  documented lifetimes is distinct from the library retaining stale data.
- HTTP clients can reach destinations selected by the application, including
  private addresses. They are not an SSRF policy enforcement layer.

## Exercising the project

The checkout is at `/src`. The image contains the Go toolchain, module sources
and warmed normal and race build caches. The full suite runs during the online
image build. For offline runs, skip exactly `TestDialerGetDialFunc` in
`fasthttpproxy`: its NO_PROXY cases dial `github.com:80` and `github.com:443`
directly and require external DNS and connectivity. The other proxy tests,
including `TestDialerGetDialFuncForTLS`, use local listeners and remain enabled:

```sh
go test -skip '^TestDialerGetDialFunc$' -count=1 -timeout=10m ./...
go test -race -skip '^TestDialerGetDialFunc$' -count=1 -timeout=10m ./...
go test -list '^Fuzz' .
go test -run '^$' -fuzz '^FuzzRequestReadLimitBody$' -fuzztime=60s .
```

Run one fuzz target at a time. Validate differential fuzz oracles against the
documented behavior before treating a mismatch as a production defect. For
protocol findings, add end-to-end tests covering both buffered and streaming
paths and multiple messages on the same connection when relevant.

## Reports and patches

Provide a small reproducible Go test or wire-level reproducer, the affected
API, required configuration, observed impact and whether default settings are
affected. Separate remote process crashes, cross-request data disclosure and
framing attacks from resource exhaustion that requires an explicitly
unbounded API or application misuse. Rate severity from demonstrated impact
and realistic deployment conditions.

Prefer small fixes that preserve compatibility. Speed and low allocations are
core requirements: compare existing base/head benchmarks on the same machine
and measure warmed steady-state allocations when a proposed patch adds work
to common request or client paths. Reuse existing buffers and helpers where
possible.
