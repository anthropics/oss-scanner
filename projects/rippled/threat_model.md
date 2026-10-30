# rippled / xrpld: threat model and severity guide for the scanner

`xrpld` (historically `rippled`) is the reference server for the **XRP Ledger (XRPL)**, a public,
decentralized blockchain. It is a C++ daemon (ISC licensed, https://github.com/XRPLF/rippled, home
https://xrpl.org) that participates in a peer-to-peer overlay, applies transactions, runs the XRP Ledger
Consensus Protocol with other validators, stores the ledger in a SHAMap, and serves JSON-RPC / WebSocket /
gRPC APIs. The same tree builds `libxrpl`, the protocol/serialization/crypto library many other XRPL tools
depend on.

Because it is a validator and transaction processor for a live network carrying real value, the stakes are
unusual: the worst outcomes are not just crashes but **consensus failures, unauthorized movement or creation
of funds, and remote code execution on validators.** Rate findings with that in mind.

This file is a guide for a scan. Worth reading in the image before starting:

- `CONTRIBUTING.md`, `docs/` and the per-directory `README.md` files under `src/` for architecture.
- `src/libxrpl/protocol` and `include/xrpl/protocol` for the binary serialization format (STObject, STArray,
  STAmount, fields) that every transaction and ledger object uses.
- `src/xrpld/app/tx` for the transactors (one per transaction type) and the **invariant checks**
  (`InvariantCheck.*`) that run after every transaction — these encode "things that must never happen".
- The amendment list (`src/libxrpl/protocol/Feature.cpp` / `include/xrpl/protocol/detail/features.macro`):
  features gate consensus-relevant behaviour and are the project's own map of what is new and sensitive.

## What xrpld does and where untrusted input enters

"Untrusted" means anything a remote peer, an API client, or an attacker who can craft a transaction or a
network message can supply. In rough order of exposure:

- **The peer-to-peer overlay protocol** (`src/xrpld/overlay`). The largest remote surface. Peers exchange
  length-prefixed, compressed Protocol Buffer messages over TLS: transactions, consensus proposals,
  validations, `GetLedger`/`LedgerData`, `GetObjectByHash`, manifests, endpoints, `TMHaveSet`, `TMPing`,
  shard/have messages, squelch, etc. Everything here — the framing, decompression, protobuf decode, and each
  message handler — processes bytes from an unauthenticated or semi-trusted peer. A single malicious peer is a
  realistic attacker.
- **Transaction deserialization and processing** (`src/libxrpl/protocol`, `src/xrpld/app/tx`). Transactions
  arrive as the binary STObject format (from the overlay or via `submit`). Parsing (`SerialIter`, `STObject`,
  `STArray`, `STAmount`, `STI*` types), canonical-form and signature checks (secp256k1 and ed25519,
  `src/libxrpl/crypto`), fee/sequence checks, then the per-type transactor applies it and the invariant
  checks verify the result. This path decides who owns what: payments, offers/DEX, AMM, trust lines,
  escrows, checks, payment channels, NFTs, tickets, multisign, pseudo-accounts.
- **Consensus** (`src/xrpld/app/consensus`, `src/xrpld/consensus`). Proposals and validations from other
  validators drive the agreement protocol. Bugs that let an attacker force disagreement, a fork, or a halt
  live here and in the ledger-close / transaction-set logic.
- **The RPC / WebSocket / gRPC APIs** (`src/xrpld/rpc`, `src/xrpld/net`, gRPC under `proto`). JSON-RPC and
  WebSocket handlers, subscriptions, and the gRPC interface used by Clio and others. Commands are split into
  **public** (reachable by anyone the operator exposes the port to) and **admin** (privileged). The
  public/admin boundary (`Role`, `Handler` flags) is security-relevant: a public client reaching an admin-only
  command, or an admin command that trusts its JSON too much, matters.
- **SHAMap and ledger data** (`src/xrpld/shamap`, `src/xrpld/app/ledger`). Inner/leaf node blobs and whole
  ledgers fetched from peers are deserialized and hashed. Tree-walking on attacker-supplied nodes is in scope.
- **Validator trust material** (`src/xrpld/app/misc` — `ValidatorList`, `ValidatorSite`, `Manifest`). Signed
  validator lists (the UNL) and manifests are fetched over the network and parsed; accepting a forged or
  malformed one would be serious.
- **Path finding and the DEX/AMM math** (pathfinding, `STAmount`/`Number` arithmetic, offer crossing, AMM
  curve math). Attacker-chosen payment paths and order books drive large computations and delicate arithmetic
  where rounding or overflow can mean mispriced or lost funds.
- **JSON → transaction/sign conversion** (`STParsedJSONObject`, the `sign`/`submit` paths): untrusted JSON
  turned into binary objects.
- **The WASM VM / smart-contract host functions** (`crates/`, linked via corrosion; host-function glue in
  C++). This is new, executes attacker-supplied programs, and the C++/Rust boundary (host functions reading
  guest memory, gas accounting) is a fresh and high-value surface. Treat anything here as adversarial input.

`libxrpl`'s public API is the set of headers under `include/xrpl/`. Code reachable only from the unit tests
(`src/test`, `src/tests`) via test-only hooks is not, by itself, a public entry point — a reachability
argument should name the real entry (a peer message, a transaction, an API call).

## What matters most, and what is out of scope

Most important, roughly in order:

1. **Consensus safety and integrity** — anything that can fork the ledger, let validators disagree
   permanently, double-spend, or apply a transaction that violates the protocol's invariants.
2. **Fund safety** — unauthorized transfer or spending from accounts the attacker does not control, creating
   XRP or issued assets out of nothing, destroying or freezing funds incorrectly, or arithmetic errors in
   amounts/offers/AMM that misprice or lose value. The `InvariantCheck` suite is the last line here; a way to
   bypass or defeat it is high-impact.
3. **Signature / authorization bypass** — accepting a transaction with an invalid, missing, replayed, or
   malleable signature; multisign threshold errors; regular-key / signer-list handling.
4. **Memory safety in adversarial-input paths** — the overlay protobuf handlers, transaction/ledger
   deserialization, SHAMap node parsing, the WASM host boundary. A controlled write here, remotely reachable,
   is the RCE case.
5. **Validator / network liveness** — a single peer or unauthenticated client that can crash, hang, or
   exhaust a validator (DoS). For a consensus network, liveness is a security property.
6. **Key and seed handling** — validator secret keys, node keys, wallet seeds: any disclosure, predictable
   generation, or leak (including via side channel) in `src/libxrpl/crypto` and key stores.

In scope but lower priority:

- Admin-only RPC commands: the operator is trusted, but a crash or memory bug reachable from a documented
  admin command is still worth reporting (note that it needs admin).
- `libxrpl` consumed as a library by other code: memory safety and correctness of the public API matter even
  where `xrpld` itself never passes the triggering input.
- Standalone / test-net only behaviour (`-a`, `--start`): useful for reproducers, but say so.

Out of scope, or not what we mean by security:

- **Economic and game-theoretic behaviour that is within protocol rules** — fee escalation under load, spam
  that pays the required fees, validator incentive arguments, "a large stakeholder could…" — unless there is
  an actual code defect (e.g. a fee or reserve calculation that is wrong). We want bugs, not protocol-design
  debates.
- **Third-party dependencies themselves** — boost, OpenSSL, RocksDB/NuDB, gRPC/protobuf, SOCI, libarchive,
  secp256k1, etc. come from Conan (`conanfile.py`). Our *wrappers and our use* of them are in scope; a bug
  inside the upstream library is theirs. A decompression bomb from a peer is in scope only if *we* fail to
  bound it where we should.
- **The test tree** (`src/test`, `src/tests`, anything built only for unit testing) and build tooling
  (`cmake/`, `conan/`, `.github/`, `bin/`): these assume trusted inputs. A bug in a test is just a bug.
- **Deliberate operator footguns** — configuration that an admin sets (`rippled.cfg`), unsafe flags, exposing
  an admin port to the world. Document, do not rate as a vulnerability in the code.
- 32-bit-only overflows: this image is x86-64. If analysis finds one, report it as analysis and say it was not
  reproduced here; do not claim 64-bit impact.

## The image: how to build, run and exercise it

The checkout is `/src`; `git -C /src rev-parse HEAD` names the commit under scan. **Everything runs offline,
and the binaries were built inside rippled's pinned Nix dev shell, so run them from inside that shell:** prefix
commands with `nix develop .#gcc-plain --command` and run from `/src`. For an interactive session:

```
cd /src && nix develop .#gcc-plain   # drops you into the toolchain shell; the build is in /src/.build
```

The server binary is `/src/.build/xrpld` (a Release build at `-O1` with `-g1 -fno-omit-frame-pointer` and
`-Dassertions=ON`, so `XRPL_ASSERT` invariant checks are compiled in; the unit tests are not built). Useful entry points:

- **Standalone mode.** `nix develop .#gcc-plain --command ./.build/xrpld -a --conf <cfg> --start` runs a single-node ledger
  with no network, so a crafted transaction or RPC call can be driven end to end offline.
- **A targeted reproducer.** Link a small C++ program against `libxrpl` from the build (headers under
  `/src/include/xrpl`, the library and objects in `/src/.build`) to feed bytes straight into `SerialIter` /
  `STObject` / `STAmount` parsing or the crypto routines. Build it inside `nix develop .#gcc-plain` so the toolchain and
  the Conan-provided dependencies match.

Where novel bugs are most likely: the byte-level parsers (`STObject`/`STArray`/`STAmount`/`SerialIter`, the
overlay protobuf handlers and their decompression, SHAMap node decoding) have had attention, so prefer logic
and arithmetic — transactor edge cases and invariant gaps, AMM/offer/`Number` math, multisign and signer-list
accounting, amendment-gated code paths that changed recently, consensus corner cases, and the WASM host-function
boundary (guest-memory reads, gas accounting). A reachability story from a peer message, a transaction, or an
API call matters more than an isolated missing bounds check.

## How we rate severity

A guide, not a rubric to apply mechanically. When in doubt about XRPL semantics, look at the relevant
transactor and its invariant checks, and at the suite that tests it.

### Critical

- **Remote code execution** reachable by a peer or an unauthenticated API client (a controlled write in an
  overlay handler, a deserializer, SHAMap parsing, or the WASM host boundary that plausibly leads to
  execution).
- **Consensus safety violation** — an attacker can make honest validators permanently disagree, fork the
  network, or accept two conflicting ledgers; a double-spend that the protocol should prevent.
- **Unauthorized fund movement or creation** — spending from an account without its valid key/authorization,
  minting XRP or issued assets out of nothing, or otherwise defeating the ownership rules, especially by
  bypassing or defeating the `InvariantCheck` suite.
- **Signature or authorization bypass** that enables any of the above (accepting an invalid or forged
  signature, a replay across accounts/networks, a multisign threshold defeat).
- **Validator secret key / seed disclosure or predictable generation.**

### High

- **Memory-corruption writes in an adversarial-input path** (overlay, transaction/ledger deserialization,
  SHAMap, WASM host) that are plausibly exploitable but where RCE is not demonstrated.
- **Incorrect transaction processing causing fund loss or wrong balances** under realistic conditions —
  arithmetic errors in `STAmount`/`Number`, offer crossing, AMM math, reserve/fee/trust-line accounting — even
  when the attacker only harms counterparties, not arbitrary accounts.
- **Remotely triggerable consensus liveness failure** — a single peer or client can halt or stall ledger
  progress across the network.
- **Public-to-admin authorization bypass** reaching an impactful admin command, or an invariant/amendment
  check that can be bypassed so an invalid transaction applies without the fund-level impact of Critical.

### Medium

- **Remotely triggerable crash, failed `XRPL_ASSERT`, infinite loop, or unbounded CPU/memory** on a single
  node (denial of service). Note who can trigger it (unauthenticated peer? public RPC? admin?) and whether it
  affects one node or propagates.
- **Read-only memory errors** (over-reads) in adversarial paths that do not obviously disclose sensitive data;
  may be High if they return meaningful memory to the attacker.
- **Arithmetic or logic errors with bounded impact** — wrong result in a corner case that does not by itself
  move funds or break consensus, but is reachable with attacker input.
- **Side channels that could leak long-lived key material** (non-constant-time signing or key handling with a
  plausible remote or co-resident observer).

### Low

- **Policy / configuration enforcement gaps** — the operator asked for a limit or mode and the code did not
  fully enforce it, with limited impact.
- **Side channels with limited leakage** (ephemeral values, very narrow channels).
- **Information disclosure of non-sensitive data**, or issues that require admin/trusted access and that such
  an actor could cause anyway by legitimate means.

### "It's just a bug"

Report these, rated Low or as a non-security bug, without inflating them:

- An input that makes a `XRPL_ASSERT` / invariant fail *where the result in a non-asserting build is a clean
  transaction failure (`tec`/`tem`) or a handled error*, with no further consequence. If a remote peer can
  trip it and the consequence is a crash, that is the Medium DoS case instead — rate on the consequence.
- A transaction that is correctly **rejected** with a `tem`/`tef`/`tel`/`tec` result code: that is the designed
  way to signal bad input, not a vulnerability.
- API misuse of `libxrpl` that the library fails to catch but that `xrpld` itself never performs.
- A wrong result that is benign in practice (e.g. a cosmetic field in an RPC response) — report it, say it is
  cosmetic.

### "It's not even a bug"

- Behaviour that is within protocol rules and simply has an economic cost (paying fees to spam, fee
  escalation, reserve requirements working as designed).
- An attack that needs the validator's secret key or admin access — an actor with those can already do worse.
- Parsing that ends in a proper error/exception describing why the input is invalid: that is the design.
- A dependency's own internal bug (see "out of scope" above).

## Things to leave alone

- Style, naming, `const`-correctness, unused includes, and other cleanups — the project runs clang-format,
  clang-tidy, and `pre-commit`.
- Deprecated or amendment-gated features that are not enabled on the network, except for memory safety.
- 32-bit-only issues (this image is x86-64); report from analysis only, without claiming 64-bit impact.
- Diagnostics inside third-party headers (boost, protobuf, OpenSSL, RocksDB) pulled in via Conan.

## How we would like reports and patches to look

- One finding per report, with the commit (`git -C /src rev-parse HEAD`) and the exact command, run inside
  `nix develop .#gcc-plain`. Prefer a reproducer that is one of: a standalone-mode command sequence, a small program against
  `libxrpl`, a standalone-mode (`-a`) transaction or RPC call, or a peer/protobuf message with the raw bytes.
  Include the sanitizer/gdb/assert output.
- State **who controls the input and through which entry point it arrives** (an overlay peer? a submitted
  transaction? a public vs admin RPC call? the WASM guest?), **what the attacker gains** (funds, a fork, a
  crash, a key), and which severity category above applies. A reachability argument is what distinguishes a
  real finding from "this function lacks a check".
- Patches: a minimal diff against `develop` in the surrounding style; prefer failing a transaction with the
  correct `TER` code or adding/strengthening an `InvariantCheck` over ad-hoc checks; keep public `libxrpl`
  signatures stable unless the fix requires otherwise; add a regression test under `src/test` (using the
  `jtx`/`Env` harness where it fits). Note where a fix changes consensus-visible behaviour — that normally
  needs to go behind an amendment, so flag it.
