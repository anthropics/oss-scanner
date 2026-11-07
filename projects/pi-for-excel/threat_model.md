# Pi for Excel threat model

## Project and scope

Pi for Excel is an MIT-licensed AI sidebar add-in for Microsoft Excel. Users connect a model provider, and the agent can read and change their workbook. Optional integrations add web retrieval, MCP tools, extensions, Python execution, LibreOffice conversion and terminal execution through local helper services.

The repository contains the browser taskpane and the local helper services. Both are in scope. Start with `docs/security-threat-model.md` for the project's existing security model, and verify its descriptions against the current implementation.

The security concern is the combination of sensitive spreadsheet data, provider credentials and optional access to local execution. The scanner should examine whether less trusted inputs can cross those boundaries without the authority the relevant feature requires.

## Sensitive data and untrusted inputs

Sensitive data includes provider API keys and OAuth credentials, workbook contents, conversation history, files and bridge authentication tokens. The taskpane stores credentials, settings and sessions in IndexedDB. Same-origin script execution could expose that data.

Treat workbook text, fetched pages, model responses and tool arguments, MCP responses, imported files and sessions, and inline or remote extension source as potentially hostile. Also consider requests from an unrelated website to local HTTP, HTTPS and WebSocket services. An attacker should not need control of the user's machine or their existing credentials to demonstrate such a boundary failure.

## Areas to examine

### Taskpane rendering and browser storage

Review `src/ui/`, `src/compat/marked-safety.ts`, `src/utils/`, `src/storage/`, `src/files/` and `vercel.json`. Look for script injection, unsafe links or automatic resource loads, credential exposure, and unintended access between stored workbooks or sessions. Review how content security policy interacts with the actual browser build.

### Extensions and integrations

Review `src/extensions/`, `src/integrations/` and the tools that install or invoke them. Inline and remote extensions normally use a sandboxed iframe, while trusted built-in or local-module extensions can use the host runtime. Remote sources and some permission controls have explicit settings. Review iframe messaging, source and origin checks, runtime selection, extension storage, capability checks and transitions between settings.

Use the actual defaults and enabled settings when describing a finding. A trusted host extension's intended privileges are different from an untrusted extension escaping its sandbox. A bypass of a claimed boundary remains relevant even if a more permissive mode also exists.

### Local helper services and authentication

Review `scripts/cors-proxy-server.mjs`, `scripts/proxy-target-policy.mjs`, `scripts/tmux-bridge-server.mjs`, `scripts/python-bridge-server.mjs`, the WebSocket paths and their shared helpers. Look for origin or loopback validation bypasses, unauthorized requests, token exposure, server-side request forgery, redirect handling errors and file path traversal. Document whether an attack works with default settings or requires a specific optional configuration.

Review `src/auth/`, `src/dev-auth-policy.ts` and the development middleware in `vite.config.ts`. The development server can import the developer's Pi credentials, so its access checks are relevant even though that middleware is not part of the production static build. Use synthetic credentials in an isolated home directory for reproductions.

### Workbook and execution tools

Review `src/tools/`, `src/execution/`, `src/excel/`, `src/workbook/` and `src/host/`. Look for unintended execution, unauthorized data access or modification, and failures of explicit execution or file permissions. Workbook and fetched content can also influence the agent, so distinguish demonstrated failures of an implemented security boundary from a model merely following hostile prose.

Python, terminal and Office.js execution are intentional capabilities when enabled and invoked with the required authority. Their existence alone is not a vulnerability. An unrelated website invoking a bridge, a sandbox escape or a path traversal would be a different case and should be investigated.

## Exercising the project offline

The Docker image contains the source at `/src`, npm dependencies, the production build in `dist/`, Playwright Chromium, Python, tmux and LibreOffice Calc. Run commands from `/src` without fetching additional dependencies:

```sh
npm run build
npm run test:security
npm run test:models
npm run test:context
npm run test:browser
```

`npm test` runs the broader Node test suite. Tests under `tests/` include synthetic host fixtures and local HTTP servers. Browser tests under `tests/browser/` use Playwright and intercept external requests. The scripts use the installed Node test runner and TypeScript loader, so no live model account is needed for those tests.

Start helper services directly with Node when a reproduction needs a listening service. Configure them with temporary files, synthetic secrets and isolated storage. Do not use production services or real user data.

The container cannot run Microsoft Excel, Office.js inside a real Office host, WPS desktop, or live provider OAuth. Browser fallback and mocked Office objects do not prove a defect in the real host. Reproduce browser and helper-service issues independently where possible, and state any remaining host or live-service prerequisites clearly.

## Reports and patches

For each finding, identify the affected revision, entry point, attacker control, required settings, trust boundary and demonstrated impact. Include a self-contained reproduction using synthetic data and a minimal candidate patch when possible. Distinguish default behavior from optional configurations, and explain any assumptions about the Office host or a model provider.

Do not infer severity solely from the presence of an execution tool or stored credential. Explain how an attacker obtains an unintended capability. Dependency vulnerabilities should identify a reachable defect in this project's use of the dependency, rather than repeat a version advisory without a project-specific reproduction.
