# Threat model: Code Puppy

## What this project does

Code Puppy (`code_puppy/`, CLI entry points `code-puppy` and `pup`) is a terminal AI coding agent. It runs locally as
the user who started it, sends the conversation to a model provider over HTTPS (OpenAI, Anthropic, Gemini, Bedrock,
Azure, OpenAI-compatible custom endpoints and others, configured in `models.json` / `~/.code_puppy/extra_models.json`),
and executes the tools the model calls: shell commands (`code_puppy/tools/command_runner.py`), file read/write/delete
(`code_puppy/tools/file_operations.py`, `file_modifications.py`), ripgrep search, a Playwright-driven Chromium
(`code_puppy/tools/browser/`), sub-agent invocation (`agent_tools.py`), and tools exposed by MCP servers
(`code_puppy/mcp_/`). It is extended by plugins through hooks in `code_puppy/callbacks.py`.

There is no multi-tenant server. The trust boundaries that matter are between **the user** and **content the user did
not write**: a freshly cloned repository, model output, tool and MCP results, web pages, and files on disk.

## Intended behaviour that is NOT a vulnerability

Please do not report these on their own; they are the product working as designed.

- **The model runs commands and edits files.** Shell and file tools act with the user's full privileges. There is no
  workspace sandbox: relative paths resolve against the working directory and absolute paths are accepted as-is.
- **`yolo_mode` defaults to on**, so shell commands run without a confirmation prompt unless the user turns it off
  (`/set yolo_mode false` or `--yolo false`). Sub-agents never prompt.
- **Prompt injection that merely convinces the model to call a tool** (from a README, a web page, an MCP result, an
  `AGENTS.md`, a project agent JSON, a skill) is out of scope by itself. It becomes in scope only when it defeats one
  of the controls listed below.
- Anything configured by the user in their own config (`~/.code_puppy/`, `$XDG_CONFIG_HOME/code_puppy/`, user
  plugins in `~/.code_puppy/plugins/`, user-level `mcp_servers.json`, environment variables) is trusted.
- The Universal Constructor tool lets the model create Python tools that are later executed. That is code execution
  by design.
- `!`-prefixed shell passthrough typed by the user (`command_line/shell_passthrough.py`) runs what the user
  typed.

## Security controls that ARE in scope (most important first)

1. **Repository-supplied code must not run until the user trusts it.** Opening Code Puppy in an untrusted checkout must
   not execute code from that checkout.
   - Project plugins in `<cwd>/.code_puppy/plugins/<name>/register_callbacks.py` load only after explicit trust,
     recorded as a SHA-256 of the plugin directory in `~/.code_puppy/trusted_plugins.json`
     (`code_puppy/plugins/trust.py`, `code_puppy/plugins/__init__.py`, including the bytecode check
     `_find_plugin_bytecode`). Any change must revoke trust; any error must fail closed.
   - Project MCP servers in `<cwd>/.code_puppy/mcp_servers.json` (a `stdio` server is an arbitrary command) are ignored
     until trusted with `/mcp trust` (`code_puppy/mcp_/project_config.py`, same content-hash model, store in
     `~/.code_puppy/trusted_mcp.json`). Project agents (`.code_puppy/agents/*.json`) can declare `auto_start` MCP
     bindings, so they must never be able to start an untrusted server.
   - Bypasses (hash collisions in practice, path or symlink tricks that make a repo self-trust, files excluded from the
     hash that still get imported, TOCTOU between hashing and import, a repo writing the user-side trust store) are
     the most valuable reports.
2. **Session files.** Legacy `.pkl` sessions are migrated with `SurrogateUnpickler`
   (`code_puppy/session_surrogate_unpickler.py`), an allowlisting unpickler that must never resolve a module, a
   callable with side effects, or shared mutable state. Code execution or process termination from a crafted `.pkl`
   (reachable via `--resume <path>`, `/load_context`, or the session directory) is in scope. So are path traversal or
   unsafe writes in session naming and storage (`session_storage.py`, `session_lifecycle.py`, `atomic_io.py`,
   `atomic_json.py`).
3. **Credential handling.** Provider API keys and OAuth tokens must not leak to child processes, logs, session files,
   error reports, or hosts other than the configured endpoint. Shell children get the environment minus the agent's own
   provider credentials (`provider_credentials.environment_without_credentials`). Also in scope: `secret_store.py` /
   `secret_store_backends.py` (keyring and owner-only file permissions), `shared_credentials.py`, the OAuth transport
   and refresh logic (`claude_oauth_transport.py`, `chatgpt_codex_client.py`, `gemini_code_assist.py`), OAuth
   paste-back parsing (`code_puppy/plugins/oauth_pasteback.py`), remote-MCP OAuth (`mcp_/http_auth.py`), and `$ENV`
   expansion of `api_key` / header values in model configs (an attacker-controlled config value must not be able to
   pull an arbitrary environment variable to an attacker host).
4. **Guards that hold even with yolo on.**
   - File tools refuse to modify `~/.code_puppy/plugins` (imported at startup, so a write there is persistence):
     `_refuse_user_plugin_tree` in `file_modifications.py`. Bypasses via symlinks, `..`, case or unicode tricks are in
     scope (rate low to medium, since the shell tool can still write there when the user allows shell).
   - `run_shell_command` and `pre_tool_call` callbacks registered with `fail_closed=True` must block when they crash
     (`callbacks.py`). A way to skip them, or to run a command different from the one they approved (rewrite and
     quoting confusion), is in scope.
   - With `yolo_mode` off, the approval prompt for shell commands and the file-permission flow must not be bypassable
     by tool arguments the model controls.
5. **Parsing untrusted data without crashing or executing it.** Model responses and tool-call JSON (`json-repair`
   paths, `mcp_/tool_arg_coercion.py`, `_pydantic_tool_helpers.py`), MCP server results, the models catalog
   (`models.json`, `models_dev_api.json`, `models_dev_parser.py`), i18n catalogs (treated as untrusted: no
   `str.format` attribute or index access), `AGENTS.md` loading (encoding, size), image attachments
   (`command_line/attachments.py`, `image_utils.py`), and terminal output rendering (escape-sequence injection from
   model or tool output into the user's terminal).
6. **TLS.** Outbound HTTP clients (`http_utils.py`, `httpx2_utils.py`, `ca_bundle.py`, `reopenable_async_client.py`)
   must verify certificates unless the user explicitly configured otherwise.

## Out of scope

- Vulnerabilities in third-party dependencies (pydantic-ai, mcp/FastMCP, Playwright, httpx, etc.) unless Code Puppy
  uses them unsafely.
- The separately published `code-puppy-core-plugins` package (built-in plugins such as hooks, ACP, OAuth providers,
  the destructive-command guard). It is installed in the image so the CLI behaves normally, but it lives in a different
  repository. Report it only if the root cause is in this repository.
- Windows-only code paths (`win_shell_io.py`, Windows ACL hardening) cannot be exercised in this Linux image; report
  them only with a clear argument from the code.
- Denial of service that requires the user's own configuration or a hostile model provider the user chose, model
  quality issues, and token-cost amplification.
- Findings that need the attacker to already control the user's home directory or environment.

## How to exercise it

- `code-puppy-tests` runs the pytest suite offline the way CI does (fake provider keys, `CI=1`,
  `CODE_PUPPY_TEST_FAST=1`, no coverage). Pass paths or pytest args to narrow it, e.g.
  `code-puppy-tests tests/plugins/test_plugin_trust.py tests/mcp/test_project_config.py`. Offline, as root, the
  whole suite passes except 3 tests that rely on read-only file modes (root ignores them); they pass as non-root.
- Relevant tests: `tests/plugins/` (project plugin trust), `tests/mcp/` (project MCP trust), `tests/tools/`
  (shell and file tools, credential scrubbing in `test_command_runner_env.py`), `tests/test_provider_credentials.py`,
  `tests/test_atomic_io.py`, session migration tests.
- `code-puppy --help` works offline. An interactive run needs a model; without network access, drive the tool
  functions directly from Python or use the test fixtures. The venv is `/src/.venv` (on `PATH`); Chromium for the
  browser tools is under `/opt/ms-playwright`.
- A malicious-repository scenario: create a directory with `.code_puppy/plugins/<name>/register_callbacks.py`,
  `.code_puppy/mcp_servers.json` and `.code_puppy/agents/*.json`, `cd` into it with an empty `HOME`, and check that
  nothing from it executes before trust is granted.

## How we rate severity

- **Critical:** code execution from merely opening Code Puppy in an untrusted repository (no trust granted), or
  silent exfiltration of provider credentials or OAuth tokens to a third party, with no user action beyond normal use.
- **High:** code execution from a crafted session file; a bypass of the plugin or MCP trust gate that needs one
  plausible user action (for example, trusting a different, benign plugin); credential leak to a child process,
  log or session file readable by others; TLS verification silently disabled.
- **Medium:** bypass of the yolo-off approval prompt or a `fail_closed` guard; writes into
  `~/.code_puppy/plugins` through the file tools; terminal escape injection that can spoof an approval prompt;
  path traversal in session storage.
- **Low:** crashes or hangs on malformed model, MCP or catalog data; information leaks limited to local, user-owned
  files; issues that need the attacker to already control user-level config.
- A finding without a working reproducer is capped one level below what it would otherwise be.

## Reports and patches

Please include the exact command or Python snippet that reproduces the issue in the image, and keep patches small and
in the style of the surrounding code (Python 3.11+, type hints, files under 600 lines, tests in `tests/` next to the
existing ones for that module).
