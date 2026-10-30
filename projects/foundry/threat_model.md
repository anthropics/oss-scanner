# Foundry

Foundry is a Rust toolkit for developing, testing, debugging, and deploying Ethereum applications. Forge compiles and tests contracts and executes deployment scripts; Cast handles chain data, transactions, and signing; Anvil provides a local development node; Chisel is a Solidity REPL. Correct execution and transaction construction, protection of signing material, and enforcement of intended host-access boundaries matter to its users.

## Scope and trust boundaries

Review the whole repository, including optional features, supporting libraries, update/install tooling, and the embedded Solar CLI. The following priorities do not exclude other components. State the command, enabled feature, configuration, and attacker capabilities required to reach a finding.

- Treat Solidity and Vyper input, ABI/JSON data, bytecode, compiler output, dependency metadata, archives, RPC responses, traces, and persisted artifacts as potentially adversarial. Follow their paths through parsing, compilation, decoding, rendering, and filesystem operations.
- Review Forge execution, fuzzing, invariants, symbolic execution, and cheatcodes for incorrect results and violations of configured host-access permissions. FFI is an explicit capability, and filesystem cheatcodes have configured permissions; distinguish intended use from bypasses. Foundry is not a general sandbox for arbitrary malicious repositories or configuration files. Identify the specific boundary that is supposed to constrain an input.
- Review signing, keystores, hardware/cloud signer integrations, secret handling, and transaction construction. Look for unintended disclosure, incorrect destination/value/calldata/chain selection, and transactions signed or broadcast without the user's requested authorization. Local script execution, transaction simulation, and broadcast are distinct stages; demonstrate which stage causes an externally visible effect.
- Treat remote RPC and explorer responses as untrusted data even when the endpoint is operator-selected. Review response validation, redirects, cache keys, resource limits, and whether remote data can influence signing or host filesystem access beyond the command's intended behavior.
- Anvil is a development node. Its known default keys, unlocked development accounts, impersonation methods, mining controls, and state mutation APIs are intentional capabilities, not production authentication guarantees. Assess remote crashes, unintended host access, and corruption in the context of the actual listener exposure. Exposure of a deliberately unlocked development node does not by itself establish an authentication bypass.
- Review EVM execution, network-specific transaction handling, fork state caching, and proof/receipt/trace handling for correctness. Anvil does not participate in Ethereum mainnet consensus; do not equate a local simulation discrepancy with a network consensus failure without a separate impact path.
- Review `foundryup`, compiler acquisition, dependency installation, archive extraction, and path handling for integrity failures or writes outside their intended locations. Identify the authenticity check or filesystem boundary that is bypassed, rather than assuming an attacker already controls the trusted release channel or local administrator account.

## Severity and evidence

Prioritize theft or disclosure of signing secrets, unauthorized signing/broadcast, arbitrary host execution across an intended boundary, and exploitable filesystem-permission bypasses. Assess severity from actual reachability, privileges, required configuration, and demonstrated impact. Execution or simulation errors can be serious when they lead users to authorize unsafe transactions; show that connection rather than assigning production-chain impact to every test discrepancy.

For denial of service, measure attacker-controlled input and effort against CPU, memory, disk, and elapsed time. Distinguish a remotely reachable Anvil outage from a user explicitly compiling or fuzzing a costly local project. Account for configured limits and cancellation. Debug-only assertions, ordinary expensive compilation, missing external services, and intentionally enabled FFI are not vulnerabilities by themselves.

Provide the exact revision, command or API entry point, required configuration, root cause, expected and actual behavior, and a deterministic offline reproducer. Use temporary directories, local test chains, and disposable test keys. Never send real transactions or include real credentials. Group reports by root cause and include a focused patch and regression test where practical. Report privately to `security@tempo.xyz`, the contact in the Foundry organization's security policy at https://github.com/foundry-rs/.github/blob/main/SECURITY.md.

## Build and offline investigation

The checkout is `/src`. The image retains Rust, native build tools, Cargo caches, release binaries for Forge, Cast, Anvil, Chisel, and Solar, and precompiled unit tests. Binaries use their default Cargo features. Optional cloud signer and additional network features can be enabled for targeted investigation; they are not excluded from scope. Release debug information and frame pointers are retained, LTO is disabled, and compilation uses four jobs. Lower `CARGO_BUILD_JOBS` if the analysis VM needs it.

Solidity 0.8.38 is installed in `/root/.svm/0.8.38/solc-0.8.38` and exposed as `solc`. The architecture-specific release manifest is retained at `/opt/solc/list.json` through `SVM_RELEASES_LIST_JSON`, so Rust rebuilds do not need to fetch it. Vyper 0.4.3 and Z3 5.1.0.0 are on `PATH`. No credentials or external RPC services are configured.

```sh
cargo build --locked --release --bins -p forge -p cast -p anvil -p chisel -p solar
cargo test --locked --release --lib -p foundry-primitives -p forge-fmt -p anvil-core
```

For local Solidity fixtures, use `forge test --offline --use 0.8.38` with dependencies already present in the image or with a self-contained reproducer. Other workspace tests can be built from the cached dependencies, but fixtures requiring other compiler versions, dependency downloads, remote forks, explorer credentials, cloud signers, or external services need additional setup. The precompiled tests are a smoke check, not a restriction on analysis scope or a claim that every integration suite runs offline. Consult `AGENTS.md` and `docs/dev/README.md` for the checked-out revision's test conventions.
