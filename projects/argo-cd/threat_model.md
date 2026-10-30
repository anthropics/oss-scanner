# Argo CD threat model

Argo CD is a declarative GitOps continuous delivery tool for Kubernetes. It watches Git, Helm and OCI
repositories, renders Kubernetes manifests from them, and syncs those manifests into one or more
Kubernetes clusters. It holds credentials for those clusters and for the repositories, so a flaw can
lead to cluster takeover or credential theft across many environments.

Project security policy: https://github.com/argoproj/argo-cd/blob/master/SECURITY.md
Operator security notes: `docs/operator-manual/security.md`, `docs/operator-manual/applicationset/Security.md`

## Components and where untrusted input enters

All components are built from one binary (`cmd/main.go`) and selected by name.

- **argocd-server** (`server/`, `util/session`, `util/oidc`, `util/rbac`, `util/settings`): gRPC and
  REST/gRPC-gateway API, the web UI, SSO login/callback/logout, webhooks (`util/webhook`), and the
  application and terminal proxies. This is the main network-facing component. Treat every HTTP/gRPC
  request, header, cookie, JWT, OIDC response and webhook payload as attacker-controlled.
- **argocd-repo-server** (`reposerver/`, `util/git`, `util/helm`, `util/kustomize`, `util/app/discovery`,
  `util/io`): clones repositories and renders manifests by running git, helm, kustomize and config
  management plugins. Treat repository *contents* as attacker-controlled: anyone with write access to
  any tracked repository can supply them. It must not escape the repository or application path,
  read other repositories' files or the server's files, or execute arbitrary commands.
- **argocd-application-controller** (`controller/`, `gitops-engine/`): reconciles and syncs resources
  into clusters using stored cluster credentials. Rendered manifests and live cluster state are input.
- **argocd-applicationset-controller** (`applicationset/`): generates Applications from generators
  (Git, SCM providers, pull requests, cluster lists, plugins). Data returned by SCM providers and Git
  is untrusted, and generated Applications must stay within the AppProject constraints.
- **argocd-commit-server** (`commitserver/`): writes hydrated manifests back to Git.
- **argocd-cmp-server** (`cmpserver/`): runs config management plugins as sidecars.
- **argocd-notifications** (`notification_controller/`): sends notifications using templates.
- **CLI** (`cmd/argocd`): runs on user machines and talks to the API server. A malicious or
  compromised API server is a valid attacker for CLI bugs (e.g. local file writes or command execution).
- **UI** (`ui/`, React/TypeScript): renders resource names, annotations, manifests, logs, links and
  other data that originate from Git or from clusters. Stored or reflected XSS through that data is in scope.

## Attackers to consider

- Unauthenticated network clients of argocd-server.
- Authenticated users with limited RBAC permissions: read-only users, users scoped to one AppProject,
  and project-scoped automation tokens. The core security boundary is **RBAC and AppProject
  restrictions** (allowed source repos, destination clusters and namespaces, resource allow/deny lists,
  `sourceNamespaces` for apps in any namespace). Any way for such a user to act outside their
  permissions or project is in scope.
- Users with write access to a Git/Helm/OCI repository that some Application tracks, but no Argo CD
  permissions.
- Senders of webhook requests and responders to outbound requests (SCM APIs, OIDC providers, Helm/OCI
  registries).

## Trusted / out of scope

- Argo CD administrators and anyone who can change `argocd-cm`, `argocd-rbac-cm`, `argocd-secret`,
  `argocd-cmd-params-cm` or the Argo CD namespace. They are fully trusted.
- Anyone with direct Kubernetes API access to create or modify Argo CD CRDs in the Argo CD namespace.
- Config management plugins themselves: they are operator-installed code and can run anything.
- Documented risks in `docs/operator-manual/security.md`, for example that a user with write access to
  a tracked repository can change what gets deployed, or that helm/kustomize may follow remote bases and
  chart dependencies. Report these only if they bypass a documented restriction (e.g. reading files
  outside the repository, escaping AppProject source/destination limits).
- Vulnerabilities in dependencies (helm, kustomize, git, Go modules, npm packages) that are not
  reachable through Argo CD code. Dependency CVEs reported only from a version number are out of scope.
- `test/`, `hack/`, `docs/` and `examples/`, and e2e test fixtures.

## How to exercise it

- Unit tests sit next to the code (`go test ./server/...`, `./reposerver/...`, `./util/...`,
  `./controller/...`, `./applicationset/...`). Many API server tests build an in-memory server with fake
  Kubernetes clients; `server/application/application_test.go` and `server/server_test.go` show how.
- Manifest generation can be driven directly through `reposerver/repository` tests, which have
  fixtures under `reposerver/repository/testdata` and `util/helm/testdata`.
- helm, kustomize and git-lfs are installed at the versions Argo CD ships with.
- The UI's dependencies are installed in `ui/node_modules`; `cd ui && pnpm test` runs its tests.
- There is no Kubernetes cluster in the image. Prefer reproducers as Go unit tests.
- The image runs as root, so tests that expect permission-denied errors (`TestDirectoryPermissionInitializer`,
  `TestInit` and `Test_getPotentiallyValidManifests/unreadable_file_throws_error` in `reposerver/repository`)
  fail there. That is expected and not a finding; Argo CD components run as a non-root user (UID 999) in production.
- The scan has no network access, so tests that fetch remote content (for example `TestGenerateHelmWithURL`,
  which downloads a Helm values file from GitHub) fail. That is also expected and not a finding.

## How we rate severity

We use CVSS 3.1 and publish advisories through GitHub Security Advisories. As guidance:

- **Critical**: unauthenticated remote code execution, authentication bypass on argocd-server, or
  obtaining cluster or repository credentials without authentication.
- **High**: an authenticated low-privilege user (or a holder of a project token) gaining admin
  privileges, deploying outside their AppProject's allowed destinations, sources or resource kinds,
  or reading secrets they are not authorized to see; code execution or arbitrary file read on the
  repo-server driven by repository contents; stored XSS in the UI from repository or cluster data.
- **Medium**: information disclosure of non-secret data across projects, open redirects, CSRF on
  state-changing endpoints, denial of service of a component by an authenticated user.
- **Low**: denial of service that needs administrator-controlled configuration, or issues that need an
  unusual, insecure configuration that the docs warn against.

## How we would like reports

Keep reports short. Please include the affected component, the attacker's required access (none,
read-only user, project member, repository writer), and a reproducer, ideally as a Go unit test.
Please validate impact before reporting, and don't report theoretical issues without a concrete path
from attacker input to impact.
