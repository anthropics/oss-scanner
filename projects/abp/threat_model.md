# ABP Framework

ABP is an open-source framework for ASP.NET Core applications. Its framework libraries and reusable modules implement authentication integration, permission checks, multi-tenancy, persistence, and HTTP APIs used by downstream applications. A flaw in these shared components can affect applications that depend on them.

## Scope and priorities

Scan the public `abpframework/abp` repository on the default development branch, `dev`. Prioritize runtime code in `framework/src/` and `modules/*/src/`, especially:

- `modules/identity/` and `modules/account/`: user and role administration, registration, login, external login, password reset, email confirmation, two-factor authentication, and security stamps.
- `modules/openiddict/`: token issuance and validation integration, grant handling, refresh tokens, client permissions, scopes, and tenant-bound identity.
- `framework/src/Volo.Abp.Authorization*` and `modules/permission-management/`: application-service authorization and user, role, client, and resource permission checks.
- `framework/src/Volo.Abp.MultiTenancy*`, `framework/src/Volo.Abp.AspNetCore.MultiTenancy/`, `framework/src/Volo.Abp.EntityFrameworkCore/`, and `modules/tenant-management/`: tenant resolution, tenant context, repository filters, and separation between tenant and host data.
- `framework/src/Volo.Abp.AspNetCore*`: conventional HTTP APIs, input handling, antiforgery protection, authentication integration, and redirects.

All public source remains available for inspection. Proprietary modules and repositories are not part of this enrollment. Docs, demos, templates, and tests can explain usage or support a reproducer; a finding confined to an intentionally permissive test fixture is not a production vulnerability. Report a template issue when an ordinary generated application actually inherits the insecure behavior.

## Attacker inputs and trust boundaries

Consider unauthenticated remote callers and authenticated users with ordinary privileges, including users in another tenant. Treat HTTP parameters, request bodies, headers, cookies, token requests, return URLs, submitted identifiers, and user-controlled profile fields as untrusted. State the configuration and enabled features needed to reach each entry point.

Tenant selection is not authorization. Distinguish changing a request's tenant context from obtaining another tenant's protected data or privileges. A tenant identifier alone is not a secret. Demonstrate unauthorized access or a protected state change, rather than treating the presence of a tenant selector as a vulnerability.

Framework APIs such as `ICurrentTenant.Change` and disabling a data filter are available to trusted application code. Calling those APIs from arbitrary server-side code is not an attacker capability by itself; show a reachable path that lets an untrusted caller cross a boundary. Host administrators, deployment operators, and installed server-side modules are trusted for their intended powers. Identify an additional privilege gained if a report starts with an administrator account.

Follow the actual authentication entry point through the whole request flow. Password login, external/OIDC login, token grants, and two-factor flows must be assessed separately when they take different branches. Account for middleware ordering, persisted identity state, cookie/token issuance, and permission enforcement on the actual exposed endpoint.

## Build and offline reproduction

The Dockerfile installs .NET 10 and builds selected backend security test projects and their referenced source projects in Debug mode. It also builds the dynamically loaded MVC test plugin, the Account Web/HTTP API and Identity/Permission Management HTTP API projects. Source, build outputs, restored NuGet packages, and SDK tools remain in the image.

Run `abp-oss-test` from `/src` to execute the prepared suites without restore or rebuild. Results are written to `/tmp/abp-oss-results`, or to the directory passed as the first argument. The test suites use in-process hosts and local SQLite/in-memory fixtures; no external database or real account credentials are supplied.

For an individual prepared project, use `dotnet test <project.csproj> --no-build --no-restore --configuration Debug`. For an edited prepared project, use `dotnet build <project.csproj> --no-restore --configuration Debug --disable-build-servers -m:2`. Keep new reproducers within dependencies already cached in the image; do not require network downloads.

The image is a backend audit environment, not a prebuilt deployment of every sample application. It does not prepare Angular builds, browser automation, MAUI workloads, or external cloud/database services. Those limitations describe the available harness, not a blanket exclusion of security issues in public runtime code. Use a self-contained local reproducer when possible and clearly identify any remaining environmental requirement.

## Findings, severity, and patches

For each finding, include the affected commit/branch, exact source locations, the actual exposed entry point, required permissions and configuration, a self-contained reproducer, expected versus observed behavior, and the resulting security impact. Prefer existing test infrastructure with at least two tenants for cross-tenant reports. Use only local test systems and synthetic accounts/data.

Rate severity using demonstrated impact and exploit prerequisites. Unauthenticated code execution, broad authentication bypass, and unauthorized access to protected cross-tenant data deserve priority. Distinguish a complete exploit from a hypothesis, a robustness bug, or a defense-in-depth improvement. Do not assume that normal tenant selection, an intentional trusted-code escape hatch, or a dependency advisory alone establishes a vulnerability.

Provide a small candidate patch and a regression test when available. Do not weaken authorization or tenant isolation, disable antiforgery checks, replace authentication flows, or suppress failing tests to make a reproducer pass. Group findings that share the same root cause; explain distinct exploitation paths in the same report when appropriate.

Send reports privately to the configured security contact. Do not open public issues or publish an unpatched reproducer.
