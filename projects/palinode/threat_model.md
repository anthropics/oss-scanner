# Threat model — Palinode

## What this project does and where untrusted input enters
Palinode is a memory server for AI agents: memories are Markdown files with YAML frontmatter in a git-versioned
directory (`PALINODE_DIR`), indexed into SQLite (FTS5 + sqlite-vec), and served to agents over MCP and an HTTP API.
Every save is a git commit. Treat all of the following as attacker-controlled:

- **MCP tool arguments** (`palinode/mcp.py`; 39 tools such as `palinode_save`, `palinode_read`, `palinode_search`,
  `palinode_ingest`, `palinode_rollback`, `palinode_push`, `palinode_restore`, `palinode_history`/`blame`/`diff`).
  Arguments come from LLM agents that may themselves be steered by prompt injection.
  Transports: stdio (`palinode-mcp`, `main`) and streamable HTTP (`palinode-mcp-http`, `main_http`, default
  127.0.0.1:6341, serves `/mcp/`). The MCP server proxies to the HTTP API.
- **HTTP API requests** (`palinode/api/server.py`, `palinode/api/routers/*.py`; default port 6340). Routes include
  `/save`, `/read`, `/list`, `/search*`, `/ingest`, `/ingest-url`, `/history/{path}`, `/blame/{path}`, `/diff`,
  `/trace/{path}`, `/rollback`, `/restore`, `/archive`, `/unretract`, `/forget-withdraw`, `/push`, `/reindex`,
  `/corrections/*`, `/prompts/{name}/activate`, `/migrate/openclaw`, `/session-end`, plus the provenance web UI under
  `/ui/` (`palinode/api/ui/`; e.g. `/ui/memory/{path}`, `/ui/history/{path}`, `/ui/delivery/{bundle_id}`).
  Auth is an optional bearer token (`palinode/core/auth.py`), **off by default on loopback**; the server refuses a non-loopback bind without a token unless `PALINODE_API_ALLOW_UNAUTH=1`.
  CORS allows `http://localhost:3000` / `127.0.0.1:3000` with credentials (`server.py`). Body size cap 5 MB
  (`palinode/api/rate_limit.py`).
- **Memory file contents and frontmatter** — files may be imported, synced from a shared git remote, or written by
  other agents (`palinode/core/parser.py`, `palinode/import_/vault.py`, `palinode/migration/openclaw.py`,
  `palinode/indexer/watcher.py`).
- **File paths** supplied by callers — resolved through the single guard `palinode/core/path_guard.py`
  (HTTP adapter `palinode/api/path_safety.py`, which also opens with `O_NOFOLLOW`).
- **URLs** for ingest — `palinode/ingest/pipeline.py` fetches http(s) with its own SSRF vetting
  (`_vetted_addresses`, `is_safe_url`, manual redirect handling, proxy-tunnel handling).
- **Ingested documents** (PDF via pymupdf or `pdftotext` subprocess, HTML/readability, `.url`/`.webloc` files).
- **Git metadata and history** of the memory repo (`palinode/core/git_tools.py`, which shells out to git with argv,
  no shell) — refs, commit messages, file names supplied by a hostile remote or a crafted repo.
- **LLM output** consumed by consolidation (`palinode/consolidation/`, `op_parse.py` uses `json-repair`) — treat
  model-produced operations as untrusted.

## Components that matter most / least
Most:
1. Path handling: `core/path_guard.py`, `api/path_safety.py`, every caller that writes/moves/archives files
   (`core/save.py`, `core/memory_write.py`, `consolidation/archive.py`, `consolidation/executor.py`, restore/rollback).
2. Auth and bind gating: `core/auth.py`, `api/server.py` middleware, `mcp.py` `main_http` bind checks; also
   unauthenticated loopback API reachable from a browser (DNS rebinding / CSRF against `127.0.0.1:6340`).
3. Git operations: `core/git_tools.py` (argument injection via refs/paths beginning with `-`, rollback/restore).
4. SSRF in `ingest/pipeline.py` (`/ingest-url`, `palinode_ingest`).
5. Provenance UI rendering (`api/ui/`, markdown-it with HTML disabled + nh3 sanitizer, Jinja2) — stored XSS from
   memory content.
6. Parsing of frontmatter/YAML and SQL built for FTS5/vector search (`core/store.py`, `api/routers/search.py`).

Less (still in scope): CLI (`palinode/cli/`), diagnostics (`palinode/diagnostics/`), `palinode init` config writers
(`cli/init.py`, `cli/mcp_config.py`), the delivery-time prompt-injection detector.

## How to exercise it
- Install is done in the image (editable at `/src`, venv at `/opt/venv`). Run tests:
  `pytest tests/ -q --ignore=tests/integration` (unit, mirrors CI) and `pytest tests/integration -q`.
  `tests/live/` needs a running server and is excluded by default.
- The build's test output is kept in `/opt/test-baseline/{unit,integration}.log`; compare against it before
  attributing a failure to a finding. Two tests can fail in a container for environmental reasons and are deselected
  from that run (their output is in `/opt/test-baseline/known-failures.log`); they are test fragility, not
  vulnerabilities: `test_worktree_reconcile.py::test_alive_lock_is_skipped` (fails when the test process has a single-digit PID) and
  `test_context_prime_budget.py::test_unset_budget_renders_exactly_the_unbudgeted_digest` (same-mtime ordering).
- Embeddings/LLM are mocked in tests (`tests/conftest.py`); no Ollama is available offline.
- Existing security tests to extend: `tests/integration/test_security.py`; MCP end-to-end over stdio:
  `tests/integration/test_mcp_stdio.py`, `test_mcp_e2e.py`.
- Start the API in-process with `fastapi.testclient.TestClient(palinode.api.server.app)` (as
  `tests/integration/test_api_roundtrip.py` does) with `PALINODE_DIR` pointed at a temp dir, or run
  `palinode-api` / `palinode-mcp-http` on 127.0.0.1.

## How you rate severity
- **Critical:** remote code execution; arbitrary file write/read outside `PALINODE_DIR`; auth bypass on a
  token-protected API or MCP HTTP endpoint; bind-gate bypass that exposes an unauthenticated server on a
  non-loopback address.
- **High:** path traversal or symlink escape (read or write) reachable from an MCP tool or API route even on
  loopback; git argument injection; SSRF that reaches internal/link-local addresses; browser-reachable
  state-changing requests against the default loopback API (DNS rebinding/CSRF to `/save`, `/push`, `/rollback`,
  `/ingest-url`); stored XSS in the provenance UI; memory corruption/data loss of the git history.
- **Medium:** cross-project data leak bypassing project scoping; information disclosure of filesystem layout or
  tokens in errors/logs; SQL/FTS query injection without data modification.
- **Low:** denial of service (large inputs, regex, pathological markdown) on loopback-only surfaces; bypasses of
  the enumerated prompt-injection phrase detector.

## Anything to leave alone
- Prompt-injection *content* findings alone (an LLM obeys text stored in memory) — documented limitation in
  SECURITY.md "Memory poisoning and trust limitations"; report only if it leads to one of the code-level issues above.
- Running unauthenticated on a non-loopback bind after explicitly setting `PALINODE_API_ALLOW_UNAUTH=1`
  (documented opt-out).
- Out of scope: `bench/` (benchmark harnesses and results), `docs/`, `examples/` (sample hooks), `specs/`,
  `skill/`, `claude-plugin/` (config only), `deploy/`, `nix/`, `scripts/` (dev/CI linters), `tests/`.
- TypeScript delivery adapters under `plugin/` and `plugins/` are outside the initial enrollment scope; they have
  separate CI and may be added in a later enrollment update.
- Third-party dependency CVEs already covered by pip-audit in CI, unless Palinode's usage makes them reachable.

## Report preferences
- Prefer **minimal patches** over merge-ready refactors.
- PoC preferably as a **pytest test** that fails before and passes after the fix; otherwise a short script/curl.
- Deduplicate by root cause (one report per underlying bug, listing all reachable entrypoints).
