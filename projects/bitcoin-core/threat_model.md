# Bitcoin Core threat model

Bitcoin Core is a full node: it validates blocks and transactions, relays them over an unauthenticated P2P network, and serves a wallet and JSON-RPC. In-tree references: `/src/SECURITY.md`, `doc/JSON-RPC-interface.md`, `doc/developer-notes.md`.

## Security model

What matters most: attacks an unauthenticated peer can run automatically, and wallet fund loss in normal operation.

### What we protect

1. Consensus: no inflation, no theft through validation, no chain split. A block must validate the same way on every node and every time, whatever the version, configuration, platform, cache state (signature, script execution, coins) or history of restarts and reorgs.
2. Funds: with no attacker access to the local machine, the wallet does not lose funds or keys, pay more or elsewhere than the user approved, sign what the user did not approve, or reveal key material.
3. Availability: an unauthenticated peer cannot crash, stall or exhaust a node, keep it off the best chain, stop it relaying or serving peers, or cheaply isolate it from honest peers, directly or indirectly (for example through address relay or eviction).
4. Mining: untrusted input cannot make the node's block templates invalid, stall their creation, or cheaply strip the fees they would collect.
5. Durable state: block, undo, chainstate, index and wallet data survive restarts, crashes and reorgs.
6. Anonymity options: with a proxy or `-onlynet`, no connection leaves the configured networks; with `-privatebroadcast`, the node is not revealed as the origin of those transactions. There is no other privacy guarantee: linking identities across networks, inferring transaction origin and fingerprinting are not vulnerabilities.

### Who is trusted

| Source | Trust | Notes |
|---|---|---|
| P2P peers | Untrusted | Inbound and outbound. Inbound connections are cheap to open in bulk. Outbound peers are chosen by the node, hard to obtain and relied on more: state how many outbound slots an attack needs, and treat a cheap way to obtain them as a finding. |
| Blocks and headers with valid proof of work | Untrusted, costly | State the mining cost. Header chains below the minimum chain work go through headers presync; such chains are cheap to build when they fork from early blocks, so state the fork point and the work it needs. |
| Relayable fee-paying transactions | Untrusted, costly | State the fees, including replacements. |
| HTTP before RPC authentication | Untrusted | RPC binds to localhost by default. REST is off by default, unauthenticated and not hardened against resource exhaustion: through REST, only crashes, memory corruption and code execution are findings. Browser-mediated attacks (DNS rebinding, cross-site requests) are out of scope. |
| Authenticated RPC clients, including `-rpcwhitelist`-restricted ones; IPC clients | Trusted | A failure only they can trigger, including resource exhaustion and aborts, is a bug, not a vulnerability, unless it bypasses authentication. |
| PSBTs, transactions and descriptors given to the wallet | Untrusted for funds safety, not liveness | The wallet must sign and report exactly what the user was shown. Crashes, errors and resource use from this content are bugs, unless they involve memory corruption. |
| The local machine: datadir, `bitcoin.conf`, wallet files, external signer | Trusted | Anything needing local access or write access to these files is out of scope (crafted wallets, snapshots, mempool dumps, permissions, links). A corrupt file counts only if a remote party or a crash can produce it; an injected failure only if an ordinary event like a full disk produces the same state. |
| Build system, `depends/`, CI, Guix | Out of scope | |

### Defaults

Report against the default configuration. Off by default: REST, ZMQ, IPC, `-txindex` and the other indexes, `-peerblockfilters`, `-privatebroadcast`, pruning, assumeutxo, RPC beyond localhost. A finding that needs one of these is lower severity; name the options. BIP37 bloom filter serving (`-peerbloomfilters`) is out of scope.

## What counts as a vulnerability

- Release-build semantics. `NDEBUG` builds are refused, so `assert` and `Assert()` always abort: a reachable one is a remote crash. In release builds `Assume()` does nothing and `CHECK_NONFATAL()` throws (an RPC error); report only their release-build consequence.
- Regtest enables `-checkmempool` and `-checkblockindex`; mainnet does not. A check that untrusted input can make fail is a finding: report the inconsistency, and what the bad state breaks if you can find it, but not the check's own abort as a crash. Take CPU and memory measurements with both set to 0.
- A remotely reachable AddressSanitizer report is in scope on its own. An UndefinedBehaviorSanitizer report needs a demonstrated consequence.
- Reachability. Defects in libraries, utilities, subtrees or the `bitcoinkernel` API count only when `bitcoind` or the wallet reaches them with attacker input, through P2P, HTTP, RPC, REST or a file Bitcoin Core writes itself. Input beyond the protocol limits (4 MB P2P messages, 32 MiB HTTP bodies) and allocation failure (which terminates by design) are not reports.
- Resource exhaustion. Cost proportional to input, and bounded per-peer state freed on disconnect, are expected; amplification alone is not a finding. In scope:
  - one P2P message or pre-authentication HTTP request taking about a second or more of CPU in an optimised build without sanitizers (messages are handled on one thread); cold-disk wall time alone does not count;
  - one message leading to more than 1 GiB of additional memory use;
  - memory that grows without bound over a connection's lifetime or across reconnects (slow growth is lower severity);
  - per-peer-bounded memory totalling 4 GiB or more across 200 simultaneous connections; measure one peer, then extrapolate only as far as global limits allow (the orphanage, mempool and other shared structures cap the total regardless of peer count);
  - sustained disk I/O far beyond what serving the same requests normally costs (forced flushes, compaction storms, write amplification); measure bytes read and written in `/proc/<pid>/io`;
  - bandwidth amplification, only when extreme.

  Retained memory outranks transient allocation. Measure, mark each figure as measured or extrapolated, and give the number of connections needed. The thresholds are orders of magnitude, so this VM is accurate enough.
- Log flooding needs a way around `-logratelimit`, which is on by default.
- Not implementation vulnerabilities: protocol-level properties (pinning, replacement cycling, selfish mining) unless Bitcoin Core deviates from its documented behaviour; the known issues BIP54 addresses (timewarp, slow-to-validate blocks, 64-byte transaction Merkle ambiguity, duplicate coinbases); known test network issues such as testnet block storms.
- Bugs, not vulnerabilities: `bitcoin-cli` behaviour; GUI crashes; control characters from peer data reaching the operator's terminal through logs or RPC output; logs or responses only the operator sees; backlogs behind `-walletnotify` or `-blocknotify`; wallet transactions that fail safe (the mempool rejects them or the RPC errors); fee estimation accuracy, unless an attacker can cheaply and significantly skew the estimates; relay or orphan gaps that heal when another peer or a later announcement supplies the transaction (one peer persistently blocking propagation is in scope); stale cache entries cleared on a tip change; intended behaviour, often asserted by a test.

## Severity

Bitcoin Core's categories:

- Critical: network-wide: inflation, theft through consensus, a permanent chain split, remote code execution.
- High: remote, in the default configuration: a crash or long stall, memory corruption, code execution needing local network access, the wallet leaking keys or signing what the user did not approve.
- Medium: limited scope or exploitability, or non-default settings: resource exhaustion as above, failures in non-default features, a crash needing local network access.
- Low: hard to exploit or minor impact, such as needing non-default configuration or a privileged position. Leaks through the anonymity options are usually Low or Medium.

Give a severity and the reason; do not inflate it. Focus on Medium and above, and send Low only with a working reproducer. Do not send non-security bugs.

## Evidence required

- A reproducer against the unmodified build in this image, with default limits and timers and no test-only hooks: a regtest functional test. Use a unit test only when a functional test cannot reach the code, and say why. Include a passing control run. Code reading alone is not enough.
- Whether it reproduces in `/src/build`, not only under sanitizers.
- What the attacker needs: connection direction and count, permissions, proof of work, fees, options, timing.
- The scanned revision, when the bug was introduced, and which releases it affects.
- One root cause per report. Check the history and tests for an earlier fix, for tests asserting the behaviour as intended, and for pull requests closed without merging.
- A minimal patch with a test that fails before it and passes after.

## Scope

Everything shipped in release binaries is in scope. Prioritise code that input from unauthenticated peers reaches.

Subtrees (`src/secp256k1`, `src/leveldb`, `src/crc32c`, `src/minisketch`, `src/ipc/libmultiprocess`) count when Bitcoin Core reaches the affected code, including through normal operation, such as a race in LevelDB's compaction thread; name the subtree.

Only Linux x86-64 is built. Other platforms, 32-bit builds and `src/qt` are low priority and need a concrete argument that a supported release reaches the code. Out of scope: `test/`, `src/test/`, `src/bench/`, `contrib/`, `ci/`, `depends/`, except code shipped in release binaries. Tracing is out of scope: USDT tracepoints only act when a privileged local user attaches to them.

## Build

`/src` is the checkout, with git history.

- `/src/build`: release-like, GCC 14, `-O2 -g`, the `dev-mode` preset without the GUI and the fuzz binary (wallet, IPC, ZMQ, USDT, bench, kernel library), with `compile_commands.json`. Its behaviour is what counts.
- `/src/build_asan`: clang with the ASan CI job's sanitizers (address, float-divide-by-zero, integer, undefined). Run reproducers through its `test/functional/test_runner.py`, and unit tests through `test/with_sanitizer_env.py`, to get Bitcoin Core's sanitizer settings and suppressions. The integer sanitizer flags unsigned wraparound, which is defined; it needs a consequence like any UBSan report.

The unit tests and four functional tests ran at build time; results are in the build log, and failures did not stop the build. Previous-release binaries and BPF tooling (`interface_usdt_*`) are not available; check test output for skips.

Use disposable regtest nodes only; never connect to public networks or use real funds. Cap compilation and test parallelism at two jobs. Prefer a small deterministic counterexample to exhausting the VM.

```sh
ctest --test-dir /src/build --output-on-failure -j2 --timeout 300
timeout --kill-after=5 600 python3 /src/build/test/functional/test_runner.py -j2 interface_ipc.py interface_zmq.py p2p_invalid_messages.py wallet_basic.py
```
