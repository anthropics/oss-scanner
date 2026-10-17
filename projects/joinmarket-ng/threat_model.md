# JoinMarket NG threat model

JoinMarket NG is an independent Python implementation of the JoinMarket CoinJoin protocol for Bitcoin, wire-compatible with the reference implementation (joinmarket-clientserver). Makers offer liquidity and earn fees; takers pick offers, build a CoinJoin transaction, and pay makers. Peers find each other through directory servers and then exchange sensitive data in end-to-end encrypted private messages, relayed by a directory or sent over direct onion connections. Protect, in order: users' funds and keys, the unlinkability of CoinJoin inputs to equal-value outputs (and of an operator's identity to their UTXOs), and availability of makers, takers, and directories.

## Existing project guidance

Read these in the checkout before starting: `AGENTS.md` (layout, commands, style), `docs/technical/threat-model.md` (adversaries, assets, per-threat mitigations), `docs/technical/security.md` (controls and resource limits), `docs/technical/maker-verification-checklist.md` (the invariants a maker enforces before signing), `docs/technical/protocol.md` (wire format, CoinJoin flow, which commands must be encrypted), and `docs/technical/privacy.md` (PoDLE, fidelity bonds, encryption). Where this file and those pages disagree, this file sets scan priorities and the docs describe intended behavior.

## Components and entry points

The repository is a monorepo; each component has its own `src/` and `tests/`:

- `jmcore`: shared library. Wire protocol and message parsing (`protocol.py`, `models.py`, `network.py`, `directory_client.py`), NaCl encryption (`encryption.py`), PoDLE (`podle.py`, `commitment_blacklist.py`), nick authentication (`nick_auth.py`, `crypto.py`), fidelity bond math (`bond_calc.py`, `btc_script.py`), transaction parsing and policy (`bitcoin.py`, `transaction_policy.py`), rate limiting and dedup, config and secure file handling (`settings.py`, `config_file.py`, `secure_files.py`).
- `maker`: the most safety-critical code. `tx_verification.py` decides whether to sign a taker's transaction; `coinjoin.py`, `maker_session.py`, `protocol_handlers.py` run the per-taker state machine; `direct_connection.py` accepts inbound onion connections; `fidelity.py` publishes bond proofs.
- `taker`: `taker.py`, `coinjoin_session.py`, `tx_builder.py` build and sign the CoinJoin; `orderbook.py`, `eligibility.py`, `multi_directory.py` parse and select offers from untrusted makers and verify bond proofs; `podle.py`, `podle_manager.py` generate commitments.
- `tumbler`: schedules many taker and maker runs; persists plans on disk.
- `jmwallet`: BIP32/39/84 wallet, signing (`wallet/signing.py`, `wallet/psbt_signer.py`, `wallet/psbt.py`), coin selection, spend construction, wallet file encryption, and backends (`backends/descriptor_wallet.py` for Bitcoin Core RPC, `backends/neutrino.py` with TLS pinning in `backends/_transport_security.py`).
- `jmwalletd`: FastAPI HTTP and WebSocket daemon compatible with the reference `jmwalletd` so the JAM web UI works unchanged. JWT auth in `auth.py`, routes in `routers/`. Default bind is 127.0.0.1:28183 with TLS.
- `directory_server`: public relay that every peer connects to. `handshake_handler.py`, `message_router.py`, `peer_registry.py`, `server.py`.
- `orderbook_watcher`: aggregates offers from directories and serves a public web UI (`server.py`, static files) that renders peer-supplied data.
- `install.sh` and `scripts/`: installer (downloads and verifies signed releases) and maintainer tooling.

Treat every other JoinMarket peer (maker, taker, directory) as adversarial: it controls nicks, offers, bond proofs, PoDLE commitments, every field of every message, the unsigned transaction a taker proposes, and the signatures and UTXOs a maker returns. A directory can drop, reorder, replay, or fabricate relayed messages and peerlists. Anyone who can reach the orderbook watcher's HTTP port, or a jmwalletd port without a token, is an attacker. The Bitcoin Core RPC backend and the operator's own config are trusted. A neutrino server is trusted only after its pinned TLS certificate and bearer token check out; mempool.space style fee and transaction APIs are untrusted for anything other than the data they serve.

## What to look for, in priority order

1. Loss of funds: a maker signing a transaction that underpays its CoinJoin or change output, drops one of its inputs, or pays more fee than offered; a taker paying fees above its configured caps or signing inputs or outputs it did not intend; any path that signs something other than what was verified (verify-then-sign mismatch, parser differentials between verification and signing, sighash or script-type confusion, duplicate outputs, address normalization).
2. Key or secret disclosure: mnemonic, xprv, private keys, wallet password, NaCl session keys, or JWT secrets leaking to a peer, the network, logs, an HTTP response, or a world-readable file.
3. Remote code or command execution, path traversal, or arbitrary file write from peer messages, HTTP requests, config values set over the API, wallet names, or tumbler schedules.
4. jmwalletd authentication or authorization bypass, token confusion between wallets, or CSRF/CORS issues that let a web page drive the API.
5. Deanonymization beyond the protocol's baseline: revealing which equal-value output belongs to whom, linking a maker's UTXOs across sessions without the PoDLE cost, linking onion address or nick to UTXOs, or bypassing the encryption requirement for `!auth`, `!ioauth`, `!tx`, `!sig`.
6. Accepting forged fidelity bond proofs, PoDLE proofs, or nick signatures; replaying messages across sessions or channels.
7. Remotely triggerable crashes, hangs, or unbounded memory or CPU in directory servers, makers, or the orderbook watcher with default settings.
8. Stored or reflected XSS in the orderbook watcher UI from peer-supplied fields.

## Out of scope or known and accepted

- Attacks that require control of the operator's Bitcoin Core node, OS, Tor binary, or hardware wallet firmware.
- Sybil attacks that the protocol inherently allows (many cheap identities, directories censoring), unless a bug lets an attacker avoid the fidelity bond or PoDLE cost.
- On-chain amount analysis (subset-sum, change heuristics) that follows from the protocol design rather than from an implementation bug.
- jmwalletd endpoints that are unauthenticated by design to mirror the reference daemon for JAM compatibility (`getinfo`, `session`, `wallet/all`, `wallet/create`, `wallet/recover`, `wallet/{name}/unlock`). Report them only if they reveal or allow more than the reference implementation does, or if the password check, lifecycle limits, or retry backoff can be bypassed.
- Plaintext protocol commands listed as plaintext in `docs/technical/protocol.md`.
- `scripts/`, `tests/`, `docs/`, `flatpak/`, and CI workflows, unless there is a concrete exploit against users or the release process.
- Third-party libraries (python-bitcointx, PyNaCl, cryptography, FastAPI) unless JoinMarket NG reaches the vulnerable code in a way an attacker controls; name the upstream owner.

## Build and bounded validation

The checkout is `/src`. Every component is installed in editable mode into the system Python 3.14 from the hash-locked `requirements*.txt` files, so edits under `/src` take effect immediately. Do not modify the requirements files. `JOINMARKET_DISABLE_PROCESS_HARDENING=1` is set so gdb and py-spy style tools can attach. The VM has two CPUs and 8 GB of memory; tests time out at 60 s each via `pytest.ini`.

Run the unit suites as CI does (the two invocations cannot be merged because each component ships its own `tests` package):

```sh
pytest -c pytest.ini --no-cov jmcore jmwallet directory_server orderbook_watcher maker taker jmwalletd tumbler
pytest -c pytest.ini --no-cov tests --ignore=tests/playwright --continue-on-collection-errors
pytest -c pytest.ini --no-cov maker/tests -k tx_verification   # a single area
```

Expected noise in this image, not findings: a few `tests/e2e` modules and `tests/test_reference_maker_helpers.py` fail to collect because they call `docker` at import time, and the read-only directory tests in `jmwallet/tests/test_utxo_metadata.py` fail because the shell runs as root.

Tests marked `docker` (everything under `tests/e2e`) need docker compose and are excluded by default; do not try to run them. For end-to-end reproductions, Bitcoin Core 31.1 is installed with a regtest config in `/root/.bitcoin/bitcoin.conf` (RPC 127.0.0.1:18443, user and password `test`). Start it with `bitcoind -daemon`, create and fund wallets with `bitcoin-cli`, then run the components on localhost without Tor, using the same environment the project's `docker-compose.yml` uses:

```sh
DIRECTORY_SERVER__HOST=127.0.0.1 DIRECTORY_SERVER__PORT=5222 NETWORK_CONFIG__NETWORK=testnet \
  DIRECTORY_SERVER__NICK_AUTH_DIRECTORY_ID=test:local-5222 jm-directory-server &
export NETWORK_CONFIG__NETWORK=testnet NETWORK_CONFIG__BITCOIN_NETWORK=regtest \
  NETWORK_CONFIG__ALLOW_CLEARNET_CONNECTIONS=true BITCOIN__BACKEND_TYPE=descriptor_wallet \
  BITCOIN__RPC_URL=http://127.0.0.1:18443 BITCOIN__RPC_USER=test BITCOIN__RPC_PASSWORD=test \
  DIRECTORY_SERVERS=127.0.0.1:5222 'NETWORK_CONFIG__NICK_AUTH_DIRECTORY_IDS={"127.0.0.1:5222":"test:local-5222"}'
# then jm-maker start / jm-taker coinjoin with separate JOINMARKET_DATA_DIR and MNEMONIC per role
```

Use throwaway mnemonics and temporary data directories. Never connect to mainnet, signet, or testnet directories or Tor, and never use real keys or funds.

## Evidence and severity

For each finding give the exact revision, the component and entry point, the attacker's position (any peer, a directory operator, a maker, a taker, a network client of jmwalletd or the watcher, a local unprivileged user), whether it works with default configuration, and the observed result. Prefer a pytest test or a short script that fails before the fix. For fund-loss findings, show the unsigned transaction and what the victim signed or would sign. Keep source-only hypotheses separate from reproduced behavior.

- Critical: theft or loss of funds, or disclosure of keys or wallet secrets, triggerable by a remote peer or an unauthenticated network client; remote code execution.
- High: jmwalletd authentication bypass; deanonymization of CoinJoin participants or linking operator identity to UTXOs through an implementation bug; forged fidelity bond or PoDLE acceptance; a remote crash or sustained DoS of directory servers or makers with default settings.
- Medium: bounded DoS or resource exhaustion; XSS in the orderbook watcher; privacy leaks into logs or local files; issues that need a malicious directory plus extra preconditions.
- Low: local-only issues against other unprivileged users, issues that need a non-default or explicitly discouraged configuration, and hardening.

A crash that only drops one session and is recovered is not a node crash. Keep patches minimal, follow `AGENTS.md` (typed Python, Conventional Commits), add a regression test, and keep wire compatibility with the reference JoinMarket implementation: a fix that changes the wire format must be flagged as such.
