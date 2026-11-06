# Threat model: neutrino

## What this project does and where untrusted input enters

neutrino is a Bitcoin light client implementing BIP 157 and BIP 158. It syncs block headers and compact filter
headers (one hash per block committing to that block's filter), downloads a filter only when needed, and
downloads the full block when a filter matches a watched script or outpoint. lnd and btcwallet use it to detect
payments without a full node. All data comes from peers the client chooses, any of which may be hostile. There is
no authentication beyond the transport, so essentially the whole input surface is hostile.

Entry points:
- `blockManager.handleHeadersMsgWithPeers` (`blockmanager.go`) consumes `wire.MsgHeaders`: up to 2000
  attacker-authored 80-byte headers. `blockManager.handleInvMsg` consumes `wire.MsgInv`, which drives sync-peer
  selection.
- Filter header sync consumes unauthenticated `wire.MsgCFHeaders` and `wire.MsgCFCheckpt` via
  `getCFHeadersForAllPeers`, `checkForCFHeaderMismatch`, `detectBadPeers`, `resolveCFHeaderMismatches` and
  `writeCFHeadersMsgs`.
- `wire.MsgCFilter` and `wire.MsgBlock` responses are fetched in `query.go` and matched in `filtermatch/`.
- Rollback paths in `headerfs/store.go` and `headerfs/sql_store.go` take heights derived from a peer's claimed
  chain. `banman/`, `headersync/` and `querysync/` turn peer behaviour into ban and scheduling decisions.
- `chainimport/` reads a header file from disk or HTTP. This is operator-initiated, but it is a second parser for
  the same data.

Filter matching is inherently incomplete (false positives, and a filter cannot prove what a block lacks). Security
rests on proof of work over the header chain plus the filter hash commitment chain.

## Components that matter most

In order of damage if wrong:
1. Header acceptance and storage: `checkHeaderSanity` in `blockmanager.go`, `headersync/validation.go`
   (`ValidateHeaderRange`, `ValidateAnchorResponse`), and `WriteHeaders` in `headerfs/`.
2. The filter header chain built by `writeCFHeadersMsgs`.
3. Peer arbitration in `blockmanager.go` (`checkForCFHeaderMismatch`, `detectBadPeers`,
   `resolveFilterMismatchFromBlock`, `banAndDisconnect`, `fetchFilterFromAllPeers`) and `filtermatch/verify.go`.
   Banning an honest peer is a cheap liveness attack; never banning a lying peer is a correctness failure.
4. The durable stores: `headerfs/store.go`, `file.go`, `index.go`, `sql_store.go`. The legacy backend uses a flat
   file plus a bbolt index that must reconcile after a crash; the SQL backend uses SQLite or PostgreSQL.
5. The sync schedulers `headersync/` and `querysync/`. A fault here wedges sync even though every message
   received was valid.
6. The query path (`query.go`, `utxoscanner.go`, `rescan.go`, `rescan/`), `banman/`, and the validators in
   `chainimport/`.

## Out of scope or low priority

- `p-models/`: a formal model in the P language with its own toolchain, not shipped Go code.
- `docs/` (orientation only) and `tools/` (a separate module for `btcd` and lint tooling).
- `sqldb/legacy_bdb.go` and `sqldb/migrate_legacy*.go`: a one-way legacy bbolt import run once at operator
  request on a local file.
- Mocks (`headerfs/store_mock.go`, `chainimport/*_mock.go`, mocks in `banman/`).
- `sqlc` output under `sqldb/`, including `sqldb/queries.go`. A logic bug in a hand-written query wrapper is in
  scope; a style complaint about generated code is not.
- `chainimport/file_source.go` and `http_source.go` where the operator chose the file: a malformed local file is
  operator error. The validators in front of the import stay in scope.
- Behaviour that needs an already-inconsistent caller struct or a `Config` the docs contradict, and test files
  and fixtures including `testdata/`.

## How to exercise it

A plain Go module with no cgo, scanned offline. Run `go test ./...` directly (`make unit` first runs `make btcd`,
which needs the network). `cache/` is a nested module that `./...` skips, and `sqldb` has a `test_db_postgres`
build tag needing a live PostgreSQL server.

The deterministic-sync (DST) harness is the most useful tool; use it before writing anything from scratch
(`docs/deterministic-sync-testing.md`, `blockmanager_transport_dst_test.go`, `dst_fixture_test.go`,
`dst_invariants_test.go`). It runs the real `blockManager`
handling, `headersync` and `querysync` actors and header validation against scripted peers with virtual time.

```
go test . -run '^TestHeaderTransportDST$' -count=1
```

There is no network, `bitcoind` or second node, so `rpctest.New` (used in `blockmanager_test.go` and
`sync_test.go`) will not run. Express a malicious peer, in order of preference, as: (1) a scripted peer in the DST
harness; (2) a direct call to `handleHeadersMsgWithPeers` with a `*headersMsg` and `*ServerPeer`, as
`blockmanager_validation_test.go` does; (3) a unit test on a pure function such as `chainsync.ValidateCFHeader`,
`filtermatch.VerifyBasicBlockFilter`, `headersync.ValidateHeaderRange` or `ValidateAnchorResponse`. State which
you used. A reproducer needing a live chain or second node is still in scope but is weaker evidence and is rated
accordingly. A live environment is genuinely required for mainnet retargeting at a historical height, for two
unscripted peers interacting, and for PostgreSQL.

## How we rate severity

Critical:
- Any path by which a peer, or colluding peers, can make the client accept a block header, filter header or chain
  tip that an honest node following the same consensus rules would reject.
- Any path that lets a peer make the client persist a filter header committing to a filter set inconsistent with
  the header chain, so the client permanently skips blocks containing payments to a watched script.
- Any path to loss of funds in a wallet built on the client: a spend reported as confirmed that is not, a watched
  output missed so it is never spent, or a rescan result attributing a transaction to the wrong height or hash.
- Remote unauthenticated memory corruption, or an unauthenticated panic the caller cannot recover from. A panic
  reached by one message from a fresh peer is critical; one needing thousands of messages of history is high.

High:
- Validation divergence: the client applies a different rule than the network, so a header the network accepts is
  refused (or the reverse) at a reachable height. Lower than critical only because the usual effect is a stalled
  client rather than a wrong one.
- Unbounded memory or CPU growth from peer messages, where one peer can exhaust the process. High rather than
  critical when the client stays correct.
- A liveness break one peer can cause: sync that cannot advance past a height although honest data is available,
  or a client that keeps choosing the same non-serving peer forever.
- A peer that provably served invalid data is not banned, or one that merely failed to answer is banned. State
  which peers and messages.

Medium:
- Crashes and panics that need more than one message, or that a caller in the tree already recovers.
- A remote DoS that needs an established, repeatedly used connection, needs the peer to be the selected sync
  peer, or needs the attacker to have been the client's tip at some point. State the prerequisite.
- Storage growth or a store state that only a deliberate local write can produce.
- Privacy breaks. Peers learning which blocks or scripts the client cares about, or that it runs neutrino, is
  largely inherent to the design, which trades some query privacy for bandwidth. Rate a new, unavoidable leak
  medium, and say explicitly that it is a privacy finding.
- A peer making the chosen sync peer flap between honest candidates without stalling sync.

Low:
- Missing validation with no demonstrated impact. Say what you tried in order to reach impact.
- A misleading error message or log line that leaks nothing and breaks nothing.
- A defect only reachable from an operator-supplied file or caller-controlled configuration, or an efficiency
  issue with no attacker involved.

Out of scope for a rating, though worth a sentence as context:
- The inherent incompleteness of filter matching, and anything in a test fixture or a mock.
- Anything that needs a peer with valid proof of work at a height the client has already checkpointed past.
- Flat-file versus SQL differences that come only from durability ordering, with no observable difference in what
  the client reports.

## Report and patch preferences

The ideal report is a failing Go test. Name the file, function and line. Name the attacking peer's position
(fresh connection, selected sync peer, one of several peers, or only peer), since this changes severity more than
anything else. State the broken property as observable behaviour, such as a tip written that does not match the
headers received, a peer banned that served consistent data, or sync stopped at height N with an honest peer
available. For DST findings, include the seed or saved fuzz input (stored under
`testdata/fuzz/FuzzHeaderTransportDST`) so it replays with one command. If a finding needs a live environment,
include the test patch and reasoning and mark it as not reproducible in the image.

A patch is welcome. Keep it to the component at fault and prefer removing the state that allows the bad case over
adding a check for it. Do not change exported signatures, add configuration options, or weaken ban logic or peer
arbitration to make a reproducer pass. If a fix would change the on-disk format, say so in the report instead of
shipping it. Group findings that share a root cause into one report, and separate distinct attacker positions
into separate reports even when the code is the same.

## Anything to leave alone

These shapes look wrong and are not.

- The filter header checkpoints in `chainsync/filtercontrol.go` are a designed trust anchor; `ValidateCFHeader`
  returning nil outside the table's range is intended. `filtermatch.VerifyBasicBlockFilter` counts OP_RETURN
  matches without failing on them, because older filters included OP_RETURNs.
- `resolveFilterMismatchFromBlock` falls back to majority voting among peers; a finding must show an attacker can
  cheaply control the majority. `banAndDisconnect` treats "invalid" and "unresponsive" differently on purpose
  (see `detectBadPeers`); a missing response is not proof of a lie.
- `headerfs/file.go`'s `appendRaw` and `readRaw` use explicit seeks because the flat file is a fixed-record
  format. `CheckConnectivity` erroring on an inconsistent store is its purpose. The double hash in filter header
  computation is the BIP 157 definition.
- The actors and FSMs in `headersync/` and `querysync/` and `protofsm/` have no goroutines or outbox dispatch of
  their own; the surrounding code drives them (`docs/sync-architecture.md`).
- Lease epochs and range stealing in `headersync` recover from a stalled peer; a report must show a steal causing
  a duplicate commit or a lost range.
- The oracles in `rescan/dst_*_test.go` are test-only assertions.
- The `sqlc` schema and queries under `sqldb/`: a missing index is not a vulnerability, and a correct but slow
  query is low at most. Code behind `//go:build test_db_postgres` that only works on SQLite is not a bug.
- Mixed-backend `Config.SQLConfig` values or two stores on one file are caller misuse. The `cache` submodule's
  LRU eviction is not a security boundary.
