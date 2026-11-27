# Threat model

## What this project does and where untrusted input enters
- osparc-simcore is a platform for running computational studies (services) in the cloud. It is a monorepo of microservices (services/), shared libraries (packages/) and a Qooxdoo JavaScript frontend (services/static-webserver/client).
- The webserver (services/web/server, aiohttp) exposes the public REST/WebSocket API to authenticated and anonymous users. All HTTP request data (body, query, path, headers, cookies) and WebSocket messages are untrusted.
- api-server (public API, API keys), storage (file/S3 access), payments (webhooks), invitations and dynamic-sidecar/director-v2 (run user-provided service containers) also process data that originates from users.
- User-provided data (study/project documents, service metadata and labels, file names and paths, S3 links, compose specs) is untrusted.
- Users are authenticated; access to studies, services, wallets and files is controlled by product, group and role-based access rights.

## Components that matter most / least
- Most: services/web/server (authentication, authorization, session handling, projects, file access, invitations, payment webhooks), services/api-server, services/storage, services/director-v2, services/dynamic-sidecar, services/dynamic-scheduler, services/catalog, services/payments, services/invitations, and the shared packages they use (service-library, models-library, settings-library, simcore-sdk, postgres-database, service-integration).
- Internal-only services (agent, autoscaling, clusters-keeper, resource-usage-tracker, docker-api-proxy, migration, notifications, dask-sidecar) are in scope, but report them only where untrusted user input can reach them, directly or through another service.
- The frontend (services/static-webserver/client/source) is in scope for XSS and similar client-side issues; it is not built in the image.
- Out of scope: tests, scripts, CI, docs, generated files, vendored/third-party libraries (e.g. qx_libs, qx_packages) and dependency vulnerabilities unrelated to how this code uses them.

## How to exercise it
- Each service has its own virtualenv at /opt/venvs/<name> (e.g. webserver, api-server, storage, director-v2, dynamic-sidecar, service-integration), with the repo packages installed as editable from /src.
- Unit tests that need no external services: services/web/server/tests/unit/isolated (run with /opt/venvs/webserver/bin/python -m pytest). Other services have tests/unit as well, but many need Postgres, Redis, RabbitMQ, S3 or Docker, which are not available.

## How you rate severity
- Authentication bypass, privilege escalation, cross-user/cross-product data access (IDOR), SQL injection, remote code execution, container escape via user-provided specs, SSRF reaching internal services: high or critical.
- Stored/reflected XSS, CSRF and open redirects on authenticated endpoints: medium to high depending on impact.
- Denial of service that requires authentication or heavy resources: low to medium.
- Reports must include a concrete reproducer through a public API entry point.

## Anything to leave alone
- Do not report missing hardening of development-only configuration (docker-compose.devel*.yml), test fixtures or hard-coded test credentials in tests/.
