# RSKj threat model (for automated security scanning)

## What the system is

RSKj is the reference full node for Rootstock (RSK), an EVM-compatible chain that is merge-mined with Bitcoin and has a two-way peg to BTC. Nodes run on the public internet and process data from untrusted peers. These properties shape the security analysis:

1. **Merged mining.** An RSK block's proof of work is a Bitcoin header, a coinbase transaction that commits to the RSK block hash, and a Merkle branch. The Bitcoin block itself does **not** need to be valid on Bitcoin. The miner controls every field in it, so the merged-mining proof is attacker-controlled input that every node parses.
2. **The Bridge precompile (`0x0000000000000000000000000000000001000006`, `co.rsk.peg`).** The Bridge holds the RBTC reserve allocated at genesis. It keeps an SPV view of Bitcoin, credits RBTC when a BTC deposit to the federation (a "peg-in") is proven, and builds BTC withdrawal transactions (peg-outs) from federation UTXOs. Federators sign those transactions with PowHSM devices, which sign only after about 4,000 RSK confirmations of cumulative proof of work, and the Bridge re-checks every signature. The HSMs and the Bridge's re-validation protect signing integrity. The federation changes over time: after a new federation activates, the Bridge moves funds from the retiring federation to the new one, then stops tracking the retiring federation.
3. **REMASC (`0x…01000008`, `co.rsk.remasc`).** A precompile that runs as the forced last transaction of each block and pays out block rewards after 4,000 blocks.
4. **Ethereum-derived execution with RSK-specific consensus rules.** These include the Unitrie state, RSK-specific precompiles (`co.rsk.pcc`: HD-wallet utils, BlockHeader, Environment, secp256k1 helpers), header versions and per-network activation heights (`ActivationConfig`, `ConsensusRule`, `rskj-core/src/main/resources/config/*.conf`).

**Components outside this repo.** A consensus-valid object that RSKj accepts or emits and that powpeg-node, bitcoinj or rsk-powhsm cannot parse or bound is a peg-liveness bug and is **in scope**.
- [`powpeg-node`](https://github.com/rsksmart/powpeg-node): the federator, which embeds RSKj. Consumes RSK block headers, transaction receipts and logs, receipt-trie proofs, and serialized BTC transactions.
- [`bitcoinj`](https://github.com/rsksmart/bitcoinj) (`org.bitcoinj:core`, RSK fork): powpeg-node's Bitcoin network library. Parses and broadcasts the BTC transactions the Bridge builds.
- [`rsk-powhsm`](https://github.com/rsksmart/rsk-powhsm): C firmware on the federators' HSMs. Consumes the same data, passed in by powpeg-node.
- [`bitcoinj-thin`](https://github.com/rsksmart/bitcoinj-thin) (`co.rsk.bitcoinj:bitcoinj-thin`, dependency JAR): BTC parsing, SPV checks and coin selection inside the Bridge. Its behavior reached through Bridge code is in scope.
- [`native`](https://github.com/rsksmart/native) (`co.rsk:native`, dependency JAR): native secp256k1 and altBN128 libraries that RSKj loads over JNI instead of the Java implementations. Differences between native and Java results are in scope.

## Scope

**In scope (by priority):**

| # | Area | Main packages / classes |
|---|---|---|
| 1 | Bridge and two-way peg: peg-in registration (including Flyover), BTC header store and SPV proofs, peg-out lifecycle (`releaseBtc` → `updateCollections` → `addSignature`), federation lifecycle (proposal/SVP, activation, migration, retirement), governance votes | `co.rsk.peg.*` |
| 2 | Consensus: block and tx validation and execution (identical results across OSes, CPU architectures and crypto backends), VM, precompiles, gas (including work or memory that outgrows the gas charged), difficulty, merged-mining proof validation, uncles, fork choice, REMASC, activation gating | `co.rsk.core`, `co.rsk.core.bc`, `org.ethereum.core`, `org.ethereum.vm`, `org.ethereum.cost`, `org.ethereum.solidity`, `co.rsk.pcc`, `co.rsk.validators`, `org.ethereum.validator`, `co.rsk.remasc`, `org.ethereum.config`, `co.rsk.config`, `co.rsk.RskContext` |
| 3 | Cryptography and transaction identity: signatures, sender recovery and caches, chain ID, hashing, native vs. Java backends | `org.ethereum.crypto`, `co.rsk.crypto`, `org.ethereum.core.*SignatureCache`, `co.rsk.pcc.altBN128`, [`co.rsk:native`](https://github.com/rsksmart/native) |
| 4 | State and encoding: Unitrie, repository and state roots, RLP, block/header/receipt encoding | `co.rsk.trie`, `co.rsk.db` (`MutableTrie*`, `StateRootHandler`), `org.ethereum.db.MutableRepository`, `org.ethereum.util.RLP` |
| 5 | Peer input before validation, and sync: discovery, RLPx handshake and framing, message decoding and queueing, block and transaction relay, sync, peer scoring | `co.rsk.net.*`, `org.ethereum.net.*`, `org.ethereum.sync`, `co.rsk.scoring` |
| 6 | Objects that cross into the components outside this repo (powpeg-node, bitcoinj, rsk-powhsm) | headers, receipts/logs, `BridgeEvents`, trie proofs, BTC tx serialization |
| 7 | Transaction pool and mining template; merged-mining submission (`mnr_*`) | `co.rsk.core.bc.TransactionPoolImpl`, `co.rsk.net.handler`, `co.rsk.mine` |
| 8 | JSON-RPC under **default** configuration; persistence, crash consistency, bootstrap import | `co.rsk.rpc`, `org.ethereum.rpc`, `co.rsk.jsonrpc`, `co.rsk.logfilter`, `org.ethereum.db` stores, `org.ethereum.datasource`, `co.rsk.db.importer` |

The package lists are starting points, not limits; follow the code wherever it leads.

**Out of scope:** do not report these, or report them as informational only when noted.

- Attacks that need ≥ 50 % of RSK merged-mining hashpower, majority Bitcoin hashpower, or a governance-key quorum. Reorgs, censorship, selfish mining, and timestamp or tie-break choices within the rules are expected miner powers. Report only a code defect that lets **fewer** resources achieve them, or that lets fewer keys than the configured threshold act.
- Compromise of the operator: local files, config, database directory, keystore, JVM flags or environment. Compromise of HSM devices, firmware or federator hosts. Malicious release or dependency artifacts.
- RPC modules that are disabled by default (`debug`, `trace`, `mnr`, the wallet), and any RPC module exposed beyond localhost by the operator. An **unsafe default** (something dangerous that is enabled or reachable out of the box) is reportable, rated by the default exposure.
- Plain volumetric flooding (bandwidth, connections, RPC requests) with no amplification, and rate limiting on public RPC endpoints.
- Test, fuzz and integration-test code (`src/test`, `src/fuzzTest`, `src/integrationTest`), docs, scripts, regtest-only behavior, and operator CLI tools (`co.rsk.cli`).
- Dependency CVEs with no reachable path from RSKj code.
- Behavior on Java versions other than 17, the only supported runtime.
- Losing **your own** funds through an action the specification says is unsupported. Losing funds through a **supported** peg-in or peg-out format (per the RSKIPs in force) is in scope.
- Breaks of the underlying cryptographic primitives. Gas-price or fee-market opinions, MEV and ordinary front-running, unless they cause one of the impacts under Severity.
- Legacy behavior that applies only below the current mainnet height and is kept for historical replay.

## How to exercise it

- JUnit 5 tests in `rskj-core/src/test`. Helpers: `co.rsk.test.World` with DSL scripts in `src/test/resources/dsl`, `BlockGenerator`, `BlockChainBuilder`, `BridgeSupportBuilder`, `RskTestContext`. Run one class with `./gradlew :rskj-core:test --tests <Class>`.
- Local node: `java -Dpublic.ip=127.0.0.1 -cp rskj-core/build/libs/rskj-core-*-all.jar co.rsk.Start --regtest` runs a single-node network offline, useful for RPC and P2P paths. Keep `-Dpublic.ip`: without it the node asks `checkip.amazonaws.com` for its address, which with no network stalls on DNS and logs an ERROR before falling back to `127.0.0.1` — an artifact of the sandbox, not a finding. Regtest activates upgrades that are not active on mainnet and enables the wallet, so check findings against the mainnet config.
- The image is built and its Gradle cache is warm; Gradle is already offline by default, so no command needs `--offline`. `/src/.oss-scanner/AGENT-NOTES.md` has the build, node and resource notes for this image.

## Attackers and trust

**Untrusted: assume they are hostile.**
- **Users** can send any RSK transaction (any calldata or value, to any address including precompiles), deploy contracts, perform peg-ins (send any BTC transaction to the federation and register it with the Bridge) and peg-outs, and call default RPC methods on public nodes.
- **Peers** can run many node identities and send any network message, including false status or difficulty claims.
- **Minority miners (RSK or Bitcoin)** can produce valid-PoW blocks with any contents the rules allow, and grind block hashes.

**Partly trusted: can delay, not steal.**
- **Federators, even a majority,** can call the federator-only Bridge methods or stop participating. Their HSMs sign only peg-outs that a Bridge command, backed by enough cumulative RSK proof of work, authorizes.
- **Governance key holders below the voting threshold** can cast their votes in their module.

**Fully trusted:** the node operator, local config and disk. Majorities of hashpower or governance keys are out of scope (see Scope), but a defect that lets a governance majority skip the federation-change safeguards (SVP, activation delay) is in scope.

**Before rating**
- **Mainnet activation:** check `config/main.conf` and `reference.conf`. A height of `-1` means not active on mainnet. Code in no release tag is unreleased.
- **Defaults:** check `reference.conf` and the network configs. Features that are off by default are opt-in.
- **Gas:** the mainnet block gas limit is 10M (voted by miners), not the code default.
- **Ethereum differences:** where an [RSKIP](https://github.com/rsksmart/RSKIPs) documents a difference from Ethereum, it's by design.

## Severity

Rate **Impact × Likelihood**: take the impact tier from the outcome, then adjust it for likelihood. Maintainers set the final severity.

**Impact**
- **Critical:** theft or permanent loss of USD 100,000 or more, counting repeats within a few hours. Smaller amounts rate lower in proportion, down to Info for trivial amounts. Network-wide crash or halt spread by relayed blocks or transactions.
- **High:** permanent freeze of funds; protocol-wide halt of peg-in, peg-out or migration that needs a hard fork to recover; consensus split among honest, up-to-date mainnet nodes.
- **Medium:** temporary freeze of funds or halt of the peg; remote crash, wedge or eclipse of targeted nodes, including miners and federators; a VM bug that bypasses a contract's protections, such as access control.
- **Low:** only the attacker's own funds; node-local degradation that heals itself; DoS of an RPC node.
- **Info:** hygiene or defense in depth; a VM deviation with no security impact.

State the inputs to the rating: for theft or loss, the maximum amount at risk in BTC or RBTC and how fast the attack repeats; for DoS, whether the effect spreads through relayed data or hits only targeted nodes.

**Recovery.** For frozen or stalled funds, use the cheapest recovery path that works, and state it:
- **On its own, through a routine call** by any user or one federator (for example, re-registering a peg-in), **or through a governance vote:** temporary.
- **A hard fork:** permanent.
- **Only the emergency (ERP) keys after their timelock:** permanent, at the severe end of High, close to a loss.

**Likelihood.** The impact tier assumes an unprivileged attacker, default configuration and code live on mainnet. Lower it if the attack needs a privileged actor (federators, or governance key holders below the voting threshold), significant unrecovered capital or hashpower, an opt-in non-default configuration, code not active on mainnet (activation `-1`) or not yet in a release, or an expensive hash grind. With no reachable trigger, rate Info.

**Delaying block production.** Rate a sustained delay of block production, for example blocks that are expensive to process, from Info up to High, depending on how much each block is delayed and for how long the attacker can keep it up. It counts only if processing a 10M-gas block, on a machine meeting the minimum requirements (8 GB RAM), takes more than 30 seconds (the average block time) or runs out of memory. Below both, rate Info. Report the measured time and peak memory, the attacker's cost per block in RBTC, and whether the cost recurs every block or the effect persists (for example, through state growth).

## Reports and fixes

- State the networks and releases where the code path is live, with the activation height.
- Separate what was executed (preferably a JUnit test) from what was reasoned from source, and say what couldn't be exercised.
- Group manifestations of the same root cause in one report.
- Prefer a small fix with a regression test; avoid unrelated refactoring and silently suppressing errors.
- Gate every fix that changes consensus (block or transaction validity, execution results, gas, state, or Bridge and REMASC behavior); otherwise nodes running it fork from the network. Add a `ConsensusRule` (a placeholder RSKIP number is fine) and map it in `reference.conf` (`blockchain.config.consensusRules`) to the newest upgrade in `NetworkUpgrade` whose mainnet height in `config/main.conf` is `-1`. Keep pre-activation behavior identical, and test both sides of the activation.
