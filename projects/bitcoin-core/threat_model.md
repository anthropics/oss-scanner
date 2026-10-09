# Bitcoin Core threat model

Bitcoin Core validates the Bitcoin blockchain and participates in its peer-to-peer network. It also provides a wallet, JSON-RPC server, command-line tools, and optional local IPC services. Protect consensus correctness, private keys and signing intent, node availability, durable chain and wallet state, and transaction privacy.

## Existing project guidance

Read the checkout's [SECURITY.md](https://github.com/bitcoin/bitcoin/blob/master/SECURITY.md), [JSON-RPC security guidance](https://github.com/bitcoin/bitcoin/blob/master/doc/JSON-RPC-interface.md#security), [fuzzing guide](https://github.com/bitcoin/bitcoin/blob/master/doc/fuzzing.md), [developer notes](https://github.com/bitcoin/bitcoin/blob/master/doc/developer-notes.md), and [test guide](https://github.com/bitcoin/bitcoin/blob/master/test/README.md).
The project's policies take precedence over this summary.
Use the scanned checkout for technical instructions, since linked documentation follows `master`.

## Actors and entry points

Treat unauthenticated peers as adversarial. Trace P2P messages, transactions, blocks, headers, compact blocks, addresses, and transport negotiation through validation, allocation, queues, persistence, and cleanup. Distinguish arbitrary peer input from data that requires valid proof of work, mining, or a consensus-valid transaction or block.

HTTP parsing occurs before RPC authentication. Review request framing and resource accounting on that path, and REST when enabled. RPC access is privileged and intended for trusted clients. Identify authentication and authorization requirements before claiming a remote attack. Check externally supplied descriptors, PSBTs, transactions, wallet imports, signing requests, and external-signer replies for violations of the user's intended operation. Keep mempool policy separate from consensus and wallet accounting.

Review reorgs, initial synchronization, pruning, snapshot activation, indexes, restart, cancellation, and partial failures. Check thread and callback lifetimes, stale state, arithmetic widths, input-to-output amplification, retained resources, and disk durability. State the exact fault needed for corruption-dependent bugs and establish whether a real producer can create it.

Check UTXO conservation across connect and disconnect, cache flags and undo data, and consistent validation across full blocks, compact blocks, RPC submission, and reindex. Invalid blocks must not poison retained state. Examine validation-cache provenance, asynchronous script-check lifetimes, one-shot compact-block reconstruction, mutable block-index ordering keys, and preservation of dirty entries after failed database writes. Review peer scheduling, headers synchronization, transaction requests and orphans, package accounting, and AddrMan eclipse resistance.

Persisted inputs include block and undo files, peer state, mempool data, fee estimates, snapshots, and wallet databases. Trace their producer as well as their reader. For wallets, review database transactionality, encryption, and PSBT merge and finalization alongside the operation approved by the user.

IPC is a local interface. Distinguish a libmultiprocess API defect from a failure reachable through Bitcoin Core's actual callers. Trace generated proxies, callbacks, connection teardown, shared state, and timeouts. Local access and non-default features are prerequisites to record when assessing impact.

## Scope and ownership

The whole repository is in scope for source review. The priorities below guide investigation rather than exclude other code.

Prioritize consensus divergence or inflation, remotely reachable memory corruption and node failure, key or fund loss, persistent corruption, and practical resource exhaustion. Also investigate authenticated, optional, local-file, and supported platform-specific paths when there is a concrete security failure. A parser accepting malformed bytes or a theoretical large allocation alone does not establish a vulnerability.

The image enables wallet, IPC, ZMQ, unit tests, and benchmarks. It does not build the Qt GUI or exercise other operating systems or 32-bit architectures. These are build and execution limits, not exclusions from source review. Record any additional prerequisites needed to reproduce a finding outside this environment. Bundled libraries remain in scope when Bitcoin Core reaches the affected code, but identify their upstream owner before proposing changes, including libsecp256k1, LevelDB, libmultiprocess, and minisketch. Do not conflate a standalone library contract with demonstrated node impact.

## Build and bounded validation

The checkout is `/src`. The normal build is `/src/build`, with binaries under `/src/build/bin`, functional tests under `/src/build/test/functional`, and a compilation database at `/src/build/compile_commands.json`. Unit tests and four functional smoke tests run during the Docker build. Dependencies, including the Python IPC bindings and `/qa-assets`, are fetched before network access is removed. `DIR_UNIT_TEST_DATA` points to `/qa-assets/unit_test_data` so the external script test data is available.

Previous release binaries are not fetched, so backwards-compatibility tests that require them cannot run offline in this image.
The `interface_usdt_*` tracepoint tests need BPF tooling that is not installed.
These are execution limits, not source-review exclusions.
Check test output for skips before reporting coverage. The selected IPC and ZMQ tests require the installed `pycapnp` and `python3-zmq` bindings.

Use repository-native tests with an independent expected result. Reproduce only against disposable regtest nodes and temporary files. Never connect test nodes to public Bitcoin networks or use real wallets or funds. Keep CPU, memory, disk, runtime, and test parallelism bounded. Prefer a small deterministic counterexample, fault injection, or accounting assertion over exhausting the environment. Initial compilation uses ten jobs in the larger build environment. Cap recompilation and test parallelism at two jobs in the scanner VM.

```sh
ctest --test-dir /src/build --output-on-failure -j2 --timeout 300
timeout --kill-after=5 600 python3 /src/build/test/functional/test_runner.py -j2 interface_ipc.py interface_zmq.py p2p_invalid_messages.py wallet_basic.py
```

The separate `/src/build_fuzz` build uses the project's `libfuzzer` preset with AddressSanitizer and UndefinedBehaviorSanitizer. Existing harnesses are under `/src/src/test/fuzz`, and seed corpora are under `/qa-assets/fuzz_corpora`. Select the matching corpus for a target and keep each run bounded. Corpus initialization can exceed libFuzzer's run and time limits. Use an external timeout to bound the whole process, with five seconds for termination before a forced kill:

```sh
timeout --kill-after=5 180 env FUZZ=process_message python3 /src/build_fuzz/test/with_sanitizer_env.py /src/build_fuzz/bin/fuzz /qa-assets/fuzz_corpora/process_message -runs=100 -max_total_time=30 -rss_limit_mb=2048
```

The generated `with_sanitizer_env.py` wrapper applies Core's sanitizer defaults and suppression files, while preserving explicit environment overrides.
The generated fuzz test runner at `/src/build_fuzz/test/fuzz/test_runner.py` also uses this wrapper. Select targets explicitly and keep its parallelism at two jobs.

## Evidence and severity

Record the exact revision, build options, affected versions, attacker control, enabled-by-default status, prerequisites, and observed consequence. Keep source-only hypotheses separate from targeted tests and reproductions against the real node or library build. For resource findings, distinguish a protocol-derived bound from the largest tested input and measured victim impact. A standalone model or harness crash needs a demonstrated path to the application before claiming a node attack.

Identify sanitizer and hardened-library instrumentation in the evidence. An abort enabled by extra assertions is not proof of a crash in the project's normal configuration. Reproduce the claimed production consequence in the relevant supported build.

Use the current [Bitcoin Core security advisory policy](https://bitcoincore.org/en/security-advisories/) to calibrate severity. Critical concerns protocol-level theft, inflation, or permanent network-wide splits. High generally requires significant default-remote impact with potential for widespread disruption. Medium covers noticeable degradation with limited scope or exploitability. Low covers minor impact or difficult exploitation. Bug-class labels, an assertion, or a sanitizer report do not determine severity on their own. Keep confidence, remediation urgency, and disclosure timing separate.

Check available Git history and existing tests for the same root cause and remediation. Identify any duplicate or already-fixed failure. Record when comparison with current upstream proposals needs later online triage by the security contacts. Keep patches focused and follow Bitcoin Core's contribution rules. Where useful, establish current behavior before a fix and update the same test to assert the corrected result.

Send findings privately to `security@bitcoincore.org` as specified by [SECURITY.md](https://github.com/bitcoin/bitcoin/blob/master/SECURITY.md). Do not put suspected vulnerabilities, reproducer details, private review history, or unreviewed findings into public issues or PRs. Include the smallest bounded reproducer, actual output, expected result, and relevant evidence limits in each report. Disclosure decisions belong to the project's security contacts.
