# Threat model

## What this project does and where untrusted input enters
- RavenDB is a distributed document database written in C#. It runs as a server (`src/Raven.Server`), as a multi-node
  cluster, or embedded (`src/Raven.Embedded`). It also ships client libraries (`src/Raven.Client`) and a web UI
  (`src/Raven.Studio`, TypeScript, served by the server).
- Untrusted input arrives over the network:
  - the HTTP(S) API: every handler under `src/Raven.Server` (documents, queries, indexes, attachments, counters,
    time series, bulk insert, subscriptions, changes API over WebSocket, import, admin endpoints);
  - the TCP endpoint used for replication, subscriptions and cluster (Rachis) traffic between nodes;
  - optional listeners, off by default: the PostgreSQL wire protocol (`src/Raven.Server/Integrations/PostgreSQL`,
    `Integrations.PostgreSQL.Enabled`) and SNMP (`src/Raven.Server/Monitoring/Snmp`, `Monitoring.Snmp.Enabled`);
  - endpoints that accept unauthenticated clients. Find them by `AuthorizationStatus.UnauthenticatedClients` on
    `[RavenAction]`:
    - the setup wizard (`/setup/*`, which handles certificates, Let's Encrypt and setup packages). Every route except
      `/setup/alive` works only while `Setup.Mode` is `Initial` (see `AssertOnlyInSetupMode`);
    - two-factor authentication (`/authentication/2fa*`) and `/certificates/whoami`;
    - static files and pages served in every mode: `/studio/$`, `/wizard/$`, `/eula/$`, `/2fa/$`, `/auth-error.html`
      and `/`. Their file path handling is pre-authentication surface;
  - endpoints marked `AuthorizationStatus.RestrictedAccess` (`/info/remote-task/topology`, `/info/remote-task/tcp`):
    the router lets certificates that are not registered in the cluster through, and the endpoint authorizes them itself
    (used by pull replication sinks);
  - cross-site requests from a browser that holds a RavenDB client certificate. Browsers send the certificate
    automatically, so the CSRF filter (`Security.Csrf.Enabled`, on by default, `RequestHandler.CheckCSRF`) is a security
    control.
- Attacker-controlled data also includes:
  - JSON documents and request bodies, parsed by the blittable JSON reader in `src/Sparrow` and `src/Sparrow.Server`;
  - RQL query text and parameters (parser and query runner under `src/Raven.Server/Documents/Queries`);
  - JavaScript that non-admin users may submit: patches, JavaScript indexes (allowed for `ReadWrite` users unless
    `Indexing.Static.RequireAdminToDeployJavaScriptIndexes` is set), subscription filters and query projections. It runs
    in the embedded Jint engine;
  - files supplied for import or restore (`.ravendbdump`, backups, snapshots). Import (`POST /databases/*/smuggler/import`)
    is open to `ValidUser` with write access; restore (`POST /admin/restore/database`) needs `Operator`;
  - stored data written by one user and later read or rendered by another, including in Studio;
  - prompts and stored documents that reach AI agents (`/databases/*/ai/agent`, open to `ValidUser`) and AI tasks;
  - data received over replication (`src/Raven.Server/Documents/Replication/Incoming`). Documents, revisions,
    attachments, counters and time series arrive as raw blittable, not JSON, so the receiving side's handling of
    malformed or crafted blittable is attack surface. Treat it as untrusted from anything other than a member of the
    same cluster, in particular a pull replication sink or hub, which may be run by another party.

## Security model
- Secured mode: clients authenticate with X.509 client certificates over TLS. Clearances are `ClusterAdmin`, `Operator`
  and `ValidUser`. A `ValidUser` holds per-database access: `Admin`, `ReadWrite` or `Read`. Certificates can also
  require two-factor authentication; until it is provided they are treated as unauthenticated.
- Cluster members authenticate with `ClusterNode` certificates and are trusted: a node that is already a member of the
  cluster attacking another member is not a boundary. A certificate without `ClusterNode` clearance acting as a cluster
  node is.
- Pull replication sinks authenticate with certificates registered on a replication hub, not in the cluster. Such a
  certificate may only replicate the hub's database within its `AllowedHubToSinkPaths` and `AllowedSinkToHubPaths`.
- Unsecured mode (no server certificate): anyone who can reach the server has full access. This is allowed only from
  the address range in `Security.UnsecuredAccessAllowed` (default `Local`). Escaping that restriction is a bug.
  Authorization findings (which clearance may call what) count only in secured mode.
- Boundaries we care about: unauthenticated to authenticated; `Read` to `ReadWrite`; `ReadWrite` to database `Admin`;
  a user without access to a database reaching that database; a pull replication sink certificate reaching beyond its
  hub's database or allowed paths; a client acting as a cluster node; a web page acting with the certificate of the
  browser that visits it (CSRF, or script injected into Studio); and JavaScript submitted by a non-admin user to the host
  process.
- Database `Admin`, `Operator` and `ClusterAdmin` are trusted with server code (see "Anything to leave alone"), so
  crossing from database `Admin` upwards is not a boundary.
- Sharded databases are in scope. A request on a sharded database is handled by a separate processor (the
  `Sharded*` classes); a check present in the regular processor but missing from its sharded counterpart is a bug.

## Components that matter most / least
- Most:
  - authentication and authorization: `src/Raven.Server/Web`, `RavenServer` connection authentication,
    `RequestRouter` (`CanAccessRoute`, CSRF check), certificate handling, two-factor authentication, and the
    unauthenticated and `RestrictedAccess` endpoints above;
  - HTTP handlers and their processors, the TCP and replication handlers, the cluster (`Rachis`), and the optional
    PostgreSQL and SNMP listeners;
  - parsers: blittable JSON (`src/Sparrow`, `src/Sparrow.Server`), RQL parsing and query execution;
  - the JavaScript sandbox (`src/Raven.Server/Documents/Patch`);
  - import and restore (`Smuggler`, backup restore), encryption at rest and secret handling;
  - unsafe and native code: `src/Voron` (storage engine), `src/Corax` (search engine), and `src/Raven.Pal` (C code
    behind `librvnpal`). The image uses the prebuilt `libs/librvnpal/*.so`; rebuild it with `src/Raven.Pal/make.sh`
    when testing a change to the C code.
- Medium: `src/Raven.Client` (deserializing server responses), `src/Raven.Studio` (stored XSS, token or certificate
  leaks), ETL and sinks, AI integrations.
- Lower: `src/Raven.Embedded`, `src/Raven.TestDriver`, and the admin tools `tools/Raven.Debug` and `tools/rvn`.
- Out of scope: `src/Raven.Quill` and `src/Raven.Quill.Web` (a separate hosted service with its own security model),
  `test/`, `bench/`, the rest of `tools/`, `docs/`, `scripts/`, `docker/`, vendored packages in `libs/`, and third-party
  dependencies (Lucene.Net, Jint, libsodium, zstd, npm packages). Report a dependency issue only if RavenDB's own code
  makes it reachable.

## How to exercise it
- The image has a Debug build of `RavenDB.sln` and all test projects. Tests start an in-process server and need no network:
  `dotnet test test/FastTests/FastTests.csproj --no-build -c Debug --filter "FullyQualifiedName~<Class>"`.
- Use `-c Debug --no-build` (or a plain Debug build after a change), not the Release commands in `AGENTS.md`: there is no
  Release build in the image, and building one from scratch takes far longer.
- Test base classes in `test/Tests.Infrastructure` (`RavenTestBase`, `ClusterTestBase`, `ReplicationTestBase`) create
  stores, secured servers and certificates (`Certificates.SetupServerAuthentication` and related helpers).
- To run a real server: `dotnet src/Raven.Server/bin/Debug/net10.0/Raven.Server.dll --ServerUrl=http://127.0.0.1:8080
  --Setup.Mode=None --License.Eula.Accepted=true`.

## How you rate severity
- Critical: unauthenticated remote code execution; authentication bypass in secured mode, including two-factor
  bypass; escaping the JavaScript sandbox, or getting C# code compiled, to run code on the host from a non-admin user;
  memory corruption reachable by an unauthenticated client; script injected into Studio by a non-admin user that runs
  for a `ClusterAdmin` or `Operator` (it can reach `/admin/console`).
- High: privilege escalation across the boundaries above (for example `Read` writing, or `ReadWrite` reaching admin
  endpoints); reading or writing another database without access; unsecured access from outside the allowed range;
  bypassing the CSRF filter; path traversal or arbitrary file write; memory corruption reachable by an authenticated
  user; leaking certificates, private keys or encryption keys; a remote crash of the server process from a small
  request; denial of service by an unauthenticated client (exhausting memory, CPU, threads or connections before
  authentication); stored XSS in Studio planted by one user that runs for a user with more access.
- Medium: denial of service by an authenticated user (expensive queries, unbounded memory), information leaks that need
  authentication, stored XSS in Studio that runs only for users with the same or less access than the one who planted
  it; prompt injection that makes an AI agent return data the caller cannot read or act beyond its configured tools.
- Low: hardening gaps with no demonstrated exploit.

## Anything to leave alone
- By design, `ClusterAdmin` and `Operator` can run arbitrary code and change server configuration. The admin JavaScript
  console (`/admin/console`, `src/Raven.Server/Documents/Patch/AdminJsConsole.cs`) requires `ClusterAdmin`.
- By design, deploying a C# index runs arbitrary C# code inside the server process, as the OS user the server runs as.
  It needs database `Admin` (`PUT /databases/*/admin/indexes`). The same holds for C# analyzers and sorters (database
  `Admin` per database, `Operator` server-wide). Do not report these as code execution or as privilege escalation.
- Getting a C# index, analyzer or sorter deployed or compiled without that clearance is in scope: for example through
  `PUT /databases/*/indexes` or `POST /databases/*/indexes/test` (both open to `ValidUser`, and meant to accept only
  JavaScript indexes from non-admins), `POST /databases/*/smuggler/import` by a non-admin, or replication.
- Restore needs `Operator`, and a backup carries its database's indexes, analyzers, sorters, scripts and connection
  strings. Applying that content on restore is by design. A crafted backup or snapshot is in scope only for bugs in
  reading the file itself (memory corruption, path traversal or file write outside the target directory).
- Stored XSS in Studio that needs database `Admin` or higher to plant, and self-XSS, are out of scope.
- The output quality of language models used by AI integrations is out of scope.
- Do not report resource use by an authenticated user that a documented limit already bounds: a query that runs until
  `Databases.QueryTimeoutInSec`, a script stopped by `Patching.MaxStepsForScript` or `Indexing.MaxStepsForScript`, a
  query capped by `Query.MaxClauseCount` or `Query.RegexTimeoutInMs`, or subscription connections up to
  `Subscriptions.MaxNumberOfConcurrentConnections`. Report it when such a limit can be bypassed or does not apply to a
  path it should cover, or when the work continues after the limit fires.
- Do not report findings that need an attacker who already controls the server's file system, data directory, settings
  file or command line, or unsecured mode deliberately opened to `PublicNetwork`.
- Do not report missing TLS in unsecured mode on a local development setup.
- SSRF through ETL, backup or connection-string targets that a database admin configures is by design.
