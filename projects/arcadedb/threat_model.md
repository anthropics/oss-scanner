# Threat model

## What this project does and where untrusted input enters
- ArcadeDB is a multi-model database (graph, document, key/value, time series, vector) written in Java 21. It runs embedded
  (engine module) or as a server (server module).
- Untrusted input arrives over the network once the server runs: the HTTP/JSON API (`/api/v1/...`, including `command`,
  `query`, `batch`, import and backup endpoints), the Postgres, Redis, MongoDB, Bolt, gRPC, Gremlin and GraphQL wire
  protocols, the MCP endpoint, the WebSocket event bus, and the Raft HA transport between cluster nodes.
- Query text (SQL, OpenCypher, Gremlin, GraphQL, MongoDB and Redis commands) is attacker-influenced when the caller is an
  authenticated but low-privileged user. Stored data, imported files (CSV, JSONL, GraphML, GraphSON) and backups are
  also untrusted.
- Authentication and per-database, per-type authorization (users, groups, type ACLs) are security boundaries.

## Components that matter most / least
- Most: `server` (HTTP handlers, authentication, security, API tokens), every wire protocol module (`postgresw`, `redisw`,
  `mongodbw`, `bolt`, `grpcw`, `gremlin`, `graphql`, `mcp`), `ha-raft` and `network`, and `engine` (query engines,
  scripting/polyglot, importers, file and page handling, serialization).
- Least: `console`, `integration`, `metrics`, `tracing`, `bindings`, `examples`, `studio` (a static jQuery webapp; report
  only XSS or token leaks that are exploitable from stored data).
- Out of scope: `e2e*`, `load-tests`, `k8s`, `docs`, third-party code under `node_modules` and vendored libraries.

## How to exercise it
- Embedded: `com.arcadedb.database.DatabaseFactory` in the engine module. Server: `com.arcadedb.server.ArcadeDBServer`
  (`bin/server.sh` in a distribution). Test fixtures in `server/src/test` start a server on a free port and show how to
  authenticate (user `root`, set via `-Darcadedb.server.rootPassword=...`).
- Unit tests live under each module's `src/test/java`; the build has run `mvnw install -DskipTests`, so artifacts and test
  dependencies are already in the local Maven repository (offline).

## How you rate severity
- Critical: unauthenticated remote code execution, or an authenticated low-privilege user reaching code execution on the
  host (scripting sandbox escape, arbitrary class loading, arbitrary file write).
- High: authentication bypass; authorization bypass that reads or writes another user's database or type (including via
  secondary paths such as batch, async, import, wire protocols or replication); path traversal outside the database
  directory; SSRF from importers or `LOAD CSV`; leaking secrets or tokens; memory corruption or an unauthenticated remote
  crash or unbounded memory exhaustion from a small request.
- Medium: DoS by an authenticated user with expensive queries, missing resource limits that need privileges to trigger.
- Low: hardening gaps with no demonstrated exploit.

## Anything to leave alone
- A user holding the `root` or admin role can run arbitrary SQL, scripts and configuration changes by design.
- Do not report missing TLS on a default local development setup, or findings that require an attacker to already control
  the server's filesystem or JVM flags.
- Prior advisories covered authorization gaps on non-primary code paths, scripting sandbox escapes, path traversal, SSRF in
  importers and token leaks; look for siblings of those classes before reporting anything exotic.
