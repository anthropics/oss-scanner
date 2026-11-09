# Clio: threat model and severity guide for the scanner

Clio is an XRP Ledger API server (ISC licensed, https://github.com/XRPLF/clio, written in C++23). It is built to
serve `rippled`-compatible JSON-RPC and WebSocket API calls at scale. It does not take part in consensus or the
peer network. It pulls validated ledgers from one or more `xrpld` servers over gRPC and WebSocket (ETL), stores
them in Cassandra or ScyllaDB, and answers read requests (`account_info`, `account_tx`, `ledger`, `book_offers`,
`nft_*`, `tx`, `server_info` and so on) from that store. Write requests such as `submit` are forwarded to `xrpld`.

Clio is usually exposed directly to the public internet, so the API surface is the main concern. It holds no keys
and moves no funds, so the worst outcomes are remote code execution on the Clio host, serving wrong ledger data
to clients, and taking the service down.

## Where untrusted input enters

- **The JSON-RPC and WebSocket API** (`src/web`, `src/rpc`). HTTP and WebSocket servers (Boost.Beast, optional
  TLS) parse requests from any client: framing, JSON, command names and parameters. Each handler in `src/rpc/handlers`
  validates its own input (account IDs, ledger indexes, markers, limits, hashes, binary blobs). A single client is
  a realistic attacker.
- **Request handling controls** (`src/web/dosguard`, `src/web/ng`): rate limiting, connection and request-size
  limits, admin versus public roles (admin password or allowed IPs). A public client reaching an admin-only
  command, or a way around the DoS guard, is in scope.
- **Subscriptions** (`src/feed`): WebSocket clients subscribe to streams, accounts and order books. Resource
  growth per subscriber, and ordering or data leaks across subscribers, are in scope.
- **ETL input from the connected `xrpld`** (`src/etl`): ledger data, state diffs and transactions arrive as
  protobuf over gRPC, and as JSON over WebSocket. The server is configured by the operator and is largely
  trusted, but a malformed or hostile response that corrupts the database or crashes Clio is worth reporting
  (note that it needs a hostile `xrpld`).
- **Forwarding** (`src/rpc` forwarding to `xrpld`): requests relayed to `xrpld` and replies relayed back. Look for
  injection of fields that change which command runs, and for leaks of admin-only data.
- **Binary parsing of XRPL objects**: Clio decodes ledger objects and transactions with `libxrpl` (serialization,
  `STObject`, `SerialIter`) when it serves and formats data. Crafted values stored in the ledger (by a transaction
  that was validated on the network) are attacker-controlled data.
- **The database layer** (`src/data`): CQL statements are built from request values. Look for query injection
  and unbounded scans or result sets driven by request parameters.
- **Configuration** (`src/util/config`): the operator supplies the config; treat it as trusted.

## What matters most, and what is out of scope

Most important, roughly in order:

1. **Remote code execution or memory corruption** reachable from the API (HTTP/WebSocket parsing, JSON handling,
   handler input, `libxrpl` decoding of ledger data).
2. **Serving wrong data**: a handler that returns balances, offers, transactions or ledgers that differ from the
   ledger, or that mixes data across ledgers or requests, so a wallet or exchange acts on it.
3. **Public-to-admin escalation** and DoS guard bypass.
4. **Denial of service by a single client**: a request that crashes Clio, hangs a worker, or makes the server do
   unbounded work or use unbounded memory (large limits, marker abuse, expensive queries such as `book_offers`
   and `account_tx`, subscription growth), beyond what the DoS guard is meant to bound.
5. **Database query injection** and corruption of stored data.
6. **TLS and authentication handling**: certificate checks, admin password comparison (timing), and secrets in logs.

Out of scope, or not what we mean by security:

- Third-party dependencies themselves (Boost, OpenSSL, the Cassandra driver, libxrpl internals, fmt, spdlog, and so
  on). Clio's wrappers and use of them are in scope; a bug inside the upstream library is theirs. Bugs in `libxrpl`
  that `xrpld` shares should be reported with the `libxrpl` entry point they come from.
- The test and tooling trees (`tests/`, `benchmarks/`, `cmake/`, `conan/`, `docs/`, `.github/`) and the migration
  helper.
- Operator choices: exposing the admin interface, running without TLS, an empty admin password in the config, or a
  rate limit set too high.
- Economic and protocol behavior of the XRP Ledger itself.
- 32-bit-only issues: this image is x86-64.

## The image: how to build, run and exercise it

The checkout is `/src`; `git -C /src rev-parse HEAD` names the commit under scan. **Everything runs offline, and
the binary was built inside xrpld's Nix dev shell, so run it from inside that shell:** prefix commands with
`nix develop .#gcc-plain --command` and run from `/src`. The build is in `/src/build`; the server binary is
`/src/build/clio_server` (a Release build at `-O1` with `-g1 -fno-omit-frame-pointer`; the unit tests are not built).

- `nix develop .#gcc-plain --command ./build/clio_server --verify docs/examples/config/example-config.json` checks a config.
- Clio needs a Cassandra or ScyllaDB backend and an `xrpld` server to run normally, and neither is in the image.
  For API work, build a small harness against the handler or parser under test (headers under `/src/src`, the
  library objects in `/src/build`), or build the unit tests inside the shell
  (`cmake -S . -B build -Dtests=ON` with the same toolchain file, then `cmake --build build --target clio_tests`;
  the mock backend in `tests/unit` stands in for the database).
- Fuzz or review the request path from the HTTP/WebSocket layer through `src/rpc` handlers and their input validators.

Where novel bugs are most likely: handler parameter validation (markers, limits, ledger specifiers, binary and
`ledger_hash` forms), the code that merges cached and database data, subscription feeds, forwarding, and the
DoS guard. The HTTP and JSON layers are Boost-based and have had more review.

## How we rate severity

- **Critical**: remote code execution on the Clio host; unauthenticated admin access; a way to alter the stored ledger.
- **High**: memory corruption reachable from the public API without proof of code execution; serving wrong
  ledger data that a wallet or exchange would act on; public-to-admin escalation.
- **Medium**: a single request that crashes Clio or exhausts CPU or memory beyond the DoS guard (say who can
  trigger it and whether it affects one node); an over-read that does not disclose sensitive data; query injection
  with limited reach.
- **Low**: an inconsistency with `rippled`'s response format with no security impact; secrets in debug logs that
  need admin access; information disclosure of nonsensitive data.
- **Not a bug**: a request correctly rejected with an error code; behavior that needs the operator's config to be
  hostile; a slow request that the DoS guard bounds as designed.

## Things to leave alone

- Style, naming, `const`-correctness and other cleanups. The project runs clang-format, clang-tidy and pre-commit.
- Differences from `rippled` behavior that are documented in Clio's API docs.
- 32-bit-only issues.
- Diagnostics inside third-party headers pulled in through Conan.

## How we would like reports and patches to look

One finding per report, with the commit, the exact command, and the output (sanitizer, gdb or assertion output).
Prefer a reproducer such as a raw HTTP or WebSocket request, or a small program against a handler. State who
controls the input and what the attacker gains. Patches should be a minimal diff against `develop` in the
surrounding style, with a regression test under `tests/unit`.
