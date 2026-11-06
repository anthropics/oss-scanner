# bark threat model

## What this project does

bark is an implementation of the Ark protocol on bitcoin: a layer 2 in which a
server lets clients hold and transfer bitcoin off-chain, while each client can
unilaterally "exit" its balance on-chain at any time.

The repository holds both sides of that system:

| Path | Crate | What it is |
| --- | --- | --- |
| `server/` | `bark-server` | `captaind`, the Ark server. Every client-facing RPC. |
| `server/src/bin/watchmand` | `bark-server` | `watchmand`, a daemon with no client interface. It watches the chain and acts on what it sees. |
| `bark/` | `bark-wallet` | The wallet library. |
| `bark-cli/` | `bark-cli` | `bark`, a CLI wallet; `barkd`, a wallet daemon with a REST API. |
| `lib/` | `ark-lib` | Protocol primitives: VTXOs, rounds, forfeits, arkoor, the lightning policies. |
| `server-rpc/`, `bark-rest/` | | The gRPC and REST surfaces. |
| `bitcoin-ext/`, `cln-rpc/` | | Bitcoin Core and Core Lightning clients. |

## Trust boundary

The server is honest and the operator is trusted. The attacker is a client.

A client can send arbitrary bytes to any RPC, in any order, at any time, and
can cancel a stream mid-call. A client can run a modified wallet: no guard that
lives only in `bark/` or `bark-cli/` counts as a defence, because the attacker
does not run that code. A client can also attack another client through the
server.

Cryptography holds. Bitcoin consensus holds, and so does the full node.

Out of scope: attacks by the operator against clients, and attacks in which
the only funds at risk are the attacker's own.

## What matters most

**Money.** Can a client make the server lose funds, or spend the same VTXO or
output twice? The invariants:

- A VTXO is spent at most once, across rounds, forfeits, offboards, arkoor
  sends and lightning flows.
- No flow pays out more than it takes in.
- Every forfeit and every offboard is fully collateralised by what the client
  contributed.
- Out-of-round sends and cosigning cannot create value the client did not fund.
- No lightning path yields a preimage or funds without the payment, and none
  strands server funds in an HTLC the client controls.
- The server never cosigns value movement the requester did not fund, and no
  signing flow acts as an oracle for another.
- Every path that consumes a VTXO rejects every way that VTXO can have stopped
  being legitimately spendable, not only the way a recent bug highlighted.

One unguarded case is a money bug. We would rather read ten money findings than
miss one.

A specific thing to look for: the server holds off-chain state in PostgreSQL
and the chain holds the truth. Where a release of value is authorised against
the database alone, ask whether the chain can already disagree, and whether a
client can make it disagree on purpose.

**Denial of service**, second. It counts when it costs the server money, kills
a process, stalls something every other client needs such as the round loop or
a global lock, or leaves permanent free state in bitcoind or Core Lightning at
no cost to the attacker. Say which of those it is.

Availability is not fund loss. Stranding a server-owned resource is
availability, even when the resource holds funds.

Everything else — memory safety in the parsing paths, authentication and
authorisation on the REST surface, injection, secret handling — is in scope and
welcome, but rank it below the two above.

## Components that matter least

`testing/`, `fuzz/`, `wasm-testing/` and `contrib/` are harness and tooling.
Neither the directory name nor the fact that an artifact is published decides
this: the config an artifact ships decides it. An image pushed from a release
path is still a regtest rig when the config beside it pins a test network. That
does not excuse the build integrity of the same image.

## How to exercise it

The image builds bark through its nix flake, and nothing is on the default
PATH. Use the wrapper:

```
bark-run cargo build --workspace                       # rebuild
bark-run cargo nextest run --workspace --exclude ark-testing   # unit tests
bark-run cargo nextest run -p ark-testing --test core  # daemons come up
bark-run cargo nextest run -p ark-testing --test bark  # wallet against server
bark-run bash -i                                       # a shell in it
```

`bark-run` runs as the unprivileged user `bark`, because the integration tests
start PostgreSQL and `initdb` refuses to run as root. To do it by hand:
`. /opt/bark-env.sh` as that user.

The integration harness in `testing/` is the best way to demonstrate a finding.
It starts a real regtest bitcoind, a real Core Lightning with the hold plugin,
a real PostgreSQL and a real `captaind`, all offline. `ark_testing::TestContext`
builds the world; `captaind::proxy::ArkRpcProxy` sits between a wallet and the
server and can delay, drop or rewrite any RPC, which is how you model a client
that does not follow the protocol. Put a new test beside the others in
`testing/tests/bark/`.

A money proof-of-concept should end on a balance assertion: the attacker
finishes with more than the attacker funded, or the server finishes with less
than it took in. That assertion is what we will run.

## How we rate severity

- **Critical** — a client takes funds that are not theirs, spends one VTXO
  twice, or drains server funds, using only the public RPCs and no unusual
  precondition.
- **High** — the same outcome, but it needs a race, particular timing, a
  server restart, or an uncommon configuration. Also: a client makes another
  client lose funds. Name the other client and what they lose.
- **Medium** — DoS that meets the bar above. Also: a memory-safety or
  authorisation defect with no demonstrated path to funds.
- **Low** — a real defect with no demonstrated harm.

Rate on demonstrated impact, not on how alarming the code looks. If you cannot
state the consequence in one sentence — money lost, a process killed, or
another user harmed — it is not a finding.

## What already stops you, so do not report it

These three are deployment facts. You cannot see them in this checkout, so
their absence from the code is never a finding. Do not search for them and
report what you fail to find. What is reportable is code that defeats one from
inside, such as a handler reachable on a path that never passes the proxy.

1. A reverse proxy terminates every public RPC and applies per-IP token
   buckets. The bucket bounds what one IP can accumulate, not only how fast it
   can call, so a resource held open per request passes through the same
   bucket. "No cap on concurrent X per IP" is therefore not a finding.
2. Traffic between hosts is encrypted and authenticated at the network layer.
3. The container registry is private, and its credentials reach only protected
   CI branches.

The next three are properties of this codebase and of the protocol, so you
*can* check them here. Report one that is absent or misconfigured.

4. An expired VTXO is safe to serve. "This path does not compare expiry to the
   chain tip" is a finding only with a client-to-client harm attached.
5. The rightful owner has exit-delta priority. No finding may rest on either
   side winning a fee race.
6. A gap is kept between incoming and outgoing HTLC expiries. Cancelling at
   expiry is deliberate.

## Not a deliverable

- Local CPU burn, in-process memory growth, or state fill that a per-IP bucket
  absorbs.
- A fixed or linear number of upstream RPCs per request. That is the cost of
  the feature. To report amplification, show that the cost grows faster than
  the request count one IP can buy, and that the work is not intrinsic to what
  the endpoint promises.
- Deliberate retention. A table that only grows is an accepted trade-off.
- A hold of seconds on a resource the operator owns, unless it is unbounded or
  a client can extend it at will.
- Anything the attacker pays for. Price one unit of harm first: if causing it
  costs a fee, a premium or a held VTXO, we are being paid for the damage.
- A control that was never built. A missing rate limit, quota or ban list is a
  roadmap item, not a vulnerability.
- A defect owned by an upstream crate, such as key zeroization on drop.
- A migration or a behaviour too old to change. Roughly three months is the
  limit.
- A fix that would break a documented function.
- A defect already fixed on master. Re-read the live code at HEAD before you
  report.

## How to write it up

Most rejected findings were right about the code and wrong about the system,
because a guard somewhere else bounded the damage. So, in every report:

- Name the guard you looked for and say why it does not cover this path, or say
  you found none and where you looked.
- State the consequence in one sentence.
- Give the file and line at HEAD.
- Give a patch. Minimal is fine; we would rather see the smallest change that
  closes the hole than a refactor.
- Give a test in `testing/tests/` where the finding is reachable that way.

## How to deduplicate

One report per unguarded code path, not one per call site that reaches it. If
the same missing check is absent in four handlers, that is one finding with
four locations. If four handlers each miss a different check and all four lead
to the same loss, that is four findings — we have to fix each one.
