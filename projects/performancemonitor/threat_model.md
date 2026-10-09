# Threat model

## What this project does and where untrusted input enters

PerformanceMonitor collects performance data from SQL Server and PostgreSQL servers and shows it to an operator. The repository has these parts:

| Part | Path | What it is |
|---|---|---|
| Darling | `Darling/PerformanceMonitor.Darling.Service` | A headless collector service. It runs as a Windows service or in a Linux container. It writes to a PostgreSQL store and serves a web dashboard (port 5153) and an MCP server (port 5152). |
| Darling store code | `Darling/PerformanceMonitor.Darling.Storage` | Store migrations, roles and grants. |
| Darling Viewer | `Darling/PerformanceMonitor.Darling.Viewer` | A WPF desktop client that reads the store. |
| Lite | `Lite/` | A WPF desktop app. It collects into a local DuckDB and Parquet store in the user's profile and serves a local MCP server (port 5151). |
| Shared libraries | `PerformanceMonitor.Collectors`, `.Common`, `.PlanAnalysis`, `.Analysis`, `.Alerting`, `.Notifications` | The collectors, the statement filter, the plan parser, analysis, alert evaluation, and email and webhook delivery. Darling and Lite both use them. |
| Server-side T-SQL | `install/*.sql`, `upgrades/` | Creates a `PerformanceMonitor` database, procedures and SQL Server Agent jobs on each monitored SQL Server. Used by the deprecated Dashboard. |
| Deprecated | `deprecated/Dashboard`, `deprecated/Installer`, `deprecated/Installer.Core` | The older WPF Dashboard and the CLI installer that runs `install/*.sql`. Bug-fix support only. |

### Where untrusted input enters

1. Data from monitored servers. Treat every value that a monitored server returns as attacker-controlled. A low-privilege user on a monitored server can put chosen text into most of it. This includes:
   - query text and `pg_stat_statements` text
   - execution plan XML, deadlock XML, blocked process report XML and Extended Events data
   - database, object, login and job names
   - SQL Server and PostgreSQL log lines, and setting values

   The code that reads this data:
   - the collectors in `PerformanceMonitor.Collectors` and `Lite/Services/RemoteCollectorService.*.cs`
   - `Darling/PerformanceMonitor.Darling.Service/Targets/`, including the Amazon RDS log, deadlock and plan ingestors
   - the plan parser in `PerformanceMonitor.PlanAnalysis`
   - the PostgreSQL log parsers: `PgServerLogCsvParser.cs`, `PgServerLogJsonParser.cs`, `PgDeadlockLogParser.cs` and `PgPlanLogParser.cs`
2. HTTP requests to the Darling web dashboard: `Mcp/DarlingWebHostService.cs`, `DarlingWebEndpoints.cs`, `Hosting/*.cs`, `Compose/*.cs`, `AlertNotebookEndpoint.cs`, `DarlingTriageEndpoint.cs`, and the single-page app in `wwwroot/`.
3. MCP requests to Darling (`Mcp/DarlingMcpHostService.cs` and the `Mcp/DarlingMcp*Tools*.cs` files) and to Lite (`Lite/Mcp/McpHostService.cs` and `Lite/Mcp/Mcp*Tools.cs`).
4. The store as a channel. Some store roles have fewer rights than the service. These roles write rows that the service later reads and acts on. The rows are saved custom views, custom alert rules, mute rules, monitored server rows, and the `config.config_command` queue that `DarlingCommandExecutor.cs` runs.
5. Configuration files: `darling.json` with its `env:` and `file:` secret references, and the Lite config folder. Lite can also import settings and data from a previous install folder (`Lite/Services/SettingsImport.cs`, `Lite/Services/DataImportService.cs`).
6. Files that a user opens: `.sqlplan` and `.xml` plan files in Lite and the Darling Viewer.
7. Replies from external services. These are the OIDC provider's discovery document and token endpoint (`Hosting/DarlingWebOidc.cs`), and the AWS STS and RDS APIs (`Targets/Aws*.cs`, `Targets/Rds*.cs`).
8. The server-side T-SQL in `install/`. SQL Server Agent runs it on the monitored server. Database names, Extended Events data and query text from that server reach dynamic SQL there.

### Who the attacker is, and the trust boundaries

- An unauthenticated network user. This user can reach a Darling web or MCP port only when the operator adds a `network` block (LAN exposure). The gates are, in order:
  1. a Host header allowlist (the DNS rebinding guard)
  2. an in-app CIDR check against `allowFrom`
  3. for MCP, a bearer token
  4. for the web, a token that becomes an HMAC-signed, HttpOnly, SameSite=Strict session cookie, or an OIDC sign-in

  In managed mode the store can also be exposed. Its gates are `pg_hba.conf` `hostssl` rules for named roles, SCRAM-SHA-256, and TLS that the client verifies in full.
- A holder of the web token, or an OIDC admin seat. This user can read the collected data. This user can also write custom views, custom alert rules, mute rules, server tags, database state overrides and alert dismissals, and can add and edit servers. This user must not be able to:
  - read a stored secret
  - run SQL other than the compiled read queries
  - write outside the role grants
  - make the service read a local file or an environment variable
  - act on a monitored server outside the fixed connection probe
- An OIDC viewer seat. Read-only. `DarlingWebSeat.IsRequestAllowed` refuses every unsafe HTTP method except `POST /api/compose/run`, which compiles read-only queries.
- A holder of the MCP token. This user gets the read tools, `analyze_server`, the custom view tools, the alert tuning tools and the server onboarding tools. No MCP tool runs SQL that the client wrote on a monitored server.
- A malicious monitored server, or a low-privilege user on one. This attacker must not get:
  - code execution in Darling or Lite
  - SQL injection into the store, or into SQL that runs on any monitored server
  - script execution in the web dashboard
  - injection into email, webhook or generated script output
  - a view of a statement that the statement filter withholds
- A low-privilege local user or non-interactive process on the Darling host (another service, a scheduled task, a sandboxed process). This attacker must not read `darling.json` secrets, the store credential files (`pg-*-credential.dpapi` or the `darling-credentials` volume), the password key or the log-hash key. This attacker must not replace files in the install folder.
- The store roles. `darling` owns the store and is the service. `admin` is the operator: it can write `config_command`, monitored servers and notification settings. `viewer` and `mcp` are least-privilege roles. They cannot read the secret columns, and each can write only the tables its surface needs. `Darling/tools/provision-roles.sql` is the authoritative grant list for a store that the operator provisions.

Design decisions that set the boundaries:

- The web and MCP endpoints bind to loopback by default and have no token in that mode. The design treats any local caller of a loopback-only endpoint as the operator. A request that another program sends for an attacker is not the operator. Examples are a web page in a browser (a cross-site request or DNS rebinding) or a local service that fetches a URL the attacker chose. Such a request is in scope. When the operator adds a `network` block, the token is required on every listener, loopback included.
- Darling targets a single-operator host. Interactive users on the Darling host are the operator. `darling.json` and the `admin` and `viewer` credential files are readable by `NT AUTHORITY\INTERACTIVE` on purpose.
- Lite runs as the signed-in user and keeps its data and credentials in that user's profile and Windows Credential Manager. Windows protects one user's profile from another.

These attackers are out of scope: local administrators, SYSTEM, the Darling service account and the store owner. Also out of scope are anyone who can edit `darling.json` or the install folder, a compromised OIDC provider or certificate authority, and physical access.

## Components that matter most / least

Most important first:

1. The Darling web and MCP hosts:
   - `Mcp/DarlingWebHostService.cs` and `Mcp/DarlingMcpHostService.cs`
   - `Hosting/DarlingHostBinding.cs` (the Host allowlist and the bind rules) and `Hosting/CidrAllowList.cs`
   - `Hosting/DarlingWebSeat.cs` (the write gate)
   - `Hosting/DarlingWebOidc.cs` (authorization code with PKCE)
   - `Hosting/DarlingWebTls.cs` and `Hosting/DarlingListenerTls.cs` (TLS fails closed)
   - the `application/json` content-type gate on every mutation route in `DarlingWebEndpoints.cs` (the CSRF defense)
2. Secrets:
   - `DarlingSecretSource.cs` (web and MCP refuse a password that is an `env:` or `file:` reference)
   - `DarlingSecrets.cs` (DPAPI) and `DarlingPasswordKey*.cs` (SQL passwords sealed to a key that only the service holds)
   - `DarlingWebhookSecrets.cs`, `DarlingOwnedSecrets.cs` and `StoreTlsCertificates.cs`
   - `SecretTextGuard.cs` (redaction for logs and the diagnostics bundle)
   - the store role grants
3. The statement filter: `PerformanceMonitor.Common/SensitiveStatements*.cs`, `PerformanceMonitor.Common/Mcp/SensitiveStatementOutputFilter.cs`, `PerformanceMonitor.Collectors/PgSensitiveStatementFilter.cs`, `PgLogTextRedactor.cs`, `PgSettingRedactor.cs`, `PerformanceMonitor.Alerting/AlertStatementFilter.cs`, and `PgStatementTextScrub.cs`. The guarantee: a statement that the pattern names is never stored, returned by MCP or web, sent in an alert, or exported. If the judge times out or cannot parse a value, it withholds the value.
4. SQL that Darling builds from request input: `Compose/ComposeCompiler.cs` with `Compose/MeasureCatalog.cs`, `CustomAlertEvaluator.cs`, `CustomAlertRuleDefinition.cs`, `CustomAlertRuleStore.cs`, `CustomViewStore.cs`, and the server admin routes and tools. The guarantee: identifiers come from a fixed catalog, and every value is a bound parameter.
5. SQL that the product runs on monitored servers: the collectors, `Targets/`, and the command plane in `DarlingCommandExecutor.cs`. Database names are escaped before they reach `[db].sys.sp_executesql`. `execute_actual_plan` takes only a store row identifier and runs the stored query text after the Viewer gets the operator's consent. `Targets/HypotheticalIndexExperiment.cs` runs only `EXPLAIN (GENERIC_PLAN)`, refuses a multi-statement string, and rolls back.
6. Parsers of monitored-server data: plan XML, deadlock and blocked process XML, Extended Events, PostgreSQL logs, and RDS logs.
7. Output rendering. In the web app (`wwwroot/js`), data reaches the page only through `util.el()` and `textContent`, and no code assigns data to `innerHTML`. Email bodies (`PerformanceMonitor.Notifications/EmailTemplateBuilder.cs`), webhook payloads (`WebhookAlertService.cs`) and generated repro scripts (`Mcp/DarlingReproScript.cs`) must escape or quote monitored-server text.
8. Install and upgrade: `Darling/tools/install-darling.ps1`, `upgrade-darling.ps1`, `uninstall-darling.ps1`, and the service's `--harden-files` and `--configure-firewall` verbs. The install script refuses an install tree that an ordinary user can already write to, then locks the folder, `darling.json` and the credential files.
9. Lite: `Lite/Mcp/McpHostService.cs` (loopback only, with the shared `HostHeaderGuard`), `Lite/Services/CredentialService.cs`, the DuckDB queries in `Lite/Services/LocalDataService.*.cs`, and the import paths.
10. `Targets/AwsRoleAllowlist.cs`. If `darling.json` does not list an AWS role, the service does not assume it. This is true for a role saved from the web, MCP, the Viewer or `--add-server`.

Lower priority but in scope:

- `install/*.sql`. SQL Server Agent runs these jobs on the monitored server with the Agent's rights. Dynamic SQL there that a monitored server's data can reach is a privilege escalation inside that server.
- `deprecated/Dashboard`, `deprecated/Installer` and `deprecated/Installer.Core`.
- The WPF user interface code in Lite, the Darling Viewer and `PerformanceMonitor.Ui`.

## How to exercise it

The build image has the .NET 10 SDK on Linux. These projects target `net10.0` and build and run there:

- `Darling/PerformanceMonitor.Darling.Service` (the service, also published as the Linux container in `Darling/Dockerfile`)
- `Darling/PerformanceMonitor.Darling.Storage` and `Darling/PerformanceMonitor.Darling.Analysis`
- `PerformanceMonitor.Collectors`, `.Common`, `.PlanAnalysis`, `.Analysis`, `.Alerting` and `.Notifications`

Lite, the Darling Viewer, the Dashboard, `PerformanceMonitor.Ui`, and the test projects `Darling/Darling.Tests`, `Lite.Tests` and `deprecated/Dashboard.Tests` target `net10.0-windows` with WPF. They compile on Linux only with `-p:EnableWindowsTargeting=true`, and they cannot run there. Read their tests as a specification of the intended behavior. For example, the `SensitiveStatement*` and `StatementFilter*` classes and `SensitiveStatementCorpus.cs` in `Darling/Darling.Tests` show what the statement filter must withhold. `deprecated/Installer.Tests` targets `net10.0`, but most of its classes need a SQL Server.

To run Darling:

1. Build the service with `dotnet publish Darling/PerformanceMonitor.Darling.Service/PerformanceMonitor.Darling.Service.csproj -c Release -o /out/darling`.
2. The service needs a PostgreSQL 16 or later store. TimescaleDB is optional. If the image has PostgreSQL, create a `darling` database and use it as the store.
3. Write a `darling.json` like `Darling/compose/darling.sample.json`. Set `postgres.managed` to `false` and point `postgres.connectionString` at the local store. For a target, add a `servers` entry for a PostgreSQL server, which can be the same local PostgreSQL. Set `web.enabled` and `mcp.enabled` to `true`.
4. Run `dotnet /out/darling/PerformanceMonitor.Darling.Service.dll --config <path to darling.json>`. Run `--validate-config` first to see config errors.
5. With no `network` block, the web dashboard is at `http://localhost:5153/` and MCP is at `http://localhost:5152/`, both tokenless. To test the token, cookie and CIDR gates, add a `network` block with `listen`, `allowFrom` and `token`. Outside managed mode, the service honors that block only in a container, so set `DOTNET_RUNNING_IN_CONTAINER=true`.
6. To act as a malicious monitored server, run statements with chosen text against the PostgreSQL target. The text then appears in `pg_stat_statements`, `pg_stat_activity` and the server log, and the collectors store it. Then read it back through `GET /api/read/...` on the web host and through MCP tools such as `get_pg_top_queries`.
7. `--diag-bundle` exports a diagnostics bundle. It must hold no secret and no withheld statement.

The library code can also be driven from a small console project that references the `net10.0` libraries. Good targets are `SensitiveStatements.Xml`, `SensitiveStatements.Json`, the `Session` type, the plan parser, the PostgreSQL log parsers, and `ComposeCompiler`.

## How you rate severity

Critical:

- An exposed Darling web or MCP endpoint (one with a `network` block) serves a data or write route without a valid token, session cookie or OIDC sign-in. The same applies to a request from an address outside `allowFrom`.
- Remote code execution in Darling or Lite from data that a monitored server returns, or from a web or MCP request.
- SQL of the attacker's choice runs on a monitored server through the product, without the operator's consent step.

High:

- An OIDC viewer seat makes a write. The `viewer` or `mcp` store role reads a secret column or writes outside its grant.
- A web or MCP request makes the service read a local file or an environment variable.
- SQL injection into the store, or into SQL that the product runs on a monitored server. This applies whether the input is a monitored server's data or an authenticated web or MCP request. It includes dynamic SQL in `install/*.sql` that a monitored server's data can reach.
- Disclosure of a secret through any output: web, MCP, logs, the diagnostics bundle, or alerts. Secrets are SQL passwords, store credentials, web and MCP tokens, the session cookie key, the password key, the log-hash key, SMTP and webhook secrets, and the OIDC client secret.
- Disclosure of statement text that the statement filter must withhold. This includes a statement form that carries a credential and that the pattern misses.
- Script execution in the web dashboard from monitored-server data or from a view or rule that another user saved.
- A cross-site request or DNS rebinding attack that causes a write or reads data.
- A low-privilege local user or process on the Darling host reads a credential file or the password key, or writes into the install folder.
- An XML external entity or DTD resolution in any plan, deadlock, blocked process or Extended Events parser.

Medium:

- Denial of service of the collector, the web or MCP host, or the store, from monitored-server data or from authenticated requests. Examples are unbounded memory or CPU, a regular expression that runs past its time budget, or unbounded store growth.
- Injection into email HTML, a Slack, Teams, PagerDuty or generic webhook payload, or a generated repro script, where a person must act before harm occurs.
- An issue that stays inside what a valid token grants, but gets past a limit that the code enforces. Examples are a row cap or a statement timeout.

Low:

- An issue that needs write access to the user's own profile, the Lite data folder, `darling.json`, or the install folder.
- An issue that needs a request to a loopback-only endpoint with no `network` block. The exception is an issue that gets more than the operator role has, such as a stored secret, code execution as the service account, or SQL outside the grants.
- Missing security headers, verbose errors with no secret in them, or timing differences on values that are not secret, with no working exploit.

For `deprecated/Dashboard` and `deprecated/Installer`, report only high and critical findings.

## Anything to leave alone

- Test projects and their fixtures: `Darling/Darling.Tests`, `Lite.Tests`, `deprecated/Dashboard.Tests`, `deprecated/Installer.Tests`. `SensitiveStatementCorpus.cs` and similar files hold fake credentials on purpose.
- `tools/`, `Darling/tools/generate-ladder-fixture`, `docs/`, `community/`, `Screenshots/`, and the CI workflows under `.github/`.
- Sample and placeholder values: `Darling/compose/darling.sample.json` (including its `allowFrom` of `0.0.0.0/0`), `Darling/compose/secrets/README.md`, and the password placeholders in `Darling/tools/provision-roles.sql`.
- These documented design decisions. Report a finding against one of them only if it gets more than the decision allows:
  - The loopback-only web and MCP endpoints have no token. Lite's MCP server is loopback only and has no token. A request that a browser or another local service sends for an attacker is still in scope.
  - DPAPI blobs use LocalMachine scope and an entropy constant that is in the source. The file ACL is the protection. `--print-mcp-token` and `--print-web-token` print the token to an elevated user on purpose.
  - Interactive users on the Darling host can read `darling.json` and the `admin` and `viewer` credential files.
  - The OIDC client does not check the ID token signature. The token comes straight from the token endpoint over TLS, as OIDC Core section 3.1.3.7 allows. The client still checks `iss`, `aud`, `azp`, `exp` and the nonce.
  - The web and MCP endpoints serve plain HTTP unless the operator sets a `tls` block, and the service logs a warning at each start. With a specific `listen` address, the loopback listeners stay HTTP.
  - A plaintext `token` in `darling.json` works, with a warning.
  - The store `admin` role can write `config_command`, monitored servers and notification settings. It is the operator.
  - `add_servers`, server add and edit, and `test_connect` connect to the host that the caller names. That is the onboarding feature.
  - The statement filter withholds statements that can carry a credential. It is not a filter for personal data. Other text that a monitored server returns is stored and shown as collected data.
