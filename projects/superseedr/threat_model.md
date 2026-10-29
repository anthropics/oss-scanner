# Threat model

## What this project does and where untrusted input enters
superseedr is a BitTorrent client written in Rust with a terminal UI. It runs on users' desktops and on headless
home servers (often in Docker behind a VPN), stays connected to the public Internet for long periods, and talks to
arbitrary, anonymous peers. Treat every byte received from the network as attacker-controlled:

- **Peer wire protocol over TCP and uTP** (`src/networking/protocol.rs`, `src/networking/utp.rs`,
  `src/networking/session.rs`, `src/peer_manager/`): handshakes, extension messages (BEP 10), metadata exchange
  (BEP 9, magnet links), PEX (BEP 11), bitfields, requests and piece data. Inbound connections arrive on the listen
  port; outbound peers come from trackers, DHT and PEX.
- **DHT** (`src/dht/`): KRPC messages over UDP from any host, compact node/peer encodings, BEP 42 node ID checks,
  routing table and peer store.
- **Trackers** (`src/tracker/`): HTTP(S) and UDP announce/scrape responses.
- **Web seeds** (`src/networking/web_seed_worker.rs`): HTTP responses from BEP 19 seed URLs.
- **WebTorrent** (`src/networking/webtorrent/`, `webtorrent` feature): WebSocket tracker signalling and WebRTC data
  channels.
- **Torrent metainfo** (`src/torrent_file/`): `.torrent` files and `info` dictionaries from magnet metadata, RSS
  feeds, the watch folder and the command line. This includes BitTorrent v2 / hybrid file trees and Merkle piece
  layers (`src/torrent_manager/merkle.rs`).
- **File names and paths** taken from metainfo: these decide where data is written on disk.
- **RSS feeds** (`src/integrations/rss_*.rs`): remote feed XML and the torrents they link to.

Local inputs (the config file, the control/watch-inbox files under the user's data directory, persisted state in
`src/persistence/`) are written by the same user who runs the client. Treat them as trusted, except where a remote
party can influence their content (for example a torrent name that is later persisted and re-parsed).

## Components that matter most / least
- Most important: anything a remote peer, tracker, DHT node, web seed or feed can reach without user interaction;
  metainfo parsing; piece/hash verification (v1 SHA-1 and v2 Merkle); and file path construction from torrent
  metadata (path traversal, absolute paths, symlinks, writing outside the download directory).
- In scope but lower priority: TUI rendering of attacker-chosen strings (terminal escape injection in torrent names,
  peer client names, tracker messages), and resource exhaustion that a remote party can trigger.
- Out of scope: `web/` (a browser-only demo that performs no real network or disk I/O), `wix/`, `packaging/`,
  `integration_tests/`, `agentic_*`, `docs/`, and the `synthetic-load` / `browser-contract` features, which are
  test-only. Third-party crates are out of scope unless superseedr uses them unsafely.

## How to exercise it
- `cargo test --all-targets --all-features` runs the unit, property (proptest) and integration tests.
- `fuzz/fuzz_targets/` holds libFuzzer harnesses for the uTP decoder, the TCP peer message parser, torrent and
  `info` dictionary parsing, KRPC decoding and the DHT lifecycle reducer. They are thin wrappers over functions in
  `src/fuzzing.rs`, which can be called from a unit test to replay an input.
- The binary is `target/debug/superseedr`; it needs a terminal. Network tests should use loopback peers.

## How you rate severity
- Critical: remote code execution, or writing/overwriting files outside the configured download directory, triggered
  by a peer, tracker, DHT node, web seed, feed or a crafted torrent/magnet.
- High: reading local files outside the torrent's own data and sending them to a peer; accepting data that fails
  hash verification as complete; any memory-safety bug in `unsafe` code reachable from the network.
- Medium: a remote party crashing the client (panic, abort, unbounded allocation, infinite loop) with a small number of
  packets; terminal escape injection that changes what the TUI shows.
- Low: denial of service that needs sustained high-volume traffic; issues that need a malicious local config file.

## Anything to leave alone
- Do not report that BitTorrent traffic is unencrypted, that peers learn the user's IP address, or that v1 uses SHA-1;
  these are protocol properties.
- Do not report bugs in the browser demo under `web/`.
