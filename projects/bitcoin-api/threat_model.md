# bitcoin-api threat model

## Purpose and trust boundaries

bitcoin-api is an Apache-2.0-licensed, self-hostable FastAPI application for
Bitcoin fee intelligence and agent-facing Bitcoin data. Its former public
hosted deployment is paused. Scan the open-source code using synthetic data;
no production deployment, paid request or real transaction is needed.

Untrusted inputs include HTTP/WebSocket requests, JSON-RPC parameters,
transactions and PSBTs, webhook registration URLs, billing callbacks and
external price/node responses. API keys authorize different tiers. RPC,
billing, email and database credentials belong to the operator. Administrative
operations and user-owned subscriptions/alerts must remain isolated.

## Priorities

- Authentication and authorization in `src/bitcoin_api/auth.py`, key/admin
  routers, billing flows and middleware. Check tier gates and object ownership.
- `routers/rpc_proxy.py`: method allowlisting and parameters. Wallet/admin
  methods are forbidden; `sendrawtransaction` is an intentional exception to
  the read-only method set and requires the existing API-key gate.
- `routers/alerts.py`, notification workers and outbound clients: SSRF through
  untrusted webhook targets, redirects and credential forwarding.
- Rate limits, streaming/WebSocket lifetimes, caches, background jobs and
  database/indexer queries: practical resource exhaustion and unsafe input.
- Billing webhook verification and optional MCP integration. Optional external
  services should be mocked when exercising their first-party integration.

## Build and exercise

The complete checkout, installed development package, and optional billing,
email, Redis, analytics, AI and indexer dependencies are in `/src`.
Run `python /opt/oss-scanner/run-tests.py tests/ -q --ignore=tests/test_e2e.py
--ignore=tests/locustfile.py` as one command. `tests/conftest.py` supplies mocked
RPC responses and temporary test state. The suite disables the live indexer.
The omitted E2E/load tests require a separately running deployment; this does
not remove those application paths from the audit. The wheel is in `/src/dist`.

The test runner supplies a deterministic DNS answer for the positive-test
hostname `example.com` only. The selected address is a synthetic public-IP
fixture, not a live-DNS assertion. Every other hostname/address uses the normal
resolver, and the suite retains localhost, private-IP and metadata-IP rejection
tests. The fixture exists only in this test process; it does not configure DNS
or alter application code when an auditor runs/imports the application normally.

## Severity and scope

Demonstrated unauthenticated code execution or broad administrative takeover
is critical. Cross-user API-key/secret disclosure, billing/authorization bypass,
or reachable access to privileged internal resources is high. A bounded
availability failure is normally medium; show persistence or a wider blast
radius before raising severity. A paid-tier discrepancy needs a demonstrated
authorization or billing consequence, not only a different response shape.

An operator's configured Bitcoin RPC URL and database credentials are trusted
configuration. An attacker-controlled webhook URL crossing that boundary is
in scope. Do not infer a wallet-spending interface from the broadcast method;
broadcasting an already signed transaction does not grant signing authority.
Repository-external x402 extensions are separate projects; do not assume an
optional import means their implementation exists here. Dependency reports
must identify a reachable first-party call path. Include an offline reproducer,
affected revision, preconditions and a minimal patch with regression coverage.
