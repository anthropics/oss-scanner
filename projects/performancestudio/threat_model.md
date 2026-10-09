# Threat model

## What this project does and where untrusted input enters

Performance Studio reads SQL Server execution plans (showplan XML), analyzes them, and shows what is wrong. The repository has these parts:

| Part | Path | What it is |
|---|---|---|
| Core | `src/PlanViewer.Core` | The plan parser, the analysis rules, the layout engine, the output writers, the script generators, the SQL Server queries, plan capture, and the credential stores. The next section names the files. |
| Desktop app | `src/PlanViewer.App` | An Avalonia GUI for Windows, macOS and Linux. It opens plan files, connects to SQL Server, runs queries to capture plans, reads Query Store, checks for updates (`Services/UpdateChecker.cs`, `ProxyAwareDownloader.cs`), and can serve a local MCP server (`Mcp/`). |
| CLI | `src/PlanViewer.Cli` | The `planview` command: `analyze` (a plan file or a live server), `credential`, Query Store commands, and an experimental REPL with an MCP surface (`ReplSurface/`). It reads a `.env` file (`EnvFile.cs`). |
| Web viewer | `src/PlanViewer.Web` | A Blazor WebAssembly plan viewer that runs in the browser as a static site. It can share a plan through PlanShare (`Services/PlanShareService.cs`) and load a shared plan from a `?share=` link. |
| PlanShare | `server/PlanShare` | A public ASP.NET Core service that stores shared plans in SQLite, behind nginx. Routes: `POST /api/share`, `GET /api/plans/{id}`, `DELETE /api/plans/{id}`, `POST /api/event`, `GET /api/stats`, `GET /health`. |
| SSMS extension | `src/PlanViewer.Ssms` | A VSIX for SSMS (.NET Framework 4.7.2). It saves the current plan to a temp file and starts the desktop app with it. |
| SSMS installer | `src/PlanViewer.Ssms.Installer` | An elevated installer that installs the VSIX into SSMS. A signed installer installs only a VSIX with the same signature. |

### Where untrusted input enters

1. Plan XML. Treat every plan as attacker-controlled. A plan can come from a file, a paste, a shared link, the SSMS extension, Query Store, or a server. A plan carries query text, object names, parameter values and statistics. Anyone who can run a query on the source server can choose these values.
2. Data that a connected SQL Server returns: Query Store rows, query text, schema and object names, wait statistics, and server metadata.
3. HTTP requests to PlanShare from anyone on the internet: the uploaded plan document, analytics events, and the delete token.
4. A shared plan that the web viewer downloads from PlanShare. Anyone can upload one.
5. MCP requests to the desktop app's MCP server and to the CLI REPL's MCP surface.
6. Local files: `~/.planview/settings.json`, the CLI's `.env` file, saved connections, recent plan lists, and the scratch buffer store.
7. The update check's reply and download.

### Who the attacker is, and the trust boundaries

- An unauthenticated internet user, against PlanShare. PlanShare trusts `X-Forwarded-For` only from the loopback nginx. This attacker must not be able to:
  - read a plan without its ID, or delete a plan without its delete token
  - run code or SQL on the server, or read the visitor salt
  - get past the size limit, the rate limits or the daily upload budget
  - read `/api/stats` when `STATS_TOKEN` is set
- The author of a malicious plan. This attacker gives a plan to a user through a file, a paste, a shared link or a server. The plan must not cause:
  - code execution
  - script execution in the web viewer or in an exported HTML report
  - file reads through XML entities
  - injection into a generated T-SQL script
  - unbounded memory or CPU use
- A malicious SQL Server, or a low-privilege user on one. Values that the server returns must not cause SQL injection in the queries that Performance Studio sends next. They must also not cause any of the effects listed for a malicious plan.
- A local process that calls the MCP server. The desktop app's MCP server is off by default. When it is on, it binds to `localhost`, and it refuses a request whose remote address, `Host` header or `Origin` header is not loopback. Its Query Store tools run a fixed read-only query, and no tool runs SQL that the client wrote. The REPL's MCP surface opens plan files only inside the folders that `McpPlanPathPolicy.cs` allows.
- A low-privilege local user. Credentials live in Windows Credential Manager or the macOS Keychain, in the user's own account. Settings live in the user's profile.

These attackers are out of scope: local administrators, root, and the PlanShare host's operator. Also out of scope is a user who attacks their own profile, files or registry keys, such as the SSMS extension's `InstallPath` key.

## Components that matter most / least

Most important first:

1. PlanShare (`server/PlanShare/Program.cs`, `ClientKey.cs`, `UploadBudget.cs`, `StorageCheck.cs`, `dashboard.html`). It is the only part on the public internet. Share IDs come from a cryptographic random generator, and the ID is the only access control on a shared plan.
2. The plan parser and its limits in `PlanViewer.Core` (`ShowPlanParser*.cs`, `PlanXml.cs`, `PlanXmlPreflight.cs`, `PlanResourceBudget.cs`, `Output/AnalysisJson.cs`). Every other part feeds it.
3. Output that a plan reaches: `Output/HtmlExporter.cs`, the Blazor pages in `src/PlanViewer.Web/Pages`, and the generated scripts in `ReproScriptBuilder.cs`, `ParameterSubstitution.cs` and `DdlScripter.cs`. Plan text must be encoded for HTML, and quoted or escaped for T-SQL.
4. SQL that Performance Studio sends to a server: `QueryStoreService*.cs`, `SchemaQueryService.cs`, `ServerMetadataService.cs`, `SqlObjectResolver.cs`, plan capture (`ActualPlanExecutor.cs`, `EstimatedPlanExecutor.cs`), and the MCP Query Store tools. Names and values that come from a plan or a server must be bound parameters or quoted identifiers.
5. The desktop app's MCP server (`src/PlanViewer.App/Mcp/McpHostService.cs`) and the CLI REPL's path policy (`src/PlanViewer.Cli/ReplSurface/McpPlanPathPolicy.cs`, `OpenedFilePathResolver.cs`).
6. Credential handling: `WindowsCredentialService.cs`, `KeychainCredentialService.cs`, `PasswordResolver.cs`, `EnvFile.cs`, `ConnectionStore.cs`, `EntraInteractiveAuth.cs`.
7. The update check and download (`UpdateChecker.cs`, `ProxyAwareDownloader.cs`, `ProxyHttpHandlerFactory.cs`).
8. The SSMS extension (`AppLauncher.cs`, `ShowPlanHelper.cs`) and the elevated installer's signature check (`src/PlanViewer.Ssms.Installer/Program.cs`).

Lower priority: the analysis rules' wording and scores, the layout engine, and the Avalonia controls that only draw what the parser produced.

## How to exercise it

The build image has the .NET 10 SDK on Linux. Every project except the two SSMS projects targets `net10.0` and builds there.

- `tests/PlanViewer.Core.Tests` is an xUnit project that references Core, the CLI, the desktop app and PlanShare. Run it with `dotnet test tests/PlanViewer.Core.Tests/PlanViewer.Core.Tests.csproj`. It uses real `.sqlplan` fixtures, and it has endpoint tests for PlanShare that set `PlanShare:DataDir` to a temp folder.
- The CLI analyzes a plan file with no server: `dotnet run --project src/PlanViewer.Cli -- analyze <file.sqlplan>`, with `--output text` or the default JSON. Use it to feed hostile plan XML to the parser, the analysis rules and the output writers.
- PlanShare runs on its own: `dotnet run --project server/PlanShare`. Set `PlanShare:DataDir` to a writable folder. `PlanShare:MaxDatabaseBytes` and `PlanShare:DailyUploadBytes` set smaller limits for tests. Send requests to `POST /api/share`, `GET /api/plans/{id}`, `DELETE /api/plans/{id}`, `POST /api/event` and `GET /api/stats`.
- `src/PlanViewer.Web` builds to static files. The HTML that it renders from a plan can be checked through its components, or by loading a shared plan from a local PlanShare.
- The desktop app needs a display. Its MCP server and services can be driven from tests or a small console project.
- The image has no SQL Server. Code paths that need a live server can be read but not run.

## How you rate severity

Critical:

- Remote code execution on PlanShare.
- Code execution in the desktop app, the CLI or the web viewer from a plan or from data a server returns.
- Reading or deleting any shared plan on PlanShare without its ID or delete token.

High:

- SQL injection in a query that Performance Studio sends to a server, reachable from a plan or from data that a server returns.
- Script execution in the web viewer or in an exported HTML report from a plan.
- XML external entity resolution, or a DTD that reads files or makes network requests, in any plan parser.
- Injection into a generated repro, parameter or DDL script, where plan text becomes T-SQL that runs when the user runs the script.
- Disclosure of a password through logs, output, MCP or crash reports. This includes a password from the credential store, the `.env` file or the command line.
- The MCP server accepts a request from a non-loopback address, a non-loopback `Host`, or a non-loopback `Origin`. An MCP client opens a file outside the allowed folders. An MCP tool runs SQL that the client wrote.
- PlanShare stores or shows a visitor's IP address, or the visitor salt leaks.
- The elevated SSMS installer installs a VSIX that does not have the installer's signature.
- An update download that is not checked for the expected source or content.

Medium:

- Denial of service from a plan or a PlanShare request, such as unbounded memory or CPU use or very deep nesting.
- A way past a PlanShare size limit, rate limit, upload budget or storage limit.
- Spoofing the client key on PlanShare to get past a per-client limit.
- Stored script execution in the PlanShare stats dashboard from analytics events.

Low:

- An issue that needs write access to the user's own profile, settings, `.env` file or registry key.
- `/api/stats` readable when `STATS_TOKEN` is not set. That is the documented default.
- Missing security headers, or verbose errors with no secret in them, with no working exploit.

## Anything to leave alone

- Test fixtures and sample plans in `tests/` and `examples/`. They are real or crafted plans on purpose.
- The PlanShare CORS policy that allows every origin. The web viewer is a static site on another origin, and PlanShare has no cookies or other ambient credentials.
- Capture of an actual plan runs the user's query on the server. That is the feature, and the CLI and README say so.
- `--login` and `--password` on the CLI command line, and passwords in a `.env` file. These are documented options for development, and the user chooses them.
- Generated build output, `.github/` workflows, `.signpath/` policies, screenshots, and documentation.
