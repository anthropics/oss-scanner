# Threat model

## What this project does and where untrusted input enters
assistant-ui is a set of TypeScript libraries for building AI chat interfaces (React, React Native, Vue, terminal) plus runtime adapters for AI backends and agent protocols. It runs mostly in the end user's browser and in the application's server routes. Model output must be treated as attacker-controlled (prompt injection), as must tool results, MCP servers and remote agents. Untrusted input enters through:

- **Streamed responses**: text, markdown, tool calls, tool results and data parts decoded from backend streams (`packages/assistant-stream`, `packages/react-data-stream`, `packages/ai-sdk`, `packages/react-ai-sdk`, `packages/react-langgraph`, `packages/react-langchain`, `packages/react-ag-ui`, `packages/react-a2a`, `packages/react-google-adk`, `packages/eve`, `packages/react-opencode`, `packages/react-pi`).
- **Rendering of model output**: markdown and code (`packages/markdown`, `packages/react-markdown`, `packages/react-streamdown`, `packages/react-syntax-highlighter`, `packages/react-ink-markdown`), generative UI (`packages/generative-ui`, `packages/react-generative-ui`), and model-generated HTML and SVG widgets in sandboxed frames (`packages/generative-frame`, `packages/safe-content-frame`). XSS, sandbox or origin escape, script execution, CSP bypass, abuse of the frame-to-host bridge (`sendPrompt`, `openLink`, tool calls), or unsafe URL schemes reachable from model output are in scope.
- **User input**: composer text, mentions, attachments and file uploads (`packages/core`, `packages/react`, `packages/react-lexical`).
- **Persisted threads and cloud sync**: thread and message data loaded from storage or `packages/cloud` must not be able to execute code or corrupt runtime state when decoded.
- **MCP and tool integrations**: `packages/react-mcp`, `packages/mcp-docs-server`.
- **Build-time "use generative" compiler**: `packages/x-generative-compiler`, used by `packages/next`, `packages/vite` and `packages/metro`, splits a tool into server-only and client-only code. Server-only code or secrets reaching the client bundle is in scope.
- **VS Code webviews**: `packages/vscode` tunnels fetch from a webview to the extension host; a webview reaching hosts or capabilities it should not is in scope.
- **CLI**: `packages/cli` and `packages/create-assistant-ui` fetch templates and registry components and write files; path traversal or command injection from remote content is in scope. `packages/agent-launcher` spawns the Claude Code CLI; command or argument injection there is in scope.
- **Remote components**: `packages/remote-components-*` serve and host HTML documents as components, with a message protocol and value codec between host and frame.
- **Registry components**: `packages/ui` is the source of the styled components the CLI copies into users' projects.

## Components that matter most / least
- Most: stream decoding (`assistant-stream` and the adapters), markdown, HTML and generative UI rendering, `generative-frame` and `safe-content-frame`, `core`/`react` message handling, CLI file writes.
- Less: devtools (`react-devtools`), observability (`react-o11y`), styling and presentational packages (`tw-shimmer`, `heat-graph`, `diagrammatic`, `docs-theme`, `variants`).
- Out of scope: `apps/` (docs and websites), `examples/`, `templates/`, `python/`, `evals/`, packages prefixed `x-` other than `x-generative-compiler` (internal tooling), test files, and vulnerabilities that live entirely in third-party dependencies unless assistant-ui code makes them reachable.

## How to exercise it
- Library packages are built under `packages/*/dist`. Unit tests are vitest files colocated with sources (`packages/*/src/**/*.test.ts(x)`); run `pnpm --filter <package> test`.

## How you rate severity
- Critical: script execution in the host page (XSS) or sandbox escape triggered by model output or stored thread data under default configuration; remote code execution or arbitrary file write via the CLI.
- High: XSS that needs an uncommon but supported configuration; prototype pollution from stream or thread data; leaking data across threads or users; server-only code or secrets shipped to the client.
- Medium: denial of service of the chat UI from a single malicious response (e.g. unbounded memory or ReDoS); unsafe link handling requiring user interaction.
- Low: issues requiring the developer to opt into clearly unsafe behaviour (e.g. rendering raw HTML explicitly).

## Anything to leave alone
- Do not report that the application developer did not authenticate their own backend route; assistant-ui does not own the backend.
- Reports should include a minimal reproducer (a vitest test or small component) against the built packages and a patch against `packages/` where possible.
