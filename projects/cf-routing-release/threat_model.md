<!-- threat_model.md for cloudfoundry/routing-release. Free text; the scanner reads it before it starts. -->
# Threat model — routing-release

## What this project does and where untrusted input enters
routing-release is the Cloud Foundry networking release: the layer that routes external traffic to
application instances and platform components. Its Go source lives in one vendored module at
`src/code.cloudfoundry.org`. The components and their trust boundaries:

- **gorouter** (`gorouter/`) — the platform's HTTP(S) ingress. It terminates TLS and parses, routes, and
  forwards **untrusted HTTP requests arriving from the public internet** to backends. This is the primary
  attack surface: request/header parsing, `X-Forwarded-For`/`X-Forwarded-Proto` handling, host/route lookup,
  WebSocket upgrades, keep-alive and request-smuggling concerns, TLS handling to both client and backend, and
  any header the router adds, trusts, or forwards. **Treat all client-supplied request data as hostile.**
- **cf-tcp-router** (`cf-tcp-router/`) — programs HAProxy for TCP routing. It consumes routing data from the
  control plane and renders configuration; the untrusted edge is the TCP traffic it fronts and any
  externally-influenced routing data.
- **routing-api** (`vendor/code.cloudfoundry.org/routing-api/`) — the control-plane REST API for route/router-group
  registration. It is **vendored** from the separate `cloudfoundry/routing-api` repository but routing-release still
  compiles and ships it as a binary, so it is in scope here. Callers authenticate via UAA-issued OAuth tokens, so
  this is **post-auth** surface: authorization checks, token scope enforcement, and input validation on route
  payloads matter most.
- **route-registrar** (`route-registrar/`) — a co-located agent that registers component routes over NATS.
  Its input is local configuration and platform messaging, not direct internet traffic.
- **routing-api-cli / rtr** (`routing-api-cli/`) — an operator CLI client.

## Components that matter most / least
- **Most:** `gorouter/` — internet-facing, pre-auth, high request volume.
- **High:** `routing-api/` (post-auth control plane) and `cf-tcp-router/`.
- **Lower:** `route-registrar/`, `routing-api-cli/`.
- **Out of scope:** `routing-acceptance-tests/` and other `*_test`/assets trees — these are test harnesses that
  require a live Cloud Foundry/BOSH deployment and are not shipped as attack surface. Vendored third-party code
  under `vendor/` is in scope only where routing-release's own use of it creates the vulnerability.

## How to exercise it
The build (see the Dockerfile) compiles every component with full debug info and warms the Go build/test
caches, so `go build ./...`, `go vet ./...`, and the pure-unit `go test` packages run fast and offline.
The integration and `cmd` suites (e.g. `gorouter/integration`, `cf-tcp-router/cmd/...`,
`route-registrar/integration`) are **not runnable in the scan environment and are not expected to be**: their
Ginkgo `BeforeSuite` bootstraps external components (NATS, HAProxy, Consul) and fixture binaries that the
networkless audit VM does not provide. Audit the source directly; do not treat these suites as executable.

## How you rate severity
- Anything in **gorouter** that lets an unauthenticated remote client bypass routing/authorization, reach a
  backend they should not, smuggle or desync requests, spoof `X-Forwarded-*` trust, or crash/OOM the router
  (platform-wide DoS) is **high or critical** — critical if it crosses a tenant/app isolation boundary or
  enables request forgery to internal components.
- Memory-safety or panic-on-input bugs reachable from untrusted request data are **high** at minimum (DoS),
  escalating with blast radius.
- Post-auth issues in **routing-api** (authz bypass, privilege escalation across router groups) are
  **high**; input-validation bugs with limited impact are **medium**.
- Plain DoS requiring authentication, or issues needing local/operator access, are **medium** or below.

## Anything to leave alone
- Do not report findings that require a live, misconfigured, or attacker-controlled BOSH deployment to reach.
- Do not report issues solely in the acceptance-test code or test fixtures.
