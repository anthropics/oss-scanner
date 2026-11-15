# Stagehand threat model

## What this project does

Stagehand is a browser-automation framework for AI agents. A developer's program uses an SDK (TypeScript
`packages/sdk-ts`, Python `packages/sdk-python`, or Go `packages/sdk-go`) to drive Chrome. The SDK can launch Chrome
locally or connect to a remote Browserbase session over CDP. Most of the logic runs inside a Chrome extension service
worker (`packages/extension`). It drives pages with CDP and calls LLMs for `act`, `extract`, `observe`, and agent
loops. The SDKs and the extension communicate over JSON-RPC, with schemas defined in `packages/protocol`. The `browse`
CLI (`packages/cli`) and the agent-framework integrations (`packages/integrations/*`) are published too. The
integrations expose Stagehand to LLM agents as tools.

## Trust boundaries and where untrusted input enters

Treat these sources as adversarial:

- **Web content.** This covers anything a visited site controls: DOM, accessibility tree, page JavaScript, frames,
  dialogs, downloads, cookies, redirects, and network responses. Stagehand visits arbitrary sites by design.
- **LLM output.** Model responses select elements, fill values, choose URLs, and in some modes produce code. Assume the
  model may be steered by the page (prompt injection).
- **Agent tool calls in `packages/integrations`.** The agent driving the tools is untrusted with respect to the host and
  to credentials.

These sources are trusted. They are not a security boundary:

- The developer's own code and configuration: SDK options, environment variables, `CHROME_PATH`, Chrome args, init
  scripts, file paths, `apiUrl` / base URLs, and custom LLM clients.
- The Browserbase API and the developer-chosen CDP endpoint. Robustness bugs in response handling are still welcome,
  but rate them Low.

## Security goals

1. Page content cannot escape the page realm. It must not reach the extension service worker, issue CDP commands, read
   other tabs or contexts, or run code on the host.
2. Credentials stay with the SDK process. The Browserbase API key, LLM provider keys, and signed CDP connect URLs must
   not reach the page realm, agent-visible tool output, logs, traces, or telemetry, under default configuration.
3. One session cannot read or act on another session, tenant, or browser context.
4. Developer-configured guards hold against adversarial input. These include domain allow/deny policies,
   credential redaction, and timeouts.
5. A locally launched Chrome's debugging endpoint cannot be driven by websites or by other origins.

## Components that matter most / least

- **Most:** `packages/extension` (privileged runtime; see `understudy/`, `services/`, `controllers/`,
  `callbackBatch.ts`, `rpcRouter.ts`), the SDK transport and launch code (`cdpClient`, `rpcClient`,
  `browserbase*`, local Chrome launchers in all three SDKs), and `packages/protocol` (input validation at the RPC
  boundary).
- **Medium:** `packages/integrations/*` (published agent tools and facades) and `packages/cli`.
- **Out of scope:** `packages/evals` (internal benchmark harness, not shipped), `packages/docs`,
  `packages/examples`, `scripts/`, `rules/`, `.github/`, and test fixtures. Known CVEs in third-party dependencies
  are out of scope unless you show a reachable path through Stagehand code. Bugs in Chrome itself and in the hosted
  Browserbase service are out of scope too.

## How to exercise it

The image is already built (`pnpm build`), and `CHROME_PATH` points at a local Chrome.

- TypeScript: `pnpm exec turbo run test:unit` and `pnpm exec turbo run test:browser`. The browser-runtime tests in
  `packages/sdk-ts/tests/browser-runtime/` launch local Chrome with the built extension. They are the best template
  for a proof of concept: serve a hostile HTML fixture from a local HTTP server and drive it with the SDK.
- Python: `cd packages/sdk-python && uv run --locked pytest`.
- Go: `cd packages/sdk-go && go test ./...`.
- Tests that need Browserbase or LLM API keys cannot run offline. Use a stub LLM client and local Chrome instead.

## How we rate severity

- **Critical:** web content or a malicious site achieves code execution on the host. Also Critical: theft of the
  Browserbase API key or LLM provider keys by web content or by an agent, or access to another session or tenant.
- **High:** web content reaches the extension service-worker realm or arbitrary CDP. Also High: bypassing a configured
  domain policy (for example to reach `file://` or internal hosts), credentials leaking to logs, traces, or agent
  output under default settings, or a website driving a locally launched Chrome's debug port.
- **Medium:** credential leaks that need a non-default debug or verbose mode, and SSRF or path issues that need
  uncommon but plausible developer configuration. Web content that hangs or crashes the runtime or session (ReDoS,
  unbounded recursion, memory blow-up) is also Medium.
- **Low:** denial of service that needs trusted input, crashes on malformed Browserbase or CDP responses, and
  defense-in-depth hardening.
- **Not a vulnerability:** prompt injection that steers the model only within the capabilities the developer
  granted, and anything that needs control of trusted inputs (developer code, options, environment, paths).

## Reports, patches, and deduplication

- Include a runnable proof of concept, preferably a vitest or pytest test using a local fixture page. Give the exact
  file and line where the boundary fails.
- Patches should be minimal, merge-ready, and come with a regression test. Keep each patch to the fix; don't refactor
  in the same change.
- Deduplicate by root cause. When the TypeScript, Python, and Go SDKs share the same flaw, file one report that lists
  every affected location.
