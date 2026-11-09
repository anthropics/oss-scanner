# Threat model

## What this project does and where untrusted input enters
- osparc-simcore is a platform for running computational studies (services) in the cloud.
- The webserver (services/web/server, aiohttp) exposes the public REST/WebSocket API to authenticated and anonymous users. All HTTP request data (body, query, path, headers, cookies) and WebSocket messages are untrusted.
- Uploaded or user-defined data (study/project documents, service metadata, file names and paths, S3 links) is untrusted.
- Users are authenticated; access to studies, services, wallets and files is controlled by product, group and role-based access rights.

## Components that matter most / least
- Most: services/web/server (authentication, authorization, session handling, projects, storage/file access, invitations, payments webhooks), and the shared packages it uses (packages/service-library, models-library, settings-library, simcore-sdk, postgres-database).
- Less: tests, scripts, CI, docs and generated files. Third-party dependencies are out of scope unless misused by this code.
- Other services under services/ (e.g. storage, director-v2, api-server, dynamic-sidecar) are out of scope for this scan.

## How to exercise it
- The image installs the webserver and packages in /opt/venv.
- Unit tests that need no external services: services/web/server/tests/unit/isolated.
- Tests under tests/unit/with_dbs need Postgres/Redis and are not available.

## How you rate severity
- Authentication bypass, privilege escalation, cross-user/cross-product data access (IDOR), SQL injection, remote code execution, SSRF reaching internal services: high or critical.
- Stored/reflected XSS, CSRF and open redirects on authenticated endpoints: medium to high depending on impact.
- Denial of service that requires authentication or heavy resources: low to medium.
- Reports must include a concrete reproducer through a public API entry point.

## Anything to leave alone
- Do not report missing hardening of development-only configuration, test fixtures or hard-coded test credentials in tests/.
