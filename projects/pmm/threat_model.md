# Percona Monitoring and Management (PMM) threat model for scanner reports

## Scope

Scan the PMM 3 code in `percona/pmm`: pmm-managed (`managed/`), qan-api2 (`qan-api2/`), vmproxy (`vmproxy/`), pmm-agent (`agent/`), pmm-admin (`admin/`), the API definitions (`api/`) and the web UI (`ui/`). PMM Server also bundles Grafana (a Percona fork), VictoriaMetrics, ClickHouse, PostgreSQL, nginx and the exporters. Their code lives in other repositories and is out of scope; report one only when PMM's own code or configuration in this repository makes it exploitable.

## Trust boundaries

- Browser and API clients reach PMM Server through nginx, which asks pmm-managed's auth endpoint to authenticate each request through Grafana and map its path to a minimum role (`rules` in `managed/services/grafana/auth_server.go`). Paths mapped to `none` need no login. Check that each route's role fits what its handler does, and that path handling cannot reach a stricter route through a looser prefix.
- Roles are Viewer, Editor and Admin. With access control enabled, label-based access control (LBAC) limits which services' data a user sees: vmproxy adds the filters to VictoriaMetrics queries and qan-api2 applies them to ClickHouse queries. A user reading metrics or query analytics outside their filters is a boundary break.
- pmm-managed stores monitored-database credentials (encrypted at rest, `managed/utils/encryption`) and hands them to the pmm-agent that needs them. Backup locations and cloud discovery hold S3 and cloud credentials. Check whether a lower role can read them or make PMM send them to another destination.
- Monitored databases are untrusted. Anyone who can run a query on one controls query text, slow-log and EXPLAIN content, and object names that become metric labels. That data flows through pmm-agent into qan-api2 (ClickHouse) and the UI. Check for injection into ClickHouse queries and for script injection where it renders.
- pmm-agent runs on monitored hosts, holds a long-lived connection to PMM Server, and runs the actions the server sends (`agent/runner/actions`: EXPLAIN, SHOW CREATE TABLE, SELECT and SHOW queries, pt-summary) with the monitoring user's credentials. Actions are available to Viewers. Check that no action input lets a caller run arbitrary SQL or commands on a monitored host. pmm-admin drives the local pmm-agent API (`agent/agentlocal`).
- Advisors are Starlark scripts run in a separate process (`managed/cmd/pmm-managed-starlark`). A script reaching the file system, the network or the host is a sandbox escape.

## How we rate severity

- Critical: unauthenticated code execution on PMM Server or a monitored host; unauthenticated access to stored credentials.
- High: authentication bypass; Viewer or Editor gaining Admin; a non-Admin reading stored credentials; LBAC bypass; arbitrary SQL or commands on a monitored host from a Viewer or Editor; script injection that a monitored-database user can plant and another PMM user triggers.
- Medium: server-side request forgery; script injection that needs Editor; leaks of internal details without credentials or filtered data; denial of service by an authenticated user.
- Low: hardening gaps without a demonstrated impact.
- Admins are trusted to configure PMM. An issue that needs Admin is at most Medium, unless it gives code execution on PMM Server or a monitored host (High).

## Out of scope

- `api-tests/`, `documentation/`, `dashboards/` and `dev/`. For generated code under `api/` (`*.pb.go`, gateway and swagger clients), report the `.proto` definition or the handler instead.
- Known CVEs in Go or npm dependencies and bundled components, unless PMM's code reaches the vulnerable path.
- Attacks that need root on PMM Server or on a monitored host first.
- Findings that rely on this image's development extras (Go and Node toolchains, compilers, debuggers, the checkout in `/src`), which released PMM Server images do not ship.

## How to exercise it

The image is PMM's dev server image: PostgreSQL, ClickHouse, VictoriaMetrics, vmalert, Grafana and nginx under supervisord, with this checkout's pmm-managed, pmm-agent, qan-api2 and vmproxy installed in `/usr/sbin`. It keeps the checkout at `/src`, the Go modules, a warm Go build cache, all binaries in `/src/bin` and the UI's dependencies under `/src/ui`.

- Start PMM Server as the `pmm` user, because PostgreSQL refuses to start as root: `runuser -u pmm -- bash -c '/opt/entrypoint.sh > /tmp/pmm-server.log 2>&1' &`. It is ready when `curl -sk https://127.0.0.1:8443/v1/server/readyz` returns 200, about a minute later. Log in as `admin`/`admin` at `https://127.0.0.1:8443`.
- After a code change, rebuild and restart one service, for example `make -C managed release && install -m 755 bin/pmm-managed /usr/sbin/ && supervisorctl restart pmm-managed`.
- With the server running, the Go tests that need PostgreSQL or Grafana pass from `/src`, for example `go test ./managed/services/grafana/... ./managed/models/...`. UI tests run with `pnpm test` from `/src/ui`.
- There is no MySQL or MongoDB in the image, so tests of the MySQL and MongoDB actions in `agent/runner/actions` cannot run; trace those in source.

## Report requirements

Give the request or monitored-database input that triggers the issue, the lowest role needed, whether access control must be enabled, the observed result, and a proposed patch where possible. Keep a source-level possibility separate from a demonstrated result. Do not include real credentials.
