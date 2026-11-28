# Threat model

## What this project does
Talos Linux is an immutable, minimal Linux distribution for Kubernetes. There is no shell or SSH: the node is managed
only through a gRPC API, and its whole configuration is a declarative machine config. This repository holds the
userspace (machined as PID 1, apid, trustd, and the controllers in `internal/app/machined/pkg/controllers`), the
`talosctl` client, the `pkg/machinery` library (config types, API definitions), and the image builder (`pkg/imager`).
The kernel and base packages are built in separate repositories and are out of scope here.

## Where untrusted input enters
- **Talos API** (apid, TCP 50000): mutual TLS with client certificates issued by the cluster's Talos CA. Each
  certificate carries roles (`pkg/machinery/role`): `os:admin`, `os:operator`, `os:reader`, `os:etcd:backup`,
  `os:image:verifier`, `os:meta:writer`, `os:content-library:reader`, `os:content-library:writer` and
  `os:impersonator`. Authorization is enforced per method. apid also proxies requests to other nodes (the
  `nodes` metadata). Any way to call a method without a valid certificate, with a role that should not allow it,
  or to reach a node the proxy should not reach, is in scope.
- **trustd** (TCP 50001): issues certificates to joining nodes after checking a machine token. Anything that yields a
  certificate without the token, or with more than the intended identity, is in scope.
- **Maintenance mode**: before a machine config is applied, apid serves a limited API over TLS without client
  authentication on all interfaces, so the first config can be pushed. Anyone who can reach the node then can apply a
  config, wipe disks or otherwise take it over; that is by design and the operator protects it at the network level
  (or uses SideroLink). In scope: leaking secrets from a node that already has a config, or a configured node falling
  back into maintenance mode.
- **Network inputs on the node**: DHCPv4/v6, router advertisements, platform metadata services (cloud providers,
  `internal/app/machined/pkg/runtime/v1alpha1/platform`), the discovery service, KubeSpan (WireGuard peer data),
  SideroLink, NTP and DNS responses (including the built-in DNS cache).
- **Kubernetes workloads**: pods are untrusted. A pod escaping to the node, reading node secrets or the Talos API
  credentials, or changing node state is critical. Talos-generated Kubernetes manifests and RBAC
  (`internal/app/machined/pkg/controllers/k8s`) are in scope. A privileged pod (`privileged: true`, host
  namespaces, hostPath of `/` or block devices) is root on the node: reading the STATE partition, the machine
  config or other node secrets from one is not a finding.
- **Container images and the image cache**: image pulls, image verification, and the registry mirror/cache that
  serves images between nodes.
- **Disks and filesystems**: volumes, partitions and filesystems attached to the node may be attacker-controlled
  (e.g. a disk moved from another machine). Parsing them must not compromise the node.
- **talosctl**: responses from a node, files read with `talosctl read`/`cp`, and config files given to the client.
  A malicious node or archive writing outside the target directory on the operator's machine is in scope.

## What is trusted
- The machine config and its patches. Whoever can apply a config is root on the node.
- The kernel command line, the boot media and system extensions (they are signed and measured when Secure Boot is
  used; bypassing that verification is in scope).
- Holders of `os:admin`. Admin doing admin things is not a finding.

## How to exercise it
- All Go modules are in the module cache: `go build`, `go test` and `go run ./cmd/talosctl` work offline.
- The full unit suite runs in the release build against the Talos rootfs; outside it, tests that need system files
  may skip or fail.
- Integration tests (`internal/integration`, build tag `integration`) need a running cluster and cannot run here.

## How we rate severity
- Critical: unauthenticated remote code execution or secret disclosure through the Talos API or trustd; pod-to-node
  escape, including escaping workload isolation (the `sandboxd` namespaces that hold the CRI, the kubelet and all
  pods); obtaining a Talos or Kubernetes CA key; decrypting or unsealing a Talos-encrypted volume without its key
  (TPM2-sealed, KMS, node ID or static keys in `internal/pkg/encryption/keys`), e.g. unsealing a TPM2 key on a
  modified boot chain.
- High: privilege escalation between Talos roles (e.g. `os:reader` reaching an `os:operator` or `os:admin` method or
  reading secrets); authenticated code execution below admin; Secure Boot or image verification bypass; reaching an
  unintended node through the apid proxy; weakening encryption without a full break (e.g. key material reachable by a
  non-admin role or written to logs, a TPM2 policy that binds to less than intended).
- Medium: denial of service of a node from the network or from a pod without elevated privileges; path traversal in
  `talosctl` against the operator's machine; information disclosure that does not include secrets.
- Low: denial of service that needs an authenticated role; hardening gaps without a demonstrated impact.

## Anything to leave alone
- Behaviour that requires `os:admin` or control of the machine config. Malformed config values that crash a
  controller or write outside a directory (e.g. a disk selector or an extension service name) are input validation
  bugs, not vulnerabilities: whoever writes the config is already root.
- Unauthenticated config apply, disk wipe or reset in maintenance mode (see above).
- Anything a privileged pod can do on its node.
- The provisioners behind `talosctl cluster create` (`pkg/provision`, including the remote-provision server): they
  are development and test tooling, not part of a Talos node.
- Findings in vendored or third-party Go modules, unless Talos uses them in an unsafe way.
- `hack/`, `website/` and `tools/` (build and documentation tooling), and test fixtures.
- Kernel bugs (report against siderolabs/pkgs), system extensions (siderolabs/extensions) and
  talos-cloud-controller-manager: they live in other repositories.
