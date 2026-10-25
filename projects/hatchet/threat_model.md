# Hatchet threat model for scanner reports

Hatchet is a multi-tenant durable task queue and workflow engine on Postgres. Workers run user code and take tasks from the engine over gRPC; a REST API and a React dashboard manage tenants, runs, events, webhooks and API tokens. Hatchet Cloud runs this engine for many customers with open signup, so any tenant account is low privilege.

## What matters
- Tenant isolation comes first: a user or token of one tenant reading, changing or disrupting another tenant's data, runs or workers. On gRPC the token fixes the tenant and every ID in the request comes from the caller.
- Then authentication (API tokens, sessions, OAuth, invites), roles in `api/v1/server/authz/rbac.yaml` and per-member payload access, SSRF from tenant-supplied URLs (serverless delivery), CEL evaluation in the engine, and XSS from task data in the dashboard.
- Unauthenticated callers reach login, registration, OAuth, incoming webhooks and SNS ingestion.
- The SDKs and `cmd/hatchet-cli` are lower priority; the SDKs trust the engine. Leave out `examples/`, `hack/`, `frontend/docs/`, load-test and test code, and generated code.

## How to exercise it
- `hatchet-services` starts Postgres (`127.0.0.1:5431`, user/password/db `hatchet`, migrated) and RabbitMQ. `hatchet-server` also starts the API (`http://localhost:8080`) and engine (gRPC `127.0.0.1:7070`, plaintext), seeds `admin@example.com` / `Admin123!!` with tenant `707d0855-80ab-4e1f-a156-f1c4546cbf52`, and writes its API token to `/tmp/hatchet/token`. Logs are in `/tmp/hatchet/`; settings, including the opt-in features (serverless delivery, streams, operators, OTLP), are in `/src/.env`.
- For a second tenant, register a user and create a tenant through the API, then `set -a; . /src/.env; set +a; hatchet-admin token create --tenant-id <id>`. Session cookies are set for `localhost`, not `127.0.0.1`.
- Go: `go test ./pkg/...`; with services up, `go test -tags integration ./...` (it leaves tenants in the `hatchet` database). Tests using testcontainers need Docker and fail here. SDKs: `poetry run pytest tests/unit` in `sdks/python`, `pnpm run test:unit --forceExit` in `sdks/typescript`.
- Keep `SERVER_SECURITY_CHECK_ENABLED=false` in any server you start, or it calls `security.hatchet.run`.

## How we rate severity
- Critical: RCE on the API or engine; acting as any user or tenant without credentials; forging API tokens or recovering the keysets; unauthenticated access to another tenant's task data.
- High: one tenant reading or changing another's task data, events, secrets or runs, with IDs the attacker can get; account takeover; a member gaining admin or owner; SQL injection; stored XSS in another user's session; SSRF that returns internal or cloud-metadata responses.
- Medium: cross-tenant access that needs the victim's random UUIDs; degrading another tenant's service through a logic bug; another tenant's metadata without task data; a viewer acting as a member, or reading payloads without payload access; blind SSRF or internal port probing.
- Low: bypassing an existing limiter; hardening gaps with a demonstrated impact.
- Rate by what the finding reaches, including any pivot; drop one level if it also needs winning a race. Say the attacker's role or token and the settings needed.

## Leave alone
- Intended: a tenant token has full access to its own tenant; owners, admins and self-host operators are trusted with what they control; workflow code runs on workers, not the engine; dev settings (`SERVER_GRPC_INSECURE`, `SERVER_AUTH_COOKIE_INSECURE`, `SERVER_SERVERLESS_OPERATOR_INSECURE_DESTINATIONS`, `authdisabled` builds and their committed keyset, the seeded admin, `hack/`, docker-compose files).
- Volume-based DoS and missing rate limits, missing headers or cookie flags, self-XSS, clickjacking, dependency CVEs without an exploit through Hatchet code, and attackers with database, queue, disk or memory access.

Reports: give the route or gRPC method, attacker role, reproducer (a script against `hatchet-server` or a Go test), observed result and a patch at the point of enforcement; say whether sibling routes or the other API version share the gap.
