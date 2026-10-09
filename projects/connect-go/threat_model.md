# Threat model: connect-go

## What this project does and where untrusted input enters

connect-go is the Go implementation of ConnectRPC. The scanned branch is `main`, which is v2 (`connectrpc.com/connect/v2`). The core package (`connect.go`) defines the client, server, stream, interceptor and error types and does not import `net/http`. `connecthttp` serves and calls RPCs over the Connect, gRPC and gRPC-Web protocols on `net/http`, on HTTP/1.1 and HTTP/2 (and HTTP/3 when the application supplies an HTTP/3 server or client). `connectproto` provides the binary and JSON protobuf codecs, `connectgzip` the gzip compressor, and `connectinprocess` a transport that dispatches to a `*connect.Server` in the same process. The repository also contains the code generator `protoc-gen-connect-go` and the source rewriting tool `connect-go-v2-migrate`.

A handler mounted with `connecthttp.Mount` faces the network, and most of what it parses arrives before the application has authenticated the caller. Treat all of the following as attacker-controlled:

- **The request head**: method, path, `Content-Type`, `Connect-Protocol-Version`, the timeout headers (`Connect-Timeout-Ms`, `Grpc-Timeout`), the compression headers (`Content-Encoding`, `Connect-Content-Encoding`, `Grpc-Encoding`, and their `Accept-` forms), and metadata headers, including the base64 `-Bin` forms.
- **Connect unary GET requests**, where the message, its codec, base64 flag and compression arrive in the query string (`message`, `encoding`, `base64`, `compression`, `connect`).
- **Request bodies**: Connect unary bodies, and the enveloped frames of streaming calls and of gRPC and gRPC-Web (a flag byte, a 4-byte length, a payload), including the Connect end-of-stream message and gRPC-Web trailers.
- **Compressed payloads**, which the handler inflates before decoding.
- **JSON payloads**, decoded by `connectproto` through `protojson`.
- **The timing and ordering of the peer's actions**: a client that sends part of a frame and stalls, abandons a stream, opens many streams, or stops reading its response.

A client built with `connecthttp.NewTransport` treats the server as untrusted in the same way: response headers and trailers, error bodies and error details (`Grpc-Status-Details-Bin`, the Connect JSON error), enveloped frames, compressed payloads, and streams that never end.

The documented defences are in the `connecthttp` option docs and `docs/v2-guide.md`. `WithReadMaxBytes` bounds each received message after decompression, defaulting to 4 MiB (4,194,304 bytes) for handlers and clients; it bounds each message, not the stream. Handlers can bound the whole request body with `net/http.MaxBytesHandler`, whose error connect-go maps to `CodeResourceExhausted`. Server interceptors run before any message is read or decompressed, and an interceptor that returns an error without calling `next` must end the call with no payload work; v2 documents this as where authentication belongs. Only a locally authored `*connect.Error` has its message and details serialized: any other error reaches the peer as a bare code, and an error received from a downstream call (marked remote) that a handler returns is scrubbed to `CodeInternal`. Bidirectional streams over HTTP/1.1 are refused with 505.

## Components that matter most / least

Most important, in this order:

1. `connecthttp`: protocol detection and routing in `Mount`, envelope framing (`envelope.go`), the Connect, gRPC and gRPC-Web protocol handlers and clients (`protocol_connect.go`, `protocol_grpc.go`), compression (`compression.go`), timeout and header parsing, error encoding and decoding (`error.go`, `error_writer.go`), and the full-duplex client call (`duplex_http_call.go`).
2. The core in `connect.go`: `Server.Call` dispatch, the interceptor chain, `CallInfo` and header handling, `Error` serialization and the remote-error scrubbing, and `DecodeBinaryHeader`.
3. `connectproto`, `connectgzip` (including its pooled readers and writers), and `connectinprocess`.
4. The code that `protoc-gen-connect-go` emits, checked in under `internal/gen/` and `cmd/protoc-gen-connect-go/internal/testdata/`.
5. `protoc-gen-connect-go` itself, when the input is a hostile schema.

The library does not import `unsafe`; only generated `.pb.go` files do. Memory-safety findings are therefore most likely to come from a data race (`go test -race`) or to sit in a dependency. Report one in a dependency when connect-go's use of it makes it reachable from the network, and show the path. `net/http`, `golang.org/x/net` and `google.golang.org/protobuf` have their own security processes, and a flaw that lies wholly inside one of them belongs there.

Out of scope: `internal/example/`, `internal/memhttp/`, `internal/assert/`, `internal/testdata/`, `docs/`, test files, and CI configuration. The conformance reference client and server under `internal/conformance/` are test fixtures that misbehave on request, so their own behaviour is out of scope; they remain a convenient way to send requests to the library. `cmd/connect-go-v2-migrate` rewrites a developer's own source tree and is out of scope. The gRPC health and reflection packages (`connectrpc.com/grpchealth`, `connectrpc.com/grpcreflect`) and other ecosystem packages live in separate repositories. What an application does inside its handlers, how it authenticates, and how it configures its `http.Server` are the application's concern.

## How to exercise it

The image has only loopback networking, and the commands in this section use only loopback: every module is in the Go module cache, `GOPROXY=off` and `GOTOOLCHAIN=local` are set, and the library, its tests (with and without `-race`), the example and the conformance binaries are already built in `/src`.

- **Tests**: `go test -race -short ./...` (as `make shorttest` runs it) and `go test ./...` for the slow tests. `connecthttp/connect_ext_test.go` holds the end-to-end tests across protocols; `internal/memhttp` gives an in-memory HTTP/1.1 and HTTP/2 server for new tests.
- **A server to attack**: `./.tmp/bin/example-server` serves `connect.ping.v1.PingService` (`internal/proto/connect/ping/v1/ping.proto`) on `localhost:8080` over HTTP/1.1 and cleartext HTTP/2, with default options. `./.tmp/bin/example-client` calls it. `curl` is installed and speaks the Connect protocol directly: `curl -H 'content-type: application/json' -d '{"number":1}' http://localhost:8080/connect.ping.v1.PingService/Ping`. Use `curl --http2-prior-knowledge` for gRPC on cleartext HTTP/2.
- **Other configurations**: to test a non-default option (`WithReadMaxBytes`, `WithRequireConnectProtocolHeader`, `WithCompressors`, `WithCodecs`, `WithConditionalOptions`), an interceptor that rejects calls, or `net/http.MaxBytesHandler`, write a Go test against `internal/memhttp` or `httptest`, as the tests in `connecthttp` do.
- **Conformance**: from `internal/conformance`, `../../.tmp/bin/connectconformance --mode server --conf config.yaml -- ../../.tmp/bin/referenceserver` runs the upstream ConnectRPC suite against the server, and `--mode client -- ../../.tmp/bin/referenceclient` against the client. These cover Connect, gRPC and gRPC-Web on HTTP/1.1, HTTP/2 and HTTP/3 with TLS. Use the suite to check that a proposed patch does not change protocol behaviour.
- **Code generation**: `go test ./cmd/protoc-gen-connect-go/...` exercises the generator against the schemas in its `testdata`.

## How you rate severity

A finding counts when a server or client that uses the documented API can be made to misbehave by its network peer. State the configuration the reproducer needs; a finding against the defaults weighs more than one that needs a limit raised or removed.

- **Critical**: memory corruption or a data race reachable from the network. A request that reaches a handler, or causes a message to be read or decompressed, after a server interceptor rejected it. A response, header, trailer, error or `CallInfo` that is delivered to, or attributed to, the wrong RPC.
- **High**: denial of service that an unauthenticated peer achieves cheaply and that the documented defences are meant to stop. Examples are memory or CPU growth beyond what `WithReadMaxBytes` allows (including through compression), a goroutine or stream leaked after the call ends, and a panic that takes down the process rather than one request. The text of a non-`*connect.Error`, an error cause, or a remote error's message sent to the peer.
- **Medium**: a panic confined to one request that `net/http` recovers. A parsing differential that makes an interceptor or `net/http` middleware see a different procedure, header, deadline or message from the one the handler acts on. A client that a hostile server can exhaust or hang despite its configured limits and context deadline.
- **Low**: a panic, hang or excessive memory use in `protoc-gen-connect-go` on a malformed schema. A defect that needs a non-default option meant for trusted peers, such as `WithReadMaxBytes(0)`.

A deviation from the Connect, gRPC or gRPC-Web specification with no security consequence is a bug and not a vulnerability; do not report it.

## How to report

- Give a reproducer that runs in this image, against `example-server` or the reference server or as a Go test: the exact bytes or `curl` command sent, the server command line, and what was observed. For resource exhaustion, give the measured memory or time against the configured limit.
- Name the protocol (Connect, gRPC, gRPC-Web), the HTTP version, the codec and compression, and any `connecthttp` option or `http.Server` setting that differs from the default.
- Propose a minimal patch against `main` with a regression test. Keep unrelated refactoring out of it.
- Report one root cause once. The same flaw reachable through all three protocols is one finding that lists each path.

## Anything to leave alone

- connect-go does not set `http.Server` timeouts; `ReadHeaderTimeout`, `ReadTimeout`, `IdleTimeout` and HTTP/2 limits are the application's to configure. A slow or idle connection held open against the example server, which sets none, is not a finding.
- The handler honours the timeout a client sends and does not clamp it; a request with no timeout header runs until the handler or the client ends it.
- `WithReadMaxBytes` bounds each message, not a client- or bidi-streaming request as a whole; the documented way to bound the total is `net/http.MaxBytesHandler`.
- On an early error, the gRPC handler closes the request body without draining it, so the connection may not be reused. This is deliberate (see `grpcHandlerConn.Close`).
- Do not report the absence of authentication, rate limiting or TLS in `internal/example` or the conformance fixtures.
