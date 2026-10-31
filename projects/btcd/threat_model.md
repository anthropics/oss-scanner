# Threat model: btcd

btcd is a full bitcoin node written in Go. It validates the chain, relays
transactions, serves compact block filters and a JSON-RPC API, and exposes Go
packages (script evaluation, validation, wire encoding, PSBT) that other
projects import. It is widely used as the chain backend for Lightning nodes,
whose on-chain safety depends on it reporting blocks, spends and reorgs
correctly, so a divergence from Bitcoin Core is inherited by every downstream
user. This document states our threat model, not the current state of the code.

## Where untrusted input enters

- **P2P wire.** Any host may connect. `wire/message.go` dispatches on the
  command to a message's `Decode`; `wire/msgtx.go`, `wire/msgblock.go` and
  `wire/common.go` hold the main decoders, `peer/peer.go` drives the peer loop,
  and `server.go` holds per-message policy. Peers are untrusted in every
  respect: they may claim any height, send headers that do not connect, announce
  inventory they lack, flood addresses, send invalid transactions, or serve
  filters that disagree with their blocks. The v2 transport (`v2transport/`)
  authenticates a key but gives the peer no standing.
- **JSON-RPC and websocket.** `rpcserver.go` has its own authorization
  (`checkAuth`) and an admin versus limited-user split. `rpcwebsocket.go` carries
  wallet notifications, some reachable without authentication. Treat handlers as
  reachable by a semi-trusted caller and ask whether a limited user or websocket
  client can reach an admin-only effect.
- **Library and files.** Other programs call `txscript/`, `blockchain/`,
  `mempool/` and `psbt/` directly (main entry points: `txscript.NewEngine` and
  `Engine.Execute` in `txscript/engine.go`). The caller is trusted but its data
  may come from a peer or file. Data written by an earlier run or version
  (`database/ffldb/db.go`, `blockchain/chainio.go`) flows back through
  validation at startup, so a partially written file is an input.

## Components that matter most

Ordered by damage if the component is wrong.

1. **Consensus validation** (`blockchain/validate.go`, `process.go`, `accept.go`,
   `chain.go`, `versionbits.go`, `thresholdstate.go`, `merkle.go`,
   `difficulty.go`). A permissive error follows a chain the network rejects; a
   restrictive error forks the node from it. A deployment lock-in one period
   early or late is also a consensus event.
2. **Script engine** (`txscript/engine.go`, `opcode.go`, `standard.go`,
   `consensus.go`, sighash code). The verdict must match Core for every flag set,
   and size limits and clean-stack must be exact, including for witness programs
   that are anyone-can-spend under the active flags.
3. **Wire decoders** (`wire/`). Every field is attacker-controlled and work must
   be bounded: a declared count must not cause allocation before the elements
   exist, and a truncated payload must fail without reserving anything.
   `wire/arena.go` documents that a successful decode leaves no arena-backed
   scripts in the transaction, which makes arena reuse safe.
4. **Mempool and relay policy** (`mempool/mempool.go`, `policy.go`,
   `estimatefee.go`, `mining/policy.go`, `server.go`). Orphan limits,
   replacement rules, dust and standardness checks, and ban scores matter. A
   policy stricter than the network's, or one that refuses a valid transaction
   for the life of the process with no operator remedy, can leave a Lightning
   node unable to confirm an HTLC timeout or justice transaction.
5. **Peer and sync logic** (`peer/peer.go`, `netsync/`, `connmgr/`, `addrmgr/`).
   The sync peer must lose the role when it stops advancing the tip, and
   fast-add must be used only for blocks with verified ancestry. Address
   poisoning and slot exhaustion affect the network view, not funds.
6. **RPC surface** (`rpcserver.go`, `rpcwebsocket.go`, `rpcadapters.go`,
   `btcjson/`). Admin-only commands must stay admin-only for a limited
   credential and an unauthenticated websocket client, and a notification
   stream must not deliver another client's data.
7. **Database and chain index** (`database/ffldb/db.go`, `blockchain/chainio.go`,
   `blockindex.go`). A partial write must never be observed as valid.
8. **PSBT** (`psbt/`). A signer must sign only what it meant to, and the sighash
   must be recomputed, not taken from the untrusted document.
9. **Curve and transport primitives** (`btcec/`, `btcec/ellswift/`,
   `v2transport/`). Secret-dependent operations must be constant time and
   invalid points rejected.

## Out of scope or low priority

- `integration/` (including `integration/rpctest/`), `blockchain/fullblocktests/`
  and `blockchain/internal/testhelper/`: test harness and corpus generators.
- `cmd/btcctl/`, `cmd/gencerts/`, `cmd/findcheckpoint/` and `cmd/addblock/`
  (operator tools), `docs/`, `CHANGES`, `ossec/`, `limits/`,
  `service_windows.go`, `internal/inbound/admission.go` and
  `internal/socks/socks.go` (documentation, platform glue, small locally
  configured components).
- `btcutil/`, `chaincfg/`, `chainhash/` and `address/` are in scope only where
  they parse (base58, bech32, extended keys). A surprising convenience helper
  is not a finding.
- Inputs that require handing a decoder a `wire.MsgTx` assembled by hand with
  fields no decoder could produce, since misuse by trusted code is not a remote
  input, and the `rpctest` build tag, which enables the harness only.

## How to exercise it

btcd is a root module plus nine nested modules, each with its own `go.mod`
(`address`, `btcec`, `btcutil`, `chaincfg`, `chainhash`, `psbt`, `txscript`,
`v2transport`, `wire`), mostly with version suffixes in import paths such as
`github.com/btcsuite/btcd/wire/v2`. The root `./...` excludes them, so run tests
inside each directory. The scan is offline. Fuzz targets are in
`wire/fuzz_test.go` and `btcec/fuzz_test.go`, and `wire/decode_budget_test.go`
shows how allocation bounds are asserted. Multi-node sync, mining and reorgs
(`integration/rpctest`) cannot be shown offline. A reproducer you cannot run is
still in scope: say it is analytical and name the function, the input, and why
the input is reachable.

## How we rate severity

The question is who can send the input and what the node does with the
resulting state. Consensus divergence, and anything that lets a remote party
cause it, is rated more harshly than the same bug class in an application server.

| Flaw class | Rating | Reasoning |
| --- | --- | --- |
| Validation or script-evaluation divergence from Bitcoin Core: this node accepts a block or transaction Core rejects, or rejects one Core accepts | **Critical** for acceptance divergence, **High** for rejection divergence | Acceptance divergence splits the chain and can defraud anyone who treats this node's view as authoritative. Rejection divergence is a liveness failure, close to fund loss for a Lightning node under a deadline, but does not by itself fork. |
| Remote, unauthenticated memory corruption in a wire decoder, the transport, or script evaluation | **Critical** | Pre-authentication bytes are free to send and the process holds keys and chain state. |
| A remotely triggerable panic, out-of-range index, length-computation overflow, or nil dereference reachable from a single P2P message | **Medium** by default, **High** if it crashes the process for every peer at once or recurs on restart | A restart normally recovers and chain state is durable. Escalate when the crash is persistent, such as a block that panics on every attempt to process it. |
| Unbounded allocation or CPU driven by a count or length field in one message | **High** if a small message causes work several orders of magnitude larger, **Medium** otherwise | Amplification makes this cheap. A decoder that reserves the declared count up front and then fails is the textbook case. |
| Mempool policy that permanently refuses a transaction the rest of the network would relay, with no operator remedy | **High** | A Lightning node can lose an HTLC or justice transaction through its own backend. |
| Memory or CPU exhaustion that needs many connections, many peers, or a long time | **Medium** | Attacker cost matters. A slow leak needing thousands of connections is not one packet. |
| An RPC handler reachable by a limited credential or unauthenticated websocket client that performs an admin action or discloses another client's notifications | **High** | The admin/limited split is a boundary operators are told to rely on. |
| An RPC handler that requires an admin credential but mishandles its input | **Medium** | The caller already controls the node, but the input may be proxied from elsewhere. |
| Address manager poisoning, peer slot exhaustion, or eclipse-adjacent issues that need many connections or substantial network presence | **Medium** | Rate on the number of slots or connections needed. |
| A `txscript` behavior difference that needs a flag combination no deployment uses today | **Medium** | We want parity for every flag set because a future soft fork can activate a dormant combination. This is a hardening argument and is graded on its reasoning. |
| Missing validation with no demonstrated consequence, a merely absent range check, or a comment that disagrees with the code | **Low** | Report it, but expect no more than low. |
| Anything requiring a known-bad operator configuration (such as `--notls` with a public listener) or a lost RPC credential | Out of scope for a rating | These are operator decisions, not modeled attacker capabilities. |

Bugs only in the integration harness or an unsupported node configuration are
reportable but not rated.

## Report and patch preferences

A useful report names the exact entry point (the wire command and `Decode`
method, the RPC method and handler, or the exported function and the argument
carrying hostile data; for consensus, the rule and the function implementing
it), gives the concrete input (minimized bytes, or hex for a transaction or
block), and includes a Go test reproducer in the package at fault in the
existing table-driven pattern. For a consensus claim, the strongest form is a
test case showing this node and Core disagreeing, with the Core behavior
stated. State expected versus observed behavior and the operator impact (crash,
following a bad chain, refusing a valid transaction, or leaking another
client's data).

Patches are welcome. Fix at the layer where the invariant lives (decoder fixes
in the decoder, consensus fixes in the rule, policy fixes in
`mempool/policy.go`). Say so if a patch changes an exported API, an error value's
identity, or a wire encoding, since importers can observe all three. If a fix
could reject blocks or transactions that are currently accepted, describe the
activation problem, because that is a consensus change and not a patch. If it
tightens a limit that no valid data approaches, state the tightest valid case.

## Reports we close without action

- `subtle.ConstantTimeCompare` applied to a non-secret, or ordinary comparison of
  public values such as block hashes. `checkAuth` in `rpcserver.go` compares
  hashed credentials in constant time deliberately.
- `btcec` or `ellswift` not being constant time on an operation that uses
  public data, such as verification. Identify the operation and the secret it
  touches first.
- `math/rand` in test data, and `//nolint` or `go vet` suppressions (if one
  hides a real bug, report the bug), and `btcjson` marshalling quirks that
  still parse correctly.
- Deliberate rejection of non-standard transactions. `CheckTransactionStandard`
  in `mempool/policy.go` is intentionally stricter than consensus. Report a gap
  only with a transaction the network accepts and this node refuses, and say
  where the network's rule comes from.
- Pruned-node behavior that differs from an archival node, and messages for
  state we lack (blocks we already have, filters for heights not yet reached),
  unless accepted where they should not be.
- Lack of authentication on P2P messages other than the transport handshake. The
  protocol is unauthenticated by design; "any peer can send X" matters only when
  X should have been refused.
- A panic recovered by the peer handler and turned into a disconnect, unless
  recovery leaves state inconsistent or the panic recurs across restarts.
