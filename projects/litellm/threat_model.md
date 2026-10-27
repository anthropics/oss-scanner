# Threat model

## What this project does and where untrusted input enters

LiteLLM is two things. The Python SDK (`litellm/`, outside `litellm/proxy/`) calls 100+ LLM provider APIs in the OpenAI format. The proxy server (`litellm/proxy/`), also called the AI gateway, is an OpenAI-compatible HTTP server that holds the operator's provider credentials and hands out virtual keys, each scoped to teams, models, budgets, rate limits and routes. Most deployments run the proxy, and most of our advisories are about it

The proxy is a multi-tenant service. Its callers, from most to least trusted, are these.

- the operator, who writes `config.yaml`, sets environment variables and chooses the `master_key`
- proxy admins (the master key, or the `proxy_admin` role), who manage models, keys, teams, users, guardrails, callbacks, MCP servers and pass-through endpoints through the API and the Admin UI
- `proxy_admin_viewer`, `org_admin`, team admins, `internal_user` and `internal_user_viewer` users, and virtual keys, which may only act inside their organization, team, key and model scope
- end users, who reach the proxy only through an application's key
- anyone who can reach the proxy's port without a credential

Untrusted input comes from these places.

- every HTTP request, through its headers (including `Host` and forwarding headers), query strings, and request bodies, whose fields can reach routing, provider parameters and nested metadata
- credentials the proxy must verify, such as virtual keys, JWTs, OIDC and SSO callbacks, SCIM requests, UI session tokens and passwords
- requests from lower-privileged roles to the management API (`/key/*`, `/team/*`, `/user/*`, `/organization/*`, `/model/*`, `/config/*`, `/guardrails/*`, `/mcp-rest/*`, `/credentials/*` and the rest under `litellm/proxy/management_endpoints/`)
- MCP clients connecting to the proxy's MCP gateway, and the tool results, OAuth metadata and redirects that upstream MCP servers send back
- responses from LLM providers, including tool calls, file and image URLs, and streaming chunks
- files that callers upload (batches, fine-tuning files, Skills archives, audio, images)

In the SDK, the application passes the call's arguments. A secret that the SDK sends to a host other than the one the application chose, or that it writes to a log or a callback, is a defect. An application that passes user input as `api_base` or `api_key` is the application's problem

## Components that matter most / least

These matter most.

- authentication and authorization in `litellm/proxy/auth/` (`user_api_key_auth.py`, `handle_jwt.py`, `route_checks.py`, `auth_checks.py`, `login_utils.py`, the OAuth2 and SSO checks), and the role checks in `litellm/proxy/management_endpoints/`, including `sso/` and `scim/`
- request handling that turns a body into a provider call, in `litellm/proxy/litellm_pre_call_utils.py`, `common_request_processing.py`, `route_llm_request.py`, `common_utils/http_parsing_utils.py`. A caller must not be able to change the provider URL, the credential, or another tenant's metadata
- secrets, in `common_utils/encrypt_decrypt_utils.py`, `credential_endpoints/`, `litellm/secret_managers/`, and anything that returns or logs a provider key, a virtual key, a password hash or the master key
- the MCP gateway in `litellm/proxy/_experimental/mcp_server/`, `mcp_tools.py` and the MCP management endpoints
- pass-through endpoints (`pass_through_endpoints/`), guardrails (`guardrails/`, including custom code guardrails), prompts (`/prompts/*`) and anything else that fetches a URL, reads a file, renders a template or runs code
- budget, rate limit and model access enforcement in `litellm/proxy/hooks/` and `auth/budget_throttle.py`
- data isolation for spend logs, request logs and analytics (`spend_tracking/`, `analytics_endpoints/`, `management_endpoints/usage_endpoints/`)
- the Admin UI in `ui/litellm-dashboard/`, which holds a session token and renders model output and user-supplied names
- the supply chain in `.github/workflows/`, `.circleci/`, `Dockerfile` and `docker/`, which build and publish the PyPI package and the GHCR and Docker Hub images

These matter less but are still in scope.

- `litellm/llms/` (per-provider request and response translation), except where it builds a URL, a header or a file path from request input, which matters most
- `litellm-rust/`, a Rust core that runs provider calls for the Python package through `litellm.rust_bridge` when `LITELLM_RUST=true` or the rollout selects it
- `enterprise/`, which ships in the same images under a separate license
- logging and observability callbacks in `litellm/integrations/`, except where they leak secrets

The least important are `docs/`, `cookbook/`, `tests/`, benchmarks, and scripts that only run on a developer's machine

## How to exercise it

The repository is at `/src`. LiteLLM and every extra and dependency group are installed in editable mode in `/src/.venv`, which is on PATH, with the Rust extension built in the dev profile. Nothing needs the network

- To run the proxy, start the database with `service postgresql start`, then run `litellm --config /opt/litellm/config.yaml --port 4000 &`. The image sets `DATABASE_URL` for the local database and `LITELLM_MASTER_KEY=sk-oss-scanner-master`. The first boot applies the database migrations, and the proxy answers on `/health/liveliness` in about 15 seconds. The `mock-gpt` model answers with a mock response, so no provider is needed. Redis is installed too, for configs that use it (`service redis-server start`)
- To act as a lower-privileged caller, make one with the master key and use its key:

  ```
  curl -s localhost:4000/user/new -H 'Authorization: Bearer sk-oss-scanner-master' -H 'Content-Type: application/json' \
    -d '{"user_role": "internal_user", "models": ["mock-gpt"]}'
  curl -s localhost:4000/v1/chat/completions -H 'Authorization: Bearer <key from above>' \
    -H 'Content-Type: application/json' -d '{"model": "mock-gpt", "messages": [{"role": "user", "content": "hi"}]}'
  ```

- For Python tests, `tests/unit/` mirrors `litellm/`, so the tests for `litellm/proxy/auth/user_api_key_auth.py` are under `tests/unit/proxy/auth/`. Run `pytest tests/unit/proxy/auth -n 4`. The unit tests block outbound sockets
- For Rust tests, run `cd litellm-rust && cargo test -p <crate>`. Every crate is fetched, so cargo works offline
- For Admin UI tests, run `cd ui/litellm-dashboard && npx vitest run <file>`

## How you rate severity

The levels follow the categories in our [security policy](https://github.com/BerriAI/litellm/blob/main/security.md) and our published advisories, given by ID

- Critical covers P0, a supply chain attack that lets an outsider change what our CI publishes to PyPI, GHCR or Docker Hub, such as a workflow that runs untrusted code with publishing secrets. Also a P1 where a request with no credential bypasses authentication or gets proxy admin access (GHSA-4xpc-pv4p-pm3w, GHSA-r75f-5x8p-qvmc, GHSA-jjhc-v7c2-5hh6), and a P2 where an `internal_user` becomes a proxy admin (GHSA-7hp6-4w63-5g45)
- High covers the other P1 cases, where a request with no credential reads protected data such as provider keys, virtual keys or other users' requests. Also a P2 where a non-admin caller runs code, reads files on the proxy host, or changes the proxy's configuration (GHSA-v4p8-mg3p-g94g, GHSA-xqmj-j6mv-4862, GHSA-g5ff-637f-6q2m, GHSA-53mr-6c8q-9789), and an authentication bypass on one surface, such as MCP (GHSA-7488-6r32-c95q) or password login (GHSA-69x8-hrgq-fjj8)
- Medium covers the other P2 cases, where an authenticated caller acts outside its scope, such as reading or changing another team's or user's keys, logs or spend, using a model it has no access to, getting past a budget or rate limit, or making the proxy send its own provider credentials or requests to a host of the caller's choice (GHSA-3cv6-jpf6-8222, GHSA-hx8v-g79f-8w5f). A file write through path traversal (GHSA-5jmr-gcrj-2c9q), XSS in the Admin UI (GHSA-hhww-mrg2-969h), and code execution that needs a proxy admin credential (GHSA-wxxx-gvqv-xp7p) are medium too
- Low covers minor information disclosure, missing hardening, a crash from a large or slow request, and other defects that only a proxy admin reaches (GHSA-4g5m-c9r5-49xf, GHSA-72m8-9m7m-h278)

Every report states the caller's role, the settings it needs, and whether a credential is needed at all

## Reports and patches

Give the LiteLLM version first, then the commit, the `config.yaml`, and the exact requests, as curl commands against a local proxy. Include a test under `tests/unit/` that fails before the fix

## Anything to leave alone

- Attacks that need a misconfiguration, such as a proxy with no `master_key`. Our policy rules these out
- What the operator controls, which is `config.yaml`, environment variables, and the Python modules that the config loads (custom auth, callbacks, guardrails and handlers). These are trusted code
- Features that let a proxy admin point the proxy at any URL or run a command, such as a model's `api_base`, a pass-through endpoint's target or a stdio MCP server. These are by design when only a proxy admin can reach them
- Prompt injection and jailbreaks that only change what a model says, and inputs that get past a guardrail's detection. A guardrail that is skipped when it should run is in scope
- Spend is written to the database in batches, so a key can go over its budget by the requests already in flight. Only a bypass that keeps working after the budget is spent counts
- Defects in provider APIs, third-party SDKs and other dependencies that no LiteLLM code reaches
- `docs/`, `cookbook/`, `tests/` and the example configs in `litellm/proxy/example_config_yaml/`
