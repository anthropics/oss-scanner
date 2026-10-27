# Threat model

## What this project does and where untrusted input enters
- instancez (`inz`) is a single-binary, Supabase-compatible backend: Postgres plus REST (PostgREST dialect), auth, storage and Node.js code functions, all defined by one `instancez.yaml`.
- Untrusted input: every HTTP request to `/rest/v1`, `/auth/v1`, `/storage/v1`, `/functions/v1` and the dashboard API, including headers (`apikey`, `Authorization`), JWTs, PostgREST query strings, request bodies, uploaded files and OAuth callbacks.
- Trusted: `instancez.yaml`, the function source in `functions/`, environment variables and the operator's database credentials.

## Components that matter most / least
- Most: JWT validation and role selection (`internal/adapter/http` middleware, `internal/adapter/postgres/context.go`, `pool.go`). Every request query must run under `SET LOCAL ROLE` for the role in the validated JWT; RLS is the only authorization layer.
- Most: PostgREST query parsing and SQL building (`where.go`, `select.go`, `crud_handler.go`, `rpc_handler.go`): SQL injection, filter or embed bypass of RLS.
- Most: auth (`auth_handler.go`, `mfa_handler.go`, OAuth): account takeover, token forgery, password reset and session flaws.
- Most: storage access control (`storage_v1_handler.go`): path traversal, bucket policy bypass.
- High: code-function isolation (`internal/adapter/funcs/`), dashboard auth.
- Lower: CLI commands run locally by the operator (`internal/cli`), migrations from a trusted YAML file.
- Out of scope: insecure policies written by the user in their own `instancez.yaml`; third-party dependency bugs that don't affect instancez directly.

## How to exercise it
- A local superuser Postgres is in the image: `service postgresql start`, then `inz dev` from a directory with an `instancez.yaml` (see `instancez.yaml` at the repo root and `docs/site/`). `INSTANCEZ_DATABASE_URL` is already set. The root config needs dummy `INSTANCEZ_ENV_GOOGLE_CLIENT_SECRET` and `INSTANCEZ_ENV_GITHUB_CLIENT_SECRET`. The API listens on :8080.
- Unit tests: `go test -race ./...`. Integration tests (`-tags=integration`) need Docker and won't run offline.
- `test/integration/supabase-js/run.mjs` drives `@supabase/supabase-js` against a running server.

## How you rate severity
- Critical: unauthenticated RLS bypass, SQL injection, auth bypass, JWT forgery, account takeover, RCE.
- High: authenticated RLS bypass or privilege escalation (e.g. `anon`/`authenticated` reaching `service_role`), cross-tenant data access, storage access-control bypass, stored XSS in the dashboard.
- Medium: info leaks (secrets, other users' metadata), CSRF on state-changing endpoints, unauthenticated DoS.
- Low: authenticated DoS, missing hardening headers, verbose errors.

## Anything to leave alone
- `service_role` bypasses RLS by design.
- Two DB logins (owner + `authenticator` with NOINHERIT) are intentional.
- Destructive migrations from a trusted `instancez.yaml` are operator actions, not vulnerabilities.
