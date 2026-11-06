# Gemini Notebook MCP Server and CLI

## Project and security boundaries

This Python project provides the `nlm` command-line interface and the
`notebooklm-mcp` MCP server for Gemini Notebook (formerly Google NotebookLM).
It handles Google session credentials, notebook and source operations, generated
artifact downloads, and configuration of local AI clients. See `README.md`,
`AGENTS.md`, and `SECURITY.md` in the checkout for architecture and security policy.

The CLI and stdio server normally run on a user's computer with that user's
permissions. MCP tools can also be exposed through HTTP/SSE. Network transports
default to loopback, lack built-in authentication, and refuse non-loopback
binding unless the operator explicitly permits it. Do not assume the server is
a publicly accessible authenticated multi-user service. Investigate bypasses of
these safeguards and attacks against a default local deployment.

Treat notebook/source content, API responses, research results, artifact URLs,
download names, and imported files as potentially untrusted. Explain how an
attacker can influence each input and whether the victim must approve an action.
Distinguish an intentionally requested privileged operation from an attacker
crossing a security boundary through crafted content.

## Areas to prioritize

- `core/auth.py`, `core/credential_store.py`, `core/auth_migration.py`,
  `core/credential_backend_worker.py`, `services/auth*.py`, and `utils/config.py`:
  credential confidentiality, file permissions, encrypted storage, profile
  isolation, migration/rollback safety, and redaction of diagnostics.
- `core/download.py`, `services/downloads.py`, and `services/pipeline.py`:
  path containment, symlink handling, unintended overwrites, untrusted URLs,
  redirects, and any access to unintended local or network resources.
- `utils/cdp.py`, `utils/auth_browser.py`, and `core/cdp_transport.py`:
  browser selection, account isolation, safe cookie extraction, and process or
  connection handling. Do not report CDP's inherent lack of authentication alone.
- `mcp/server.py`, `mcp/tools/`, and `services/`: transport binding safeguards,
  validation, confirmation checks for destructive operations, and error handling.
- `cli/commands/setup*.py` and `cli/setup_safety.py`: configuration writes,
  containment, and preservation of existing client configuration.

## Offline build and testing

The Dockerfile places the checkout at `/src`, installs the project in editable
mode with its locked development dependencies in `/src/.venv`, and builds a
wheel and source distribution in `/src/dist`. Python 3.12 and `uv` are installed;
the virtual environment is on PATH and `UV_OFFLINE=true` is set after building.

From `/src`, run:

```sh
pytest -q --tb=short -m 'not e2e and not wizard_e2e and not real_os_store'
nlm --help
notebooklm-mcp --help
```

Tests use mocks and temporary directories. The default pytest configuration
also excludes wizard and real-keystore tests. Live Google tests are disabled
unless `NOTEBOOKLM_E2E` is set. Do not enable live tests, log into Google, mount
real credentials, or request access to a maintainer's cookies. Platform-specific
macOS/Windows keystore behavior cannot be fully exercised in this Linux image;
its implementations and mocked tests remain available for review. Chromium is
installed so mocked login tests can discover a supported browser executable;
no authenticated browser or desktop keyring session is required.

## Scope and reports

Follow the checkout's `SECURITY.md`. Google's hosted services are out of scope.
An attack that requires already possessing the victim's Google session cookies
is out of scope; a flaw in this project that discloses those cookies is in scope.
Do not include real credentials or sensitive notebook content in reproductions.

Report the affected commit, file/line, attacker prerequisites, reachable input,
specific impact, and a minimal offline reproducer using synthetic data. Assess
severity from demonstrated impact and deployment assumptions; do not classify
intentional operations or speculative chains as vulnerabilities without showing
the missing security boundary. Suggest a focused patch and a regression test
where practical. Deduplicate reports that share the same root cause. Deliver
findings privately through the scanner's configured reporting channel.
