# KubeVela threat model

KubeVela is a control plane for application delivery on Kubernetes. Platform engineers
publish capabilities as X-Definitions (ComponentDefinition, TraitDefinition,
PolicyDefinition, WorkflowStepDefinition) whose templates are CUE. Application developers
submit an `Application` custom resource that references those definitions. The
controller (`cmd/core`, `pkg/controller`) renders the CUE, runs the application workflow,
and applies the resulting Kubernetes objects to the local cluster or to managed clusters
through cluster-gateway. The `vela` CLI (`references/`) and a kubectl plugin
(`cmd/plugin`) talk to the same APIs. Admission webhooks (`pkg/webhook`) validate and
default Applications and definitions.

This enrolment covers the `kubevela/kubevela` repository only. VelaUX, prism, kube-trigger,
the standalone workflow controller and the addon catalog are separate repositories.

## Trust boundaries

| Actor | Trust | Notes |
|---|---|---|
| Cluster administrator, platform engineer | Trusted | Authors X-Definitions, enables addons, installs the chart. CUE templates execute inside the controller by design, so a definition author can already make the controller apply anything its RBAC allows. That is not a finding. |
| Application developer, namespace-scoped | Untrusted toward other namespaces and cluster scope | Creates and updates `Application` objects. Everything in `spec.components[].properties`, trait properties, policy properties, workflow step properties, `inputs`/`outputs` and annotations is attacker-controlled. |
| Users of the CLI | Trusted for local files, untrusted for remote content | Local files passed to `vela` are trusted. Content fetched from addon registries (Helm, OCI, git), definition URLs and remote templates is untrusted. |
| Managed clusters | Semi-trusted | A compromised spoke cluster must not be able to read credentials for other clusters or escalate on the hub. |
| Network peers of workflow steps and CueX providers | Untrusted | Built-in steps and providers make outbound HTTP, read and apply objects, and send email. Responses are untrusted. |

## Where untrusted input enters

- `Application` spec and annotations, through the API server and webhooks.
- Properties flowing into CUE evaluation (`pkg/cue`, `pkg/appfile`, `pkg/workflow`), including
  values passed between components by `inputs`/`outputs` and `dependsOn`.
- Workflow step parameters for built-in steps that perform I/O: `webhook`, `notification`,
  `request`, `read-object`, `apply-object`, `export2secret`, `export2config`, `deploy`.
- CueX providers reachable from templates: `http`, `kube`, `email`, and anything registered
  through `Package` objects.
- VelaQL queries (`pkg/velaql`): views are platform-authored, but query parameters come from
  users and from VelaUX.
- Multi-cluster paths (`pkg/multicluster`): cluster names, labels and placement in topology
  policies; kubeconfigs and secrets handled by `vela cluster join`.
- CLI inputs from remote sources: addon registries and archives (`pkg/addon`), definition files
  fetched by URL (`vela def`), Helm charts and OCI artifacts, `vela up -f <url>`.
- Status and `ResourceTracker` contents written back by the controller and read by users who
  may not have permission to read the underlying resources.

## Security properties we care about

1. **Tenant isolation.** A namespace-scoped application developer must not read or write
   resources in other namespaces or at cluster scope beyond what their own RBAC allows.
   In the default chart install the controller's service account is bound to
   `cluster-admin` and applies rendered resources as itself, so isolation at default depends
   entirely on which definitions a tenant may use. Multi-tenant deployments are expected to
   turn on `authentication.enabled` (the `AuthenticateApplication` gate), which records the
   creating identity on the Application and impersonates it when applying resources, and
   usually `authorization.definitionValidationEnabled` as well. Evaluate isolation bypasses
   against that hardened posture. At default, cross-namespace effects produced through
   component types that accept arbitrary manifests (such as `k8s-objects` or `raw`) are
   documented behaviour, not findings. Template escape is a finding in every posture: tenant
   input that makes a definition render objects, fields or namespaces its author did not
   intend (for example through CUE injection in a `webservice` property) is high at default
   and critical if it also defeats impersonation.
2. **No code execution in the controller from Application content.** CUE evaluation must not
   let an application developer run arbitrary code, read arbitrary files, or reach arbitrary
   Go functionality. Definitions may; Applications may not.
3. **Credential confinement.** Cluster-gateway credentials, kubeconfigs and secrets referenced
   by definitions must not be exposed through Application status, ResourceTracker, events,
   logs, `vela status`, VelaQL results or error messages to users who cannot read the Secret.
4. **Server-side request forgery.** Outbound requests made by workflow steps or providers on
   behalf of an application developer must not reach the Kubernetes API server, cloud metadata
   endpoints or cluster-internal services with the controller's credentials.
5. **Admission integrity.** Validation and defaulting webhooks must not be bypassable by
   crafted objects, unusual API versions or conversion paths.
6. **Availability.** A single Application must not be able to hang or crash the controller
   for everyone: unbounded CUE evaluation, recursive references, oversized objects, or
   reconcile storms.
7. **CLI safety against remote content.** Archive extraction, template rendering and file
   writes driven by registry or URL content must not escape the intended directory or execute
   fetched content.

## Configuration that changes the model

Much of KubeVela's security posture is set by Helm values and controller feature gates, not
by code paths alone. Rate findings against the **default install** below, and state in every
report which of these settings the finding needs, and whether the hardened posture
(`authentication.enabled=true` with `withUser=true`, plus
`authorization.definitionValidationEnabled=true`) prevents it. A finding that only exists
under a non-default, less secure setting is low. A finding that survives the hardened
posture is rated at full severity.

| Setting | Default | What it changes |
|---|---|---|
| Controller RBAC (`charts/vela-core/templates/kubevela-controller.yaml`) | Bound to `cluster-admin` when `authentication.enabled=false`; bound to the scoped `:manager` ClusterRole when true, which still holds `impersonate`, full `core.oam.dev`, and Secret write | Every "controller does X for a tenant" at default is a full-cluster impact. The scoped role is in scope for over-permission. |
| `authentication.enabled` → `AuthenticateApplication` gate | `false` | On: resources are applied by impersonating the Application's creator, so tenant RBAC bounds the result. |
| `authentication.withUser` | `true` | `false` impersonates `authentication.defaultUser` (`kubevela:vela-core`) for everyone. Findings that need `withUser=false` are low. |
| `authentication.groupPattern` | `kubevela:*` | Which of the creator's groups are impersonated. Bypassing the pattern to gain a group is high. |
| `authorization.definitionValidationEnabled` → `ValidateDefinitionPermissions` gate | `false` | On: a tenant may reference only definitions their RBAC grants. Bypasses are high. |
| `RestrictDefinitionNamespaces` gate | `true` | Enforces a definition's `spec.restrictions` or restrict-namespaces annotation at admission. A no-op until a definition declares one; bypasses are findings at default. |
| `admissionWebhooks.enabled` | `true` | Validation and defaulting webhooks. Findings that need webhooks disabled are low; webhook bypass with them enabled is high. |
| `DisableReferObjectsFromURL` gate | `false` | By default `ref-objects` may fetch manifests from URLs. This is an SSRF and supply-chain surface open to application developers at default. |
| `workflow.enableExternalPackageForDefaultCompiler` | `true` | CueX external packages (`Package` objects backed by HTTP providers) are available to the default compiler. Creating a `Package` is a platform action; what a tenant can reach through one is in scope. |
| `multicluster.enabled`, `multicluster.clusterGateway.secureTLS.enabled` | `true`, `true` | cluster-gateway is installed; managed-cluster credentials live in Secrets in `vela-system`. |
| `EnableCelExpressions`, `RequireCelExpressionOptIn` gates | `false`, `true` | When on, `$( )` expressions in Application properties are parsed and evaluated. A new parser surface fed by tenant input; findings here need the gate stated. |
| `EnableGlobalPolicies`, `EnableApplicationScopedPolicies` gates | `false` | Platform-authored policies transform Applications before rendering. Interactions where tenant input changes what a transform does are in scope when on. |
| `EnableAddonComponent` gate | `false` | Lets an Application component install an addon. When on, a tenant triggering an addon install is a privilege question. |
| `ApplyResourceByReplace`, `LegacyResourceOwnerValidation` gates | `false`, `false` | Change how existing resources are adopted or overwritten. Findings that need the legacy owner validation are low. |
| `sharding.enabled` | `false` | Multiple controllers scheduled by annotation. When on, the scheduling annotation on an Application is tenant-controlled. |
| `concurrentReconciles`, `kubeClient.qps`, `kubeClient.burst` | `4`, `400`, `600` | The baseline for judging whether a single Application can starve the controller. |

Feature gates are set through `featureGates.*` in Helm values or `--feature-gates` on the
controller; the full list with defaults is in `pkg/features/controller_features.go`.

## Severity

Assume the default install described above, and state clearly when a finding requires a
non-default feature gate or value, or survives the hardened posture.

| Severity | Examples |
|---|---|
| Critical | Remote code execution in the controller or webhook from Application content. A namespace-scoped user obtaining cluster-admin or taking over another tenant's workloads with the hardened posture enabled. Exfiltration of cluster-gateway credentials to a non-administrator. Template escape that also defeats impersonation. |
| High | Template escape at default posture. Cross-namespace read or write of Secrets or ConfigMaps by an application developer with the hardened posture enabled. SSRF that reaches the API server or metadata endpoints with controller credentials, including through `ref-objects` URLs at default. CLI code execution or path traversal from addon registry or URL content. Webhook bypass with webhooks enabled. Secret values appearing in status, events or logs readable by non-administrators. Over-permission in the scoped `:manager` ClusterRole beyond what the controller uses. |
| Medium | Controller denial of service from a single tenant's Application. Information disclosure of non-secret data across namespaces. CLI issues that need a malicious local file. SSRF limited to unauthenticated internal endpoints without controller credentials. |
| Low | Issues that require cluster-administrator privileges to trigger. Hardening suggestions. Missing rate limits without a demonstrated impact. |

Dependency vulnerabilities count only when a reachable path through KubeVela is shown.
Bugs that need a malicious X-Definition count only if the definition author is not already
able to achieve the same effect by design.

## How to exercise the project offline

- The checkout is at `/src`. Binaries: `/usr/local/bin/manager` (controller),
  `/usr/local/bin/vela` (CLI), `/usr/local/bin/kubectl-vela`.
- `KUBEBUILDER_ASSETS` points at envtest binaries (kube-apiserver, etcd, kubectl), so any
  test using controller-runtime envtest runs offline. The controller tests under
  `pkg/controller/...` and the webhook tests under `pkg/webhook/...` start a real API server.
- Baseline test commands, mirroring `make unit-test-core`:

  ```sh
  go test $(go list ./pkg/... ./cmd/... ./apis/... | grep -v apiserver | grep -v applicationconfiguration)
  go test $(go list ./references/... | grep -v apiserver)
  ```

- Rendering can be exercised with no cluster at all: `vela dry-run -f app.yaml -d def.cue`
  renders an Application against local definitions, and `vela def vet def.cue` validates a
  definition. Many template-level issues reproduce this way. The `No usable kubeconfig`
  message these commands print is expected here; it only means external CueX packages were
  not loaded from a cluster.
- `GOPROXY=off` and `GOSUMDB=off` are set. Reproducers must build from the module cache.

Environment notes the baseline depends on:

- The `kube-apiserver` under `KUBEBUILDER_ASSETS` is a wrapper that adds
  `--advertise-address=127.0.0.1 --endpoint-reconciler-type=none`. Without the first flag the
  API server cannot pick an address in a container that has no default route; without the
  second it refuses a loopback advertise address. Keep the wrapper if you copy or replace the
  envtest binaries.
- etcd logs `failed to detect default host` and the container hostname does not resolve. Both
  are harmless; etcd listens on loopback regardless.
- `/root/.kube/config` points at a closed port on purpose. The shared client code resolves a
  REST config with a loader that exits the process silently when no kubeconfig exists, and
  several unit tests reach it through the CueX default compiler. With a resolvable but
  unreachable config, the failure becomes a logged error and the tests run. Do not remove it;
  if you need to prove behaviour with no kubeconfig at all, set `KUBECONFIG` to a missing
  path for that one command, as `pkg/cue/cuex/compiler_guard_test.go` does.
- `GOFLAGS` skips ten tests that need Docker or the network: `TestGenSdk` and
  `TestNewDefinitionGenAPICommand` (run the OpenAPI generator through `docker`), and
  `TestAuthn`, `TestImageRegistry`, `TestHelmRepository`, `TestHelm`, `TestLoadRepo`,
  `TestHTTPGetKubernetesObjects`, `TestCueXEval`, `TestGenerateTerraformCapabilityProperties`
  (public registries, Helm repositories, cuelang.org or GitHub). They are not findings.
- The `TestCli` suite in `references/cli` reports exactly three failing specs offline, all in
  `addon_suite_test.go`: the two "addon is not installed locally, but in registry" status
  specs and "should print fluxcd in the registry as disabled". Each fails on a DNS lookup of
  `kubevela.github.io`. They are expected and are not findings; the rest of the suite is the
  CLI baseline. Everything else in the two baseline commands is expected to pass offline.
- To see envtest's own stderr when a suite fails to start, set
  `KUBEBUILDER_ATTACH_CONTROL_PLANE_OUTPUT=true`.

Preferred reproducer: a Go test, envtest-based where a controller or webhook is involved, or
a `vela dry-run` invocation for render-level issues. Preferred patch: a unified diff against
`master` that keeps the existing tests passing.

## Out of scope and things to leave alone

- Directories `e2e/`, `test/`, `hack/`, `docs/`, `design/`, `vela-templates/` and generated
  files (`zz_generated*`, `*.pb.go`, chart CRD YAML under `charts/vela-core/crds`).
- Definitions that intentionally apply arbitrary manifests (`k8s-objects`, `raw`) doing so
  for a user who is allowed to use them.
- Over-permissive defaults a cluster administrator chooses in Helm values. Chart RBAC
  templates themselves are in scope if they grant more than the controller needs.
- Deprecated `ApplicationConfiguration` compatibility code, which is excluded from the test
  suite.
- Findings that reduce to "CUE templates are Turing-complete and run in the controller".
  That is the product; the boundary is who may author them.
