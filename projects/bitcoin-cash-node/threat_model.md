# Bitcoin Cash Node threat model

## Purpose and assets

Bitcoin Cash Node (BCHN) is a Bitcoin Cash full node, transaction relay and mining
backend with an optional local wallet. Its critical assets are correct consensus
validation and chain state, availability to honest peers, wallet private keys and
funds, and the confidentiality of wallet and node metadata. A node must not accept
invalid blocks or unauthorized spends, create invalid mining templates, or lose
wallet funds because of incorrect signing, accounting or persistence.

## Trust boundaries and priorities

- **Unauthenticated P2P:** Remote inbound and outbound peers are untrusted,
  including peers reached through discovery. Network messages, addresses, blocks,
  transactions and scripts are attacker-controlled until validated. Prioritize
  message parsing, serialization, resource bounds, peer state, mempool admission,
  block validation, script execution, signature checks, reorganizations and UTXO
  accounting. A peer does not acquire administrative privileges by connecting.
- **Consensus versus policy:** Consensus validity is distinct from local mempool,
  relay and mining policy. A policy difference alone is not a consensus split.
  Assess activation rules and network context explicitly; do not propose a
  consensus-rule change as an incidental hardening fix.
- **RPC administration:** JSON-RPC is an intentionally privileged administrative
  interface, authenticated by a cookie or configured credentials. An authorized
  caller can perform the documented operations, including stopping the node,
  changing chain state through administrative methods, and spending or exporting
  keys when permitted by wallet state. Those intended capabilities are not an
  unauthenticated remote vulnerability. Operators must protect credentials and
  restrict exposure; cookie/data-directory read access is security-sensitive.
  Authentication bypass, unintended access before authentication, memory safety
  faults, and violations of actual wallet locking or authorization guarantees
  remain in scope. State any required RPC access and wallet-unlock conditions.
- **Other interfaces:** The optional REST interface is explicitly unauthenticated
  when enabled; assess it separately from authenticated RPC and record the
  required exposure/configuration. ZMQ notifications and optional UPnP/NAT-PMP
  integrations have separate inputs and deployment assumptions; do not treat a
  notification consumer as an RPC administrator.
- **Wallet and local inputs:** Wallet databases/backups, imported keys and
  descriptors, transaction/PSBT data and signing requests can cross trust
  boundaries. Prioritize key confidentiality, correct destinations and amounts,
  fees, signature commitments, encryption/locking and durable wallet updates.
  Distinguish handling an untrusted imported artifact from an attacker already
  able to read private keys or rewrite the process's files. The OS, build tools,
  operator-owned configuration and protected data directory are trusted; ordinary
  same-user file replacement is not by itself a remote privilege escalation.

The main review targets are the daemon and core libraries under `src/`, especially
network processing, consensus/validation, script/crypto, storage, RPC and wallet
code. Dependencies used by those paths matter, but distinguish an upstream library
defect from BCHN's integration. Tests and documentation help establish intended
behavior; test-only code is not a production remote surface. The Qt GUI is not
built in this headless environment, so GUI-only coverage requires another build.

## Impact classification guidance

These are triage guidelines, not an assertion that any particular issue exists.
Rate demonstrated reachable impact and prerequisites, not a dangerous-looking API
in isolation.

- **Critical:** Plausible unauthorized spending or private-key compromise across
  an actual security boundary; remotely reachable code execution; or a consensus
  validity/chain-state defect with credible network-wide financial or chain-split
  consequences. Explain scope and assumptions rather than equating any local
  test failure with network-wide impact.
- **High:** Remotely reachable memory corruption without established code
  execution, persistent/widespread loss of node availability, or serious wallet
  corruption or validation failure with substantial but more constrained impact.
- **Medium:** Bounded/recoverable denial of service, meaningful resource
  amplification, privacy disclosure, or correctness failures with limited impact
  or stronger configuration/access prerequisites. Network-wide or persistent DoS
  can warrant a higher rating; not all DoS has equal severity.
- **Low:** Limited information leakage or hardening/correctness defects with
  little demonstrated security impact. Expected administrative powers and
  deliberate insecure operator configuration are not vulnerabilities by
  themselves.

Always identify whether the entry point is unauthenticated P2P, optional exposed
REST, authenticated RPC, or a local imported artifact; describe defaults,
preconditions, persistence/recovery and funds/consensus implications. Keep reports
private to `security@bitcoincashnode.org` under `DISCLOSURE_POLICY.md`. Separate
observed behavior from hypotheses. Prefer small fixes preserving consensus and
wallet compatibility, with deterministic regression coverage and no real funds.

## Build and offline verification

The Dockerfile installs dependencies before the network is removed and builds
with CMake/Ninja in `/src/build`. It enables daemon, CLI, transaction utility,
wallet (Berkeley DB 5.3 or later), unit tests and the normal non-GUI features.
Debug symbols, source, test fixtures and build configuration remain in the image.
There is no need to download a blockchain or use production credentials.

Representative commands inside the finished image, working in `/src`:

```sh
# Existing local unit tests; no compilation or external services needed.
./build/src/test/test_bitcoin --run_test=amount_tests,arith_uint256_tests,base58_tests --report_level=short

# Existing functional tests create isolated regtest nodes and use loopback only.
python3 ./build/test/functional/test_runner.py --jobs=1 feature_config_args wallet_basic
```

These commands can run in a container started with `--network none`; loopback is
still available to the regtest harness. Use only temporary regtest data and keys,
never live networks, real wallets or third-party infrastructure. The representative
commands do not constitute full-suite, GUI or cross-platform verification.
