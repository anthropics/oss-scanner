# BTCPay Server Plugin Builder threat model

This project hosts the public BTCPay Server plugin directory, publisher and administrator interfaces, and plugin build and publication service. It accepts repository references and executes repository-controlled code, including MSBuild targets, to produce downloadable plugin packages. A private build broker owns Docker access and runs checkout, compilation, proxying, staging, and cleanup in separate disposable sandboxes.

## Components and trust boundaries

Prioritize `PluginBuilder/`, `PluginBuilder.BuildBroker/`, `PluginBuilder.Builds/`, the worker scripts under `PluginBuilder/`, and the root Dockerfiles. The intended architecture is documented in `docs/build-isolation.md`; use it to establish the supported production configuration and expected isolation guarantees.

The public web application holds database, storage, and broker credentials. It checks user permissions, accepts build requests, records state, and publishes artifacts. It must not receive a Docker socket. The private broker is trusted and privileged: Docker access gives it control of its host. It receives fixed build parameters through an authenticated internal API and must not accept arbitrary Docker commands, mounts, or runtime settings from clients.

Submitted repositories, build outputs, build logs, plugin metadata, uploaded files, external identity proofs, and unauthenticated HTTP requests are untrusted. A publisher controls its own repository and can execute arbitrary code inside its assigned build sandbox; that execution is an intended feature. Demonstrate a path to another tenant, host or broker privileges, application credentials, persistent cross-build influence, or unauthorized publication to establish an isolation failure.

Checkout and compilation run in separate containers with private per-build files and caches. Their network access goes through a restricted proxy. Output staging runs separately without network access after the worker is removed. The broker and application validate and copy the result into private storage before publication. An artifact hash proves byte integrity, not that the plugin's code is safe to install.

## Security priorities

- Authentication, password reset and two-factor flows, publisher and administrator token scope and revocation, CSRF protections, account suspension, and ownership checks on every operation.
- Cross-user and cross-plugin access, ownership transfer, build admission, whitelists, moderation, release/version mapping, and unauthorized replacement or publication of artifacts.
- Broker authentication, lease and generation handling, fixed Docker policy, cancellation, restart recovery, fail-closed readiness and cleanup, and bounded handling of logs and artifacts.
- Sandbox filesystem and network isolation, secret exposure, source checkout validation, environment and command argument handling, per-build cache isolation, path traversal, symlinks, hard links, special files, archive contents, and attacker-controlled staging output.
- Server-side requests, redirects, webhook destinations and signatures, external identity verification, uploaded images, rendered metadata and logs, and access to private or cloud metadata endpoints.
- Resource exhaustion that a realistic anonymous caller, publisher, or submitted build can use to disrupt other users or exhaust broker, database, disk, memory, or artifact storage resources.

Administrators, deployment operators, and holders of the private broker's production token have the privileges documented for their roles. Explain any unintended expansion of those privileges. Development options such as `PB_CHEAT_MODE`, local artifact proxying, and the local `runc` configuration intentionally weaken production protections; assess the production defaults and state any required configuration. Do not equate the intended execution of plugin build code with host code execution.

## Build and offline reproduction

The scanner image contains the source at `/src`, the .NET 10 SDK, restored NuGet dependencies, and Debug build outputs for the public application, build broker, shared contracts, test assembly, and network canary fixture. Bash, Python, Git, jq, OpenSSL, and standard filesystem utilities are available for reproductions.

Run `btcpayserver-plugin-builder-oss-test` for existing standalone tests covering broker authentication and protocol validation, remote build clients, sandbox lifecycle and cleanup with fake Docker processes, executor state and configuration, process handling, staging contracts, request validation, webhook policy, identity verification, email formatting, and API documentation. The wrapper excludes `Category=ExecutorIntegration`, has a fifteen-minute timeout, and uses `--no-build --no-restore`. Loopback HTTP servers and temporary files remain available with external networking disabled.

After changing code, rebuild with `dotnet build btcpayserver-plugin-builder.sln --no-restore --configuration Debug`. Run individual tests with `dotnet test PluginBuilder.Tests/PluginBuilder.Tests.csproj --no-build --no-restore --configuration Debug --filter '<test filter>'`.

No PostgreSQL, Azure/Azurite storage, Mailpit, browser installation, live broker, Docker socket, gVisor runtime, or production credentials are provided. Database, UI, live build, and network-canary integration tests need the additional infrastructure described in `PluginBuilder.Tests/README.md` and the CI workflow. Use the existing fake HTTP and Docker fixtures for offline reproducers. Do not connect to the production service, build hostile plugins on a real host, or infer that fake Docker tests prove kernel or runtime isolation.

## Findings and severity

Assess severity by demonstrated attacker authority and impact. Unauthenticated compromise, a sandbox escape to the host, exposure of production credentials, or unauthorized replacement of widely consumed plugin packages can be critical when reachable. Rate narrower tenant isolation failures, scoped credential disclosure, persistent script injection, SSRF, and denial of service according to their actual reach and prerequisites. Bugs confined to a dependency or runtime need an affected, reachable path in this deployment; distinguish failures in this repository from vulnerabilities solely in Docker, gVisor, or an installed plugin.

Include the affected commit and source locations, attacker-controlled input, user role, required deployment options, entry point, a self-contained reproducer, expected versus observed behavior, and concrete impact. Use disposable fixtures and dummy credentials, group symptoms with one root cause, and propose a minimal patch and regression test where practical.

Disclose findings privately through the configured GitHub security advisory or security email channel. Do not open public issues or publish unpatched reproduction details.
