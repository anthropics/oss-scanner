# Threat model

The authoritative version is Airflow's security model,
`airflow-core/docs/security/security_model.rst` (published at
https://airflow.apache.org/docs/apache-airflow/stable/security/security_model.html), and in particular its
section "What is NOT considered a security vulnerability". Read it before reporting. This file summarises
it for the scanner.

## What this project does and where untrusted input enters

Apache Airflow schedules and runs workflows (Dags) written in Python. Its components are the API server
(serves the React UI, the public REST API under `/api/v2` and the Execution API for workers), the
scheduler, the Dag File Processor, the triggerer and workers. They share a metadata database.

Airflow is not meant to be exposed to untrusted users on the internet. Every UI and API user is
authenticated and known. The roles that matter, from most to least trusted:

- **Deployment Managers** install and configure Airflow. Fully trusted.
- **Dag authors** write Dag files. They can run arbitrary code on workers, the Dag File Processor and the
  triggerer, and read the credentials their tasks use. Trusted by design.
- **Authenticated UI and API users**, with roles such as Admin, Op, Connection configuration, User and
  Viewer (FAB auth manager) or the equivalent permissions of another auth manager. They are *not* trusted
  to run code or to exceed their permissions.
- **Unauthenticated network clients** reaching the API server.
- **Workers**, which hold a short-lived JWT scoped to one task instance and use the Execution API.

The defects we want found cross one of these boundaries:

- an unauthenticated client reaching anything beyond the login flow and public endpoints;
- an authenticated user exceeding their role: reading or changing Dags, runs, connections, variables,
  pools or logs they have no permission for, reading a secret through the API or UI (connection
  passwords are write-only for the Connection configuration role), or running code in the scheduler or
  the API server;
- stored XSS or similar, where one user's input executes in another, more privileged user's session;
- a worker using its Execution API token to act on another task instance (`ti:self` scope), or a token
  being accepted where it should not be;
- code from a Dag file running in the scheduler or the API server, which must never execute Dag code;
- a value inside the secret-masking contract (connection password and extra, fields matching
  `sensitive_var_conn_names`) appearing in clear text in logs or the UI.

## Components that matter most / least

Most:

- `airflow-core/src/airflow/api_fastapi/` — authentication, authorization checks on every route of the
  Core API (`core_api/`) and the Execution API (`execution_api/`), JWT handling (`auth/`).
- `airflow-core/src/airflow/serialization/` — serialized Dags are read by the scheduler and API server,
  which must not execute Dag code while deserializing.
- `providers/fab/src/airflow/providers/fab/auth_manager/` — the production auth manager: login,
  sessions, role and permission checks.
- `airflow-core/src/airflow/utils/log/` and the secret masker in `shared/` — masking of secrets.
- `airflow-core/src/airflow/ui/` — the React UI, for XSS that crosses users.
- `task-sdk/src/airflow/sdk/execution_time/` — the worker side of the Execution API.

Least: `dev/`, `scripts/`, `.github/`, documentation, example Dags, `airflow-core/tests/`,
`devel-common/` (test fixtures), the Helm chart's development values, and the Simple Auth Manager, which
is for development only. Providers other than FAB are in scope, but most of their code runs with a Dag
author's or a Connection configuration user's privileges (see "Anything to leave alone").

## How to exercise it

The repository is at `/src`; `uv sync --all-packages` installed the whole development environment
(airflow-core, the Task SDK, every provider, the shared libraries and the test fixtures) into `/src/.venv`,
which is on `PATH`.
`uv` is configured not to re-sync or reach the network, so `uv run` and plain `pytest` both use it as is.
`AIRFLOW_HOME` is `/tmp/airflow-home`.

- Unit tests without a database: `cd /src && pytest airflow-core/tests/unit/<path> --skip-db-tests -q`
  (provider tests: `pytest providers/<name>/tests/unit/<path> --skip-db-tests -q`).
- Tests that need the database use SQLite by default: run `airflow db migrate` once, then
  `pytest airflow-core/tests/unit/<path> -q`. API route tests are under
  `airflow-core/tests/unit/api_fastapi/`, and are the best way to show an authorization defect: a test
  client authenticated with a restricted role that gets a 200 where it should get 403.
- An API server for manual checks: `airflow api-server --port 8080` after `airflow db migrate`.

## How you rate severity

- Critical: an unauthenticated client executes code on, or reads secrets from, the API server or
  scheduler.
- High: an authenticated low-privilege user (Viewer, User) runs code in the scheduler or API server,
  reads connection secrets, or takes over another user's session; Dag code running in the scheduler or
  API server; a worker token acting across task instances.
- Medium: an authenticated user reads or changes objects outside their permissions without code
  execution; stored XSS from a lower-privileged to a higher-privileged user.
- Low: information disclosure of non-secret metadata across permission boundaries.

Every report must name the role the attacker holds, what they can do at the start and what they gain,
and give a reproduction against the default configuration.

## Anything to leave alone

These are documented as not vulnerabilities in the security model; please do not report them:

- Dag authors executing arbitrary code, reading credentials, or (Dag File Processor and triggerer)
  reaching the database. Code that a Dag author writes passing unsanitized input to operators or hooks.
- Connection configuration users causing code to run on a worker or influencing a client library through
  connection parameters (the boundary is crossed only when they recover a secret or run code in the
  scheduler or API server). The `test connection` feature is off by default.
- Denial of service by authenticated users; unbounded request bodies (a reverse-proxy responsibility).
- Self-XSS; anything specific to the Simple Auth Manager.
- Execution API tokens not being revocable, and Core API role changes taking effect at token expiry.
- Workers reading shared connections, variables and XComs through the Execution API.
- Findings that need a misconfiguration (an unsafe allow-list, module path or plugin), or a precondition
  that already grants the capability (database write access, placing a file in a Dag bundle).
- Hardening with no demonstrated path from an attacker-controlled entry point; CVEs in third-party
  dependencies without a demonstrated exploit in Airflow; non-Linux-only behaviour; experimental or alpha
  features such as multi-team mode; values outside the secret-masking contract such as a connection's
  `login` or Dag run configuration.
