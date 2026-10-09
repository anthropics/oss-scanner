# Threat model

## What this project does and where untrusted input enters

Selora AI is a Home Assistant custom integration (`custom_components/selora_ai/`). It sends a home's
device and usage data to an LLM (Selora Cloud, a local model, Anthropic, Gemini, OpenAI, OpenRouter,
Ollama), proposes automations, scenes and dashboards, and acts on natural-language commands from its
own panel, from Assist, from Alexa and over MCP. It runs inside the Home Assistant process with full
access to the home: it can call any service, edit the registries, write `automations.yaml`,
configuration YAML and files under the config directory, and install HACS repositories.

Untrusted input enters through:

- **The MCP HTTP endpoint** (`mcp_server/http.py`, `mcp_server/dispatch.py`). The view sets
  `requires_auth = False` and authenticates itself (`selora_auth.authenticate_request`): a Home
  Assistant token, a Selora MCP token, or a Selora Connect JWT. Anything reachable before or around
  that check is the most exposed surface.
- **The Alexa endpoint** (`alexa_view.py`), also `requires_auth = False` with its own authentication.
- **Home Assistant websocket commands** (`websocket/`, `__init__.py`). The caller is an authenticated
  HA user, who may be a non-admin; admin-only actions must check `is_admin`.
- **LLM output.** Model replies, tool calls and proposed YAML are untrusted: a model can be steered by
  prompt injection hidden in entity names, device attributes, calendar events, notifications or
  fetched pages. Tool calls are gated by risk (`mcp-service-calls.md`, `command_policy`), by the
  caller's admin status, and by a `confirmed` flag for destructive actions.
- **Recipes and blueprints** fetched from remote catalogs or URLs: their Jinja templates render in a
  sandboxed environment and their fetches must use TLS.
- **The panel** (`frontend/`) renders model output and entity data into the DOM.

## Components that matter most / least

Most important:
- Authentication and authorization on the unauthenticated-at-dispatch views (MCP, Alexa, the OAuth
  token proxy), and token/JWT validation in `selora_auth.py`.
- Privilege checks: a non-admin HA user, or an MCP client with a restricted tool set, reaching an
  admin-only tool, service call, file write or config edit.
- Path handling in config/file reads and writes (`config_files.py`, `config_yaml.py`,
  `mcp_server/files.py`): traversal outside the allowed directories, symlinks, secrets.yaml exposure.
- Code execution: Jinja template rendering escaping the sandbox, YAML loading, anything that reaches
  a shell or `exec`.
- The risk/confirmation gate on service calls and deletes being bypassable by a crafted tool call.
- XSS in the panel from entity names, model replies or conversation history.
- SSRF via user- or model-supplied URLs (recipe/blueprint import, HACS, provider base URLs).

Less important: the telemetry counters, the usage/insights export files, and prompt wording.
`local_model/` prompts are pinned copies of a model release.

Out of scope: Home Assistant core itself and its other integrations; the LLM providers; a Home
Assistant administrator doing something they are already allowed to do through Home Assistant.

## How to exercise it

`pytest tests/` runs the suite (one file per module or feature) against a real, in-process Home
Assistant from `pytest-homeassistant-custom-component`. `tests/chat_harness.py` drives a full chat
turn end to end with only the provider round trip stubbed — the best entry point for tool-call
abuse. The MCP tests (`tests/test_mcp*.py`) exercise the HTTP endpoint. `npm test` in
`custom_components/selora_ai/frontend/` runs the panel tests. `docs/dev/` describes each feature's
rules.

## How you rate severity

- Critical: unauthenticated access to the MCP or Alexa endpoints; remote code execution; reading
  or writing arbitrary files.
- High: a non-admin user or restricted token performing admin-only actions; bypassing the
  `confirmed` gate on a destructive or high-risk service call; leaking API keys or tokens;
  stored XSS in the panel.
- Medium: prompt injection that makes the model take an action the user did not ask for when the
  action would still have been permitted for that user; SSRF to internal hosts; information leaks
  to an authenticated user beyond what Home Assistant already shows them.
- Low: denial of service needing an authenticated user.

## Anything to leave alone

- That an admin can make the integration change anything in Home Assistant — that is its purpose.
- That an LLM can be talked into producing a bad automation the user then accepts.
- Findings in vendored or generated files (`frontend/panel.js` is the built bundle of `frontend/src/`).
