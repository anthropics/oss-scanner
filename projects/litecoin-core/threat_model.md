# Litecoin Core threat model

Litecoin Core (`litecoin-project/litecoin`, branch `master`, the 0.21.5.x release line) is the reference full node and
wallet of the Litecoin network. It is a fork of Bitcoin Core 0.21 with three differences that matter here: scrypt proof
of work, 2.5-minute blocks, and MWEB (MimbleWimble Extension Blocks, LIP-0002/0003/0004), a confidential-amount
extension block carried alongside every block since its activation on mainnet in 2022. Litecoin's chain secures
billions of dollars, so supply and consensus bugs are the most serious possible findings.

In-tree references: `SECURITY.md`; `doc/mweb/*.md` (especially `doc/mweb/consensus.md`, the written specification of
the MWEB consensus rules); `doc/litecoin-release-notes/` (what each release fixed); `doc/developer-notes.md`. The
upstream Bitcoin Core threat model applies to the inherited code, with the changes below.

## What we protect, most important first

1. **Supply.** No coins may be created beyond the emission schedule, on the canonical chain or inside MWEB. MWEB
   amounts are hidden in Pedersen commitments, so nobody can find MWEB inflation by adding up balances. Only the
   kernel-sum check, the range proofs, the stealth-sum check, and the HogEx and peg accounting stand in the way. MWEB
   coins can be pegged out to ordinary outputs, so MWEB inflation is real LTC inflation. Two MWEB supply bugs were
   fixed in the last year (see "Already fixed").
2. **Consensus.** Every node running this release reaches the same verdict on every block, whatever path the block
   took (full block, compact block, `submitblock`, reloaded from disk during a reorg or crash recovery), whatever is
   in its caches, and however many times it has restarted. No double spends, no spending of MWEB outputs without
   their keys, no chain splits.
3. **Funds and keys.** With no attacker access to the local machine, the wallet does not lose funds or keys, pay
   more or elsewhere than the user approved, sign what the user did not approve, credit MWEB funds that do not exist
   or cannot be spent, or permanently miss MWEB funds it owns.
4. **Availability.** An unauthenticated peer cannot crash, stall or exhaust a node, keep it off the best chain, stop
   it relaying, or cheaply isolate it.
5. **Mining.** Untrusted relayed transactions cannot make `getblocktemplate` produce an invalid block (including an
   invalid MWEB block or HogEx), stall template creation, or cheaply strip the fees a miner would collect.
6. **Durable state.** Block files, undo data, the chainstate, and the MWEB state (output PMMR, leafset, prune list,
   MWEB coins) survive restarts, crashes and reorgs, and stay consistent with each other.
7. **MWEB privacy.** MWEB hides amounts and recipients (stealth addresses). A bug that reveals an MWEB output's amount
   or recipient to a third party, or links a wallet's MWEB outputs, beyond what the design already reveals, is in
   scope. Pegin and pegout amounts and scripts are public by design. Transactions seen before block aggregation can be
   linked by design. View keys shared with a light-client server reveal that wallet's outputs and amounts to the
   server (`doc/mweb/light-clients.md`). None of these is a finding.

## Who is trusted

| Source | Trust | Notes |
|---|---|---|
| P2P peers | Untrusted | Inbound and outbound. Inbound connections are cheap to open in bulk. State how many connections, and which direction, an attack needs. |
| Blocks and headers with valid proof of work | Untrusted, costly | State the mining cost. Any miner can shape a coinbase, a HogEx and the MWEB body of a block. Scrypt PoW checks run on headers, so low-difficulty header chains are cheap to make when they fork from early blocks; state the fork point. |
| Relayable fee-paying transactions, including MWEB transactions, pegins and pegouts | Untrusted, costly | State the fees. Anyone can put crafted but valid MWEB outputs, kernels and extra data on chain, and every wallet scans them. |
| HTTP before RPC authentication | Untrusted | RPC binds to localhost by default. REST is off by default and unauthenticated: through REST, only crashes, memory corruption and code execution are findings. Browser-mediated attacks (DNS rebinding, cross-site requests) are out of scope. |
| Authenticated RPC clients, including `-rpcwhitelist`-restricted ones | Trusted | A failure only they can trigger is a bug, not a vulnerability, unless it bypasses authentication. A block submitted through `submitblock` can usually also arrive over P2P, so test it there. |
| Transactions, PSBTs and addresses given to the wallet | Untrusted for funds safety, not liveness | The wallet must sign and report exactly what the user was shown. |
| The local machine: datadir, `litecoin.conf`, wallet files, MWEB flat files | Trusted | Anything needing local access or write access to these files is out of scope. A corrupt file counts only if a remote party or a crash can produce it. An injected failure counts only if an ordinary event, such as a full disk or a power cut, produces the same state. |
| Build system, `depends/`, CI, gitian and guix | Out of scope | |

### Defaults

Report against the default configuration. Off by default: REST, ZMQ, UPnP, `-txindex` and the other indexes,
`-peerbloomfilters`, `-peerblockfilters`, pruning, RPC beyond localhost. A finding that needs one of these is lower
severity; name the options.

On by default, with no option to turn it off: MWEB, and serving MWEB light-client data. `src/init.cpp` always
advertises `NODE_MWEB | NODE_MWEB_LIGHT_CLIENT`, so every node answers `getdata(MSG_MWEB_HEADER)`,
`getdata(MSG_MWEB_LEAFSET)` and `getmwebutxos` from any peer.

The wallet is compiled in. It is in scope whenever a wallet is loaded. MWEB keys exist only in legacy (BDB) wallets,
which are the default in this version (`LegacyScriptPubKeyMan::LoadMWEBKeychain`).

## Where untrusted input enters

### P2P (`src/net_processing.cpp`)

Everything inherited from Bitcoin Core 0.21, plus MWEB:

- **Transactions and blocks with MWEB data.** `tx`, `block`, `cmpctblock` and `blocktxn` deserialize MWEB bodies
  unless the stream has `SERIALIZE_NO_MWEB`. Serialization is in `src/primitives/transaction.h`,
  `src/primitives/block.h`, `src/mweb/mweb_models.h` and the libmw models in `src/libmw/include/mw/models/`.
  - Deserialization has no per-type count caps. Input, output, kernel, pegout and extra-data counts are only limited
    by the generic `serialize.h` limits, and the weight and count rules are checked later, at validation.
  - Peers negotiate MWEB through `NODE_MWEB` and compact-block version 3 (`fWantsCmpctMWEB`).
  - The HogEx is always prefilled in compact blocks (`src/blockencodings.cpp`).
- **Light-client service (LIP-0006).**
  - Handlers: `ProcessGetMWEBLeafset` and `ProcessGetMWEBUTXOs` in `src/net_processing.cpp`, plus the
    `MSG_MWEB_HEADER` branch of `ProcessGetBlockData` (replies with a `CMerkleBlockWithMWEB`).
  - What they do: the leafset handler calls `ActivateArbitraryChain` (`src/validation.cpp`), which disconnects and
    reconnects blocks into a temporary view under `cs_main`. `getmwebutxos` assembles PMMR segments
    (`src/libmw/src/mmr/Segment.cpp`).
  - Limits: depth ≤ 10 blocks, ≤ 4096 UTXOs per request, and a node-wide token bucket (`AllowMWEBServe`; peers with
    the `noban` permission are exempt).
  - These are some of the most expensive things an unauthenticated peer can ask for. Measure their cost within these
    limits.
- **Uncommitted MWEB payloads.** A transaction's txid and wtxid do not commit to its MWEB payload, and a block's hash
  does not commit to every byte of its MWEB body.
  - So two different bodies can share one hash. An invalid variant must be rejected as mutated (`BLOCK_MUTATED`),
    must never mark the hash invalid or leave stale data on disk or in caches, and must not stop the valid variant
    being processed or relayed.
  - Code that handles this: `HasUncommittedMWEBPayload`, the `recentRejects` and orphan handling, and
    `MaybePunishNodeForBlock`. Several recent fixes were in this area.

### The chain, as seen by consensus and by wallets

- **Miners.** A miner controls the coinbase, the HogEx (the final transaction of every MWEB block, which spends the
  previous HogEx output and the block's pegins and pays the pegouts), and the whole MWEB body.
- **Transaction senders.** A sender controls every field of MWEB inputs, outputs and kernels.
- **Wallets parse all of it.** Every wallet with MWEB keys runs `mw::Keychain::RewindOutput`
  (`src/libmw/src/wallet/Keychain.cpp`) on every MWEB output, from `src/mweb/mweb_wallet.cpp` and
  `CWallet::AddToWalletIfInvolvingMe`, `blockConnected` and `blockDisconnected` in `src/wallet/wallet.cpp`.
  - These run on the validation-interface scheduler thread, which rethrows. An exception that escapes there
    terminates the node.

### Other entry points

- **RPC and REST.** No RPC names are specific to MWEB, but `getblock`, `getrawtransaction`, `decoderawtransaction`,
  `sendrawtransaction`, `testmempoolaccept`, `submitblock` and `getblocktemplate` all handle MWEB data.
  `getblocktemplate` requires the `mweb` rule.
- **On-disk data.**
  - MWEB state is in the chainstate LevelDB (prefixes `U`, `M`, `O` in `src/libmw/src/db/`) and in memory-mapped
    flat files in the datadir: `O*.dat` (PMMR hashes), `leaf*.dat`, `prun*.dat`. The mmap code is
    `src/libmw/deps/mio`, `AppendOnlyFile`, `MemMap`.
  - Undo data carries `CBlockUndo::mwundo`.
  - Say who could produce a malformed file and how: a remote party, a crash, or a full disk.

## Components that matter most and least

Highest priority, Litecoin-specific code:

- **MWEB consensus.**
  - Node integration: `src/mweb/mweb_node.cpp` (`Node::CheckBlock`, `ContextualCheckBlock`, `ConnectBlock`,
    `CheckTransaction`). The calls into it from `src/validation.cpp`: `CheckBlock`, `ContextualCheckBlock`,
    `ConnectBlock`, `DisconnectBlock`, `ReplayBlock`/`RollforwardBlock`, `MemPoolAccept::PreChecks`.
  - Mempool-side input checks: `src/consensus/tx_verify.cpp`.
  - libmw validation:
    - `src/libmw/src/node/BlockValidator.cpp`, `CoinsViewCache.cpp` (`ApplyBlockChanges`, `UndoBlock`),
      `CoinsViewDB.cpp`
    - `src/libmw/src/models/` (`Block`, `TxBody`, `Transaction`, `Kernel`, `Input`, `Output`)
    - `src/libmw/include/mw/consensus/` (`KernelSumValidator`, `StealthSumValidator`, `Weight`, `Params`)
- **HogEx and pegs.**
  - Rules: the HogEx position and marker, the HogAddr commitment to the MWEB header hash, pegin outputs (witness
    version 9) matched to pegin kernels, pegouts matched as a multiset to HogEx outputs 1..n, and the HogEx amount and
    fee arithmetic in `Node::ConnectBlock`.
  - Pegout maturity: `PEGOUT_MATURITY` in `src/consensus/tx_verify.cpp`.
  - Miner side: `src/mweb/mweb_miner.cpp`, `src/miner.cpp`, `src/libmw/src/node/BlockBuilder.cpp`.
- **Cryptography as used by MWEB.**
  - Wrappers: `src/libmw/src/crypto/` (`Bulletproofs::BatchVerify`, `Schnorr::BatchVerify`, `Pedersen`,
    `PublicKeys`, `SecretKeys`, `ConversionUtil`).
  - The process-wide LRU verification caches in `Bulletproofs.cpp` and `Schnorr.cpp`: a cache hit must imply
    everything a fresh verification would have checked.
  - The `src/secp256k1-zkp` modules enabled in `configure.ac`: generator, commitment, bulletproof, aggsig,
    schnorrsig, extrakeys, recovery.
  - BLAKE3 hashing (`src/crypto/blake3`, `src/libmw/src/crypto/Hasher.cpp`).
- **MWEB P2P.** The light-client handlers above, compact-block MWEB handling, and mutated-block handling.
- **MWEB storage.** `src/libmw/src/mmr/` (PMMR, `LeafSet`, `PruneList`, `PMMRCache`, `Segment`), the file code, and
  rewind on reorg. A crash or reorg that leaves the PMMR, leafset and chainstate inconsistent can split a node from
  the network.
- **MWEB wallet.** `src/libmw/src/wallet/` (`Keychain`, `TxBuilder`), `src/mweb/mweb_wallet.cpp`,
  `src/mweb/mweb_transact.cpp`, and the MWEB parts of `src/wallet/` (`txassembler.cpp`, `wallet.cpp`, `rpcwallet.cpp`,
  `scriptpubkeyman.cpp`).
- **Mempool and policy for MWEB.** `src/mweb/mweb_policy.cpp`, and the MWEB conflict, kernel and spent-output
  tracking in `src/txmempool.cpp` (`addUnchecked`, `removeUnchecked`, `removeForBlock`).

Also high priority: the inherited Bitcoin Core consensus, P2P and wallet code, to the extent Litecoin changed it, such
as scrypt proof of work (`src/crypto/scrypt.cpp`, `CBlockHeader::GetPoWHash`), the difficulty retarget in
`src/pow.cpp`, and `src/chainparams.cpp`.

Lower priority but in scope: `litecoin-cli`, `litecoin-tx`, `litecoin-wallet`; `src/qt`; bundled subtrees
(`src/leveldb`, `src/crc32c`, `src/univalue`, `src/libmw/deps`) when Litecoin Core reaches the bug with attacker
input. Name the subtree.

## Easy to get wrong in this codebase

- **Every path must check the same thing.** The MWEB body is validated in `ContextualCheckBlock` and again in
  `ConnectBlock`. A rule must hold whichever path a block takes: P2P full block, compact block reconstruction,
  `submitblock`, `ReplayBlock`/`RollforwardBlock`, or a body re-read from disk during a reorg. Version 0.21.5.7 fixed
  a body reloaded from disk skipping validation. A check that runs in one path but not another is a finding.
- **Policy is not consensus.**
  - `MWEB::Policy::CheckWeight` (at most 1,000 inputs and weight 4,000 per transaction) and `IsStandardTx` apply to
    relay only. Consensus allows up to 50,000 inputs and weight 200,000 per block. `MAX_MINE_WEIGHT` is a mining
    limit, not a consensus rule.
  - Applying a relay rule to blocks is a hard fork.
  - The mempool feeds `getblocktemplate`, so a transaction the mempool keeps but consensus rejects makes default
    miners build invalid blocks.
- **Deliberate exceptions.** These are not findings in themselves. Report them only if they can be used for more than
  their stated purpose:
  - frozen MWEB outputs (`consensus.frozen_mweb_output_ids`)
  - one grandfathered block (`mweb_input_metadata_grandfather_blockhash`)
  - kernel lock heights enforced only above `KERNEL_LOCK_HEIGHT_GRANDFATHER_HEIGHT`
  - rules that start at `mweb_pegout_feature_activation_height` (mainnet 3,154,440) and
    `mweb_extradata_feature_activation_height` (mainnet 3,172,640)

  Check that each gated rule applies exactly from its height, and that regtest and testnet, where the feature heights
  are 0, behave the same as mainnet above the height.
- **Arithmetic.** Amounts, fees, pegins, pegouts and supply changes are `CAmount` sums across a block. Version
  0.21.5.4 fixed a kernel fee overflow. Look for overflow and sign errors anywhere sums are taken, including
  `AmountUtil`, `TxBody::GetSupplyChange`, the HogEx amount check and `CFeeRate` with `BASE_MWEB_FEE`.
- **Point and scalar validity.**
  - Commitments, public keys (`Ke`, `Ko`, `Ks`, `Ki`, stealth excess) and signatures must be valid encodings. Values
    derived by hashing must be valid scalars (0.21.5.5 added fallbacks for hash-to-secret-key edge cases).
  - Relay policy has required valid `Ke` and `Ko` since 0.21.5.6.
- **Exceptions.**
  - libmw signals errors by throwing subclasses of `LTCException` (`ValidationException`, `CryptoException`,
    `DeserializationException`, ...) and `std::ios_base::failure`.
  - `ProcessMessage` is wrapped in a catch-all that only logs. A throw part-way through a state change can still leave
    the chainstate, the mempool, a cache or a file half-updated.
  - Threads started with `TraceThread` and the scheduler rethrow, so an exception outside `ProcessMessage` terminates
    the node.
- **Assertions.** `NDEBUG` builds are refused (`src/compat/assumptions.h`), so every `assert` is live. An assert a peer
  can reach is a remote crash.
  - There are many in libmw on validation and P2P paths: `CoinsViewCache.cpp`, `MemMMR.cpp`, `MMRUtil.cpp`,
    `PMMRCache.cpp`, `LeafSet.cpp`, `Segment.cpp`, `BigInteger.h`, `MemMap.h`, `Keychain.cpp`.
  - So does the MWEB accounting in `src/txmempool.cpp` and `src/policy/feerate.cpp`.
- **Concurrency.** Name the two call sites that run at once, or the lock that is missing, before calling something a
  race. Most MWEB state is under `cs_main`; the verification caches and the light-client token bucket are
  process-wide.

## Already fixed: check for duplicates and variants

Recent releases fixed these classes of bug (see `doc/litecoin-release-notes/release-notes-0.21.5.*.md` and
`git log`):

- **0.21.5.4–0.21.5.5:**
  - an MWEB input-validation issue that let the kernel sum become unbalanced
  - kernel fee overflow
  - duplicate pegins
  - HogEx amount and fee mismatches not treated as consensus failures (they now are)
  - kernel lock heights
  - mutated blocks leaving block data or chainstate behind
  - PMMR rewind corruption and MMR write durability
  - a cache leaf bounds check
- **0.21.5.6:**
  - light-client request exhaustion (now a node-wide limit)
  - oversized MWEB transactions in the mempool
  - invalid `Ke`/`Ko`
  - mutated MWEB compact blocks
  - empty pegout lists
- **0.21.5.7:**
  - disk-reloaded MWEB bodies skipping validation
  - empty extra data
  - pegout flag missing from undo data
  - script-check data lifetime
- **0.21.5.8:**
  - same-hash block variants
  - fast relay before connect
  - MWEB `recentRejects` censorship
  - incremental validation of staged mining aggregates
  - mempool conflicts with connected blocks
  - range-proof scratch space not released on invalid proofs
  - leaked file descriptors

A finding that is the same root cause as one of these is a duplicate unless the fix is incomplete. A variant that
gets around a fix is a finding; say which fix it gets around.

## Upstream Bitcoin Core issues

This release line is based on Bitcoin Core 0.21. Some later upstream fixes were backported (for example, the address
relay rate limit); others were not (for example, the headers pre-synchronisation added in Bitcoin Core 24.0). A
rebase onto Bitcoin Core 24 is in testing on the `24.x` branch.

A bug in inherited code that a publicly disclosed Bitcoin Core advisory describes is still in scope when this release
is affected. Rate it by its effect on Litecoin. Name the advisory or CVE and the upstream commit that fixed it, and
confirm it was not backported. Send one report per advisory. Spend most of the effort on Litecoin-specific code,
because upstream review already covers the inherited code.

## What counts as a vulnerability

- **Release-build semantics.** `assert` always aborts, so a reachable one is a crash. Report the release-build
  consequence of anything else.
- **Regtest consistency checks.** Regtest enables `-checkmempool` and `-checkblockindex` by default; mainnet does not.
  - A check that untrusted input can make fail is a finding. Report the inconsistency, and what the bad state breaks
    if you can find it, but not the check's own abort as a crash.
  - Take CPU and memory measurements with both options set to 0.
- **Sanitizer reports.** A remotely reachable AddressSanitizer report is in scope on its own. An
  UndefinedBehaviorSanitizer report needs a demonstrated consequence.
- **Reachability.**
  - Defects in libraries, utilities and subtrees count only when `litecoind` or the wallet reaches them with attacker
    input: P2P, HTTP, RPC, REST, chain data, or a file Litecoin Core writes itself.
  - Input beyond the protocol limits (32 MB P2P messages) is not a report. Neither is allocation failure, which
    terminates by design.
- **Resource exhaustion.** Cost proportional to input, and bounded per-peer state freed on disconnect, are expected.
  Amplification alone is not a finding. In scope:
  - one P2P message or pre-authentication HTTP request taking about a second or more of CPU in the optimised build
    (messages are handled on one thread)
  - one message leading to more than 1 GiB of additional memory use
  - memory that grows without bound over a connection's lifetime or across reconnects
  - per-peer-bounded memory totalling 4 GiB or more across the default 125 connections
  - sustained disk I/O far beyond what serving the same requests normally costs
  - for the light-client messages: what an attacker can make a node do within the node-wide token bucket

  Measure, mark each figure as measured or extrapolated, and give the number of connections needed.
- **Not implementation vulnerabilities:**
  - protocol-level properties shared with Bitcoin (pinning, replacement cycling, selfish mining)
  - known consensus quirks inherited unchanged from Bitcoin, such as the 64-byte transaction Merkle ambiguity and
    duplicate coinbases. Litecoin's difficulty retarget is its own (`src/pow.cpp` goes back the full period), so
    findings there are in scope.
  - MimbleWimble properties described as by design above
  - anything needing more than 50% of the hash rate
- **Bugs, not vulnerabilities:**
  - `litecoin-cli` behaviour and GUI crashes
  - control characters reaching the operator's terminal through logs or RPC output
  - logs or responses only the operator sees
  - wallet transactions that fail safe (the mempool rejects them or the RPC returns an error)
  - fee estimation accuracy, unless an attacker can cheaply and significantly skew the estimates
  - relay gaps that heal when another peer supplies the transaction
  - intended behaviour, often asserted by a test

## Severity

- **Critical:** network-wide.
  - Inflation of the canonical or MWEB supply.
  - Spending MWEB or canonical outputs without their keys, or double spends.
  - A block or transaction that makes nodes running this release disagree, permanently.
  - A crash that relay delivers to every default node.
  - Remote code execution.
- **High:** remote, in the default configuration.
  - A crash or long stall caused by a peer, or memory corruption.
  - Untrusted transactions making default miners build invalid blocks.
  - The wallet leaking keys or signing what the user did not approve.
  - A sender making a wallet credit MWEB funds that do not exist or cannot be spent, or permanently miss funds it
    owns.
  - Remote input corrupting the MWEB state so that a node needs to resync.
  - A privacy leak written into every MWEB transaction the reference wallet builds.
- **Medium:** limited scope or exploitability, or non-default settings.
  - Resource exhaustion as above.
  - Failures in non-default features.
  - A crash needing local network access.
  - An MWEB privacy leak affecting a specific wallet or configuration.
- **Low:** hard to exploit or minor impact, such as needing a privileged position or non-default configuration.

Give a severity and the reason; do not inflate it. Focus on Medium and above, and send Low only with a working
reproducer. Do not send non-security bugs.

## Evidence required

- **A reproducer against the unmodified build in this image.** Use default limits and timers and no test-only hooks.
  - Preferred: a regtest functional test, with a passing control run.
  - Use a unit test only when a functional test cannot reach the code, and say why.
- **When a reproducer isn't practical.** Some consensus and cryptography findings, such as a soundness gap in a proof
  or a check missing on one validation path, cannot reasonably be shown end to end. Report those with the exact code
  path, concrete values, and why the property fails, and say clearly that it was not reproduced.
- **Which build.** Whether it reproduces in `/src/build`, not only under sanitizers.
- **What the attacker needs:** connection direction and count, proof of work, fees, MWEB activation, options, timing.
- **Version history.** The scanned revision, and if you can, when the bug was introduced and whether the code is the
  same on the `24.x` branch (`git -C /src show origin/24.x:<path>`, if that ref is present).
- **One root cause per report**, after checking the history, the release notes and the tests for an earlier fix or a
  test asserting the behaviour as intended.

## Scope

Everything shipped in release binaries is in scope. Prioritise code that unauthenticated peers and on-chain data
reach.

Only Linux x86-64 is built here. Other platforms and 32-bit builds are low priority and need a concrete argument that
a supported release reaches the code.

Out of scope:
- `test/`, `src/test/`, `src/libmw/test/`, `src/bench/`, `contrib/`, `ci/`, `depends/`, `share/`, `build_msvc/`, except
  code shipped in release binaries
- the project's websites, DNS seeds and other live infrastructure
- other repositories (the LIPs, light wallets, Electrum-LTC)
- the `24.x` branch itself, which is not built here; you may still mention it in a report as described above

## Build and how to exercise it

`/src` is the checkout, with git history. Both builds are out of tree and share the configured sources: no GUI, no
benchmarks, wallet with BDB 5.3 (`--with-incompatible-bdb`) and SQLite, ZMQ and UPnP compiled in.

After a patch, `make -j2` in a build directory rebuilds it (ccache keeps the objects). If you need to reconfigure,
reuse the original command line from the top of that directory's `config.log`. It includes
`CPPFLAGS=-iquote <builddir>/src/secp256k1-zkp/src`, because the tree tracks a stale
`src/secp256k1-zkp/libsecp256k1-config.h` that an out-of-tree build would otherwise pick up. A new out-of-tree build
directory needs the same flag. The stale file is a known build issue, not a finding.

- **`/src/build`**: like a release, GCC, `-O2 -g -fno-omit-frame-pointer`. Its behaviour is what counts.
  - Binaries: `/src/build/src/litecoind`, `litecoin-cli`, `litecoin-tx`, `litecoin-wallet`.
  - Unit tests: `/src/build/src/test/test_litecoin` (includes the libmw tests). Run one suite with
    `-t <suite> --catch_system_errors=no`.
- **`/src/build_asan`**: clang 18 with `--with-sanitizers=address,undefined`, `-O1 -g`.
  - The image sets `ASAN_OPTIONS`, `LSAN_OPTIONS` and `UBSAN_OPTIONS`, so run reproducers through
    `/src/build_asan/test/functional/test_runner.py` to get an instrumented node.
  - `UBSAN_OPTIONS` points at `/etc/litecoin-ubsan.supp`: the in-tree `test/sanitizer_suppressions/ubsan` plus two
    lines.
    - mio's `basic_mmap` leaves `is_handle_internal_` uninitialised, and `MemMap`'s move assignment loads it on every
      MWEB leafset flush (`LeafSet::Flush`). This is a known defect. Report it only if you can show a consequence
      beyond the undefined behaviour itself.
    - crc32c's arm64 code does misaligned loads. This only applies to arm64 builds.
- **Functional tests:** `python3 /src/build/test/functional/test_runner.py <test>.py`, or run a test script directly.
  - Do not pass `--ci`: it fails on this branch because `test/functional/litecoin_scrypt.py` is not listed as a
    non-test script.
  - Tests that need previous releases (`mweb_node_compatibility.py`, `mweb_wallet_upgrade.py`, ...) skip, because
    those binaries are not available offline.
  - At build time the unit tests and ten functional tests ran against `/src/build`, and two functional tests ran
    against `/src/build_asan` (with leak detection off, because `docker build` has no ptrace). Results are in the
    build log, and failures did not stop the build.
- **Regtest and MWEB.**
  - Regtest activates MWEB at height 432. `setup_mweb_chain(node)` in `test/functional/test_framework/ltc_util.py`
    mines there and pegs in.
  - `ltc_util.py` also has HogEx and MWEB-header helpers.
  - `test_framework/messages.py` has Python classes for MWEB transactions, blocks and the light-client messages
    (`MWEBTransaction`, `MWEBBlock`, `msg_getmwebutxos`, `msg_mwebheader`, ...), for crafting P2P input.
  - The `mweb_p2p*.py`, `mweb_duplicate_pegin.py` and `mweb_pre_activation_hogex_marker.py` tests show how to send
    crafted MWEB data.
- **Fuzzing.** No fuzz binary is built, and the fuzz build (`--enable-fuzz`) is not maintained on this branch: it may
  need small fixes to `src/Makefile.test.include` before it links. No fuzz target exercises libmw directly.
- **Ground rules.** Use disposable regtest nodes only. Never connect to mainnet or testnet or use real funds. Cap
  compilation and test parallelism at two jobs. Prefer a small deterministic counterexample to exhausting the VM.

```sh
/src/build/src/test/test_litecoin --catch_system_errors=no -t <suite>
python3 /src/build/test/functional/test_runner.py -j2 mweb_basic.py mweb_p2p.py
python3 /src/build_asan/test/functional/test_runner.py -j2 mweb_p2p.py
```
