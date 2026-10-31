# Threat model

## What this project does and where untrusted input enters

Sockudo is a self-hosted realtime messaging server written in Rust. It speaks the Pusher Channels
protocol (Protocol V1, wire-compatible with Pusher client and server SDKs) plus a Sockudo-native
Protocol V2 (history/rewind/recovery, versioned mutable messages, annotations, presence history,
delta compression, tag filtering, AI Transport), an Ably-compatible protocol surface, and a push
notification pipeline (FCM, APNs, Web Push, HMS, WNS). A deployment hosts many *apps*; each app has
a key/secret pair and its own channels, connections and limits. Nodes scale horizontally over a
pub/sub adapter (Redis, Redis Cluster, NATS, Kafka, Pulsar, RabbitMQ, Google Pub/Sub, Iggy, ...).

Untrusted input enters in these places:

- **WebSocket clients** (`GET /app/{appKey}`, `crates/sockudo-server/src/ws_handler.rs`,
  `crates/sockudo-adapter/src/handler/`). Anyone on the network can connect with only a public app
  key. Every frame (subscribe, unsubscribe, client events, presence, signin, V2 history/rewind,
  recovery, annotations, message mutations, AI Transport frames) is attacker controlled. Treat
  connection-level identity as unverified until a valid channel-auth / user-auth signature or
  capability token has been checked.
- **Channel and user authorization.** Private, presence and encrypted channels require an HMAC
  signature produced by the app's backend with the app secret (`crates/sockudo-core/src/auth.rs`,
  `token.rs`). Capability tokens are JWTs (`crates/sockudo-core/src/capability_token.rs`). Forging
  or replaying an auth signature, subscribing to a private/presence channel without one, using a
  signature for one socket/channel on another, spoofing `user_id` / presence `user_info`, or
  exceeding the capabilities a token grants are all in scope.
- **HTTP REST API** (`/apps/{appId}/...`, `crates/sockudo-server/src/http_handler/`,
  `push_http.rs`, routed in `crates/sockudo-server/src/bootstrap/router.rs`). Requests are
  authenticated with the Pusher API signature scheme (`auth_key`, `auth_timestamp`,
  `auth_signature`, `body_md5`) in `crates/sockudo-server/src/middleware.rs`. Signature bypass,
  timestamp/replay problems, and using one app's credentials to read or write another app's data
  (cross-tenant access via `{appId}`, channel names, message serials, push device IDs, publish IDs)
  are high-value. Unauthenticated requests must not reach handler logic.
- **Cross-tenant isolation.** One app must never observe or affect another app's channels,
  presence, history, versioned messages, annotations, push registrations or provider credentials,
  including across nodes via the horizontal adapter and via shared cache/history backends.
- **Versioned messages and annotations.** Update/delete/append of messages and publish/delete of
  annotations must enforce the configured mutation auth (own-scoped mutations require a verified
  actor whose identity matches the original creator) identically over HTTP and WebSocket.
- **History, rewind and recovery.** Cursors and serials from clients are opaque but attacker
  supplied. Reading history of a channel the caller is not authorized for, crafting cursors that
  cross channels/apps, or recovery that delivers messages from before an authorization was granted
  are in scope.
- **Tag filters and delta compression.** V2 clients send filter expressions
  (`crates/sockudo-filter`) and negotiate delta encodings (`crates/sockudo-delta`). Expressions
  that cause unbounded CPU/memory, and delta state that leaks one subscriber's or channel's data to
  another, are in scope.
- **Ably-compatible surface** (`crates/sockudo-ably-compat`): JSON and MessagePack decoding,
  token/key auth and REST endpoints get the same treatment as the native protocol.
- **Push** (`crates/sockudo-push`): device registrations, channel subscriptions, publish requests
  and templates come from authenticated app backends or (where allowed) clients. Provider
  credentials are stored encrypted. Leaking credentials or device tokens, sending to devices of
  another app, and template injection are in scope.
- **MCP server** (`crates/sockudo-mcp`, `crates/sockudo-server/src/mcp`): scoped bearer tokens with
  per-app access lists. Scope or app-list bypass is in scope.
- **Origin validation** (`crates/sockudo-core/src/origin_validation.rs`) for apps that restrict
  allowed origins.

Trusted inputs:

- The config file, environment variables, and the app-manager backend contents (MySQL, Postgres,
  DynamoDB, SurrealDB, ScyllaDB, ...) are written by the operator and are trusted. Webhook URLs and
  push provider endpoints come from app config and are trusted (SSRF via operator-configured URLs is
  out of scope; SSRF via client-supplied data is in scope).
- Messages arriving from other Sockudo nodes over the horizontal adapter backend are trusted to the
  degree the backend is (an attacker with write access to the operator's Redis/NATS/Kafka is out of
  scope), but malformed messages must not crash a node.
- The metrics port (`/metrics`, default 9601) and `/usage` are meant to be bound to an internal
  network; their lack of authentication is by design.

## Components that matter most / least

- Most important: `crates/sockudo-adapter/src/handler/` (authentication, subscription_management,
  signin_management, message_handlers, validation, recovery, annotations, presence_update),
  `crates/sockudo-core/src/auth.rs`, `token.rs`, `capability_token.rs`,
  `versioned_message_auth.rs`, `origin_validation.rs`, `crates/sockudo-server/src/middleware.rs`,
  `crates/sockudo-server/src/http_handler/`, `push_http.rs`, `crates/sockudo-protocol`.
- Also in scope: `crates/sockudo-ably-compat`, `crates/sockudo-push`, `crates/sockudo-mcp`,
  `crates/sockudo-filter`, `crates/sockudo-delta`, `crates/sockudo-rate-limiter`,
  `crates/sockudo-webhook` (outgoing webhook signing), the horizontal adapters and replay buffer in
  `crates/sockudo-adapter`, the SQL app-manager backends in `crates/sockudo-app` (injection through
  app IDs / keys taken from requests), `crates/sockudo-server/src/history`.
- Less important: `crates/sockudo-metrics`, `crates/sockudo-cache`, `crates/sockudo-queue`,
  `crates/sockudo-ai-transport` validation helpers.
- Out of scope: `client-sdks/`, `server-sdks/`, `dashboard/`, `docs/`, `benches/`, `tests/`,
  `tools/`, `charts/`, `ops/`, `crates/sockudo-simulator`, example configs in `config/`, and
  third-party crates unless Sockudo uses them unsafely.

## How to exercise it

- The server binary is built at `target/debug/sockudo` with `--features full`. Run it with
  `target/debug/sockudo --config config/config.toml` (local adapter, memory backends; no external
  services needed). `config/config.json` is a JSON variant. It listens on port 6001 for HTTP and
  WebSocket, and 9601 for metrics.
- The default config defines an app with id `app-id`, key `app-key`, secret `app-secret`. A
  WebSocket client connects to `ws://127.0.0.1:6001/app/app-key?protocol=7`.
- Unit tests: `cargo test --workspace --lib --offline`. Integration tests that need live backends
  (Redis, Postgres, NATS, ...) are either `#[ignore]`d or expect the service at a local address
  (for example `REDIS_URL`, default `redis://127.0.0.1:16379/`). `redis-server` is installed in
  the image; start one with `redis-server --port 16379 --daemonize yes` for the Redis-backed tests.
- `crates/sockudo-adapter/src/test_support.rs` and `crates/sockudo-server/src/http_handler/test_support.rs`
  have helpers for driving handlers in-process.

## How you rate severity

- Critical: unauthenticated or cross-app remote code execution; HTTP API signature bypass;
  reading or publishing to another app's channels; leaking app secrets or push provider
  credentials.
- High: subscribing to private/presence/encrypted channels without valid auth; forging presence
  identity or user sign-in; mutating or deleting another user's messages/annotations when
  own-scoped auth is configured; reading history/recovery for unauthorized channels; any memory
  safety issue in `unsafe` code; a single unauthenticated client crashing (panicking) the whole
  server process.
- Medium: denial of service by a single client or request that exhausts CPU/memory beyond the
  configured limits (rate limits, max payload, max connections, filter complexity), rate-limit
  bypass, information leaks of channel/user metadata within the same app.
- Low: issues that require operator-level config or access to the backend stores, or that only
  affect metrics/observability accuracy.
- Panics that only kill one connection's task without affecting others are low unless they leak
  resources unboundedly.

## Anything to leave alone

- Pusher Protocol V1 behavior that matches Pusher itself (for example, public channels need no
  auth, client events need `client-` prefixed names on private/presence channels, the app key is
  public) is intended for compatibility; report it only if Sockudo deviates from Pusher in an
  unsafe direction.
- Unauthenticated metrics and health endpoints (`/metrics`, `/up`, `/ready`, `/live`) are by
  design.
- Config options whose names or docs say they disable security (for example disabling origin
  checks or running without auth for local development) are out of scope when enabled.
