# Threat model

## What this project does and where untrusted input enters
Agent402 is a self-hostable HTTP and MCP server (Express, Node 22) that sells 500+ web tools to AI agents,
paid per request over x402 (USDC on several chains), MPP, Stripe card payments and prepaid credits, or free
behind a proof-of-work gate for pure-CPU tools. It also ships three npm packages that run inside other
people's servers and agents: `tollbooth/` (pay-per-crawl middleware for site owners), `client/` (a buyer SDK
that signs payments) and `mcp/` (an MCP server that pays from the user's wallet).

Every request is untrusted. Input enters through:
- **Tool inputs**: JSON bodies and query strings on every tool route (`src/tools/*-kit.js`, mounted in
  `src/server.js`). Many tools fetch URLs, parse HTML, PDF, images, audio, YAML, CSV or JWTs supplied by the caller.
- **Payment headers**: x402 `PAYMENT-SIGNATURE`/`X-PAYMENT`, MPP `Authorization: Payment`, credits bearer keys,
  idempotency keys (`src/payments.js`, `src/mpp-shim.js`, `src/mpp-tempo.js`, `src/mpp-stripe.js`,
  `src/credits.js`, `src/idempotency.js`, `src/payer.js`, `src/replay-guard.js`).
- **Proof-of-work solutions** for the free tier (`src/pow.js`, `src/free-tier.js`).
- **Webhooks**: Stripe events (`src/human-checkout.js`, `src/stripe-subscriptions.js`).
- **MCP**: the hosted connector at `/mcp` (`src/mcp-http.js`, `src/mcp-mpp.js`, `src/mcp-tasks.js`).
- **Crawled third-party content**: the seller index fetches and parses other servers' 402 challenges, OpenAPI
  documents and discovery files (`src/x402-index.js`, `src/mpp-index.js`, `src/discovery.js`). A hostile
  seller controls that content completely.
- **Operator routes** under `/__operator/*`, protected by an operator token (`src/operator.js`).
- **Agent memory**: paid key-value and document storage keyed on the payer (`src/tools/memory.js`).

## Components that matter most / least
Most:
- **Money correctness**: anything that lets a buyer get a paid result without a settled payment, be charged
  for a failed call, be charged twice for one call, or spend another payer's credits, memory or receipts.
  The intended rule is in `CLAUDE.md` ("x402 settlement ordering"): a handler status >= 400 is never settled,
  and a 200 is charged only if settlement then succeeds. Caching, credits debits and the refund ledger key off
  the final response.
- **Payer identity**: identity-bound routes (memory, my-usage, attest, feedback) trust only the signed
  EIP-3009 `authorization.from` (`src/payer.js`). Spoofing a payer is critical.
- **Outbound requests the server makes for a caller**: SSRF guard in `src/tools/fetch-guard.js`
  (`assertPublicUrl`, `safeFetch`, `isPrivateIp`) and every fetch that should go through it. Reaching
  internal addresses, cloud metadata or loopback-only routes is high or critical.
- **Spending wallets**: route-execute buys from external sellers on the buyer's behalf (`src/tools/route-execute.js`,
  `src/x402-buyer.js`, `src/solana-buyer.js`, `src/tempo-buyer.js`, `src/external-spend-guard.js`). Anything that
  makes the server pay an attacker more than the buyer paid, or bypass the spend ceilings, is critical.
- **Parsing hostile seller content** in the index (prototype pollution, ReDoS, unbounded memory).
- **Published packages** (`tollbooth/`, `client/`, `mcp/`): a bug that lets a server drain a client's wallet,
  or lets a crawler bypass tollbooth's paywall, affects other people's deployments.
- Stored XSS or header injection on the HTML pages (`src/pages.js`, `src/seo.js`, `src/*-page.js`).

Less:
- `scripts/` (tests and operator tooling run by the maintainers), `workers/`, `wiki/`, `docs/`, `adapters/`
  (thin wrappers), `facilitator/` (a separate service with its own threat model).
- Answers from upstream data providers being wrong. That is a correctness issue, not a vulnerability, unless
  it crosses into the money or identity rules above.

## How to exercise it
- Boot without keys or payment rails: `FREE_MODE=true PORT=3000 node src/server.js`. Every tool then answers
  without payment, which is the easiest way to reach tool code. `/openapi.json`, `/api/pricing` and
  `/llms.txt` list every route with an example input.
- Paid-path behaviour is exercised by suites that boot their own server in paid mode against stub
  facilitators: `scripts/test-idempotency.js`, `scripts/test-credits.js`, `scripts/test-mpp-shim.js`,
  `client/test.js`. Most `scripts/test-*.js` files run offline with plain `node`.
- `tollbooth/test.js`, `tollbooth/edge.test.js`, `tollbooth/features.test.js` exercise the middleware.
- The scan runs offline, so tools that call upstream APIs will fail at the network step. The code before
  and after that call (input validation, URL checks, parsing of the upstream answer) is still in scope.

## How you rate severity
- **Critical**: obtaining a paid result without paying; charging a buyer for a failed call or twice for one
  call; acting as, or reading the data of, another payer; making the server's spending wallets pay out beyond
  their guards; remote code execution; SSRF to cloud metadata or internal services; operator-route access
  without the token.
- **High**: SSRF to other private addresses; prototype pollution or a crash of the whole process reachable
  from a request or from crawled seller content; stored XSS on a first-party page; bypassing the free-tier
  proof-of-work on wallet-only tools; a tollbooth or client bug that loses a user's funds or bypasses payment.
- **Medium**: ReDoS or memory exhaustion needing modest traffic; information disclosure of internal state
  (environment variable values, file paths, upstream keys, wallet keys are critical); rate-limit bypass.
- **Low**: issues that need operator misconfiguration, or that only affect the maintainers' own scripts.

## Anything to leave alone
- Free-mode behaviour (`FREE_MODE=true`) serving everything without payment is intended for local
  development and self-hosting tests.
- Tools that intentionally fetch a public URL the caller supplies are not SSRF by themselves; report only a
  way past `fetch-guard.js` or a fetch that skips it.
- Price levels, business logic choices and upstream data quality are out of scope.
- Reports should include a request (curl or a short Node script against a free-mode or paid-mode boot from the
  test suites) that reproduces the issue, and a patch where possible.
