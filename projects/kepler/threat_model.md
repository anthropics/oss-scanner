# Kepler threat model

Kepler measures energy consumption for nodes, processes, containers, pods, and
VMs and exports metrics through Prometheus and stdout. It reads host `/proc`
and `/sys`, uses Kubernetes metadata, and optionally queries NVIDIA GPUs,
DCGM exporter endpoints, and Redfish BMCs.

## Trust boundaries

- Workloads can influence process names, command lines, cgroup paths, and
  Kubernetes metadata. Treat these values as untrusted when parsing them or
  using them in metrics, logs, filesystem paths, or HTTP responses.
- HTTP clients can reach the configured metrics, health, and profiling
  endpoints according to deployment network policy. Check authentication and
  TLS behavior when the exporter web configuration enables them.
- Remote DCGM exporter and Redfish responses cross network trust boundaries.
  Check parsing, resource limits, credential handling, and connection handling.
- Administrator-supplied configuration and credentials are trusted inputs.
  An attack requiring configuration changes must explain the additional
  privilege or access it gains.

## Security goals

Prioritize privilege escalation, unintended host access, exposure of credentials
or host data, and denial of service reachable through untrusted inputs.
Follow `SECURITY.md`: host PID access, reads of `/proc` and `/sys`, and the
`SYS_PTRACE` capability are expected parts of normal operation. Explain how a
finding exceeds this intended access or exposes data to an unauthorized party.

Scope covers this repository, including its deployment manifests. Kepler
Operator and the documentation website are separate repositories.

## Build and tests

The checkout is at `/src`, and `make build` produces `/src/bin/kepler` with
debug symbols. Run `runuser -u scanner -- make test` from the scanner's root
shell for unit tests with race detection. Tests use an unprivileged user because
permission checks depend on unreadable files remaining unreadable. Dependencies
for both the root module and the separate `test/` module are cached in the
image so Go can use them without Internet access.

Hardware and cluster end-to-end tests need additional infrastructure: CPU
power tests need RAPL, GPU tests need an NVIDIA device or the documented fake
GPU mode, and Kubernetes tests need a cluster. Use existing mocks and fixtures
for offline reproduction where possible. Do not treat unavailable hardware
in the scanner environment as a vulnerability.
