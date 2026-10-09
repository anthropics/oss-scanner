# ZenML threat model

## What ZenML is and how it is deployed

ZenML is an open-source framework for building and running ML and AI pipelines. It has two halves:

- **The client**: the `zenml` Python package and CLI. Users write pipelines (Python functions decorated as steps), and the client runs them on a "stack" of infrastructure they configure (an orchestrator such as Kubernetes, an artifact store such as S3, and so on).
- **The server**: a FastAPI application (`src/zenml/zen_server/`) backed by a SQL database (SQLite or MySQL, `src/zenml/zen_stores/`). It stores pipeline and run metadata, stack configurations, users, API keys, secrets and service connector credentials. Teams self-host it with Docker or Helm, often reachable from the public Internet or a company network. The same server code also underlies ZenML's hosted commercial product.

The server is the most important thing to audit. One compromised server exposes every team member's secrets and cloud credentials. Many self-hosted servers have a single user or a small team, so for most deployments the realistic attacker is someone with network access and no account, which is why they come first below.

## Who the attacker is

In priority order:

1. **An unauthenticated network client** who can reach the server's HTTP port. They should only be able to reach the health, info and login/device-authorization endpoints (and the dashboard's static files, which are not in this repository).
2. **An authenticated, non-admin user** of a shared server. See the next section for what they may and may not do.
3. **A third party sending webhook requests** to `src/zenml/webhooks/` and `routers/webhook_endpoints.py`. Request bodies are untrusted until their signature is verified.
4. **A malicious page in the user's browser** attacking a logged-in user through cookies (CSRF, see `zen_server/csrf.py`).

## What the open-source server deliberately allows

The open-source server has users and an admin flag, but **no per-resource permissions**. The permission helpers in `src/zenml/zen_server/rbac/` do nothing unless an RBAC implementation is configured (`rbac_implementation_source`), which the open-source server does not ship. As a result, **any authenticated user can read and modify every project's pipelines, runs, stacks, components, models, artifacts, service connectors and non-private secrets. This is intended open-source behavior. Do not report it.**

The real boundaries in the open-source server, and things we do want reported:

- **Authentication**: bypassing login; forging, replaying or escalating JWTs, API keys, device-authorization codes, workload tokens or download tokens (`zen_server/auth.py`, `zen_server/jwt.py`); session or CSRF weaknesses on cookie auth.
- **Admin-only actions** (creating, deactivating or deleting users, changing another user's details or anyone's admin flag, server settings, secret backup and restore): a non-admin doing any of these is a privilege escalation.
- **Private secrets** (`private: true`) are only visible to their owner. Another user reading or changing one is a vulnerability.
- **Server-side file and code safety**: reading or writing files on the server host outside the intended directories (for example through artifact download, visualization or code archive endpoints), making the server import or execute code chosen by a non-admin user, server-side request forgery (SSRF) that makes the server reach internal hosts or cloud metadata endpoints, and leaking the server's own credentials or configuration.
- **Injection**: SQL injection through filter, sort or pagination parameters (`src/zenml/models/` filter models and `zen_stores/sql_zen_store.py`), and header or log injection.
- **Missing permission checks**: every endpoint is expected to call the `rbac` helpers (`verify_permission`, `verify_permission_for_model`, `dehydrate_*`) even though they do nothing in open source, because deployments that configure an RBAC implementation rely on them. An endpoint that skips the check or checks the wrong resource is in scope. Report it as one finding per root cause.

## Past vulnerabilities worth looking for variants of

Both are fixed and public. Variants of them, in other endpoints or code paths, are exactly what we want to hear about.

- **Account takeover through user activation** (CVE-2024-25723, fixed in 0.46.1): the activation endpoint let an unauthenticated caller set a new password for an existing account. Look for other unauthenticated or under-checked paths that change credentials or account state.
- **Arbitrary file read through the local artifact store** (fixed in 0.84.0): a user could register an artifact store pointing at the server's local filesystem and read any file through the artifact download endpoints. Remote servers now refuse local artifact store access unless `ZENML_SERVER_ALLOW_LOCAL_FILE_ACCESS` is set (`src/zenml/artifact_stores/base_artifact_store.py`). Look for other ways user-supplied URIs, paths or stack component configurations make the server read or write its own files.

## What is trusted by design (out of scope)

- **Running pipelines runs code.** Whoever registers a stack component, flavor or pipeline, or triggers a run, is executing their own Python code in their orchestrator environment. That is the product working, not a vulnerability. This also covers the documented server-side run features (`zen_server/pipeline_execution/`), which build and run a pipeline image on infrastructure the user configured.
- **Artifact stores are trusted storage.** Materializers deserialize what is in the artifact store, including cloudpickle for unknown types; the docs warn about this. Someone who can write to the artifact store can already run code. Only report deserialization if data from a *less* trusted source (an HTTP request body, a webhook, another user's private resource) reaches a deserializer.
- **Admins and server operators** (anyone who sets the server's environment variables or configuration) are trusted. A malicious admin is out of scope.
- **The `NO_AUTH` authentication scheme** and the local developer server started by `zenml login --local` (which runs with `NO_AUTH` and turns on `ZENML_SERVER_ALLOW_LOCAL_FILE_ACCESS`) are for a single user on their own machine.
- **Development defaults**: `docker-compose.yml`, `zen-dev`, `zen-test`, `docker/*-dev.Dockerfile`, `helm/` example values and `infra/`.
- **Vulnerabilities in third-party dependencies**, unless ZenML calls them in a way that creates the problem.

## Which code matters most

- **Highest**:
  - `src/zenml/zen_server/` (routers, auth, CSRF, middleware, rbac hooks, pipeline execution, streaming)
  - `src/zenml/zen_stores/` (SQL store, secrets stores, migrations)
  - `src/zenml/models/` (request and filter models that validate input)
  - `src/zenml/webhooks/`, `src/zenml/triggers/`, `src/zenml/dispatcher/`
  - `src/zenml/service_connectors/`, plus the connector implementations in `src/zenml/integrations/{aws,gcp,azure,kubernetes}/service_connectors/`
- **Medium**:
  - the client's credential storage and login flow (`src/zenml/login/`, `src/zenml/zen_stores/rest_zen_store.py`)
  - `src/zenml/deployers/` (pipeline deployments that expose HTTP endpoints)
  - `src/zenml/code_repositories/`
  - `src/zenml/artifacts/`
- **Lower**:
  - other `src/zenml/integrations/*` packages (thin wrappers around third-party tools; their libraries are not installed in this image)
  - `examples/`, `docs/`, `tests/`, `scripts/`

## How to exercise it

The image has ZenML installed editable from `/src` with the server and test extras, and no network.

- **Start a server configured like a real remote deployment** (SQLite, OAuth2 authentication, local file access off):

  ```
  ZENML_SERVER_AUTO_ACTIVATE=1 ZENML_DEFAULT_USER_PASSWORD=admin-password \
  ZENML_SERVER_JWT_SECRET_KEY=dev-jwt-secret \
  uvicorn zenml.zen_server.zen_server_api:app --port 8080
  ```

  Get a token with `POST /api/v1/login` (form fields `username=default`, `password=admin-password`), then create a non-admin user with `POST /api/v1/users` (`{"name": "alice", "password": "...", "is_admin": false}`) and log in as them to test boundaries. Do not use `zenml login --local` to judge findings, for the reason given above.
- **Python client**: `from zenml.client import Client`.
- **Tests**:
  - Unit tests: `pytest tests/unit/zen_server tests/unit/zen_stores -p no:randomly` (other directories under `tests/unit/` also work).
  - Integration tests (`tests/integration/`) need Docker or cloud services and will not run here.

## How we rate severity

- **Critical**:
  - unauthenticated remote code execution on the server
  - unauthenticated authentication bypass or account takeover
  - unauthenticated read of secrets, API keys or service connector credentials
- **High**:
  - an authenticated non-admin becoming admin
  - a non-admin executing code on the server host
  - reading another user's private secret
  - forging tokens for another user
  - SSRF that returns the response to the attacker
  - SQL injection reachable by any authenticated user
- **Medium**:
  - CSRF that performs a state-changing action
  - blind SSRF
  - a missing permission check that only matters when an RBAC implementation is configured
  - unauthenticated information disclosure of non-secret metadata
  - unauthenticated denial of service needing only a few requests
- **Low**:
  - denial of service that needs an authenticated user
  - missing hardening headers or verbose error messages
  - problems that need unusual, non-default configuration

## How reports should look

We have had many false positives from bug bounty programs in the past (often reports of intended behavior listed above, or issues that only reproduce in a modified or development setup). Please:

- Only report what the reproducer actually demonstrates against an unmodified server in its default configuration, or say exactly which non-default setting it needs.
- State which attacker from the list above the exploit assumes (no account, non-admin account, webhook sender, and so on).

- One report per root cause. If the same missing check affects several endpoints, list them in one report.
- The reproducer should be a single Python script or a short sequence of `curl` commands against a local server started as above, with the expected and actual result.
- Patches should be minimal and merge-ready for the `develop` branch, with a regression test under `tests/unit/` where practical.
