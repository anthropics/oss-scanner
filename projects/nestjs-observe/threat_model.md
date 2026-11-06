# Threat model

## What this project does and where untrusted input enters
`@nestjs/observe` is an in-process observability agent for NestJS applications. It hooks into
Nest's lifecycle (controllers, guards, interceptors, pipes, resolvers, gateways, microservice and
queue handlers, scheduled jobs), patches database drivers (`pg`, `mysql2`, `mssql`, `mongodb`) and
outbound HTTP (`fetch`/`undici`, `node:http`/`https`), and records traces, errors, logs and runtime
metrics. A detached worker thread serialises the telemetry and sends it, authenticated with an app
key and secret, to a collector (`https://observe-api.nestjs.com` by default, or a configured
`endpoint`). A CLI (`npx @nestjs/observe link`) fetches credentials and wires the SDK into a project.

The agent runs inside the host application's request path and sees everything that path sees, so
two things matter: it must never change or break what the application does, and it must not send
data off-host that its redaction is documented to remove. Untrusted input enters through:

- **Inbound requests and messages**: everything a client sends to the instrumented application
  (URL, query string, headers, body, GraphQL documents, WebSocket and microservice payloads, queue
  job data). The protocol hooks in `src/protocols` (`http-observe-agent.service.ts`,
  `graphql-observe-agent.service.ts`, `graphql-operation-parser.ts`, `rpc-`, `ws-`, `queue-`,
  `schedule-observe-agent.service.ts`, `job-trace-runner.ts`) and `src/instrument` run on that
  data before and after the application's own code.
- **Trace propagation**: `src/utils/default-trace-id-generator.util.ts` adopts a client-supplied
  `x-request-id` header or microservice metadata as the trace id, and `src/outgoing` forwards it
  on outbound requests.
- **Request capture**: `src/utils/capture-request.util.ts` records headers (and bodies, when
  `capture.body` is on) for failed and slow requests.
- **Redaction**: `src/utils/log-redactor.ts`, `src/utils/sensitive-keys.ts`,
  `src/utils/redact-url-query.ts`, and `src/outgoing/sql-statement.util.ts` (which strips literal
  values from SQL before recording it). Log lines, error messages, captured requests, URLs and
  query strings all pass through these before they leave the process.
- **Error capture**: `src/utils/source-context.util.ts` and `src/utils/source-map-resolver.util.ts`
  read source files and source maps from disk for the frames of a thrown error. Error messages and
  stack text can contain request data.
- **Driver and HTTP patches**: `src/outgoing` (`http.integration.ts`, `pg.integration.ts`,
  `mysql2.integration.ts`, `mssql.integration.ts`, `mongodb.integration.ts`, `patch-method.util.ts`)
  wrap library methods the application calls with data that may come from clients.
- **Collector responses**: `src/agent` (`observe-agent.worker.ts`, `detached-observe-worker.ts`,
  `degraded-ingest.protocol.ts`, `observe-agent.shared-buffer.ts`) sends batches and parses what the
  collector answers. A collector, or anything between it and the
  application, is not trusted to run code in the host process.
- **CLI**: `src/cli` (`link.ts`, `project-setup.ts`, `project-files.ts`, `wire-application.ts`,
  `package-manager.ts`) talks to the hosted service, then writes `.env`, `.gitignore`,
  `package.json` scripts and the application's module and `main.ts`, and runs the project's package
  manager.

## Components that matter most / least
- Most: redaction (`src/utils/log-redactor.ts`, `sensitive-keys.ts`, `redact-url-query.ts`,
  `capture-request.util.ts`, `src/outgoing/sql-statement.util.ts`), the protocol hooks in
  `src/protocols` and `src/instrument` (anything that runs on every request), the driver and HTTP
  patches in `src/outgoing`, trace-id handling, and source-context file reads.
- Also important: `src/agent` (credential handling, transport, response parsing, memory bounds of
  the shared buffer) and `src/cli` (files it writes and commands it runs).
- Less: `src/encoders`, `src/custom-metrics`, `src/objectives`, `src/profiling`,
  `src/services/node-runtime-metrics.service.ts`, which handle data the agent produced itself.
  `src/testing` contains test helpers only.
- Out of scope: `*.spec.ts` and `*.int-spec.ts` files, `scripts/`, the hosted collector and
  dashboard (not in this repository), and vulnerabilities that live entirely in the instrumented
  libraries (Nest, database drivers, BullMQ, undici) unless this package's code makes them
  reachable.

## How to exercise it
- After the Docker build, the SDK is compiled into `dist/`. Tests: `npm test` (unit, vitest) and
  `npm run test:int` (boots real Nest applications on local ports, one file at a time; a local sink
  stands in for the collector). The queue and database suites need Redis, PostgreSQL, MySQL and
  MongoDB, which are not in this image; those suites skip themselves.
- `src/**/*.int-spec.ts` show the full wiring (`createObserveModule()`, `ObserveModule.forRoot()`, an
  `endpoint` pointing at a local server) and are the easiest base for a reproducer that inspects
  exactly what is sent.

## How you rate severity
- Critical: code execution in the host application from request data, or from a collector
  response.
- High: data that the default redaction is documented to remove (credentials, `authorization` and
  cookie headers, sensitive keys, secrets matching the default patterns, SQL literal values,
  sensitive query parameters) reaching the collector; a single request, message or job that
  crashes the host process, or makes the instrumented handler fail, return a different result, or
  skip a guard, interceptor or pipe it would run without the agent; the app key or secret sent to a
  host other than the configured endpoint; the CLI writing outside the project directory or running
  something other than the project's package manager.
- Medium: redaction gaps that need a non-default but documented option; a client-chosen trace id
  that escapes `REQUEST_ID_PATTERN` (collision with or injection into another trace, header or log
  injection on outbound requests); source-context reads of files outside the application; memory
  or CPU growth driven by request data that the documented caps should bound; ReDoS in parsing or
  redaction that needs sustained traffic.
- Low: issues that need the application developer to opt in to clearly unsafe behaviour.

## Anything to leave alone
- Do not report that data the developer explicitly chose to capture (`capture.body: true`, a
  header named in `capture.headers`, attributes from `setAttributes` / `tags` / `getUserId`, logs
  with `forwardLogs` on) is sent to the collector. Report it only if redaction that should still
  apply to it did not.
- Do not report that telemetry is sent to the configured `endpoint` (or `OBSERVE_ENDPOINT`). That is
  the product; an operator who controls the environment chooses where it goes.
- Do not report that a valid `x-request-id` header is adopted as the trace id. That is documented;
  report only values that should have been rejected.
- Reports should include a minimal reproducer (a spec in the style of `src/**/*.int-spec.ts`, with a
  local collector that shows exactly what was sent) and a patch against `src/` where possible.
