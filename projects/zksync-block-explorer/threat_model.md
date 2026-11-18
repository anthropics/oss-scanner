# Threat model: ZKsync block explorer

## What this project does and where untrusted input enters

The block explorer indexes a ZKsync chain and serves its data: `packages/worker` and `packages/data-fetcher` read
blocks, transactions, logs, token transfers and contract metadata from the chain's RPC and write them to PostgreSQL;
`packages/api` is a NestJS REST API over that database; `packages/app` is the Vue web application. The same codebase
runs in two modes:

- **Public mode** serves permissionless chains (it runs explorer.zksync.io). All chain data is public by definition.
- **Prividium mode** (`PRIVIDIUM=true` on the API, with `PRIVIDIUM_PERMISSIONS_API_URL`,
  `PRIVIDIUM_SESSION_SECRET` and the session settings) serves ZKsync Prividium chains, where chain data is
  **permissioned**: the API sits behind the chain's permissions service, authenticates the caller against it, and must
  return only the entities the caller is entitled to see. In this mode the explorer is part of the chain's
  confidentiality boundary. Prividium and its permission model are documented at
  [docs.prividium.zksync.io](https://docs.prividium.zksync.io).

Untrusted input:

- Every HTTP request to `packages/api`: path and query parameters (addresses, hashes, block ranges, pagination,
  filters), and in Prividium mode the caller's session/credential material.
- Chain content ingested by `worker` and `data-fetcher`: contract bytecode, event data, calldata, token names,
  symbols and metadata, and verified-source metadata are all author-controlled by whoever deployed or called a
  contract. Everything indexed must be treated as attacker-supplied when it is later filtered, matched, or rendered.
- Everything `packages/app` renders, including the ingested fields above and URL state.

## Trust assumptions

- The chain RPC endpoint the worker reads from is the operator's own node: trusted for availability and protocol
  correctness, but the *content* it returns (user transactions, contract-emitted data) is untrusted.
- In Prividium mode, the chain's permissions service is the authority on identity and entitlements. This codebase is
  trusted to *ask it correctly* and to scope every read by the answer; any path that skips that check or scopes by the
  wrong identity is a finding.
- In public mode there is no confidentiality: every row in the database is public. Reports about "information
  disclosure" of chain data in public mode are not findings.
- The database is trusted infrastructure; queries built from request input must still be injection-safe.
- Operators configure secrets (`PRIVIDIUM_SESSION_SECRET` and the like) properly; compose files in the repository are
  development fixtures.

## Components that matter most / least

Highest priority:

- The Prividium-mode plumbing in `packages/api`: the middleware/guards that establish the caller's identity against
  the permissions service, the session cookie handling, and **every query path that must carry the caller's
  entitlement scope**. The recurring bug class is a route, filter or join that returns or matches rows outside the
  caller's scope, or a route that is reachable without the mode's gating (path normalization, casing, alternate
  prefixes and method handling all matter here).
- Address/hash/filter handling in `packages/api` generally: parameter validation, pagination bounds, and query shape
  (unbounded scans from unauthenticated input are a real cost).
- `packages/worker` and `packages/data-fetcher` ingestion: parsing attacker-authored logs, token metadata and
  bytecode must not corrupt other entities' rows (a collision or spoof that makes one contract's data appear as
  another's misleads every downstream consumer), crash the indexer on crafted input, or write unescaped content that a
  consumer later trusts.
- `packages/app` rendering of ingested fields (token names/symbols, verified-source content, calldata decoding):
  script injection through chain-sourced content is the classic explorer bug.

Lower priority: metrics and health endpoints, dev compose files, `scripts/`.

Out of scope: `*.spec.ts` fixtures and mocks, `reth_chaindata/` (a local dev chain snapshot), CI workflows.

## How to exercise it

- The unit suites need no database, were already run once at image build time, and run offline. The `api`, `worker`
  and `data-fetcher` packages use jest; on a small machine run them with
  `npm run test:ci --workspace packages/<name> -- --maxWorkers=2 --testTimeout=30000` — jest sizes its worker pool
  from the visible core count, and without the cap and headroom, contention can push one slow setup hook
  (`packages/api/src/prividium.spec.ts`) past its 5-second timeout, which is load, not a finding. The `app` package
  uses vitest and takes no jest flags: `npm run test:ci --workspace packages/app`.
- `npm run test:ci` runs all four at once exactly as CI does; expect the api hook-timeout flake above when CPUs are
  scarce.
- The unit suites mock the database and HTTP layers, so the strongest proof of concept is a spec next to the code
  under test that demonstrates the wrong decision (a guard passing a request it must reject, a query builder emitting
  an unscoped filter, a renderer emitting unescaped content). Name the file and test in the report.
- There is no live chain, database or permissions service in this image; end-to-end behaviour must be reasoned from
  the code.

## How we rate severity

- **Critical:** in Prividium mode, reading chain data without the entitlement that covers it — a route reachable
  around the gating, an identity mix-up, or a query that ignores the caller's scope; SQL injection; remote code
  execution in any package.
- **High:** leakage between callers within an otherwise-gated route (one caller's query or filter matching rows only
  another caller is entitled to see); cross-site scripting in `packages/app` through chain-sourced or API-sourced
  content (rendered token names, metadata, verified-source content, decoded calldata); session forgery,
  fixation or replay in Prividium mode; ingestion that lets one contract's crafted data impersonate or overwrite
  another entity's records.
- **Medium:** oracles in Prividium mode that reveal the existence or shape of data the caller may not read (error
  divergence, count/pagination behaviour, timing the API introduces); unauthenticated requests that trigger unbounded
  database work (sustained unavailability of the API for every user rates High); indexer crashes on crafted chain
  content (in public mode anyone transacts; in Prividium mode even permitted authors are untrusted).
- **Low:** disclosure-only issues confined to public mode, where the data is public anyway (cross-site scripting stays
  High in either mode); missing hardening headers; disclosure of non-secret configuration; findings requiring the
  operator to misconfigure documented settings.

## How we would like reports and patches

- One root cause per report. State the mode (public, Prividium, or both), the actor, and any non-default
  configuration required.
- Where possible, the reproducer is a jest/vitest spec that runs offline with the commands above.
- Keep patches minimal and in the package that owns the bug; database schema changes go in new TypeORM migrations.

## Anything to leave alone

- Public-mode visibility of chain data, transaction graphs, balances and contract code: that is what a public
  explorer is for.
- The development compose files and their placeholder secrets.
- Rate limiting and caching tiers that live in front of the production deployments rather than in this repository.
- Style, dependency-version and test-coverage observations.
