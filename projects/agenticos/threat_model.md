# Threat model

## What this project does and where untrusted input enters
AgenticOS is a self-hosted, multi-tenant platform for a company's AI agents. An agent is a versioned spec
(instructions, model, capabilities, budgets) that runs through web chat, an HTTP API and channel bots.
The operator's infrastructure is trusted; every request into it is not. Untrusted input enters through:
- the FastAPI HTTP API (`backend/app/api/`) and WebSocket endpoints, including public embed widgets and
  hosted pages reachable without a login;
- the Next.js console and its route handlers (`frontend/src`), which forward the session token to the API;
- channel webhooks (Slack, Telegram, Mattermost, Microsoft Teams) and inbound email;
- uploaded files and crawled web pages that are parsed and ingested for retrieval;
- MCP servers, connectors and model output (prompts, tool calls), which can carry attacker text;
- model-written pages ("artifacts") rendered in the console, which must stay isolated from it.

## Components that matter most / least
Most: authentication and sessions, tenant isolation (organization membership, permission catalog, resource
grants in `backend/app/core/permissions.py` and the services using `resolve_access`), the credential vault
(`backend/app/core/vault.py`), SSRF protection for outbound fetches (`backend/app/core/pinned_http.py`),
artifact/page isolation, budget enforcement, webhook signature checks, file parsers and the sandbox.
Least: documentation (`docs/`), `experiments/`, test fixtures, load-test scripts and demo data.
Out of scope: vulnerabilities in third-party dependencies with no AgenticOS-specific exploit path.

## How to exercise it
Backend tests are in `backend/tests/` (pytest with anyio; unit tests mock the database). Integration tests
need PostgreSQL with pgvector, which the image does not provide. The frontend is in `frontend/`.

## How you rate severity
- Critical: cross-tenant data access, authentication bypass, remote code execution, credential or vault key
  disclosure, SSRF reaching internal services.
- High: privilege escalation inside an organization, stored XSS that escapes artifact isolation, a
  permission gate that rejects or allows the wrong caller, secrets leaking into responses, logs or audit
  entries.
- Medium: denial of service from an authenticated user, budget bypass, missing rate limits on public
  surfaces, information disclosure of non-secret metadata.
- Low: hardening gaps with no demonstrated exploit.

## Anything to leave alone
- Findings that require operator-level access to the host, database or environment variables.
- Default development credentials in `docker-compose*` and `.env.example`; production hardening is in
  `SECURITY.md`.
- Self-XSS inside an artifact's own sandboxed frame.
