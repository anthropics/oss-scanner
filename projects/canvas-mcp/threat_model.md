# Threat model: Canvas MCP

Canvas MCP is a Model Context Protocol (MCP) server for the Canvas learning management system. An AI client
(Claude Desktop, Cursor, Codex and others) calls its tools to read courses, assignments, submissions,
discussions, pages and the Canvas Inbox, and, where the operator allows it, to grade, message, edit and delete.
The server is Python (`src/canvas_mcp/`). A TypeScript code API (`src/canvas_mcp/code_api/`) backs the opt-in
`execute_typescript` tool. Report vulnerabilities to the address in `SECURITY.md`, never in a public issue.

## Assets

- **Canvas API tokens.** A token carries every permission of the Canvas account that made it. Canvas has no
  narrower scope for these tokens (`SECURITY.md`, "Token Scope"). An instructor's token can read and change
  grades, message students and edit course content.
- **Student data.** Rosters, names, emails, submissions, grades, peer reviews, discussion posts and Inbox
  messages are education records under FERPA. The server masks student names and emails before tool output
  reaches the AI client when `ENABLE_DATA_ANONYMIZATION` is on, which is the default
  (`src/canvas_mcp/core/config.py`; the client-layer gate is `_endpoint_anonymization_mode` in
  `src/canvas_mcp/core/client.py`; tiers in `src/canvas_mcp/core/anonymization.py`).
- **Course content.** Pages, syllabi, assignments, rubrics, modules, announcements and groups. Some have no
  revision history in Canvas, so a wrong write can be permanent.

## Who is trusted, and where untrusted input enters

**Untrusted: text authored in Canvas.** Students, TAs, other instructors and anyone else who can write
something a user of this server will read. That covers page bodies, syllabus HTML, discussion posts and
replies, submissions and comments, Inbox messages, and short labels: display names, emails, filenames,
titles and group names. The server returns this text into an AI model's context, so it is a live
prompt-injection channel into an agent that holds a Canvas token. Read tools wrap it in provenance fences
(`<<<UNTRUSTED CANVAS CONTENT ...>>>`, block and inline forms) in `src/canvas_mcp/core/untrusted_content.py`.
`READ_TOOL_CONTENT_POLICIES` in that file records the trust decision for every read tool, and
`AGENTS.md` ("Untrusted Canvas content is fenced") documents the contract. Canvas error bodies are fenced too
(`format_canvas_error`).

**Semi-trusted: the AI model.** It chooses the tool calls, and injected content can steer it. Two controls
stand between a steered model and a write:
- Destructive and bulk tools need two calls. The first returns a preview and a single-use confirmation
  token. The token expires after 5 minutes and is bound to the exact previewed request and to the caller's
  credential (`ConfirmationGuard` in `src/canvas_mcp/core/write_confirmation.py`). The docstring there states
  the limit: the token proves the request did not change, not that a human approved it.
- The operator's `ALLOWED_WRITE_TOOLS` decides which tools with side effects exist at all
  (`src/canvas_mcp/core/tool_policy.py`). Every tool is classified there as read, Canvas write, local write or
  code execution. Further registration gates are `CANVAS_ROLE`, `STUDENT_WRITE_TOOLS` (empty by default) and
  `EXECUTE_TYPESCRIPT_ENABLED` (off by default).

**Local stdio mode (the default).** One user runs the server on their own machine with their own token from
`.env`. That user, their environment variables, their `.env` and their MCP client are trusted
(`SECURITY.md`, "Known Security Limitations"). Every registered tool is available unless `ALLOWED_WRITE_TOOLS`
is set. The local file tools (`download_course_file`, `upload_course_file`, the CSV and report exports) work
on the user's own filesystem.

**HTTP mode (`--transport streamable-http`).** One server process serves many callers. Each request carries
the caller's own Canvas token in `X-Canvas-Token` (`CanvasCredentialMiddleware` in `src/canvas_mcp/server.py`;
per-request context in `src/canvas_mcp/core/credentials.py`).
- The server refuses to start if `CANVAS_API_TOKEN` is set, so a request without a token can never fall back
  to a server token. A missing or blank `X-Canvas-Token` gets HTTP 401.
- The Canvas URL is pinned by the server's `CANVAS_API_URL`, which must be https. An `X-Canvas-URL` header is
  ignored.
- The server will not start ungated. It needs `MCP_ACCESS_KEYS` (checked against `X-MCP-Access-Key`), or
  `MCP_ALLOW_UNAUTHENTICATED=true` as the operator's statement that an external authenticator fronts it.
- With `ALLOWED_WRITE_TOOLS` unset, the server is read-only: no tool that changes Canvas exists.
- Local file tools refuse HTTP callers (`tests/security/test_file_tool_host_boundary.py`).
- Per-caller state (course aliases and labels, course metadata caches, course-policy verdicts, anonymization
  caches and statistics, confirmation tokens, group-creation run records) must stay with the caller that
  produced it (CHANGELOG 1.15.0; `AGENTS.md` on `resume_course_group_creation`).
- When the operator enables it, the access-request flow in `src/canvas_mcp/core/access/` serves two admin
  approval routes before any token check. Both act only on a signed token (`core/access/tokens.py`).

Canvas itself, at the configured `CANVAS_API_URL`, is trusted to authorize requests. Its response bodies are
not trusted, because users write them. The client follows a pagination link only to the same origin and
endpoint (`src/canvas_mcp/core/client.py`).

## Components that matter most

1. HTTP-mode isolation and credentials: `src/canvas_mcp/server.py` (middleware and startup checks),
   `core/credentials.py`, `core/cache.py`, `core/course_policy.py`, `core/client.py`, `core/access/`.
2. The write controls: `core/tool_policy.py`, `core/write_confirmation.py`, `core/guarded_edit.py`, and every
   tool that calls them in `src/canvas_mcp/tools/` (messaging, deletes, grading, rubrics, syllabus, content
   migrations, group creation, student writes).
3. Anonymization: `core/anonymization.py` and the endpoint tiers in `core/client.py`.
4. Untrusted-content fencing and text processing: `core/untrusted_content.py`, `core/html.py` (one bounded
   tokenizer for HTML), and the read tools that return Canvas-authored text.
5. Request building from caller input: tool parameter validation (`core/validation.py`), course and object
   identifiers that become Canvas API paths (`get_course_id` and `resolve_numeric_course_id` in
   `core/cache.py`; `tests/security/test_path_segment_injection.py`), and local file paths and CSV exports
   (`core/file_validation.py`, `core/csv_safety.py`).
6. The release and publish workflows in `.github/workflows/` (PyPI, the MCP Registry, GitHub Releases).

Lower priority, still in scope: `src/canvas_mcp/code_api/` and `tools/code_execution.py` (see the exclusions),
`resources/`, `core/logging.py` and `core/audit.py` (a token or student name written to a log matters).

Least important: `verify/` (Lean and TLA+ models of the confirmation state machine, not built here), `docs/`
(the static project site), `examples/`, `skills/`, `articles/`, `scripts/` and Markdown notes.

## How to exercise it

- The repository is at `/src`. Canvas MCP is installed in editable mode in `/src/.venv`, which is on PATH,
  with the `dev` group and the `hosted` extra. Node 24 is installed, and the code API's packages are in
  `/src/node_modules`. Nothing needs the network.
- Run the Python suite with `python -m pytest tests/ -q` and the code API suite with `npm test`. Security tests
  are in `tests/security/`. Useful starting points: `tests/test_http_transport.py` (the middleware),
  `tests/security/test_course_cache_isolation.py`, `tests/security/test_tool_policy.py`,
  `tests/security/test_confirmation_state_machine.py`, `tests/tools/test_delete_confirmation.py`,
  `tests/security/test_untrusted_content.py`, `tests/security/test_anonymization_endpoints.py` and
  `tests/security/test_text_processing_cost.py`.
- Write a proof of concept as a small pytest file. Mock Canvas with `httpx.MockTransport` (see
  `tests/tools/test_discussions.py`) or patch `canvas_mcp.core.client.make_canvas_request` (see the
  `mock_canvas_request` fixture in `tests/conftest.py`). Never send requests to a real Canvas.
- To run the server in HTTP mode offline:
  `CANVAS_API_URL=https://canvas.example.edu/api/v1 MCP_ACCESS_KEYS=test-key canvas-mcp-server --transport streamable-http --port 8819`.
  Send MCP requests to `http://127.0.0.1:8819/mcp` with `X-MCP-Access-Key: test-key` and a made-up
  `X-Canvas-Token`. Add `ALLOWED_WRITE_TOOLS=all` to expose the write tools.

## How we rate severity

State the transport (stdio or HTTP), the settings the attack needs, and who the attacker is: a Canvas user who
writes content, another caller of the same HTTP server, or a network client with no credential.

- **Critical**
  - In HTTP mode, one caller reads or changes data under another caller's Canvas credential, or gets data
    cached for another caller. This covers course lists and labels, anonymization maps, policy verdicts,
    confirmation tokens and group-creation run records.
  - In HTTP mode, a caller's Canvas token is disclosed to another party: in a response, a log another caller
    can read, an error message, or a request sent to a host other than `CANVAS_API_URL`.
  - A request is sent with a server-held credential when the caller supplied none.
- **High**
  - A Canvas write or a message send without its confirmation step. Examples: the first call writes; a token
    authorizes a change other than the one previewed (other target, recipients, body or match set); a token
    is accepted twice, after it expires, or for a different caller.
  - A tool with side effects is reachable although `ALLOWED_WRITE_TOOLS`, `CANVAS_ROLE`,
    `STUDENT_WRITE_TOOLS` or `EXECUTE_TYPESCRIPT_ENABLED` withholds it. This includes an HTTP server with
    `ALLOWED_WRITE_TOOLS` unset changing Canvas state.
  - With anonymization on, a student's real name or email reaches tool output on an endpoint or field the
    code says it masks.
  - Bypass of the HTTP access gate (`MCP_ACCESS_KEYS`), or a forged or reused access-approval token.
  - In stdio mode, the user's token is sent to a host other than `CANVAS_API_URL`, or a Canvas-supplied
    filename or content makes a local file tool write outside the directory the user chose.
  - A change to `.github/workflows/` that lets an outside contributor run code with publish credentials.
- **Medium to high: fence forgery.** Canvas-authored text closes a fence early, forges an end marker, or is
  returned unfenced by a read tool whose policy says it is fenced. Rate it high when the text is
  student-authored and reaches an educator's tool output with default settings. Rate it medium otherwise.
- **Medium**
  - Denial of service from crafted Canvas content, such as a regular expression or parser that takes
    super-linear time on a page body, discussion post or label. In HTTP mode, one request that blocks the
    event loop affects every caller.
  - An identifier that changes the Canvas API path so a request reaches a different endpoint or course.
  - CSV formula injection in an exported file.
  - A student name, email or Canvas token written to a local log.
- **Low:** crashes that fail one tool call, missing hardening without a demonstrated attack, and issues that
  only the operator or the local user can trigger.

## Reports and patches

Give the commit, the transport, the environment variables, the tool calls with their arguments and the mocked
Canvas responses. Include a pytest regression under `tests/` that fails before the fix, and assert what the
server sends to Canvas or what it must never send. Keep patches small, keep the existing error style (dict
tools return an `"error"` key, string tools return text starting with `Error`), and do not weaken an existing
test.

## Anything to leave alone

- **A model that obeys a correctly fenced injection.** Fencing marks provenance; it does not make injection
  impossible (`core/untrusted_content.py` docstring). It is a documented residual risk. So is a model that
  redeems its own confirmation token after it follows injected text (`core/write_confirmation.py` docstring);
  human approval is the MCP client's job. A fence that can be forged or skipped is in scope (see above).
- **Canvas's own authorization**: what a token may do in Canvas, Canvas permissions and roles, and Canvas
  API bugs.
- **The `execute_typescript` sandbox's egress limits.** Its network block is best-effort and does not hold
  at the container boundary. This is public as issue #157 (`SECURITY.md`, "What Code Execution Can Access").
  The tool is off by default. Enabling it removes the confirmation and fencing guarantees (`AGENTS.md`,
  "Security caveat"). Reaching `execute_typescript` while it is disabled or withheld is in scope (High).
- Anonymization limits that are documented: a pseudonym comes from the Canvas user ID alone, so it is the same
  in every course, and staff names are shown on purpose (`core/anonymization.py` docstring). The fields
  listed under "What Does NOT Get Anonymized" in `SECURITY.md` are not masked.
- What the local stdio user controls: their `.env`, environment, MCP client, and the paths they give the
  file tools.
- An HTTP server started with `MCP_ALLOW_UNAUTHENTICATED=true` and no authenticator in front of it. This
  includes trusting platform identity headers. The operator stated that one fronts it.
- Bugs in dependencies (FastMCP, the MCP SDK, httpx, the Azure SDKs) that no Canvas MCP code reaches.
