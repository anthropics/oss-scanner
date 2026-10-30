# Nezha Monitoring Dashboard: security review priorities

Scope: `https://github.com/nezhahq/nezha#master` only. The Agent (`nezhahq/agent`) and web frontends in separate repositories are out of source-code scope, but Dashboard interfaces to them are in scope. The scan image leaves source at `/src`, the built Dashboard at `/src/build/nezha-dashboard`, and Go modules in the module cache. Run `go test -mod=readonly ./...` where useful. Do not connect tests to live Dashboard or Agent deployments.

## Assets and trust boundaries

- Dashboard administration, per-user / per-tenant server ownership, OAuth/session/JWT state, API tokens, Agent secrets, notification and DDNS credentials.
- Telemetry and service-check integrity; prompt and accurate alerts are security-relevant when operators rely on them.
- Dashboard HTTP/WebSocket/API and Agent gRPC interfaces ingest network-controlled input. Authenticate *and authorize* every action at the object, server, user and tenant level.
- Dashboard→Agent task paths can reach host shell, terminal, file management, scheduled commands, and NAT; treat an Agent-installed host as a high-impact execution target.
- Stored configuration, file serving, reverse-proxy routing and hostnames must not expose secrets or redirect/forward traffic across boundaries.

## High-priority classes

1. Pre-auth and low-privilege access to files, secrets, sessions, web sockets, admin routes, SSRF and request routing.
2. Cross-tenant or cross-server IDOR / authorization gaps, especially scheduled commands, terminal and file-manager streams, alert/monitor tasks and API-token scopes.
3. Agent identity and result authenticity: prevent an Agent from impersonating another server, forging another user's service results or receiving unauthorized tasks.
4. Untrusted input causing panic, persistent crash loops, resource exhaustion or loss of the combined Dashboard and Agent-control service.
5. Build/deployment defaults that expose secrets or permit insecure Agent transport.

Severity guidance: treat demonstrated pre-auth secret disclosure and cross-tenant command execution as potentially critical; whole-instance loss of monitoring as high-impact availability even where a rating system assigns Moderate. Report realistic preconditions and whether a lower-privilege user, valid Agent secret, exposed Dashboard or special configuration is required. Distinguish a vulnerable current `master` from already-patched historical issues; deduplicate against public GitHub Security Advisories.

For each finding, provide affected commit/version, exact trust-boundary failure, safe local reproduction, impact on Dashboard and monitored hosts, a minimal patch and regression test where feasible. Do not execute payloads against third-party installations.
