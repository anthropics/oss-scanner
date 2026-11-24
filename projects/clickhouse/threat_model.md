# ClickHouse threat model

ClickHouse is a column-oriented SQL database server. It is deployed both as a self-hosted server and as a multi-tenant
service, where many mutually distrusting users share one server process. The same binary also works as a command-line
tool (`clickhouse-local`) that processes files of untrusted origin. In-tree references: `/src/SECURITY.md`,
`/src/programs/server/config.xml` and `/src/programs/server/users.xml` (the default configuration), `/src/docs/`.

## What we protect

1. Memory safety and the integrity of the server process: no input that an attacker controls may corrupt memory or
   execute code.
2. Isolation between users: a user sees and changes only what their grants, row policies, settings constraints and
   quotas allow. This includes data of other users, other databases, server files and secrets.
3. Confinement of the server: SQL may reach the filesystem, the network and external programs only through the
   paths, hosts and privileges that the configuration allows.
4. Availability of a shared server: one user cannot take it down for everyone.

## Where untrusted input enters, by attacker position

| Source | Trust | Notes |
|---|---|---|
| Unauthenticated network clients: native TCP protocol (port 9000), HTTP (8123), MySQL (9004) and PostgreSQL (9005) wire protocols, gRPC, Arrow Flight, Prometheus endpoints | Untrusted | Everything before authentication completes: handshakes, authentication methods (password, SSL certificates, Kerberos, LDAP, JWT), HTTP headers, compressed blocks. The default configuration listens on localhost only, but production servers listen on the network. The highest severity. |
| Authenticated users with restricted privileges | Untrusted | The main attack surface. Assume the attacker can run arbitrary queries (`readonly = 1` or `2`, or a narrow set of grants), including every function, table function, format, codec and setting that is available to them. Bypassing grants, row policies, column grants, settings constraints (`readonly`, `allow_ddl`, `<constraints>` in profiles), quotas, `SQL SECURITY` of views, or the masking of secrets is a vulnerability. |
| Data that a user inserts or that a query reads: every input format (`Native`, `RowBinary`, `Parquet`, `ORC`, `Arrow`, `Avro`, `CapnProto`, `Protobuf`, `JSONEachRow`, `MsgPack`, `BSON`, ...), compressed data and codecs, `Native` blocks on the wire, files read via `file`, `url`, `s3`, `hdfs`, `azureBlobStorage` | Untrusted | Treat any byte stream that a parser, a decompressor or a deserializer consumes as hostile. This also applies to `clickhouse-local` reading a file. |
| Metadata of data lakes and external catalogs (Iceberg, Delta Lake, Hudi, Paimon), and responses of external databases and services (MySQL, PostgreSQL, MongoDB, Redis, Kafka, S3, HTTP) that a table or a table function connects to | Untrusted | An attacker may control the bucket or the remote server that a user points ClickHouse to. |
| A server that `clickhouse-client` connects to | Untrusted for memory safety | Memory corruption in the client caused by a malicious server is in scope (lower severity). |
| ClickHouse Keeper client protocol (port 9181) | Untrusted before authentication | Clients authenticated with ACLs may only touch nodes that the ACLs allow. |
| Other replicas and shards of the same cluster, interserver HTTP (9009), the Raft port of Keeper (9234), ZooKeeper/Keeper as used by `ReplicatedMergeTree` | Trusted | These are authenticated by interserver credentials and are expected to be on a private network. Findings that require a malicious replica are not reports. |
| Server administrators: configuration files, users with `access_management`, users with `SYSTEM` or `ALL` privileges, the contents of `user_scripts_path`, `user_defined_path`, data and metadata directories on disk | Trusted | Anything that requires control over these is out of scope: for example, a crafted part on disk, a malicious executable UDF, or a dangerous configuration. |

## What counts as a vulnerability

- Memory corruption (buffer overflow, use-after-free, double free, out-of-bounds read, use of uninitialized memory,
  type confusion) reachable from any untrusted source above, confirmed with the AddressSanitizer build. An
  UndefinedBehaviorSanitizer report needs a demonstrated consequence.
- Termination of the server process (`SIGSEGV`, `std::terminate`, an uncaught exception in a background thread, an
  abort) that a restricted user or an unauthenticated client can trigger: it takes the server down for every user.
- A `LOGICAL_ERROR` exception is a bug, not a vulnerability: in release builds it is an exception that fails only the
  query. Debug and sanitizer builds abort on it, so verify the release behavior before reporting. It counts only if
  it indicates a memory-safety problem that the release build also has.
- Reading or writing files outside `user_files_path` (path traversal, symlinks, globs), reaching hosts that
  `remote_url_allow_hosts` forbids, running programs outside `user_scripts_path`, loading dictionaries or named
  collections without the corresponding privileges.
- Secrets (passwords, keys, tokens, credentials inside table function arguments, engine arguments, dictionary sources
  or named collections) appearing in `system.query_log`, `system.tables`, `SHOW CREATE`, error messages, server logs,
  or query results visible to a user without the `displaySecretsInShowAndSelect` privilege.
- Information leaks between users through shared caches (query cache, query condition cache, mark and uncompressed
  caches), system tables, error messages, timing that reveals data of another user, or skipping indices.
- Authentication bypass and weaknesses: accepting a wrong password, a bypass of `<networks>` restrictions, a flaw in
  certificate or JWT validation, timing attacks on password checks.

## What does not count, or counts lower

- Resource exhaustion by an authenticated user: SQL lets any user run an expensive query, and that is expected. It is a
  vulnerability only when it bypasses a configured limit (`max_memory_usage`, `max_execution_time`, `max_rows_to_read`,
  `max_concurrent_queries_for_user`, quotas, the server memory limit) so that the server crashes or becomes unusable for
  other users, or when one small query causes a disproportionate amount of work that cannot be cancelled. Out-of-memory
  conditions that the memory tracker catches and turns into an exception are expected.
- Server-side request forgery through `url`, `s3`, `remote`, dictionaries and similar features is intended behavior when
  the user has the privilege and the host is allowed. It counts only when it bypasses a grant or
  `remote_url_allow_hosts`.
- Features that are off by default (`allow_experimental_*`, `allow_suspicious_*`, `allow_introspection_functions`,
  non-default server settings): still in scope, but one severity level lower. Name the setting.
- `clickhouse-client` and `clickhouse-local` behavior on the terminal: control characters, escape sequences, history
  files. These are bugs.
- Third-party code in `contrib/` counts only when ClickHouse reaches it with untrusted input. Report it against the
  ClickHouse code path that reaches it. Bugs that need a library to be used in a way ClickHouse does not use it are out
  of scope.
- `tests/`, `utils/`, `docker/`, `ci/`, `docs/`, the build system, and `programs/` other than `server`, `client`,
  `local`, `keeper` and `compressor` are out of scope.
- Known limitations: lack of encryption on ports that the operator configured without TLS; brute-forcing passwords;
  denial of service by flooding the network.

## How to exercise it

The image does not build ClickHouse from source (it takes hours); it contains the binaries that ClickHouse CI built:

- `/opt/clickhouse/release/clickhouse` (also `clickhouse`, `clickhouse-client`, `clickhouse-local`, `clickhouse-server`
  on `PATH`): the release build, as users run it.
- `/opt/clickhouse/asan/clickhouse` (`clickhouse-asan`): AddressSanitizer + UndefinedBehaviorSanitizer. Confirm every
  memory-safety finding with it, for example `clickhouse-asan local --query "..."`.
- `/opt/clickhouse/COMMIT`: the commit the binaries were built from. It can be a few commits behind
  `git -C /src rev-parse HEAD` if CI had not finished the scanned commit; check with
  `git -C /src diff $(cat /opt/clickhouse/COMMIT) HEAD -- <path>` that the code you report on is the same in both.
- The binaries are stripped of debug info to keep the image small: sanitizer reports and stack traces show function
  names, but not file names and lines.
- The git history in `/src` covers only the last 14 days (`git log` stops at a shallow boundary).
- The submodules under `/src/contrib/` are not checked out, to keep the image small;
  `git -C /src submodule status` names the version of each third-party library.

`clickhouse local --query "..."` runs any query without a server, including reading files with `file` and any input
format, so it is the quickest way to test parsers, functions and codecs. `setsid clickhouse server &` started in an
empty directory runs with built-in defaults (native port 9000, HTTP 8123, user `default` without a password and with all
privileges); to test privilege boundaries, create a restricted user with `CREATE USER ... ` and `GRANT`, and connect
with `clickhouse client --user ...` or `curl 'http://localhost:8123/?user=...'`. The SQL tests in
`/src/tests/queries/0_stateless/` show how almost every feature is used; `/src/tests/clickhouse-test <name>` runs one
against a running server. Start
the server with `setsid`: `SYSTEM SHUTDOWN` sends SIGTERM to the whole process group of the server.

## Severity

- Critical: remote code execution, or memory corruption with a plausible path to it, reachable by an unauthenticated
  client or a restricted user in the default configuration; authentication bypass.
- High: other memory corruption reachable from untrusted input; reading or writing arbitrary server files; a bypass of
  grants or row policies that exposes or changes data of other users; disclosure of secrets to a restricted user;
  a server crash that an unauthenticated client can trigger.
- Medium: a server crash or hang that a restricted authenticated user can trigger; bypass of resource limits as
  described above; information leaks of limited scope (existence of objects, metadata); vulnerabilities in features
  that are off by default; memory corruption in `clickhouse-client` caused by a malicious server.
- Low: hardening issues without a demonstrated impact.

Buffer overflows without a demonstrated path to code execution are capped at high.
