# RMCP threat model

RMCP is an MIT-licensed MCP server that lets AI clients run statistical analyses
in R. It supports local stdio and Streamable HTTP, structured statistical tools,
file import/export, plots, and a custom R execution tool. The Python package's
published maintainer contact is contact@gsood.com.

## Deployment and trust boundaries

RMCP runs R as the invoking operating-system user. Its R-code checks and operation
approval mechanism are guardrails, not an adversarial R sandbox. An authorized
caller of `execute_r_analysis` can supply R code; executing that code is intended
functionality. RMCP is not intended to isolate mutually distrustful tenants.

Remote HTTP deployments require a bearer token by default. Localhost can run
without authentication; an explicit `--allow-unauthenticated` option also exists.
Treat requests from callers without a valid token as hostile when authentication
is configured. Test authentication, routing, session handling, and browser-origin
interactions in that configuration. `/health` is intentionally public.

For structured tools, treat data values, column names, formulas, file paths, and
file contents as potentially attacker-controlled, even when a trusted client
submits them. A caller supplying data to a statistical tool has not requested
arbitrary R execution. Investigate unintended code execution through those inputs.

The VFS restricts file-tool access to configured roots, enforces read-only access
unless a write is approved, and stages authorized reads before passing them to R.
Investigate traversal, symlink and rename races, alternate path representations,
and inconsistent authorization between Python validation and R operations. Do not
interpret the VFS as confinement of deliberately supplied arbitrary R code.

## Priorities and scope

- `rmcp/transport/sdk.py`, `rmcp/core/sdk_adapter.py`, and `rmcp/cli.py`:
  HTTP authentication and transport integration, request handling, and defaults.
- `rmcp/security/vfs.py`, `rmcp/core/context.py`, and file/resource tools:
  access outside configured roots, unauthorized writes, and disclosure of files.
- `rmcp/r_integration.py`, `rmcp/tools/`, and `rmcp/r_assets/`:
  unsafe R interpolation, validation gaps, subprocess handling, and resource limits.
- Operation approval and error handling: unintended side effects through
  structured tools and disclosure of secrets or sensitive data in responses.

Scope findings to RMCP's own code or its use of dependencies. Vulnerabilities
solely in R, the MCP SDK, or another dependency should go to that dependency's
maintainers. Do not contact the hosted production server or external services;
run reproductions against a disposable local instance with synthetic data.

## Running the project and tests offline

The checkout is `/src`. Python, RMCP, its development dependencies, and the R
packages used by the normal integration suite are installed during the build.
The Python environment is `/opt/venv` and its commands are already on `PATH`.
No API keys or model-provider calls are needed for the deterministic tests.

```bash
cd /src
ruff check .
ruff format --check .
pytest tests/unit/ tests/integration/ tests/evals/ -q --tb=short
Rscript rmcp/r_assets/run_tests.R
rmcp list-capabilities
```

`tests/evals/test_mcp_server_evals.py` starts a real stdio server and uses the MCP
client to exercise statistical, malformed-input, filesystem, approval, and recovery
contracts. Unit and integration tests include focused transport and VFS checks.
Deployment scenario tests that launch Docker containers or reach hosted services
are separate from the offline command above. Tests that install additional R
packages need those packages added at build time before they can run offline.

Start a disposable HTTP instance with a test-only token using
`RMCP_API_KEY=scanner-local-test rmcp serve-http --host 127.0.0.1 --port 8080`.
Use only synthetic fixtures and temporary directories for file-write or deletion
proofs of concept.

## Severity and reports

Prioritize unauthorized execution, authentication bypass, sensitive file access,
and unintended writes. Assess severity from the demonstrated attacker capability
and deployment: unauthenticated remote execution can be critical; a meaningful
file-access or structured-tool injection boundary violation can be high. Describe
availability impact and required privileges for denial-of-service findings.

Intended execution of an authorized caller's custom R code, explicitly disabling
authentication, or ordinary numerical/modeling errors are not by themselves
security vulnerabilities. Report a concrete violated boundary rather than only a
dangerous API name or the absence of a general-purpose R sandbox.

Include the commit, entry point, required configuration and privileges, a minimal
offline reproducer, observed impact, and a proposed regression test. Group findings
with the same root cause. A minimal corrective patch is welcome.
