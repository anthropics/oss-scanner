# rotki threat model

## What this project does

rotki is a self-hosted, local-first crypto portfolio tracker, accounting and tax reporting tool. It
runs on the user's own machine (Electron desktop app for Linux/macOS/Windows) or on the user's own
server (Docker image). There is no rotki-operated backend holding user data: everything lives in a
local, SQLCipher-encrypted per-user database.

What an attacker would want from a rotki install:

- **Exchange API keys and secrets** (Binance, Kraken, Coinbase, ...), plus API keys for external
  services (Etherscan, CoinGecko, ...). These are stored in the encrypted user DB and held in memory
  while the user is logged in. Many users grant more than read-only permissions on those keys.
- **The user's complete financial picture**: every tracked address across chains, exchange balances,
  full transaction history, PnL reports. Linking addresses to one person is itself the damage.
- **The user's password / DB key and premium credentials.**
- **Code execution on the user's machine**, which is typically the same machine that holds their
  wallets.

rotki does not hold wallet private keys or seed phrases. It tracks addresses. Do not report
"private key theft from the DB" style findings unless you actually find key material being stored.

## Components

| Path | What it is |
|------|-----------|
| `rotkehlchen/` | Python backend ("rotki-core"). REST API under `rotkehlchen/api/` (`/api/1/...`), websockets, accounting engine, DB layer, chain/exchange integrations. |
| `colibri/` | Rust HTTP service that handles performance-critical endpoints and reads the same databases. |
| `crates/starling*` | Rust supervisor that spawns core + colibri. In Docker mode it is PID 1, the **only externally bound listener**: it serves the frontend and reverse-proxies `/api/`, `/ws/` and `/colibri/` to the loopback backends. It starts as root and drops privileges (`privsep.rs`). |
| `frontend/app/src/` | Vue 3 SPA. |
| `frontend/app/electron/` | Electron main process, preload and IPC. |
| `rotkehlchen/mcp/` | MCP server exposing rotki data to AI assistants. |
| `rotkehlchen/premium/` | Client for rotki's premium server, including encrypted DB sync (upload/download). |

## Where untrusted input enters

Treat all of the following as attacker-controlled:

1. **On-chain data.** Anyone can send a tracked address a token or NFT with arbitrary name, symbol,
   metadata and image URL, or emit arbitrary logs. This flows through the decoders
   (`rotkehlchen/chain/**/decoding`, `modules/`), into both databases, and is rendered by the
   frontend. This is the cheapest attack to mount: it needs nothing but the victim's public address.
2. **Responses from remote services**: exchange APIs, RPC nodes (including user-added ones), indexers
   (Etherscan, Blockscout, Routescan), price oracles, Beaconchain, CoinGecko/CryptoCompare/DefiLlama,
   icon and NFT image hosts, GitHub-hosted data updates. Assume any of them is malicious or MITM'd.
3. **Requests to the local API.** The backend listens on loopback in the desktop app. Any web page
   open in the user's browser can try to reach it (CSRF, DNS rebinding, permissive CORS, websocket
   hijacking). So can other local processes and other local users. In Docker mode the proxy is
   reachable from the network.
4. **Files the user imports**: CSVs from exchanges and other tools (`rotkehlchen/data_import/`),
   user DB backups and exports, custom asset zip imports, icons.
5. **Remote updates applied to local state**: asset updates from the `rotki/assets` repository are
   SQL that is executed against the global DB; the `rotki/data` repository feeds spam lists, RPC
   nodes, airdrop metadata, accounting rules and location mappings.
6. **The premium server and synced DB blobs.**
7. **Content rendered in Electron**: anything that reaches the DOM, any URL handed to the OS
   (`shell.openExternal`), any IPC message from the renderer to the main process.

## What matters most

In rough priority order:

1. Remote code execution, by any route. Especially renderer XSS escalating to the Electron main
   process or to backend API calls, deserialization of remote or imported data, path traversal on
   write, command/argument injection in starling or the Electron process manager.
2. Exfiltration of exchange/API credentials, the DB password, or the decrypted database.
3. A malicious web page driving the local API without the user's involvement: reading portfolio
   data, adding or changing settings, RPC nodes or API keys, triggering imports, exports or purges.
4. SQL injection in either database, from on-chain data, remote API data, imports or API parameters
   (Python `rotkehlchen/db/`, `rotkehlchen/globaldb/` and Rust `colibri/src/database`, `globaldb`).
5. SSRF and local file read through attacker-chosen URLs (token/NFT image URLs, icon fetching,
   metadata URIs), and anything that makes the backend send credentials to the wrong host.
6. Weaknesses in the user DB encryption, key derivation, password handling, session handling
   (`rotkehlchen/api/session_*.py`) or in the premium sync encryption.
7. Privilege separation and exposure issues in the Docker deployment (starling proxy, access
   control on the proxied routes, the control channel, volume ownership handling).
8. Secrets leaking into logs, error messages, websocket messages, debug bundles or MCP responses.
9. Integrity bugs with a security consequence: remote data that can silently corrupt or wipe the
   user DB, or make rotki misreport balances in a way an attacker can steer.

## Out of scope / please do not report

- Anything that requires the attacker to already have the user's DB password, or to already run
  code as the same OS user.
- The user pointing rotki at an RPC node or service of their own choosing. That is the feature. A
  *remote party* choosing the destination is in scope.
- Wrong accounting, tax or PnL numbers, missing or wrongly decoded events, and price inaccuracies,
  unless they lead to one of the outcomes above. Those are ordinary bugs; we are happy to hear about
  them but they are not vulnerabilities.
- Rate limiting and missing security headers on a loopback-only listener, unless it enables a
  concrete attack.
- Known-vulnerable versions of dependencies with no reachable path in rotki. Renovate handles those.
- `rotkehlchen/tests/`, `rotkehlchen_mock/`, `tools/`, `docs/`, `packaging/`, benchmark and CI
  scripts, and the frontend's `tests/` and `scripts/dev/` directories. Development-only code.
- Vendored third-party code and generated files.

## How to exercise it

Everything is built in the image; the network is not needed.

```bash
cd /src

# backend, standalone (data dir anywhere writable)
python -m rotkehlchen --rest-api-port 4242 --data-dir /tmp/rotki-data
curl http://127.0.0.1:4242/api/1/ping
# create a user:  PUT /api/1/users  {"name": "x", "password": "y"}

# backend tests. Tests marked vcr replay recorded HTTP from /opt/test-caching and need both variables.
CI=true CASSETTES_DIR=/opt/test-caching pytest rotkehlchen/tests/unit/test_fval.py
CI=true CASSETTES_DIR=/opt/test-caching pytest -n 2 rotkehlchen/tests/api/test_settings.py

# rust services
./target/debug/colibri --help
./target/debug/starling --help
cargo test --offline -p colibri   # icons::tests::test_uniswap_v{3,4}_position_icon query a live RPC and fail offline

# frontend (run from frontend/, never from frontend/app/)
cd frontend && pnpm run test:unit src/modules/balances/AssetBalances.spec.ts
# built web bundle: frontend/app/dist
```

Unit tests do not open sockets (pytest-socket blocks it), so a reproducer that needs a "remote"
service should stand up a local HTTP server and point rotki at it, or patch the relevant client.
API documentation is in `docs/api.rst`.

## How we rate severity

- **Critical**: code execution on the user's machine, or theft of exchange API secrets / DB password
  / decrypted DB, triggered remotely with no user interaction beyond normal use (for example the
  victim merely tracking an address, having rotki open while browsing, or syncing balances).
- **High**: the same outcomes but requiring one plausible user action (opening a specific view,
  importing an attacker-supplied file, adding an attacker-supplied token); SQL injection reachable
  from remote data; a web page reading or modifying user data through the local API;
  authentication or access-control bypass on the Docker deployment; breaking DB or sync encryption.
- **Medium**: SSRF limited to blind requests; local file read of non-secret files; persistent
  denial of service from remote data (rotki will not start, or the DB is corrupted, until manual
  repair); disclosure of the address set or balances without credentials; secrets written to logs.
- **Low**: transient DoS (a crash or hang that a restart fixes), issues needing an unlikely
  configuration, hardening gaps without a demonstrated attack.

Please do not inflate: a crash in a decoder on malformed log data is Low unless it persists across
restarts. Memory-safety issues in the Rust code are at least High if reachable from untrusted input
in safe-looking code paths, and should say whether `unsafe` or a dependency is the root cause.

## Report and patch preferences

- One report per root cause. If the same missing check is reachable from several endpoints or
  decoders, list them all in one report rather than filing each.
- Say which component (core / colibri / starling / frontend / electron) and which deployment
  (desktop, Docker, both) is affected, and what the attacker needs to control.
- Reproducers: a pytest test under `rotkehlchen/tests/` or a short script against a locally started
  backend is ideal. For frontend issues, a vitest spec or the exact payload and the view that
  renders it.
- Patches should be minimal and follow the surrounding style (see `CLAUDE.md` / `AGENTS.md` in the
  repository root): narrow exception types, no `except Exception`, explicit TypeScript types. A
  regression test with the fix is very welcome.
