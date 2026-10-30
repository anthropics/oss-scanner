# Threat model: wavelength

## What this project does and where untrusted input enters

wavelength is a self-custodial implementation of an Ark-style protocol. A client holds bitcoin in
VTXOs (virtual transaction outputs) that live off-chain inside a shared tree owned by an operator,
and can unilaterally exit back to the chain after a timeout without the operator's cooperation.
Value moves through rounds (where VTXOs are refreshed and forfeited), out-of-round (OOR) transfers
between clients, and boarding and exit/`unroll` flows to and from the base chain.

The security model is unusual and it is the whole point of the design: the operator is a
**counterparty but not a custodian**. It can refuse to serve, stall, or vanish, and the client must
still be able to get its money out. It must not be able to help itself to a client's value, to
forge a VTXO's state, or to make a client believe it holds something it does not.

This self-custody guarantee applies to VTXOs. Credits are custodial balances in the swap server's
ledger and do not provide the same unilateral-exit guarantee.

Trust boundaries:

- **The operator (`serverconn`, `swapclientserver`, `swaprpc`/`arkrpc` gRPC).** Every message the
  operator sends is attacker-controlled from the client's point of view, and vice versa: the operator
  must not trust a client's claimed value, signatures or VTXO set either. Where the two sides
  disagree about the state of a round, the assignment of a VTXO, or the outcome of a forfeit, at most
  one of them can be right, and a client that believes the wrong one can lose funds. This boundary is
  the highest-value target in the codebase.
- **The chain source (`chainsource`, `chainbackends`).** Blocks, transactions and confirmation counts
  drive every timeout and every unilateral exit. A hostile chain source can withhold data (out of
  scope below, since that is not curable in software), but a *malformed* view — a transaction that
  spends a VTXO in an unexpected way, a reorg that reorders a timeout, a confirmation that arrives
  just before a deadline — is in scope.
- **ArkScript and policy scripts (`lib/arkscript`, `rules`, `docs/arkscript_spec.md`,
  `docs/policy_arkscript_review_guide.md`).** A small script language decides who may spend a VTXO
  and under which timelock and key conditions. If a policy compiles to something weaker than it
  reads, the script itself is the vulnerability, and it applies to every VTXO using it. The parser and
  the compiler are both in scope, plus the golden tests that pin their output.
- **The mailbox (`mailbox`, `serverconn/mailboxpull`, `docs/RPC_MAILBOX_CONTRACT.md`).** A relay for
  messages between client and operator. It is not trusted with plaintext, and its contract says so.
- **Local RPC (`rpc`, `rpcauth`, `wavecli`).** The operator of the daemon. Not a remote attacker, so
  lower weight, but an argument that reaches a signing or spending decision with the wrong value is
  still worth reporting.
- **The daemon database (`db`, `db/schemas.go`).** Durable accounting state. Corruption here is a
  correctness and fund-safety issue, not usually an adversary.

## Components that matter most

1. **`lib/arkscript/` — `lib/arkscript/compose.go`, `lib/arkscript/node.go`,
   `lib/arkscript/policy_template.go`, `lib/arkscript/checkpoint.go`, `lib/arkscript/anchor.go`,
   `lib/arkscript/nums.go`, `lib/arkscript/boarding_asset.go`.** The script language and its compiler. The property that must
   hold is that the script a policy compiles to enforces exactly the conditions the policy states:
   the same keys, the same timelocks, the same spend paths, and no extra path. `lib/arkscript/golden_test.go` pins
   the compiled form, so a divergence between what a policy means and what it emits is the bug class
   to hunt. `lib/arkscript/nums.go` defines the NUMS internal key used to prevent key-path spending.
   Recipient VTXO policies must disable key-path spending, require a non-operator signer on
   collaborative paths, and provide CSV-gated operator-free recovery paths. Checkpoint, tree, and
   anchor outputs must be validated against their respective protocol roles.
   The client must verify the exact output script before signing. Compilation must be canonical
   and deterministic, and
   policy and witness decoding must bound leaves, depth, nodes, keys, and script elements.
2. **`round/` (66 files) — `round/actor.go`, `round/fsm_timeouts.go`, `round/asset_request.go`,
   `round/asset_vtxo_state.go`, `round/from_proto.go`, `round/deadline.go`.** The round state machine. This is where
   value is refreshed and forfeited. The properties are that a round cannot complete with value
   unaccounted for, that a forfeit is only accepted against a VTXO that genuinely exists and belongs
   to the party forfeiting it, that a client's VTXO set after a round is exactly what it is entitled
   to, and that a non-cooperating or hostile participant cannot cost more than its own stake
   (collateral damage must be bounded). `round/from_proto.go` and `round/asset_request.go` are the decode
   surfaces; `round/fsm_timeouts.go` and `round/deadline.go` decide what happens when a counterparty goes quiet,
   and a timeout that resolves the wrong way is a fund-loss path.
   Before producing a nonce or signature, the client must validate the complete tree, exact
   parent-to-child value conservation, ownership of its leaves, quote amounts, sweep policy, and
   connector ancestry. Before releasing a forfeit signature, it must validate the replacement
   outputs and connector binding and, where replacement VTXOs are created, verify their signed
   tree. Boarding signatures must remain withheld until commitment and tree-signature validation
   succeeds. MuSig2 nonces must never be reused across signing attempts, including after abort or
   restart. Messages must bind the expected round and phase. Reservations release only for their
   owning round, and restart recovers confirmation and accounting exactly once.
3. **`unroll/` (50 files) — `unroll/fsm_logic.go`, `unroll/exit_plan.go`, `unroll/feasibility.go`,
   `unroll/db_store.go`, `unroll/deferred_checkpoint_codec.go`, `unroll/descriptor_resolver.go`.** The unilateral exit. This is the
   backstop that makes the whole thing self-custodial: if the operator disappears, every client must
   be able to get out within a known bound. The property is that an exit is always *feasible* — the
   plan exists, the transactions are broadcastable, the deadlines fit inside the on-chain timelock —
   and that the client's own view of its exit progress cannot be advanced past what the chain has
   actually confirmed. `unroll/feasibility.go` is where "can I still get out" is answered, so a wrong answer
   there is critical.
   Recovery proofs must form a complete, acyclic, bounded graph and broadcast in topological
   order. Signed sweep state must be durable before broadcast, with replay reusing its exact bytes
   and destination. Fee replacement must preserve the input and destination while respecting fee
   and locktime limits. An unexpected ancestor or external spend must fail closed or trigger
   recovery, never be mistaken for the client's own exit.
   For vHTLCs, admission and recovery must preserve enough time for ancestry materialization and
   the applicable CSV/CLTV claim or refund path, without racing cooperative and unilateral spends.
4. **`swapwallet/` (50 files) — `swapwallet/credit_projector.go`, `swapwallet/creditmath.go`,
   `swapwallet/admin.go`, `swapwallet/batch_wait.go`, `swapwallet/history.go`,
   `swapwallet/inspection.go`.** The client-side wallet, including the credit accounting that
   tracks what the client is owed across pending operations. `swapwallet/creditmath.go` is value arithmetic;
   `swapwallet/credit_projector.go` projects durable credit state. A discrepancy here is a value-conservation
   bug even if no signature is forged.
5. **`credit/` (17 files) — `credit/policy.go`, `credit/op_actor.go`, `credit/state.go`,
   `credit/states.go`, `credit/registry.go`, `credit/snapshot.go`.** Credit authority and its durable actor. The property is that credit is only
   granted, moved or released under the authority that owns it, that an operation is charged exactly
   once, and that a rejected or retried operation leaves no residue but also does not lose the value
   it was holding. `docs/credit_system.md` and `docs/credit_durable_actor_design.md` state the intent;
   compare the code against them.
   The server ledger is authoritative for custodial credit accounting; client-side authorization,
   payment-evidence, and VTXO-validation checks still apply. Credit, pay, receive, and redeem
   operations need
   stable idempotency keys, durable operation state before external effects, and interlocks
   against concurrent redemption or double release. In-flight obligations reduce available credit.
   Retries and restarts converge to one operation; malformed durable state must reach a
   recoverable terminal state rather than wedge the wallet.
6. **`vtxo/` (56 files) — `vtxo/actor.go`, `vtxo/chain_resolver.go`, `vtxo/expiry.go`,
   `vtxo/expiry_reconcile.go`, `vtxo/expiry_target.go`, `vtxo/authenticated_expiry.go`,
   `vtxo/filter.go`.** The client's view of which VTXOs it
   holds and when they expire. The properties are that a VTXO's expiry is derived from the chain and
   cannot be moved later by a hostile counterparty, that a VTXO the client no longer owns is dropped,
   and that an unconfirmed or conflicting VTXO is never treated as spendable.
   A server push is only a hint: live balance requires an owned script, chain-authenticated
   ancestry, and locally derived expiry. Spending, forfeiting, exiting, and spent states must be
   mutually exclusive and round-fenced. An error assessing exit feasibility must never suppress
   the unilateral-exit safety path.
7. **`serverconn/` (56 files) and `swapclientserver/`.** The operator's and client's connection
   handling. The properties are that a response is bound to the request that produced it (no
   cross-talk between sessions or between rounds), that a replayed or reordered response cannot move
   the client's state machine backwards or forwards, and that a malicious peer can at worst stall.
   Durable ingress must commit each envelope before advancing its cursor, preserve that ordering
   across disconnects and restarts, and make replay idempotent. Replayed or reordered messages
   must not move value or skip recovery work. Hostile floods need bounded sessions, messages,
   retries, and resident state.
8. **`ledger/`, `coinselect/`, `chainbackends/`, `chainsource/`, `txconfirm/`, `chainfees/`.**
   Accounting, coin selection, and the chain view. Coin selection that can double-select an input, a
   fee computation that can be made arbitrarily large by a counterparty, or a confirmation rule that
   accepts an unconfirmed spend are all in scope.
9. **`fraud/`.** Fraud protection must not be considered active until all required watches are
   installed; partial failures must remain recoverable. A spend may
   be treated as an authorized operator sweep only when its revealed script matches the committed
   sweep policy. An unrecognized non-operator ancestor spend must trigger unilateral exit for
   every affected target, and a failure for one target must not suppress recovery for the rest.
10. **`oor/`.** Incoming packages must validate their complete ancestry, checkpoint signatures,
   two-of-two collaborative path, scripts, value, and chain-authenticated expiry before becoming
   balance. The client must verify the operator's signatures on the returned Ark and checkpoint
   transactions before releasing its checkpoint signatures. Co-signed checkpoints must be persisted
   verbatim and replayed idempotently; a changed recipient, amount, or output set under the same
   caller key must be rejected. A stalled peer must not block durable recovery or unrelated wallet
   operations.

## Out of scope or low priority

- **`systest/`, `harness/`.** System-test harnesses. Useful to you as a reference for how to drive a
  full scenario, but a bug that only affects the harness is not a finding.
- **`p-models/`, `tla-models/`, `formal/`.** Formal models and their tooling. A disagreement between
  a model and the code is interesting as a *lead*, but the finding has to be in the Go code. A model
  that under-specifies something is not itself a vulnerability.
- **`baselib/`.** A separate Go module of generic actor and FSM primitives, shared with other
  projects. It is built and its tests compiled in the image, but it is generic infrastructure: report
  a flaw there only if you can show a concrete consequence in wavelength's own value handling, and
  say which.
- **`cmd/`, `waved/`, `wavecli`, `build/`, `make/`, `scripts/`, `tools/`, `internal/`, `metrics/`.**
  Daemon startup, CLI plumbing, build and observability.
- **`p-models/bridge/`, `docs/`, `sdk/ark`, `arkrpc/` generated stubs.** Generated types and
  documentation. `sdk/ark` is a client convenience layer; a bug that only makes the SDK awkward, with
  no wrong value reaching a signature, is low priority.
- **The daemon database being malicious.** As with any wallet, whoever can write the database can
  delete it. A panic on a hand-corrupted SQLite file, with no signature produced and no key released,
  is a robustness note.
- **A chain backend that is offline, slow or withholding.** The protocol's answer to that is the
  unilateral exit; if the exit works, the withholding is not a vulnerability. If the exit does *not*
  work under withholding, that is a `unroll/feasibility.go` finding and it is critical — report it
  that way rather than as a DoS.
- **Privacy of the mailbox or the transport.** Understood and documented in
  `docs/RPC_MAILBOX_CONTRACT.md`.

## How to exercise it

The image is a Go workspace: `go.work` covers `.`, `./baselib` and `./tools`, so every module resolves
in place. The full suite is compiled at build time.

```
go test ./...                                   # root module, what `make unit` runs
go test ./round/... ./unroll/... ./vtxo/...     # the three fund-safety cores
go test ./lib/arkscript/...                     # script compilation, golden tests
go test ./credit/... ./swapwallet/...           # credit accounting
cd baselib && go test ./...                     # the separate module
```

Specific entry points worth knowing, all reachable without a network:

- **ArkScript.** `lib/arkscript/golden_test.go` and `lib/arkscript/compose_test.go` show how a policy is compiled
  and pinned. The cheapest strong reproducer for a policy-semantics bug is a new case in that
  harness: one policy, the script you expected, the script that was produced.
- **Unroll feasibility.** `unroll/exit_plan.go` and `unroll/feasibility.go` compute whether an exit
  is possible from a given VTXO set and chain height. `unroll/` has an FSM with an explicit logic file
  (`unroll/fsm_logic.go`) and a persisted store (`unroll/db_store.go`), so a scenario can be driven as a sequence of
  events against the FSM with a fake chain and fake clock rather than a live chain.
- **Rounds.** `round/actor.go`, `round/fsm_timeouts.go` and `round/deadline.go` are driven by messages; the
  `systest/` harness shows the message shapes that a full round exchanges, which you can replay
  against the FSM directly with adversarial modifications.
- **Credit.** `credit/` is an actor with durable state and explicit `credit/states.go`; the `credit_*_test.go`
  files in `swapwallet/` and the other `credit_*_test.go` files in `swapwallet/` show the existing
  patterns for asserting on credit state after an operation sequence.
- **Timelocks and expiry.** `vtxo/expiry.go`, `vtxo/expiry_reconcile.go` and `round/deadline.go` take a
  height and a clock. Faking both is the way to test a deadline boundary without mining blocks.

Reproducers that need a live operator, a second client, or a chain cannot be demonstrated in the
image. Provide the smallest in-process equivalent — usually an FSM driven with a hostile message
sequence, or a direct call on a plan/feasibility function with adversarial inputs — and say clearly
which one you ran. A reproducer that cannot run in the image is still in scope; it is just weaker.

## How we rate severity

The question to ask is what the operator, or a hostile counterparty in a round, gains.

| Severity | What falls here |
| --- | --- |
| **Critical** | Any path by which a client loses value it should be able to recover: value not accounted for after a round, a forfeit accepted against a VTXO the client did not commit, an OOR transfer that credits the sender's view but not the recipient's (or the reverse), credit granted or released twice. Any unilateral exit that is not actually feasible within its timelock under a realistic chain view — a client that cannot get out is the failure the whole design exists to prevent. Any ArkScript or policy compilation that produces a weaker spend condition than the policy states, or lets a party spend a VTXO it should not. Value inflation: a client or operator able to claim more than it put in. |
| **High** | A value-conservation break whose worst case is bounded and recoverable, or which the counterparty can trigger but which requires an operator that is otherwise behaving. A forged or replayed operator response that moves a client's state machine to a wrong-but-not-fund-losing outcome. A timelock or deadline computation that is wrong at a boundary in a way that narrows the exit window. Durable accounting state that can be driven into an inconsistent form requiring manual repair. Denial of service reachable by a counterparty in a round that costs the victim more than it costs the attacker. |
| **Medium** | A panic or unrecoverable error reachable from a malformed operator message, a malformed gRPC field (`round/from_proto.go`) or a crafted VTXO record, where nothing is signed and no state is lost. Bounded memory or CPU exhaustion from a hostile peer where recovery is automatic. A cross-session or cross-round message mix-up that leaks or confuses metadata but not value. A local RPC argument bug whose worst case is a refused or mis-parameterised but non-destructive operation. |
| **Low** | Missing validation with no demonstrated effect. A CLI or startup misconfiguration that only harms the operator who made it. A crash on input a real counterparty cannot produce. Hygiene issues in dead or debug paths. |
| **Out of scope for rating** | Anything that requires the attacker to already hold the daemon's local database, its keys, or an unlocked RPC session. The operator refusing to serve, stalling, or going offline — as long as `unroll/` still works, that is the protocol functioning as designed. Formal models disagreeing with code. `baselib/` generic primitives with no demonstrated wavelength consequence. |

For a *rating* we discount, but still want reported: a flaw that needs the victim to be running an
already-suspect configuration, a DoS that needs an authenticated peer, and anything whose impact is
only on the SDK.

## Report and patch preferences

- **State the value flow in the report, explicitly.** For anything in `round/`, `credit/`, `vtxo/` or
  `unroll/`, write the amounts and the direction: who starts with what, what the attacker does, who
  ends with what. A conservation claim you cannot draw as a balance sheet is not yet a finding.
- **For `lib/arkscript/`, give both scripts.** The policy you wrote, the script you expected, the
  script that was compiled. That is a two-line report that a reviewer can act on immediately.
- **Prefer a reproducer that drives the FSM or the accounting directly** over one that stands up an
  operator. The FSM logic files and the credit actor are both designed to be driven by a message
  sequence.
- **Propose a merge-ready patch when the fix is a validation, a bound or an ordering.** For a change
  to round or exit logic, a minimal patch plus a short statement of the invariant that was violated
  is better than a refactor: the reviewer needs to re-derive the invariant, not read a diff.
- **Say whether the operator or the client is the party that benefits.** In a two-sided protocol the
  answer to "who is the attacker here" changes the severity, and it is the first thing a maintainer
  will ask.
- Do not paste whole files. Quote the lines that matter with the function name.

## Anything to leave alone

These recur and are not findings.

- **Panics recovered by an actor supervisor, and actor restarts.** The codebase is built on durable
  actors (`baselib/actor`) that deliberately stop and restart on bad input. A recovered panic is only
  interesting if the recovery loses durable state, double-charges credit, or repeats on input the
  system will keep receiving.
- **Deliberate use of timers, deadlines and timeouts that look "too short" or "too long".** They are
  set against protocol constants stated in `docs/`; a report about a timeout needs to name the
  constant it violates and cite where that constant is specified.
- **Test files, `systest/`, `harness/`, `qemu`/`waved` fixtures.** Convenient by design.
- **`-gcflags "all=-N -l"` and the `dev` build tag.** Deliberate: debug info without inlining keeps
  stack traces and reproducers matching the source.
- **`unsafe`, manual byte slicing and hand-rolled codecs in the VM and codec files
  (`unroll/deferred_checkpoint_codec.go` and the TLV handling in `baselib/tlvutil`).** Report only if you can
  show a length check missing or a slice escaping its bound; the presence of `unsafe` is not a finding.
- **Constant-time comparison of hashes and keys.** Intentional. Conversely, comparing public
  identifiers — VTXO IDs, txids, round IDs — non-constant-time is fine; identify a secret before
  reporting a timing side channel.
- **The operator learning things it is allowed to learn.** The operator sees round structure and the
  VTXO set by design. Privacy concerns that follow from the architecture, rather than from a deviation
  the docs describe, are not findings here.
- **A chain backend that is offline, slow, or withheld.** As above: if the exit still works, that is
  the design working. If it does not, that is a critical `unroll/` finding, not a DoS.
- **The mailbox relay seeing message metadata,** which `docs/RPC_MAILBOX_CONTRACT.md` explicitly
  scopes out.
- **Formal-model gaps.** `p-models/`, `tla-models/` and `formal/` under-specifying something is a
  documentation observation; the finding must be in the Go code.
