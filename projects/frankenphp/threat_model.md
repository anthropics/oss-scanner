# FrankenPHP threat model

FrankenPHP is a PHP application server written in Go and C. It embeds the PHP interpreter (ZTS) into Caddy through CGO.

Read `/src/docs/security.md` first: it defines the trust boundaries, FrankenPHP's own attack surface, and what is out of scope.
`/src/docs/internals.md` and `/src/docs/worker.md` describe threads, the CGO boundary, and worker-mode state.

## Untrusted input

The remote HTTP client is the attacker: method, URI, headers, cookies, body, and uploads.
The operator (Caddyfile, environment, `php.ini`, PHP code, extensions) is trusted.
PHP application code is trusted by provenance but consumes tainted request data.

## Components that matter most

- C code in `frankenphp.c` and the CGO calls in `*.go` at the repository root: memory safety, string lifetimes, thread-local state.
- Request to `$_SERVER` mapping (`cgi.go`) and script path resolution (`split_path`, document root joining).
- Isolation between requests, threads, and worker iterations (`worker.go`, `phpthread.go`, `threadworker.go`, `threadregular.go`).
- Caddy module and directives in `caddy/`, including the admin API endpoints.

Out of scope: vulnerabilities in PHP, Caddy, Go, or third-party PHP extensions, and bugs in the PHP test fixtures under `testdata/`.

## How to exercise it

The image is built from `dev.Dockerfile`: PHP 8.5 (debug ZTS build) is installed under `/usr/local`, with `/etc/frankenphp/php.ini`, and the checkout lives in `/go/src/app` (linked from `/src`). GDB and Valgrind are available. Always build and test through `./go.sh`, which sets the cgo flags and build tags; `-DFRANKENPHP_TEST` enables extra C test hooks.

```sh
cd /src
export GOPROXY=off CGO_CFLAGS=-DFRANKENPHP_TEST
./go.sh test -race -count=1 ./...
./go.sh test -run '^$' -fuzz FuzzRequest -fuzztime 60s .
./go.sh -C caddy test -count=1 ./...
./go.sh -C caddy/frankenphp build -buildvcs=false
./caddy/frankenphp/frankenphp php-server --root testdata --listen 127.0.0.1:8080
```

`testdata/` holds PHP scripts and worker scripts used by the tests; reproducers can be added there.

## How we rate severity

- Critical: remote, unauthenticated memory corruption with a credible path to code execution; executing a file outside the document root or a file the operator did not intend to serve.
- High: memory corruption without a demonstrated exploit, request data or headers leaking to another client's request (including through worker mode), header/CRLF injection or request smuggling introduced by FrankenPHP.
- Medium: remote crash of the whole process, or denial of service with a significant amplification factor.
- Low: denial of service needing sustained traffic, information disclosure of non-sensitive internals.

State persistence documented in `docs/worker.md` (static variables, globals, `$_ENV`, `ini_set()`) is expected behavior, not a vulnerability, unless FrankenPHP fails to reset what the docs say it resets.

## Reports

Include a minimal reproducer, preferably a Go test using the helpers in `frankenphp_test.go` with a PHP script in `testdata/`, and the patch.
