# Threat model

## What this project does and where untrusted input enters
assistant-ui is a set of TypeScript libraries for building AI chat interfaces (React, React Native, Vue, Svelte, terminal) plus runtime adapters for AI backends. It runs mostly in the end user's browser and in the application's server routes. Untrusted input enters through:

- **Model output and streamed responses**: text, markdown, tool calls, tool results and data parts decoded from backend streams (`packages/assistant-stream`, `packages/react-data-stream`, `packages/react-ai-sdk`, `packages/react-langgraph`, `packages/react-ag-ui`, `packages/react-a2a`, and other adapters). Model output must be treated as attacker-controlled (prompt injection).
- **Rendering of model output**: markdown and code rendering (`packages/react-markdown`, `packages/react-streamdown`, `packages/react-syntax-highlighter`, `packages/react-ink-markdown`), generative UI (`packages/generative-ui`, `packages/react-generative-ui`) and sandboxed HTML (`packages/safe-content-frame`). XSS, sandbox escape, script execution, or unsafe URL schemes reachable from model output are in scope.
- **User input**: composer text, attachments and file uploads (`packages/core`, `packages/react`).
- **Persisted threads and cloud sync**: thread/message data loaded from storage or `packages/cloud` must not be able to execute code or corrupt runtime state when decoded.
- **MCP and tool integrations**: `packages/react-mcp`, `packages/mcp-docs-server`.
- **CLI**: `packages/cli` and `packages/create-assistant-ui` fetch templates and registry items and write files; path traversal or command injection from remote content is in scope.

## Components that matter most / least
- Most: stream decoding (`assistant-stream`), markdown/HTML/generative UI rendering, `safe-content-frame`, `core`/`react` message handling, CLI file writes.
- Less: devtools (`react-devtools`), styling packages (`tw-shimmer`), build helpers.
- Out of scope: `apps/` (docs and websites), `examples/`, `python/`, packages prefixed `x-` (internal tooling), test files, and vulnerabilities that live entirely in third-party dependencies unless assistant-ui code makes them reachable.

## How to exercise it
- Library packages are built under `packages/*/dist`. Unit tests are vitest files colocated with sources (`packages/*/src/**/*.test.ts(x)`); run `pnpm --filter <package> test`.

## How you rate severity
- Critical: script execution in the host page (XSS) or sandbox escape triggered by model output or stored thread data under default configuration; remote code execution or arbitrary file write via the CLI.
- High: XSS that needs an uncommon but supported configuration; prototype pollution from stream or thread data; leaking data across threads or users.
- Medium: denial of service of the chat UI from a single malicious response (e.g. unbounded memory or ReDoS); unsafe link handling requiring user interaction.
- Low: issues requiring the developer to opt into clearly unsafe behaviour (e.g. rendering raw HTML explicitly).

## Anything to leave alone
- Do not report that the application developer did not authenticate their own backend route; assistant-ui does not own the backend.
- Reports should include a minimal reproducer (a vitest test or small component) against the built packages and a patch against `packages/` where possible.
