# libsoup threat model

## What this project does and where untrusted input enters

libsoup is GNOME's HTTP library: an HTTP client (`SoupSession`) and server (`SoupServer`) supporting
HTTP/1.1, HTTP/2 (through nghttp2), WebSockets, cookies, HSTS, an HTTP cache, content decoding and
sniffing, proxies, and Basic, Digest, NTLM and Negotiate authentication. Its most exposed consumer is
the network process of WebKitGTK, which loads every resource a web page asks for through
libsoup. GStreamer's souphttpsrc, gvfs, evolution-data-server and many GNOME applications use the
client; Rygel and other services embed the server. TLS is provided by GIO (glib-networking/GnuTLS).

**Client side.** Treat everything a server, proxy or on-path attacker of a plain-http connection
sends as hostile:

- status lines, headers and header parameters (`libsoup/soup-headers.c`,
  `libsoup/soup-message-headers.c`, `libsoup/http1/soup-message-io-data.c`);
- HTTP/1 body framing: chunked encoding, Content-Length, connection reuse and keep-alive
  (`libsoup/http1/`);
- HTTP/2 frames, streams, flow control, GOAWAY/RST handling and stream lifetime
  (`libsoup/http2/`). nghttp2 parses the frames, but libsoup's callbacks and state machine are in scope;
- Content-Encoding streams (gzip/deflate, Brotli, zstd) and compression dictionary transport
  (`dcb`/`dcz`, `Use-As-Dictionary`) in `libsoup/content-decoder/`;
- content sniffing of response bodies (`libsoup/content-sniffer/`), which WebKit uses to decide how
  to treat a response;
- multipart responses (`libsoup/soup-multipart-input-stream.c`, `libsoup/soup-multipart.c`);
- authentication challenges: `WWW-Authenticate`/`Proxy-Authenticate` parameters, Digest, NTLM type 2
  messages and Negotiate tokens (`libsoup/auth/`). `SoupSession` enables only Basic and Digest by
  default. Applications add NTLM and Negotiate (WebKit does), and Negotiate is offered only to the
  URIs listed in `SOUP_GSSAPI_TRUSTED_URIS`;
- `Set-Cookie` and cookie policy (`libsoup/cookies/`, public suffix checks in `libsoup/soup-tld.c`),
  `Strict-Transport-Security` (`libsoup/hsts/`), redirects (`Location`) and cacheability headers
  (`libsoup/cache/`);
- WebSocket handshake responses and frames, including permessage-deflate (`libsoup/websocket/`).

**Server side.** Treat everything a client sends to a `SoupServer` as hostile: request lines, headers,
chunked or length-delimited request bodies, `Expect: 100-continue`, `Range`, `Authorization` parsed by
`SoupAuthDomainBasic`/`SoupAuthDomainDigest` (`libsoup/server/`), WebSocket upgrades and frames, and
forms decoded with `soup_form_decode()`/`soup_form_decode_multipart()`. Server-side HTTP/2
(`libsoup/server/http2/`) is opt-in. It is enabled only by the `SOUP_SERVER_HTTP2` environment variable
or a private API. It is in scope, but a report must say it needs that setting.
Upstream libsoup does not recommend using `SoupServer` as a public facing internet server, so
denial of service bugs are not in scope generally.

**Public parsing APIs** that applications call on untrusted strings are in scope even when no network
code is involved. They include `soup_header_parse_list()`, `soup_header_parse_param_list()` and
friends, `soup_headers_parse_request()`/`_response()`, `soup_cookie_parse()`,
`soup_date_time_new_from_http_string()`, `soup_uri_decode_data_uri()`, `soup_form_decode()`,
`soup_multipart_new_from_message()`, `soup_message_headers_get_ranges()` and
`soup_message_headers_get_content_disposition()`.

## Trusted inputs and API contract

- The application is trusted. Bugs that need the caller to break the documented API (wrong lengths,
  freed objects, incorrectly encoded text, unsupported cross-thread use of a `SoupSession`,
  or callbacks that violate their contract) are not vulnerabilities. A `g_return_if_fail()`
  precondition reached only by calling the API wrongly is not a finding either.
- Local state the application owns is trusted. That covers the cookie jar files
  (`SoupCookieJarText`, `SoupCookieJarDB`), the HSTS database and the cache directory index
  (`soup.cache2`). A finding there needs network-originated data that is stored and then corrupts
  memory or policy when it is read back, not a hand-edited file.
- Environment variables (`SOUP_DEBUG`, `SOUP_FORCE_HTTP1`, `SOUP_GSSAPI_TRUSTED_URIS`,
  `SOUP_NTLM_AUTH_DEBUG`, `SOUP_SERVER_HTTP2`) and the `ntlm_auth` helper are trusted.
- `SoupLogger` is a debugging aid. It prints headers and bodies, including credentials, by design.
- Certificate validation itself belongs to GIO/glib-networking. libsoup's use of its result is in
  scope: treating a connection with TLS errors as secure, reusing a connection across different TLS
  or proxy contexts, or mishandling a proxy's `CONNECT` response.

## Security properties beyond memory safety

libsoup is a protocol library, so logic bugs with a security impact count as well as memory errors:

- **Framing and smuggling.** Disagreement about where a message ends (duplicate or conflicting
  Content-Length and Transfer-Encoding, malformed chunk sizes, obs-fold, bare CR or LF, NUL bytes in
  headers) that lets a peer smuggle a request past a proxy in front of `SoupServer`, or poison a
  reused client connection with a response meant for another request.
- **Credential and cookie confinement.** Sending `Authorization`, `Proxy-Authorization` or cookies
  to an origin they were not set for. Examples: across a cross-origin redirect, a downgrade from
  https to http, auth-cache confusion between hosts or between a proxy and an origin, or Digest/NTLM
  downgrade.
- **Cookie, SameSite and public-suffix policy.** A site that can set or read cookies for another
  site, for a public suffix, or ignore `Secure`/`HttpOnly`/`SameSite`/`__Host-` rules leaks
  cross-site state in WebKit.
- **HSTS bypass.** An http load that HSTS should have upgraded, or a policy an attacker can remove
  or shorten from an insecure origin.
- **Resource limits.** libsoup caps header blocks at 100 KiB (`HEADER_SIZE_LIMIT`), multipart part
  headers at 100 KiB, WebSocket frame payloads at 128 KiB by default, and the server's total WebSocket
  message size at 128 KiB. Bypassing a limit, or unbounded memory or CPU from a small input, is in
  scope. Decompressed bodies that libsoup streams to the caller may legitimately be large. Buffering
  them without a limit inside libsoup is a finding.

## Components that matter most / least

- Most important: everything listed under client side, server side and public parsing APIs above,
  especially NTLM and Digest authentication, and the connection manager.
- Important, but less exposed: the cache (`libsoup/cache/`), forms, `SoupServer`'s auth domains and
  path map, and the logger.
- Lower priority: `examples/`, `tests/`, `fuzzing/` and `docs/`. A crash confined to a test helper or
  fuzz harness is not a library vulnerability.
- Third-party code (GLib/GIO, glib-networking, nghttp2, libpsl, Brotli, zstd, zlib, SQLite, GSSAPI)
  is out of scope. libsoup's use of it is in scope: unchecked return values, wrong lengths, lifetime
  errors around callbacks.

## How to exercise it

The checkout is at `/src`. All dependencies are installed, and rebuilding and running the tests need
no network. There are three Meson trees:

- `/src/build`: gcc, debugoptimized, all features (GSSAPI, NTLM through Samba's `ntlm_auth`, Brotli,
  zstd, PKCS #11 tests). It runs the full test suite, including the Apache-backed `auth`,
  `connection` and `proxy` tests.
- `/src/build-asan`: clang, ASan and UBSan, the same features except NTLM, which upstream's ASan CI
  also disables. UBSan's `function` check is off because GObject calls callbacks through cast function
  pointers by design.
- `/src/build-fuzz`: clang, ASan and UBSan, a static libsoup with libFuzzer coverage instrumentation,
  and the fuzzers from `fuzzing/`.

```sh
meson compile -C /src/build-asan
export ASAN_OPTIONS=abort_on_error=1:fast_unwind_on_malloc=0   # full stacks, so leak suppressions match
meson test -C /src/build-asan --print-errorlogs            # whole suite
meson test -C /src/build-asan --print-errorlogs header-parsing-test websocket-test
/src/build-asan/tests/server-test --debug -p /server/...    # one GTest case
```

The tests start their own servers on 127.0.0.1, so they are a good template for a reproducer: copy
the pattern in `tests/test-utils.c`. A raw-socket server or client written in Python is often the
quickest way to send malformed HTTP/1, HTTP/2 or WebSocket traffic. `nghttp`, `nghttpd`, `h2load`,
`openssl s_server`/`s_client`, `socat` and `curl` are installed. `/src/build-asan/examples/get` fetches
a URL with a `SoupSession` (`get -h` lists options). `/src/build-asan/examples/simple-httpd` and
`simple-proxy` are small `SoupServer` programs to point a malicious client at. The image sets
`SOUP_TEST_NO_IPV6=1`, because the scan environment may not have IPv6 loopback. Set
`SOUP_SERVER_HTTP2=1` to enable server-side HTTP/2.

Fuzzers are in `/src/build-fuzz/fuzzing/`: `fuzz_headers_parse_request`,
`fuzz_headers_parse_response`, `fuzz_header_parsing` (parameter lists), `fuzz_cookie_parse`,
`fuzz_date_time`, `fuzz_decode_data_uri` and `fuzz_content_sniffer`. Seeds are in
`/src/fuzzing/corpus/<target>/`, except that the content sniffer's are `/src/tests/resources/`. The
dictionaries are `/src/fuzzing/*.dict`, and `fuzz_header_parsing.dict` also suits the request and
response header targets. `meson test -C /src/build-fuzz --suite fuzzing` gives every target a short
run with its dictionary and seeds. For longer runs, start a target directly. libFuzzer writes new
inputs to the first corpus directory, so put a scratch directory before the seeds:

```sh
mkdir -p /tmp/corpus
/src/build-fuzz/fuzzing/fuzz_headers_parse_response -fork=2 -max_total_time=120 -max_len=4096 \
  -dict=/src/fuzzing/fuzz_header_parsing.dict /tmp/corpus /src/fuzzing/corpus/fuzz_headers_parse_response
/src/build-fuzz/fuzzing/fuzz_cookie_parse -runs=1 /path/to/crash   # replay one input
```

The fuzzers cover only the pure parsers. Message I/O, HTTP/2, content decoding, multipart,
authentication, WebSockets, cookie jar policy and HSTS have no fuzzer. Write a small harness against
`/src/build-asan` or drive them through a real `SoupSession`/`SoupServer` over a socket.

`ASAN_OPTIONS`, `UBSAN_OPTIONS` (halt on error, print a stack trace) and `LSAN_OPTIONS` (the
suppressions in `/src/.gitlab-ci/leak_suppressions`) are set in the image.

## How we rate severity

- **Critical:** memory corruption (out-of-bounds write, use-after-free, double free) reachable by a
  remote peer against a default `SoupSession` configuration, with a plausible path to
  code execution. A hostile web server reaching this in the WebKit network process is the motivating
  case.
- **High:** other remotely reachable memory corruption. An out-of-bounds read that discloses memory to
  the peer. Request smuggling or response-queue poisoning. Leaking credentials or cookies across
  origins. TLS or HSTS handling that silently downgrades a secure load.
- **Medium:** a remotely triggered crash (NULL dereference, abort, stack exhaustion), an out-of-bounds
  read without demonstrated disclosure, a cookie or SameSite policy violation with limited reach, or
  disproportionate memory or CPU use from a small input. The same bug in an opt-in feature (server-side
  HTTP/2, NTLM, Negotiate) is generally one level lower unless the feature is on by default for a major
  consumer.
- **Low:** `g_critical()` warnings reachable from the network with no memory-safety consequence, and
  correctness or RFC-conformance deviations with no security impact. Issues that need the trusted
  inputs listed above, or that are confined to `examples/`, `tests/` or `fuzzing/`, are not findings.

A sanitizer report alone does not establish exploitability. Explain what an attacker controls and
what the observable effect is in a release build. Treat different inputs that reach the same root
cause as one finding.

## Reports and patches

- Give the tested commit, which tree you used, a minimal reproducer (raw bytes, a small Python peer,
  or a GTest case modelled on `tests/`), exact offline commands, and the full sanitizer output or
  backtrace.
- Prefer a small patch that fixes the root cause without changing public API/ABI. Add a regression
  test to the matching `tests/*-test.c`, or a minimized input for parser bugs.
- Patches must pass `meson test -C /src/build` and `meson test -C /src/build-asan`. Follow the
  existing style and use GLib types and helpers.
- libsoup also builds on macOS and Windows/MSVC. Avoid Linux-only or GCC-only constructs in library
  code.
