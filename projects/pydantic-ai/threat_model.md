# Threat model: Pydantic AI

The maintainers' threat model is `/src/THREAT_MODEL.md`. Read it first: it maps every trust boundary, names
the control that owns it, links the component documentation and lists published advisories by failure
pattern. This file summarises it and adds what the scanner needs. Where the two differ, `THREAT_MODEL.md`
wins.

## What this project does and where untrusted input enters
Pydantic AI is an agent framework for Python. This uv workspace holds several packages:
- `pydantic_ai_slim/pydantic_ai/`: the agent runtime, model providers, tools, MCP, UI adapters, realtime,
  durable execution and instrumentation.
- `src/pydantic_ai_harness/`: capabilities for agents (file system, shell, Code Mode, sandboxes, memory,
  sub-agents, guardrails and others).
- `pydantic_graph/`, `pydantic_evals/`, `clai/` (the CLI and its local web interface) and `examples/`.
- `src/pydantic_clai2/`: CLAI 2, which is not launched yet.

The application is trusted: its code, its configuration, the tools, dependencies, credentials, MCP servers
and execution backend it chooses. Untrusted input is:
- Client-submitted protocol messages that reach a UI adapter (AG-UI, Vercel AI): history, tool calls and
  results, approvals, frontend tool definitions, file references.
- Model output, including tool arguments. Treat them as untrusted input to the tool implementation.
- URLs and the content downloaded from them, MCP responses, tool results and repository files.
- Browser requests to a local web interface.

## Components that matter most
1. **UI adapters and history**: `pydantic_ai_slim/pydantic_ai/ui/` (`ag_ui/`, `vercel_ai/`, `_adapter.py`,
   `_messages_builder.py`), `messages.py`. Of interest: client history that selects provider state,
   instructions, uploaded files or tool calls it should not; server instructions, internal endpoints or
   other users' state disclosed to the client; a history round trip that turns plain data into a `FileUrl`
   or an `UploadedFile`.
2. **URL fetching**: `pydantic_ai_slim/pydantic_ai/_ssrf.py` (`safe_download`), `_file_input.py`,
   `common_tools/` and the harness browser capabilities. Of interest: SSRF through alternate address forms,
   redirects, DNS and hostname normalization, access to private or metadata addresses, and response size
   limits applied after the expensive work.
3. **Local web interfaces**: `pydantic_ai_slim/pydantic_ai/ui/_web/`, `_cli/`, `clai/`. Of interest:
   cross-origin requests, DNS rebinding, and request-controlled UI assets.
4. **Tools, approvals and deferred calls**: `_tool_execution.py`, `tool_manager.py`, `_deferred.py`,
   `external_events.py`, `toolsets/`, `capabilities/`. Of interest: a tool that runs without the approval it
   requires, including through delegated, resumed, background and Code Mode paths.
5. **Telemetry and secrets**: `_instrumentation.py`, `_otel_messages.py`, `models/instrumented.py`,
   `providers/`. Of interest: content exported despite a setting that suppresses it; credentials in request
   settings, URLs or MCP configuration that reach traces, UI events or another service; a provider
   credential sent to an origin other than its `base_url`.
6. **Availability**: every path above. Of interest: work that grows super-linearly with untrusted input,
   an allocation that outlives its request (concurrency slots), and blocking the event loop.
7. **Harness execution boundaries**: `src/pydantic_ai_harness/pydantic_ai_harness/` (`code_mode/`,
   `file_system/`, `shell/`, the `*_sandbox/` backends, `permissions/`, `peers/`). Judge each against the
   boundary the "Harness and CLI execution boundaries" table documents for it, not against a stronger one.

## How to exercise it
- `tests/` is a pytest suite. Run `pytest -n logical --dist=loadgroup` from `/src`, or one file with
  `pytest tests/test_ag_ui.py`. Model requests are replayed from cassettes in `tests/**/cassettes/`; tests
  marked `*_live` need credentials or a daemon and are skipped.
- `pydantic_ai.models.test.TestModel` and `pydantic_ai.models.function.FunctionModel` run an agent with no
  network, and `FunctionModel` lets a PoC choose the model output. Drive UI adapters with a Starlette app and
  `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`.
- Every extra is installed except `mcp-tasks` and `sentence-transformers`, so the examples that use
  `sentence-transformers` fail. So do the Pixeltable tests in `tests/harness/pixeltable/`, which cannot reach
  their database here. `TYPECHECK_EXAMPLES=false` is set, because pyright needs Node.js.
- Answer the "Proposed report-evaluation questions" of `THREAT_MODEL.md` in each report: the deployment
  profile, the attacker-controlled input, the path to the protected resource and the control that owns it.

## How we rate severity
Score a library finding for a reasonable embedding scenario, as `THREAT_MODEL.md` asks.
- **Critical**: code execution on the host, or escape from a boundary documented as an isolation boundary,
  from untrusted input under a documented configuration.
- **High**: SSRF to private or metadata addresses past `safe_download`; a client that changes execution or
  provider access through adapter history; a required approval bypassed; credentials or other users' state
  disclosed; a browser reaching a local web interface cross-origin.
- **Medium**: an availability issue that meets the bar in "Availability and resource lifetime" (about a
  second of blocked event loop or CPU, or hundreds of megabytes, at an input size the default cap admits or
  at 1 MB); content or secrets exported to telemetry despite a setting that suppresses them; the High issues
  when they need an unusual but documented configuration.
- **Low**: issues that need the attacker to control application-authored input.

## Anything to leave alone
`THREAT_MODEL.md` treats these as bugs or application responsibilities, not vulnerabilities:
- `LocalWorkspace`, `WindowsWorkspace` and `BubblewrappedWorkspace` are not isolation boundaries. A bypass of
  file-tool containment or of allow, deny and read-only patterns that stays within the OS user's authority
  is a correctness bug.
- `ToolCallJudge` and `ApprovalReviewer` are model-based filters, and prompt-injection defences are hints.
  A model that follows injected text is not a finding; a tool that runs without its required approval is.
- Authentication, tenant identity, CORS, CSRF and authorization of tool actions belong to the application.
- Cost that grows linearly with input the application can bound, and pathological cost from input the
  application authors (its code, agent specs, tool schemas, the MCP servers it chooses).
- Unlaunched packages (`src/pydantic_clai2/`), `examples/`, documentation snippets, `docs/`, `scripts/`, and
  the repository's own CI and agentic workflows under `.github/`.
- Vulnerabilities in third-party dependencies or CPython themselves.
