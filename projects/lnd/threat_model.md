# Threat model: lnd

lnd operates a Lightning Network node: it holds bitcoin and channel value, speaks the peer-to-peer Lightning protocol, forwards HTLCs for
other nodes, tracks the public channel graph, and manages the on-chain contracts that resolve channel value after a force close or breach.
Almost every bug that matters is a bug in how a daemon holding money reacts to bytes someone else wrote. This document states our threat
model, not the current state of the code or a list of known problems.

## Where untrusted input enters

**The Lightning peer wire.** Any host on the internet can connect to the listen address (default port 9735) and attempt a BOLT 8 handshake
(Noise XK over secp256k1), implemented in `brontide/noise.go` and `brontide/listener.go`. A successful handshake authenticates the remote
static key and yields encrypted frames, each with a two-byte message type and a body. `peer/brontide.go` reads frames and passes bodies to
`lnwire.ReadMessage` in `lnwire/message.go`, which calls the concrete message's `Decode`. Every `Decode` in `lnwire/` is attacker-reachable.
An established peer is not a trusted peer: it may be hostile, lie about the graph, send messages out of order, address one channel by
different identifiers, and disappear at the worst moment. A peer sharing no channel with us can still send channel-scoped messages.

**The RPC surface.** gRPC, REST and a websocket proxy carry the operator API. Definitions are in `lnrpc/lightning.proto` and the sub-server
directories under `lnrpc/`. Handlers are in `rpcserver.go` and the per-sub-server `*_server.go` files, for example
`lnrpc/routerrpc/router_server.go`. Authorization runs through `rpcperms/interceptor.go` and `macaroons/service.go`.
`lnrpc/websocket_proxy.go` turns a browser websocket into a REST request, so its header handling is untrusted input from any origin the CORS
policy allows. A macaroon is a bearer credential: assume a semi-trusted caller holds one with a subset of permissions, possibly heavily
caveated, and treat any operation exceeding the grant as a boundary crossing. Before unlock, a small set of methods in
`walletunlocker/service.go` is intentionally reachable without the usual authorization.

**The chain backend.** lnd trusts a backend (btcd, bitcoind or neutrino) for chain state, wrapped in the `chainntnfs/` adapters implementing
`chainntnfs/interface.go`. Blocks, transactions, filter matches and reorg notifications originate on the bitcoin network and are
adversary-influenced even though the backend is locally configured. With a light client backend, a compact block filter match is a hint, not
a proof.

**Locally configured but remotely fed inputs.** Tor and SOCKS proxying (`tor/net.go`), DNS bootstrap of the graph
(`discovery/bootstrapper.go`) and watchtower connections (`watchtower/wtserver/server.go`) are operated by the node owner but carry remote
data. A watchtower is a separate trust domain. Invoices (`zpay32/`, `bolt12/`), PSBTs (`lnwallet/chanfunding/psbt_assembler.go`), channel
backups (`chanbackup/`) and SCID aliases arrive as bytes an RPC caller supplies, so even a limited macaroon can carry crafted input.

## Components that matter most

Ordered by damage if the component is wrong.

1. **Commitment and channel state** (`lnwallet/channel.go`, `chanstate/open_channel.go`). Failure modes: a counterparty signature accepted
   over an unintended state, revocation material released so an old state goes unpunished, fee and dust accounting that does not sum to
   capacity, signatures checked against a reconstruction that differs from what is broadcast, and state heights moving backwards or
   skipping.
2. **HTLC forwarding** (`htlcswitch/switch.go`, `htlcswitch/hop/payload.go`). Value must be conserved across the incoming and outgoing pair
   with the fee as the only difference, each circuit must resolve exactly once, and a peer-supplied channel reference (short channel ID,
   alias, channel ID) must be bound to a channel that peer shares before any balance moves. A message naming an alias must not resolve to
   the real SCID, or the reverse.
3. **On-chain contract resolution** (`contractcourt/chain_arbitrator.go`, `contractcourt/channel_arbitrator.go`,
   `contractcourt/breach_arbitrator.go`, `sweep/sweeper.go`). Every locally claimable output needs exactly one owner that sweeps it,
   recognizes it as spent, or retries until a defined terminal condition, across reorgs, conflicting spends, fee bumps and restarts. Failure
   modes: a claim abandoned because an error was treated as terminal, a claim swept twice, and a resolver reporting success without
   evidence.
4. **Peer session and message dispatch** (`peer/brontide.go`, `lnwire/message.go`). Messages must be bound to the authenticated remote key,
   and channel-scoped messages must only affect channels shared with that key. Decoding must be bounded and fail closed: a message that
   cannot be fully and unambiguously decoded must not produce partially trusted state.
5. **Wallet, key derivation and signing** (`lnwallet/btcwallet/`, `keychain/derivation.go`, `input/musig2.go`, `lnwallet/chanfunding/`).
   Every derivation and signature must bind the intended network, key family, script, input, sighash and purpose. MuSig2 secret nonce reuse
   across distinct transcripts is a key-recovery event, so session identity, completion and cleanup are security-relevant.
6. **RPC authorization** (`rpcserver.go`, `rpcperms/interceptor.go`, `macaroons/service.go`, `walletunlocker/service.go`). Every protected
   method must require its declared permission on every transport, every caveat must be checked against the actual request, and the
   pre-unlock state must expose only the intended lifecycle methods.
7. **Gossip and the public graph** (`discovery/gossiper.go`, `graph/builder.go`, `routing/router.go`). Announcements are signed by their
   origin but arrive through a peer who may lie about what it received. Validation must check origin signatures and update ordering, and
   must not promote private hints into public graph state. Routing must keep dispatches within the payer's amount, fee and timelock budget.
8. **Payments, invoices and onion messages** (`payments/db/kv_store.go`, `invoices/invoiceregistry.go`, `onionmessage/hop.go`). One payment
   must have one durable terminal result. Hold invoices separate acceptance from preimage release, and that separation is a value boundary.
   Onion messages grant no HTLC or wallet authority.
9. **Persistence, migrations and clustering** (`sqldb/migrations.go`, `cluster/`, `chanbackup/`). See `docs/db_migration_guide.md`. A
   migration that records a new version before its transformation is durable, or two instances writing the same node identity in cluster
   mode, are problems of this kind.
10. **Chain notification** (`chainntnfs/txnotifier.go`, `chainio/blockbeat.go`). Confirmations, spends and reorgs must reach every consumer
    that acts on them, and a historical rescan must reach a terminal answer.

## How we rate severity

Grade the demonstrated impact and the prerequisites, not the category of bug. The classes below are defaults. A report that argues its way
off the default with evidence gets the argued rating.

| Flaw class | Rating | Reasoning |
| --- | --- | --- |
| A remote party obtains channel or wallet value, or prevents us claiming value inside its CLTV or CSV window | **Critical** | The outcome cannot be repaired afterwards. Examples: theft, an unpunishable revoked state, an abandoned claim, a sweep paying the counterparty's script, a signature released over the wrong transaction. |
| Unauthenticated remote memory corruption, or a panic in the message path reachable before the handshake completes | **Critical** | Pre-handshake code sees bytes from anyone on the internet at no cost, and memory unsafety in a process holding keys has no recovery. |
| Remotely triggerable divergence in commitment, HTLC or contract logic such that two honest participants disagree about channel value | **Critical** | Divergence in a money protocol is the worst class of bug. |
| Loss of funds requiring the attacker to be the counterparty on the affected channel and put value at risk | **High** | Still theft, but the attacker is identified, bound to a funded channel, and the loss is bounded by its capacity. |
| Missing or incorrect authorization on an RPC method, or an unenforced caveat | **High** if the method can move funds, sign, or disclose wallet material; **Medium** if it only discloses state a restricted macaroon was meant to hide | What matters is what the method does. Name the method, what it moves or discloses, and what a caller must hold to reach it. |
| Remote denial of service needing an established, authenticated peer and a funded channel to sustain | **Medium** | The attacker is identified and pays. Damage is availability, and operators can close and ban. |
| Remote denial of service needing no channel and no authentication, or repeatable at negligible cost | **High** | Free, repeatable resource consumption against a routing node is a real operational problem. Critical if it stops the node resolving existing HTLCs within their deadlines, because that converts availability into fund loss. |
| A crash, panic, nil dereference or goroutine leak, reachability unproven | **Medium** | The daemon restarts and resumes from durable state. High or critical only with an argument that it recurs on every restart or lands where value is at stake. |
| Unbounded allocation, queue growth or goroutine creation driven by one peer's input | **Medium**; **High** if one small input amplifies by three or more orders of magnitude, or the growth is never reclaimed | Bounded-work decoding is a hard requirement. The rating depends on how cheap the trigger is and whether the resource comes back. |
| Missing validation with no demonstrated consequence, or a hardening suggestion with no stated prevention | **Low** at best, often informational | A missing check can precede a future bug, but "this field is not range-checked" is not a vulnerability. Say what the check would prevent. |
| Anything requiring the operator to have already lost control of the host, config file or seed | Out of scope for a rating | Not an attacker capability we model. |

Also out of scope for a rating, though in scope for reporting: a bug that only affects a build configuration we do not ship
(`-tags=integration`, `lowscrypt`), and one whose only impact is on an unsupported node configuration, such as macaroons disabled. Report
both, expect low, and expect us to ask whether the finding also applies to a default build. In general, anything gated on an authenticated
session that has put value at risk ranks below anything gated on a TCP connection.

## Out of scope or low priority

- `itest/`, `lntest/` and `lnwallet/test/` are the integration harness.
- `mobile/` is a thin gomobile wrapper and is not built here.
- `lnrpc/*.pb.go`, `lnrpc/*_grpc.pb.go`, `lnrpc/*.pb.gw.go` and their equivalents under `lnrpc/*rpc/` are protoc output. Review the `.proto`
  files and the hand-written `*_server.go` beside them.
- `tools/`, `scripts/`, `docs/`, `contrib/`, `docker/` and `make/` are build and documentation infrastructure.
- `lntest/mock/`, `lnmock/`, `htlcswitch/mock.go` and `*_test_utils.go` files are test fixtures.
- `autopilot/`, `chanfitness/`, `monitoring/`, `healthcheck/` and `peernotifier/` are heuristics and telemetry. A path from a heuristic
  score to an actual spend is in scope. A heuristic that scores badly is not.
- Code reachable only when the caller passes an already-malformed struct, or a reproducer needing a cooperating node, a live bitcoind or
  privileged networking, is in scope for reporting but weaker evidence. Expect grading on the argument rather than the demonstration.

## Known non-findings

- **`math/rand`.** It is used in `server.go`, `discovery/`, `peer/brontide.go` and fee-estimator jitter for peer shuffling, retry jitter and
  sampling. None derive a key, nonce, session identifier or macaroon, so a weak-randomness report must show the value flowing into a secret.
- **Non-constant-time comparison.** lnd compares public identifiers (channel IDs, hashes of public data, aliases) without constant-time
  equality because they are not secrets. Before reporting a timing side channel, identify the secret. "Missing authorization" on methods
  documented as unauthenticated (the pre-unlock list in `rpcserver.go`) is also not a finding.
- **`nolint:gosec` annotations.** They appear in `htlcswitch/switch.go`, `sqldb/interfaces.go`, `actor/actor.go`,
  `lnwallet/chainfee/estimator.go` and `kvdb/sqlbase/migration_bulk_postgres.go`. Re-raising one needs an argument about the value.
- **Panics recovered by design.** Decoders and RPC handlers recover panics into errors. A recovered panic matters only if the recovery is
  incomplete, the state left behind is inconsistent, or the same input panics again on the next connection.
- **Chain backend noise.** A stale tip, missing transaction or filter false positive is the backend's business. It is a finding only if lnd
  acts on that data in a way that loses value or abandons a claim. A channel-scoped message about a channel we do not have is normal crawler
  noise, and matters only if it is accepted and changes state.

## How to exercise it

The scan image (see the project Dockerfile) is `golang:1.26.10-bookworm` with the checkout at `/src`, all modules downloaded, `btcd` on
`PATH` and `GOPROXY=off`. It has no bitcoin node, regtest chain, second lnd or privileged networking, so `make itest` and anything driven
through `lntest/harness.go` will not run. We still want reports that need a confirmed funding transaction, a reorg or a cooperating
counterparty: name the state machine step, show the input that reaches it, and show why the code that should reject it does not.

Use the build tags from `make/testing_flags.mk`:
`dev autopilotrpc chainrpc invoicesrpc neutrinorpc peersrpc signrpc walletrpc watchtowerrpc`. `dev` is required to match the configuration
CI tests. A reproducer that only works under `lowscrypt` or `integration` is weaker than one working under the default tags. `tlv`, `tor`,
`kvdb`, `sqldb` and others are separate Go modules (see `scripts/unit_test_modules.sh`), so test them from inside their directory.

The cheapest routes to a test are `CreateTestChannels` in `lnwallet/test_utils.go` (two in-memory `LightningChannel` instances exchanging
commitment signatures with no chain or network), the mock switch plumbing in `htlcswitch/mock.go`, and the fuzz targets
(`lnwire/fuzz_test.go` for every wire message, plus `brontide/`, `tlv/`, `bolt12/`, `zpay32/`, `watchtower/wtwire/` and `macaroons/`).
`make fuzz` runs them (see `docs/fuzz.md`).

## Report and patch preferences

A useful report has five parts:

1. The entry point named precisely: the wire message type and its `Decode` or dispatch function, the RPC method and proto name, or the chain
   backend callback. "A malicious peer could" is not one.
2. The state that must hold for the input to be accepted and the state it leaves behind. For channel issues, give the commitment state and
   what each side has sent and acknowledged.
3. A reproducer. A Go test in the existing table-driven style is ideal, either a case in a `*_test.go` next to the code or a new test using
   `CreateTestChannels` or two mock switch peers. A fuzz corpus entry is acceptable for a decoder bug. Failing both, give the exact ordered
   function calls reaching the fault. If it needs a chain, describe it in `lntest` terms so a maintainer can run it locally.
4. Expected versus observed behaviour.
5. The consequence in value, availability or privacy, with the prerequisite stated.

A merge-ready patch is welcome and usually more useful than a reproducer alone, under three constraints. Keep it minimal: fix the specific
check and leave surrounding logic alone. Do not change exported function signatures or protobuf definitions, since mobile wallets and other
Lightning implementations depend on them. Do not silently change wire behaviour, and say explicitly if the fix alters what we send, because
a peer protocol compatibility change is a much larger decision than a validation fix. For a missing check, prefer rejecting the input early
and cheaply over sanitising it later. For an ordering problem, prefer a change that makes the bad order unrepresentable over a compensating
branch.
