# Threat model

## What this project does and where untrusted input enters
apowerb is a multi-tenant server (FastAPI, Google ADK, PostgreSQL) on which organisations build and run AI
agents. Users authenticate with JWTs; each user belongs to an organisation, and an organisation's agents,
runs, files, credentials and data must never be visible to another one. Treat as untrusted:
- every HTTP request to the routers in `src/apowerb/routers/`, `src/apowerb/bi/`, `src/apowerb/users/` and
  `src/apowerb/admin/`, from authenticated users of any organisation and from anonymous callers;
- webhook bodies: `routers/hooks.py` and `routers/webhooks.py` (authenticated by HMAC signature only),
  `routers/rag/webhook.py`;
- uploaded files and documents ingested for RAG (`routers/files.py`, `routers/rag/index_*.py`: PDF, Office,
  spreadsheets, URLs, S3), parsed with pypdf, PyMuPDF, openpyxl, python-docx, python-pptx, calamine;
- anything a language model produces: tool-call arguments, generated SQL, chart or dashboard specifications.
  Assume the model can be steered by prompt injection from a document, a web page or a data source.

## Components that matter most / least
Most important:
- tenant isolation and authorisation: `auth/`, `middleware/`, `admin/guard.py`, organisation scoping of every
  query, shared links (`routers/share.py`). Reading or changing another organisation's objects is critical.
- text-to-SQL (`sqlgen/`): generated SQL must stay read-only (`sqlgen/safety.py`, `sqlgen/readonly.py`)
  and confined to the data source the agent was given.
- tool and MCP execution (`core/agent_helpers/mcp_loader.py`, `tools_store/`, `skills_store/`): the stdio
  MCP transport spawns local processes and must stay disabled unless the deployment enables it; any path
  from a request or a model output to command execution on the server is critical.
- stored secrets: integration tokens and connector credentials are encrypted with `ENCRYPT_KEY`; leaking
  them in clear, in logs or across organisations is high or critical.
- SSRF from URL ingestion, connectors and MCP/HTTP tools toward internal services.
Less important: `bench/`, `docs`, the CLI (`src/apowerb/cli/`, run by an operator on their own machine).
Out of scope: `tests/unit_scei/` and `tests/test_scei_*` (they import a private client overlay that is not in
this repository).

## How to exercise it
The image has the package installed in editable mode in `/opt/venv` with pytest. Load the test environment
first: `set -a; . /etc/apowerb-test.env; set +a` (it sets `ENCRYPT_KEY`; `DB_SCHEMA=""` is already set so
models work on SQLite). Then `pytest -q -m "not integration" tests/<file>`. Most routers are tested with
FastAPI's TestClient in `tests/`; `tests/conftest.py` and `tests/helpers/` show how to build an app and users.
Tests marked `integration` need a live server and PostgreSQL, which the image does not have.

## How you rate severity
- critical: unauthenticated or cross-organisation access to data, credentials or agents; remote code
  execution on the server; SQL that writes through the text-to-SQL path.
- high: privilege escalation inside an organisation (member to admin), authentication bypass for a single
  account, webhook signature bypass, SSRF reaching internal services, secrets written to logs.
- medium: denial of service from a single request (parser bombs, unbounded loops), information disclosure
  limited to metadata.
- low: issues that need an administrator of the same organisation to act against themselves.

## Anything to leave alone
- the stdio MCP transport when it is explicitly enabled by the deployment: running a configured local
  command is its purpose. Report it only if it can be enabled or reached without that setting.
- `admin/migration.py` builds DDL with f-strings from the configured schema name, which comes from the
  operator's settings, not from requests.
- missing rate limiting on its own.
