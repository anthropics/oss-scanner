# Core Lightning Threat Model

Core Lightning (CLN) is a Lightning Network node implementation written primarily in C and Rust, using a multi-daemon architecture where a master `lightningd` process supervises isolated subdaemons (`connectd`, `openingd`, `channeld`, `closingd`, `gossipd`, `onchaind`, `hsmd`) and JSON-RPC / gRPC / REST / LSPS plugins.

## Assets

- **On-chain and Lightning channel funds**: Bitcoin UTXOs controlled by the node wallet (`wallet/`), channel commitment transactions, HTLCs, dual-funded / splicing transactions, and closing transactions.
- **Secret keys and HSM state**: `hsm_secret` and derived node identity keys, channel basepoints, and per-commitment secrets isolated inside `hsmd/` (`lightningd` and channel daemons must never be able to trick `hsmd` into signing unauthorized spends).
- **Channel and node database**: `db/` SQLite/PostgreSQL state (commitment numbers, revocation secrets, HTLC state, peer balances). Loss or corruption of state can cause loss of funds or penalty triggers.
- **Node and payment privacy**: payment preimages, onion routing hops, and private channel announcements.

## Trust boundaries and where untrusted input enters

1. **Lightning P2P peers (untrusted)**:
   - Noise_XK handshake and message framing in `connectd/` and `wire/`.
   - Channel establishment, dual-funding, splicing, and commitment updates in `openingd/`, `channeld/`, `closingd/`, `common/`.
   - Onion packets, blinded paths, trampoline/onion messages, and HTLC forwarding in `lightningd/`, `channeld/`, `gossipd/`.
   - Gossip network messages (`node_announcement`, `channel_announcement`, `channel_update`, gossip queries) in `gossipd/`.
2. **Untrusted payment requests and metadata**:
   - BOLT11 invoices and BOLT12 offers / invoice requests / invoices (`common/bolt11*`, `common/bolt12*`, `plugins/offers*`).
   - BIP353 DNS payment instructions (`plugins/bip353-plugin/`).
   - LSPS1 / LSPS2 / LSPS0 messages (`plugins/lsps-plugin/`, `lsps-types/`).
3. **Network-exposed plugin interfaces**:
   - `plugins/grpc-plugin/`, `plugins/rest-plugin/`, `plugins/wss-proxy-plugin/` (check authentication/rune enforcement, input validation, path/method/parameter handling).
4. **Subdaemon IPC and `hsmd` boundary**:
   - `hsmd/` enforces signing policy over requests sent by `lightningd`, `openingd`, `channeld`, `closingd`, and `onchaind`. A compromised subdaemon or bug in `hsmd` validation that allows signing an invalid spend or leaking secret material is high/critical severity.
5. **On-chain data**:
   - Transactions, blocks, and fee/mempool data from `bitcoin/` and `onchaind/`.

## Components that matter most / least

- **Matter most**: `hsmd/`, `channeld/`, `openingd/`, `closingd/`, `onchaind/`, `connectd/`, `gossipd/`, `wire/`, `common/`, `wallet/`, `db/`, `lightningd/`, `plugins/offers*`, `plugins/lsps-plugin/`, `plugins/rest-plugin/`, `plugins/grpc-plugin/`, `plugins/wss-proxy-plugin/`, `plugins/bip353-plugin/`, `cln-rpc/`, `cln-grpc/`.
- **Matter least**: `doc/`, `contrib/`, `devtools/`, `tests/`, `nix/`, formatting/linting scripts.

## How to exercise it

- Build and run C unit tests: `uv run make -j"$(nproc)" check-units`
- Run Rust unit tests offline: `cargo test --locked --workspace`
- Build and run libFuzzer / fuzz targets under `tests/fuzz/`
- Run individual offline Python integration tests (using the preinstalled `bitcoind`):
  `uv run pytest tests/test_<module>.py -k <test_name>`

## How we rate severity

- **Critical**: Remote theft or permanent loss of funds; remote code execution; `hsmd` signing-boundary bypass allowing unauthorized signatures or key extraction; unrecoverable channel/database corruption triggered by a remote peer.
- **High**: Remote crash or persistent denial of service of `lightningd` or critical subdaemons (`gossipd`, `hsmd`, `onchaind`) across peers; rune/authentication bypass on REST/gRPC/WSS interfaces; HTLC/invoice amount or preimage confusion causing unfair loss.
- **Medium**: Single-peer subdaemon crash (`channeld`/`openingd`) causing forced channel close or temporary unavailability; memory safety issues in C without direct RCE/funds impact; privacy leaks beyond standard Lightning protocol assumptions.
- **Low**: Minor local CLI/RPC bugs requiring an already-authenticated admin rune; non-security resource leaks.

## Anything to leave alone

- Known Lightning protocol-level tradeoffs documented in the BOLTs: channel jamming (HTLC slot/liquidity griefing), counterparties holding HTLCs until expiry, probing/balance discovery, transaction pinning and replacement cycling, counterparties force-closing their own channels, and timing/fingerprinting attacks.
- Issues that assume a malicious local `bitcoind` or an attacker who already holds an unrestricted admin rune or local filesystem access to `hsm_secret`.
