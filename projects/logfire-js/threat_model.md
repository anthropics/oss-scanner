# Threat model: Pydantic Logfire (JavaScript and TypeScript SDKs)

## What this project does and where untrusted input enters
This pnpm workspace holds the JavaScript SDKs for the Logfire observability platform, built on OpenTelemetry.
The packages are in `packages/`:
- `logfire-api` (published as `logfire`): the core API, scrubbing, formatting, managed variables and the CLI.
- `logfire-node`: the Node.js SDK. `logfire-browser`: the browser SDK. `logfire-cf-workers` and
  `otel-cf-workers`: Cloudflare Workers.
- `logfire-session-replay`: a browser recorder that uploads DOM snapshots.
- `logfire-agent-sandboxes` and `logfire-ai-sdk-code-mode`: clients that run model-written Python in Logfire
  Agent Sandboxes, with the application's tools staying in the host process.

The backend is closed source and is not in this repository.

The application, its code, its configuration and its environment variables are trusted. Untrusted input is:
- Data the application handles and the SDK records: headers, URLs, bodies, error messages, attribute values.
- Incoming trace context and baggage headers.
- In the browser: the page content the recorder captures, and URLs of requests and resources.
- Model output: the Python program and the tool arguments that code mode receives.
- Responses from the network.

## Components that matter most
1. **Scrubbing and redaction**: `packages/logfire-api/src/AttributeScrubber.ts`, `exportScrubbing.ts`,
   `packages/logfire-browser/src/telemetryUrls.ts`, `BrowserUrlSpanProcessor.ts`. Of interest: a value that
   the default patterns should redact but that reaches an exporter through another attribute, event or
   package (Node.js, browser and Workers each have an export path).
2. **Session replay privacy**: `packages/logfire-session-replay/src/privacy.ts`, `capture.ts`, `recorder.ts`,
   `transport.ts`. Text and input values are masked by default (`maskAllText`, `maskAllInputs`). Of interest:
   text, input values or blocked subtrees that are uploaded despite the defaults, and uploads sent to a host
   other than the configured one.
3. **Code mode and agent sandboxes**: `packages/logfire-ai-sdk-code-mode/src/` (`codeMode.ts`, `approval.ts`,
   `limits.ts`, `stubs.ts`, `values.ts`) and `packages/logfire-agent-sandboxes/src/`. Of interest: a
   model-written program that calls a host tool without the approval it requires, calls a tool that was not
   offered, bypasses a limit, or makes the host process run code or read files.
4. **Credentials**: `packages/logfire-api/src/tokenBaseUrl.ts`, `src/cli/` (`credentials.ts`, `authClient.ts`,
   `client.ts`), `packages/logfire-node/src/credentials.ts`, `logfireConfig.ts`. Of interest: a token sent to
   a host other than the configured one, stored with loose file permissions, or written to logs and errors.
5. **Trace context**: `packages/logfire-node/src/noExtractPropagator.ts`. Of interest: incoming context or
   baggage that is honoured when distributed tracing is off.
6. **Serialization and formatting**: `packages/logfire-api/src/serializeAttributes.ts`, `formatter.ts`,
   `fingerprint.ts`, `src/vars/` (template rendering and composition). Of interest: a recorded value that
   takes super-linear CPU time or unbounded memory, pollutes a prototype, or throws into the application.

## How to exercise it
- Run `pnpm run test` from `/src` for every package, or `pnpm --filter <package name> test` for one. The
  packages are already built (`pnpm run build`). Tests are Vitest files next to the sources (`*.test.ts`).
- `packages/logfire-session-replay/browser-tests/` needs Playwright browsers, which are not installed; use
  the jsdom tests instead.
- `examples/` has small applications for each runtime.

## How we rate severity
- **Critical**: code execution in the host process from recorded data or from a model-written program.
- **High**: a token sent to another host or written to logs; a code mode approval or limit bypass; session
  replay uploading text or input values that the default settings mask; a scrubbing bypass for the default
  patterns under the default configuration; a small recorded value that exhausts CPU or memory, or crashes
  the application, under the default configuration.
- **Medium**: the same issues when they need a non-default but documented option; incoming trace context
  honoured when distributed tracing is off.
- **Low**: cost that grows linearly with the recorded data, and issues that need a malicious Logfire backend.

## Anything to leave alone
- The Logfire backend, the sandbox service itself, and vulnerabilities in dependencies (`@opentelemetry/*`,
  `rrweb`, `@pydantic/monty`) themselves, unless the SDK uses them in an unsafe way.
- Scrubbing and masking are pattern-based by design: a secret under a name, or in a shape, that no default
  pattern matches is not a finding. Neither is content recorded after the application turns masking off.
- A frontend application token in browser code is public by design: it can only write telemetry for that
  frontend application. An application that puts a project write token in a browser bundle is misusing it.
- `examples/`, `docs/`, `scripts/`, `agent/`, `plans/` and `reports/`.
