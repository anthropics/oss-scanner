# Threat model

## What this project does and where untrusted input enters
- anacrolix/torrent is a BitTorrent client library (plus `cmd/` tools) embedded in other applications, often long-running and exposed to the public Internet.
- All network peers are untrusted: the peer wire protocol (`peer_protocol/`, `peerconn.go`, handshake, message encryption in `mse/`), extension protocols (ut_metadata, PEX, ut_holepunch, LTEP), uTP and WebRTC/WebTorrent transports.
- Trackers (HTTP, UDP, WebSocket in `tracker/`, `webtorrent/`) and the DHT are untrusted, as are webseed servers (`webseed/`).
- Metainfo (.torrent files), magnet links, and bencoded data (`bencode/`, `metainfo/`) may come from untrusted sources, including metadata fetched from peers.

## Components that matter most / least
- Most: bencode decoding, metainfo/info parsing, peer message parsing and request handling, metadata exchange, v2 piece layers/merkle verification, piece hashing/verification, and file storage path handling (path traversal from torrent file names into the storage directory).
- Less: `cmd/` utilities, `fs/` (FUSE), test helpers, and example code; still in scope where they handle untrusted input.

## How to exercise it
- `go test ./...` from /src; package tests and fuzz tests (e.g. in `bencode/`, `metainfo/`, `peer_protocol/`) are good drivers. `cmd/torrent` is a full client.

## How you rate severity
- Remote code execution, or writing files outside the configured storage directory from attacker-controlled torrent/metadata: critical.
- Memory corruption via unsafe/cgo, or accepting data that fails hash verification as valid: high.
- A remote peer, tracker or webseed crashing the process (panic) or causing unbounded memory/CPU/goroutine growth: medium to high depending on how cheap it is to trigger.
- Minor resource inefficiencies or issues requiring a malicious local user: low.

## Anything to leave alone
- Data races found only by the race detector with no security consequence: report as low at most.
- Exposure of IP addresses to peers/trackers is inherent to BitTorrent and not a vulnerability.
