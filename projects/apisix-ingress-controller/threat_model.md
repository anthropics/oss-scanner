# APISIX Ingress Controller scanning guidance

## Authoritative model and scope

This enrollment targets only `apache/apisix-ingress-controller`.
The repository's `AGENTS.md` inherits the Apache APISIX PMC threat model:
https://github.com/apache/apisix/blob/master/docs/en/latest/security-threat-model.md

Read the model cached at `/opt/apisix-threat-model.md` before producing findings,
especially sections 4.3, 4.6, 4.8, 4.9, 4.11a, and 4.13. The Dockerfile fetches
that document during online setup so it is available during the offline audit.
Use its trust assumptions, exclusions, severity guidance, and triage dispositions.
This enrollment does not independently scan APISIX, ADC, or the Dashboard.

## Controller-specific boundaries

The controller translates Kubernetes Ingress, Gateway API, and APISIX resources
into gateway configuration, including routing, authentication, plugins, consumers,
and TLS secrets. Examine resource references, namespaces, selection rules,
translation, reconciliation, and admission handling in this repository.

The shared model identifies CRD-to-Admin-API fidelity as a security property:
dropping, injecting, or renaming fields during translation can silently weaken a
configured security policy. Demonstrate the resulting configuration and the
reachable security consequence, not merely a schema difference.

Kubernetes RBAC, resource ownership, and the trust assigned to resource creators
are assumptions supplied by the shared model. Identify the attacker's actual
Kubernetes permissions and the violated property when reporting namespace or
reference isolation issues. Report credential or certificate disclosure only
when an actor obtains material beyond their authorized access.

## Offline environment

The full source is at `/src`, the controller binary is at
`/src/bin/apisix-ingress-controller`, and the Go toolchain and module cache remain
installed. Local Kubernetes API server and etcd binaries for envtest are cached
under `/opt/envtest`; their exact directory is in `/opt/envtest-path`.

Run the prepared test package set with:

```sh
timeout 900 oss-scanner-test
```

The driver sets `KUBEBUILDER_ASSETS`, disables Go module downloads and toolchain
downloads, and runs the package set selected by upstream's unit-test exclusions.
It does not use an external Kubernetes cluster. Cluster E2E, Gateway API
conformance, and benchmark packages are excluded. APISIX and ADC services are
not running; use fake Kubernetes clients, envtest, and local HTTP fixtures to
exercise controller behavior. Explicitly identify any finding whose end-to-end
gateway impact still needs a live-backend reproduction.

When writing an envtest reproducer in a network-disabled container, set the API
server's advertised address to loopback before starting the environment:

```go
testEnv.ControlPlane.GetAPIServer().Configure().Set("advertise-address", "127.0.0.1")
cfg, err := testEnv.Start()
```

Without this setting, kube-apiserver tries to discover a default network route
and fails to start in a container that has only loopback connectivity.

## Reports

Provide the commit, attacker permissions, minimal Kubernetes resource manifests,
the relevant shared-model property, resulting translated configuration, and a
local regression test. Keep synthetic secrets in reproducers. Distinguish
verified behavior from hypotheses and provide a focused patch where possible.
