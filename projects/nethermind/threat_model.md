# Nethermind

Nethermind is an Ethereum execution client written in C#. It processes adversarial peer traffic, transactions, blocks, contract bytecode and JSON-RPC requests. Correct execution and availability are security properties of the client.

## Audit scope

Audit the entire repository, including every production component, plugin, consensus implementation, networking layer, RPC module, storage backend, cryptographic implementation, import/export path, supporting tool, build script and test infrastructure. No project or directory is excluded. The priorities below guide triage; they do not restrict coverage to selected modules. Review supporting tools in the context of their intended privileges and deployment.

## Trust boundaries and priorities

- Treat remote peer messages, discovery packets, transaction and block contents, serialized data and EVM bytecode as untrusted. Prioritize attacks reachable through default P2P and discovery interfaces.
- Investigate consensus-invalid block acceptance, rejection of valid blocks, divergent execution or state roots, and violations of EVM isolation.
- Investigate remotely triggered crashes, hangs, unbounded memory growth, excessive computation, resource leaks and persistent database corruption. Account for protocol limits, gas accounting, peer penalties and existing resource budgets.
- Treat JSON-RPC requests as untrusted when an operator exposes the relevant interface. State which transport, enabled modules, authentication and configuration are necessary. Distinguish public RPC exposure from authenticated Engine API access.
- The Engine API is intended for a trusted consensus client with JWT authentication. Investigate authentication bypasses and reachable robustness failures, and identify any assumption that requires an attacker to control that trusted client.
- Investigate filesystem path handling, archive extraction, snapshot import, keystore access and unsafe/native interop with attacker-controlled inputs. Identify which feature and permissions make a path reachable.
- Local administrator control, deliberate edits to trusted configuration and already-compromised hosts are not by themselves vulnerabilities. Optional features remain in scope when the enabling conditions are explicit.

## Severity and evidence

Assess severity using realistic reachability, default exposure, required privileges and impact. Distinguish node denial of service from demonstrated network-wide consensus impact. A performance regression alone does not establish an exploitable denial of service; quantify attacker cost and victim resource consumption.

Provide the affected revision, entry point, required configuration, root cause, expected versus actual behavior and a minimal deterministic reproducer. Use isolated test fixtures or private local networks; do not contact public peers or live networks. Group reports with the same root cause. Include a minimal patch and regression test where practical.

## Build and tests

The source checkout is at `/src`. The image retains the .NET SDK, restored NuGet packages and Release build outputs for `src/Nethermind/Nethermind.slnx`. The repository uses Microsoft.Testing.Platform; follow the checked-out repository's test instructions. Keep test execution offline and disable restore/build when using the existing outputs. Some integration and external-fixture tests may require resources outside this image; describe any missing prerequisite rather than treating it as a client vulnerability.

## Reporting

Send findings privately to `security@nethermind.io`. Follow the repository's `SECURITY.md`. Do not open public issues or publish unpatched vulnerability details.
