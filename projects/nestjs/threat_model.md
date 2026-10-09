# Threat model

## What this project does and where untrusted input enters
NestJS is a server-side Node.js framework. Applications built on it expose HTTP, WebSocket and
microservice endpoints, so untrusted input reaches framework code before any user code runs:

- **HTTP**: request routing, path/query/header/body extraction and parameter decorators in
  `packages/core/router`, `packages/core/helpers`, `packages/common/decorators/http`, and the HTTP
  adapters in `packages/platform-express` and `packages/platform-fastify` (including multipart
  uploads in `packages/platform-express/multer` and raw body handling).
- **Pipes**: `packages/common/pipes` (ValidationPipe, ParseIntPipe, ParseUUIDPipe, ParseArrayPipe,
  ParseEnumPipe, ParseFilePipe and file validators, etc.) are the documented way applications
  validate and transform request data. Validation bypasses or transformations that let unexpected
  values through are in scope.
- **Guards / interceptors / exception filters** in `packages/core`: anything that lets a request
  skip a guard, reach a different handler than the route implies, or leak internal error details
  through the default exception filter.
- **WebSockets**: `packages/websockets`, `packages/platform-socket.io`, `packages/platform-ws`
  (message parsing and dispatch to `@SubscribeMessage` handlers).
- **Microservices**: `packages/microservices` server transports (TCP, Redis, NATS, MQTT, RabbitMQ,
  Kafka, gRPC) and their deserializers. Brokers are usually on a private network, but a peer able to
  publish to a queue should still not be able to crash the process, execute code, or pollute
  prototypes.
- **Serialization**: `packages/common/serializer` (ClassSerializerInterceptor) — leaking fields the
  application excluded is in scope.

## Components that matter most / least
- Most: `core` (router, execution context, guards/pipes pipeline), `common/pipes`,
  `platform-express`, `platform-fastify`, `microservices` server-side deserialization.
- Less: `testing` (test utilities only), client-side microservice proxies talking to trusted servers.
- Out of scope: `sample/` (example apps), `integration/` and `**/test/` (test suites), `tools/`,
  `scripts/`, `gulpfile.mjs`, and vulnerabilities that live entirely in third-party dependencies
  (express, fastify, multer, socket.io, broker clients) unless Nest's own code makes them reachable.

## How to exercise it
- After the Docker build, packages are compiled in place under `packages/*`. Unit tests:
  `npm run test` (vitest). Tests live next to sources in `packages/*/test`.
- `sample/` contains small apps that show typical usage; `integration/` contains end-to-end specs
  (most need external services and will not run offline, but they show realistic wiring).

## How you rate severity
- Critical: remote code execution, or authentication/authorization bypass (e.g. a request that skips
  a guard or reaches a different handler) reachable by an unauthenticated remote client with default
  framework configuration.
- High: prototype pollution reachable from request data, validation bypass in a built-in pipe under
  its documented configuration, path traversal in static/file handling, crash of the whole process
  from a single request or message.
- Medium: information disclosure through default error responses, ReDoS or other resource exhaustion
  needing sustained traffic, issues that require an uncommon but supported configuration.
- Low: issues that require the application developer to opt in to clearly unsafe behaviour.

## Anything to leave alone
- Do not report "the developer forgot to add a guard / ValidationPipe" — the framework does not
  enforce these by default, by design.
- Do not report DoS that only exists because an app sets no body size limit or similar, if the
  default limit is in place.
- Reports should include a minimal Nest app (or unit test) that reproduces the issue against the
  compiled packages in this image, and a patch against `packages/` where possible.
