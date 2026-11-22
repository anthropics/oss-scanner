# Threat model: Dapr runtime (dapr/dapr)

## What this project does and where untrusted input enters

Dapr is a sidecar runtime. Each application gets a `daprd` sidecar that exposes HTTP and gRPC building-block APIs
(service invocation, state, pub/sub, bindings, actors, workflows, jobs, secrets, configuration, conversation and
others) and talks to backing services through components. A control plane backs the sidecars:

- `sentry`: certificate authority. Signs workload certificates (SPIFFE IDs of the form
  `spiffe://<trust-domain>/ns/<namespace>/<app-id>`) after validating the caller's identity.
- `operator`: serves Components, Configurations, Subscriptions, Resiliency and HTTPEndpoints to sidecars.
- `injector`: Kubernetes mutating webhook that adds the `daprd` container to annotated pods.
- `placement`: actor placement tables, per namespace.
- `scheduler`: durable jobs, actor reminders and workflow timers, backed by embedded etcd.

Trust boundaries, from most to least important:

1. **Between applications / namespaces.** Sidecars authenticate each other and the control plane with mTLS using
   Sentry-issued SPIFFE certificates. Anything that lets one app act as another app ID, reach another namespace's
   components, state, secrets, actors, jobs, workflows or subscriptions, or bypass service invocation access
   control policies (`pkg/acl`) or component scopes (`pkg/scopes`), crosses this boundary.
2. **Network to sidecar / control plane.** Remote callers reaching daprd's API, internal gRPC (sidecar-to-sidecar)
   port, or any control plane gRPC/HTTP endpoint. Sentry's sign-certificate endpoint is reachable by every workload.
3. **App to its own sidecar.** daprd trusts its local app. The optional `DAPR_API_TOKEN` (app to daprd) and
   `APP_API_TOKEN` (daprd to app) tokens harden this. Bypassing a configured API token is in scope.
4. **Component metadata and resource manifests** (Components, Configuration, Subscriptions, Resiliency,
   HTTPEndpoints) are written by the cluster or host operator and are trusted.

## Components that matter most / least

Most: Sentry certificate signing and identity validation (`pkg/sentry/server`, especially the `kubernetes` and
`jwks` validators); mTLS and SPIFFE identity handling (`pkg/security`); the operator's per-namespace/per-app
resource filtering (`pkg/operator/api`); scheduler and placement namespace/app-ID scoping
(`pkg/scheduler/server`, `pkg/placement`); service invocation ACLs and app ID routing; API token middleware;
the injector's admission checks (`pkg/injector`).

Medium: daprd HTTP/gRPC API handlers (`pkg/api`), request parsing, workflow and actor state handling, HTTP
middleware pipeline, metadata forwarding to components.

Least / out of scope:

- `tests/` (test apps, e2e and integration harness, integration-only probe components), `.build-tools/`,
  `docs/`, `swagger/`, `grafana/`, `img/`.
- Component implementations live in `github.com/dapr/components-contrib` and are compiled into daprd as a
  dependency. Bugs inside a component's own logic are out of scope for this enrollment, but a daprd bug that lets
  untrusted input reach a component it should not is in scope.
- Dependency CVE lists without a demonstrated reachable path in Dapr (see
  https://docs.dapr.io/operations/support/support-security-issues/).

## How to exercise it

- The checkout is at `/src`. Release-flavour binaries are on `PATH`: `daprd`, `sentry`, `placement`,
  `scheduler`, `operator`, `injector`.
- Unit tests need the `unit` build tag:
  `go test -tags=unit,allcomponents ./pkg/<package>/...`
- Integration tests run real daprd and control plane processes locally (no Kubernetes needed; the operator and
  injector tests use an in-process fake API server):
  `go test -v -tags=integration -count=1 ./tests/integration -focus='<regex on suite/path/Name>'`
  e.g. `-focus='^sentry/'`, `-focus='^daprd/serviceinvocation/'`, `-focus='^scheduler/'`.
  The framework rebuilds every binary from `/src` on each run (the build cache makes this quick), so patched
  source is always what gets tested. Do not set `DAPR_INTEGRATION_*_PATH`, or the run uses stale binaries.
- The best reproducer is a new integration test case under `tests/integration/suite/...`, registered with
  `suite.Register`; existing cases in the same directory show how to start sentry, daprd with mTLS, the
  scheduler and so on.

## How you rate severity

- **Critical:** obtaining a Sentry-signed certificate for an identity the caller does not own in Kubernetes or
  JWKS validation mode; remote unauthenticated code execution in any Dapr binary; cross-namespace access to
  another tenant's secrets.
- **High:** impersonating another app ID; bypassing mTLS, service invocation ACLs, component scopes, secret
  scopes or a configured API token; reading or modifying another app's or namespace's state, actors, reminders,
  jobs, workflows or resources; the operator or injector leaking resources across namespaces; injector bypass
  that grants a pod privileges its creator could not otherwise get.
- **Medium:** remotely triggerable crash or resource exhaustion of a control plane service or a sidecar from
  across a trust boundary; information disclosure of non-secret data across apps.
- **Low:** issues that require the local app to attack its own sidecar without an API token configured; crashes
  only reachable from the local app; hardening gaps with no demonstrated exploit.

## Anything to leave alone

- Self-hosted mode where Sentry uses the `insecure` validator: it intentionally performs no caller
  authentication and assumes a trusted host.
- mTLS disabled by configuration, or no API token configured: absence of authentication there is by design.
- Anything requiring write access to Dapr resource manifests, component metadata, Helm values, or the Kubernetes
  API beyond what a normal workload has.
- An app being able to use its own sidecar's APIs, components and secrets as granted by its scopes.
