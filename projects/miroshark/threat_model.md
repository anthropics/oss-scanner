# Threat model

## What this project does and where untrusted input enters
MiroShark is a self-hosted simulation engine: a user uploads a document or asks a question, it builds a knowledge graph in Neo4j, spawns hundreds of LLM agents that post and trade across simulated platforms, then writes a report. Operators run it on their own servers (Docker, Railway, Cloud Run) and many expose it on the public internet.

Treat as untrusted:
- **HTTP requests to the Flask API** (`backend/app/api/`). Most of `/api/*` sits behind `internal_auth_guard` in `backend/app/__init__.py`, which requires `MIROSHARK_INTERNAL_KEY` and fails closed. A short exempt list (`/health`, the OpenAPI docs, `/api/status.json`, `/api/simulation/batch-status` and similar polling probes) is public by design and must only return public, completed simulations.
- **Uploaded files** (PDF, Markdown, text, up to 50 MB) parsed with PyMuPDF and charset detection.
- **URLs submitted for import** (`/api/graph/fetch-url`, `backend/app/utils/url_fetcher.py`) and **operator-configured webhook URLs** (`backend/app/services/webhook_service.py`): SSRF to internal or cloud metadata addresses matters.
- **LLM output and agent-generated content**: it lands in Neo4j queries, in files on disk, in reports, and in the Vue frontend (`frontend/src`, including a few `v-html` uses). Prompt injection from an uploaded document that turns into Cypher injection, path traversal, stored XSS or SSRF is in scope.
- **Public share pages and oEmbed** (`backend/app/api/share.py`): host allowlisting and which simulations they expose.
- **The stdio MCP server** (`backend/mcp_server.py`): tool arguments come from a local MCP client.

## Components that matter most / least
- Most: the auth guard and its exempt list, simulation ID handling (path traversal into `sim_dir`), Cypher query construction in `backend/app/storage/`, file upload parsing, URL fetching and webhooks, anything that leaks API keys from config or `.env`.
- Less: `backend/wonderwall/` (bundled simulation engine, a camel-ai fork), still in scope where untrusted text reaches it.
- Out of scope: `docs/`, translations, deployment examples (`render.yaml`, `cloudbuild.yaml`, `railway.json`) except where they ship an insecure default.

## How to exercise it
- `/src/.env` holds placeholder model keys and `MIROSHARK_INTERNAL_KEY=scan-internal-key` (send it as the `x-miroshark-internal-key` header). Start the backend with `cd /src/backend && uv run --offline python run.py` (port 5001). Neo4j is not in the image, so graph-backed endpoints fail soft; review the Cypher in `backend/app/storage/` by reading it.
- Offline unit tests: `cd /src/backend && uv run pytest -m "not integration"`. `backend/openapi.yaml` lists every route.
- LLM calls cannot succeed offline, so pipeline stages that need a model will error; the API, auth, storage and parsing code paths work without one.

## How you rate severity
- Critical: unauthenticated RCE; unauthenticated read of API keys or other secrets; auth bypass that gives full `/api/*` access.
- High: auth bypass on any write or simulation-control endpoint; Cypher injection; path traversal that reads or writes outside the simulation directory; SSRF that reaches internal or metadata addresses; stored XSS in a share page or report served to other users.
- Medium: info leaks from public endpoints (private or unfinished simulations), authenticated-only injection bugs, prompt injection that changes report content but not code or data paths.
- Low: DoS needing large uploads or many requests (we already cap upload size), missing hardening headers.
- Anything that requires `MIROSHARK_INTERNAL_KEY` is authenticated: cap at medium unless it gives code execution.

## Anything to leave alone
- Do not report that LLM agents can be steered by document content on its own. That is the product. Report it only when it crosses into code, data or network access.
- `FLASK_DEBUG` defaults to on for local development; that is known. Report it only if it weakens the auth guard on a managed deploy.
