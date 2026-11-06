# Threat model

## What this project does and where untrusted input enters
Fortio is a load testing tool and library (HTTP/1.1, HTTP/2, HTTPS, gRPC, TCP, UDP) that runs as a CLI (`fortio load`, `curl`, `nc`, ...) or as a server
(`fortio server`) combining an echo/debug server, a web UI + REST API to launch and view load tests, a TCP/UDP echo, a gRPC ping server, and an HTTP
proxy/multi-forwarder. It is used in production for A/B load testing and validation, typically inside private networks and clusters, and is not meant to be
exposed directly to the Internet; hardening it anyway is the goal of this scan.

Untrusted input comes from:
- Network clients of `fortio server` (HTTP/HTTPS/gRPC/TCP/UDP ports): URL paths and query parameters (e.g. `/echo?size=&status=&delay=&headers=`, `/fortio/` UI and
  `/fortio/rest/*` REST API), request headers and bodies, and the TLS/mTLS layer.
- Responses from servers under test (headers, bodies, redirects, gRPC replies, JSON) parsed by the clients and the load runners.
- Saved JSON results files loaded by the UI/`report` mode, and files/URLs given as flags.

## Components that matter most / least
Most: `fhttp` (server, client, forwarder/proxy, utilities), `ui` and `rapi` (web UI and REST API, path handling, templates, file access under the data dir),
`fnet` (sockets, DNS, TCP/UDP echo), `fgrpc`, `jrpc`, `cli`, `dflag` (dynamic flags endpoint), `stats`/`histogram` (parsing of results), `grol` (embedded scripting
language for the `grol` command).
Less: `periodic`, `log`, `metrics`, `version`, `release/`, `docs/`, `debian/`, and test code. Third-party code in go.mod is out of scope except where fortio
misuses it (a vulnerable dependency version reachable from fortio is in scope).

## How to exercise it
- The binary is `/usr/local/bin/fortio`; source is in `/src`. `fortio server` listens on 8080 (HTTP + UI at `/fortio/`), 8079 (gRPC), 8078 (TCP echo), 8081
  (redirect). Use `fortio server -data-dir /tmp/fortio-data` and `fortio help` for flags. Talk to it with `curl`, `nc`, `fortio load/curl/grpcping/nc`.
- `go test -tags netgo -race ./...` in `/src` runs the unit tests (certs are in `/src/cert-tmp`).
- `Webtest.sh` in the repo shows how CI drives a running server: e.g. `fortio server -ui-path /newprefix/ -maxpayloadsizekb 8 -pprof`, load tests
  launched through the UI fetch proxy (`/newprefix/fetch/<host>/...?url=...&load=Start&json=on`) and `rest/run`, `echo?size=`, secure gRPC with `-cacert -cert -key`
  (certs from `cert-gen` in `/src/cert-tmp`), and `fortio report` mode (limited UI, no pprof). Its steps that reach www.google.com / grpc.fortio.org cannot run offline.
- There is no Internet in the audit; use localhost servers (including a second fortio server as the target of load tests).

## How you rate severity
- By design, the UI/REST API can make the server send requests to arbitrary URLs and run load tests at configurable rates (it is a load generator). Reaching an
  arbitrary target through those features is not a vulnerability by itself. It is when a protection that exists is bypassed (e.g. the max payload size limit, TLS/mTLS
  settings, dynamic flags and pprof being off by default) or when it leads to something beyond the documented feature.
- Remote code execution, arbitrary file read or write outside the data dir, path traversal, memory-unsafe behavior, auth/TLS verification bypass: high to
  critical (critical when reachable pre-auth on a default `fortio server` configuration).
- Panics/crashes or unbounded memory/CPU from a single small request to `fortio server`: medium (high if it is not recoverable, i.e. kills the process).
- Reflected/stored XSS in the UI or echo output: medium to high depending on whether it needs unusual flags; echo-style endpoints reflecting content by design are
  not XSS by themselves unless a browser would render it as HTML with an HTML content type.
- Issues requiring local control of flags, the command line, or the filesystem, and DoS by merely asking the load generator to generate load: low or out of scope.
- Vulnerable dependencies: report only if the vulnerable code path is reachable from fortio.

## Anything to leave alone
- Insecure-by-design options that the user must opt into (`-k`/`-https-insecure`, `-curl-stdout-headers`, `-pprof`, `-allow-initial-errors`, plain HTTP).
- Test certificates and keys in the test suite and the `cert-gen` script.
- Style, lint, and missing hardening headers on endpoints meant for debugging.
Reports with a reproducer (a curl command or small Go test) and a proposed patch are most useful.
- the web UI is meant to be protected from untrusted user access so triggering scans or passing invalid form input isn't really a threat

