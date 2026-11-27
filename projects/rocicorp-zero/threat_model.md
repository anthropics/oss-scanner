# Threat model: Zero (rocicorp/mono)

## What this project does and where untrusted input enters

Zero is a sync engine. An app's browser clients keep a local copy of query results that `zero-cache` keeps up to date
as the app's Postgres database changes.

- `packages/zero-cache`: a server that apps run themselves. It replicates from Postgres into a SQLite replica, runs
  client queries incrementally against it, and pushes results to clients over WebSockets. **Clients are untrusted.**
  Everything a client sends is attacker-controlled: the connect URL and headers, auth tokens, cookies, and every
  protocol message (`packages/zero-protocol`), including query ASTs, query names and arguments, and mutations.
- `packages/zero-server`: a library the app runs in its own API server. zero-cache forwards client mutations and named
  queries to it over HTTP; it runs the app's mutators against Postgres. Mutation and query arguments come from
  clients and are untrusted.
- `packages/zql`, `packages/zqlite`, `packages/z2s`: the query engine and its translations to SQLite and Postgres SQL.
  Client-supplied values, column names and AST shapes reach these.
- `packages/zero-client`, `packages/replicache`: the browser client. It trusts the zero-cache it connects to; data
  synced from the server is data written by other, untrusted users of the app.

Trusted: the app's Postgres database and its schema, the app's own API server (`ZERO_QUERY_URL`,
`ZERO_MUTATE_URL`), the operator's configuration and environment variables, and other zero-cache nodes that present
the configured change-streamer secret.

## Components that matter most / least

Most important, all in `packages/zero-cache` unless noted:
- Authentication and authorization: JWT verification (`auth/`), forwarding of auth and cookies to the API server,
  the legacy permission rules applied to client queries and mutations, and per-user/per-client isolation in the
  view-syncer (one user must never receive rows, queries or state belonging to another user or client group).
- The sync protocol handlers (`workers/`, `services/view-syncer`, `services/mutagen`) and the message validation in
  `packages/zero-protocol`.
- SQL generation from client-influenced input: `packages/zqlite`, `packages/z2s`, `packages/zero-server`.
- The admin/debug HTTP endpoints, protected by `ZERO_ADMIN_PASSWORD` (`services/admin-auth.ts` and friends), and the
  change-streamer endpoint used between zero-cache nodes.
- Replication from Postgres (`services/change-source`, `services/replicator`): upstream is trusted, but data in
  replicated rows was written by untrusted users, and table/column names come from the app's schema.

Less important: `apps/` (demo and reference apps), `tools/`, and build/CI scripts. Client-side bugs that
need a malicious zero-cache are low.

## How to exercise it

- The image has Postgres with `wal_level=logical`; local TCP connections need no password. Start it with
  `service postgresql start`, create some tables (`su postgres -c psql`), then run zero-cache:
  `ZERO_UPSTREAM_DB=postgres://postgres@127.0.0.1/postgres ZERO_REPLICA_FILE=/tmp/replica.db ZERO_ADMIN_PASSWORD=admin node packages/zero/out/zero/src/cli.js`.
  It listens on port 4848 (the change-streamer on 4849). `node packages/zero/out/zero/src/cli.js --help` lists every option.
- `apps/zbugs` is a complete app (schema, permissions, mutators, queries) that shows how an app uses Zero.
- Test harnesses (`test/` directories, `*test-util*.ts`) are present; most test cases are not published.

## How you rate severity

- Critical: unauthenticated remote code execution on zero-cache or the app server; SQL injection reachable by any
  client; reading or writing another user's data with no special configuration.
- High: bypass of permission rules or auth checks in a common configuration; one client group affecting another's
  state; reaching admin endpoints without the admin password.
- Medium: cross-user data exposure that needs an unusual configuration; a single client crashing or hanging a
  zero-cache process.
- Low: resource exhaustion that needs many authenticated clients; information leaks in logs or error messages.
- Issues that need control of the operator's configuration, environment, Postgres database, or API server are out
  of scope.

## Anything to leave alone

- Missing rate limiting on its own, and denial of service via expensive queries an app has explicitly allowed.
- Prototype/test code under `apps/` and `tools/`.
