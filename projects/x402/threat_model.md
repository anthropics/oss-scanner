# x402 threat model

## What this project does and where untrusted input enters

x402 is a payment protocol built on HTTP status 402. A **client** asks a **resource server** for a paid
resource, gets back `402 Payment Required` with a list of payment requirements, signs a payment for one of them,
and repeats the request with the signed payload. The resource server checks the payload itself or through a
**facilitator** (`/verify`), serves the resource, and has the payment settled on-chain (`/settle`). The
normative text is in `specs/` (`x402-specification-v2.md`, `schemes/`, `transports-v2/`, `extensions/`); each
scheme document has a security section, and the SDKs are expected to enforce it.

This repository holds the reference SDKs (`typescript/`, `go/`, `python/x402/`, `java/`) and the EVM contracts
(`contracts/evm/`). Every role treats the other two as untrusted:

- **Resource server** (middleware for Express, Hono, Fastify, Next, Gin, Echo, net/http, FastAPI, Flask, a Java
  servlet filter, MCP servers). Untrusted: the whole HTTP request of an anonymous internet client, above all the
  `PAYMENT-SIGNATURE` header (v2) and `X-PAYMENT` header (v1), which carry base64 JSON; the method and path used
  to match a paid route; the `x402/payment` field of an MCP tool call; extension data sent by the client
  (Sign-In-With-X, payment identifier, gas sponsoring, offer and receipt).
- **Facilitator** (`x402Facilitator` and the `facilitator/` half of each mechanism). Untrusted: the bodies of
  `/verify` and `/settle` (payment payload plus payment requirements), from any caller. A facilitator holds a
  funded key that pays gas, and on Solana it is the fee payer and co-signs the client's transaction.
- **Client** (`x402Client`, the fetch and axios wrappers, MCP clients, the browser paywall). Untrusted: the 402
  response (`PAYMENT-REQUIRED` header or body), every field of the payment requirements (amount, asset, `payTo`,
  network, `extra`), the `PAYMENT-RESPONSE` header, and for MCP the tool result.
- **Contracts** (`x402ExactPermit2Proxy`, `x402UptoPermit2Proxy`, `x402BatchSettlement`, `periphery/`). Untrusted:
  every caller and every argument.

Trusted: the configuration of whoever integrates an SDK (routes, prices, `payTo`, the facilitator URL, signers,
hooks), the facilitator a resource server has chosen (for the answers it gives that server), and the chains,
RPC nodes and wallets themselves.

## Components that matter most / least

Most important:

- Payment verification in the facilitator mechanisms, where a wrong answer costs money. EVM:
  `typescript/packages/mechanisms/evm/src/{exact,upto,batch-settlement,auth-capture}/facilitator`,
  `go/mechanisms/evm` (including `verify_1271.go`, `verify_universal.go`, `verify_strict.go` for smart-wallet
  signatures), `python/x402/mechanisms/evm`. Solana: `typescript/packages/mechanisms/svm/src/exact/facilitator`
  (`instructionLayout.ts`, `smartWalletVerification.ts`, `signatureVerification.ts`), `go/mechanisms/svm`,
  `python/x402/mechanisms/svm`.
- The core of each SDK: `typescript/packages/core/src` (`server/`, `facilitator/`, `http/x402HTTPResourceServer.ts`
  with its route matching and path normalisation, `schemas/`), `go/*.go` and `go/http`, `python/x402/*.py` and
  `python/x402/http`.
- The contracts in `contracts/evm/src` (not `mocks/`).
- The client half of each mechanism: what a client agrees to sign.
- Extensions in `typescript/packages/extensions/src`, `go/extensions`, `python/x402/extensions`: Sign-In-With-X
  (it grants access without a payment), payment identifier (idempotency), the two gas-sponsoring extensions (the
  facilitator broadcasts for the client), offer and receipt.
- The paywall, `typescript/packages/http/paywall` and the generated templates in `go/http` and
  `python/x402/http/paywall`: HTML that a resource server returns to browsers, with values from the request and
  the route configuration in it.
- MCP transport: `typescript/packages/mcp`, `go/mcp`, `python/x402/mcp`.

In scope, lower priority: the other network mechanisms (`typescript/packages/mechanisms/*` apart from `evm` and
`svm`, `python/x402/mechanisms/{cardano,tvm}`, `go/mechanisms/casper`); the v1 packages that are still published
and used (`typescript/packages/legacy`, `go/legacy`, `python/legacy`); the Java SDK (`java/`, v1 only);
`typescript/site`, which serves x402.org and a public testnet facilitator under `app/facilitator`.

Out of scope: `examples/`, `e2e/`, `docs/`, `static/`, `foundation/`, `scripts/`, `contracts/evm/vanity-miner`,
`contracts/evm/script`, test files and mocks, and third-party dependencies and git submodules (unless x402 uses
them unsafely).

## How to exercise it

Everything is built at `/src` and all dependencies are in the image. There is no network, so nothing can reach a
real chain or a hosted facilitator; the unit tests use mock signers and mock facilitators instead. The machine is
small, so run one package at a time.

- TypeScript (`/src/typescript`, pnpm workspace, Vitest): `pnpm --filter @x402/core exec vitest run`, or with a
  file path for one test file. The `test` script of a package adds a coverage threshold and can fail with every
  test passing. Rebuild one package with `pnpm --filter @x402/<name> build`; a test that imports another package
  uses that package's build, which the image has for everything under `packages/`. The `test:integration`
  scripts need funded testnet keys and RPC access and cannot run here.
- Go (`/src/go`): `go test ./...`, or one package such as `go test ./mechanisms/evm/...`. `make test` adds the
  race detector. Tests under `test/integration` are behind build tags and need the network.
- Python (`/src/python/x402`): `uv run pytest tests/unit`, or a single file.
- Java (`/src/java`): `mvn -o test`. The two tests in `org.x402.integration` start Jetty and ask it for its URI,
  which is null on a machine with only a loopback interface; they fail there for that reason alone.
- Contracts (`/src/contracts/evm`): `forge test --no-match-contract ForkTest` (unit, fuzz and invariant tests;
  the fork tests need an RPC URL). `anvil` is installed, so a local chain is available for a reproducer that
  needs the contracts and an SDK together; `src/mocks/` has the tokens to deploy on it.
- To drive a resource server or a facilitator over HTTP, start from the minimal ones in
  `examples/typescript/servers`, `examples/typescript/facilitator`, `examples/go/facilitator/basic` and
  `examples/python/facilitator`. Their own dependencies are not installed; import the built workspace packages
  instead, or copy the wiring into a script inside `typescript/packages/core`.

## How we rate severity

Rate by what an attacker in one of the untrusted positions above gains, with the SDK in its documented default
configuration.

- **Critical**: funds move, or get locked, against what the payer signed (in the contracts, or because an SDK
  client signs something other than the payment requirements it showed and accepted). A facilitator's key is made
  to spend its own balance beyond the gas of a valid settlement, for example by co-signing a Solana transaction
  that moves the fee payer's funds. A facilitator or resource server accepts a payment that is forged, or that is
  for another recipient, asset, network or a lower amount, so that anyone gets paid resources for free. Remote
  code execution in any SDK from a header, request body or response.
- **High**: a paid route is served without a payment through request shaping (path, method or encoding tricks
  against route matching, header parsing differences between verification and settlement). One payment is
  accepted for several deliveries where the scheme or the payment-identifier extension promises it is not.
  Sign-In-With-X accepts a signature that is invalid, replayed, expired or bound to another domain. `/verify`
  answers valid for a payload that `/settle` then rejects for a reason the verification is specified to check.
  Cross-site scripting in the paywall from request-controlled values. A client is led to sign for more than the
  amount it was shown, or to leak its key or a reusable signature.
- **Medium**: a single request or response that crashes or hangs a resource server, facilitator or client
  (uncaught exception or Go panic in middleware, unbounded parsing, catastrophic regular expressions). Making a
  facilitator pay gas for settlements that revert, at a bounded cost per request. Disclosure of another payer's
  payment data. Memory or storage growth without limit from unauthenticated requests.
- **Low**: hardening and defence in depth with no demonstrated loss of funds, free access or crash. Problems that
  need a facilitator to attack the very resource server that chose it. Problems only in the testnet site.

A report on a finding that touches money needs a reproducer: a failing unit test, a script against the built
packages, or a Foundry test. Without one, cap it at medium. A divergence between the SDKs (one language accepts
what another rejects) is worth reporting when the laxer side is wrong against `specs/`; say which one is.

## Anything to leave alone

- A resource server can be configured to serve before settlement completes, and then a payment that fails to
  settle has been served for free. That is a documented trade-off. Report it only if it happens in a mode that
  promises settlement first.
- A resource server trusts the facilitator it configured. "A malicious facilitator can lie to its server" is not
  a finding. A facilitator moving a payer's funds other than as signed is one.
- Front-running, reorgs, RPC outages, gas price swings and other properties of public chains; bugs in Permit2,
  OpenZeppelin, USDC or a wallet.
- Keys, addresses and endpoints in tests, `e2e/`, `examples/` and `.env` templates: they are placeholders or
  testnet fixtures.
- The contracts under `contracts/evm` have been audited (`contracts/evm/audits/`). Do not restate what an audit
  report already lists as acknowledged; a finding there has to be new.
- Outdated dependencies with no reachable path in x402, missing rate limiting, and missing security headers on
  the example servers.
