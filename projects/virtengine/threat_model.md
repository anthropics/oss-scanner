# Threat model

## What this project does and where untrusted input enters
VirtEngine is a Go (Cosmos SDK / CometBFT) blockchain node and compute marketplace. Untrusted input enters via:
- on-chain transactions and messages (`x/*` modules: market, marketplace, escrow, settlement, veid, mfa, enclave, hpc, provider, ...);
- P2P / consensus traffic from other nodes and validators;
- gRPC, REST and CLI endpoints exposed by `cmd/virtengine`;
- provider-daemon (`cmd/provider-daemon`, `pkg/provider_daemon`) inputs: tenant manifests, orders, and backend adapter data (Kubernetes, SLURM, MOAB, Open OnDemand, Waldur);
- identity data submitted for VEID verification (`x/veid`, `pkg/verification`, `pkg/enclave_runtime`).

## Components that matter most / least
Most: consensus-critical state machines and ante handlers, escrow/settlement/staking (fund movement), VEID/MFA/encryption/key management, enclave attestation, provider-daemon request handling.
Less: simulators and benchmarks (`cmd/ve-sim`, `sim/`, `cmd/benchmark-daemon`), `docs/`, `_docs/`, `infra/`, `mobile/`, `portal/` (frontend), generated code and test utilities.

## How to exercise it
- Build output: `/src/bin/` (`virtengine`, `provider-daemon`, ...).
- Security tests: `go test -tags=security ./tests/security/...`; also see `SECURITY.md` and `tests/security/scripts/`.
- Module unit tests: `go test ./x/<module>/...`.

## How you rate severity
Per SECURITY.md:
- Critical: consensus manipulation, unauthorized fund movement, signing-key compromise, complete MFA/VEID bypass.
- High: validator/provider privilege escalation, replayable attestation or identity flows, sensitive data disclosure.
- Medium: bounded logic bugs, non-critical authz drift, incomplete audit logging.
- Low: defense-in-depth gaps and hygiene issues.
Non-determinism in consensus-path code (map iteration, floats, time, randomness) that can cause chain halts is at least High.

## Anything to leave alone
- Code derived from Akash and third-party dependencies unless VirtEngine's usage is the flaw.
- Findings that require a compromised validator majority, or local access to a node operator's own keys/config.
