# NetBird threat model

NetBird is a WireGuard-based overlay network with a control plane. Organisations
use it to connect laptops, servers, and containers into private networks governed
by access policies, either self-hosted or through NetBird Cloud. A flaw can expose
private networks to outsiders, let one tenant or peer reach another, or give a
local user root on every machine running the agent.

## Components and trust boundaries

- **Agent** (`client/`): runs on user machines as a privileged daemon (root on
  Unix, LocalSystem on Windows). It manages the overlay interface, routing,
  firewall rules (nftables, iptables, userspace filter), DNS, the embedded SSH
  server, and Rosenpass. The CLI and desktop UI talk to it over a local gRPC API
  (`client/proto/`, served by `client/server/`) on a Unix socket or Windows named
  pipe. **This daemon IPC is a privilege boundary**: any local user may connect,
  every RPC field is untrusted, and caller identity comes only from the kernel via
  `client/internal/ipcauth`.
- **Management** (`management/`): the multi-tenant control plane. It exposes a
  REST API (`management/server/http/`, schema in
  `shared/management/http/api/openapi.yml`) authenticated by IdP JWTs or personal
  access tokens, and a gRPC API (`shared/management/proto/`) that peers use to
  register (setup keys or SSO), log in, and receive network maps. It evaluates
  policies, groups, posture checks, routes, DNS settings, and SSH access.
- **Signal** (`signal/`): brokers connection offers and ICE candidates between
  peers. Payloads are end-to-end encrypted between peers; signal must not be able
  to read them, and a peer must not be able to impersonate another peer through it.
- **Relay** (`relay/`, `shared/relay/`): forwards traffic between peers that cannot
  connect directly. Access is gated by HMAC tokens issued by management.
- **Proxy** (`proxy/`): identity-aware reverse proxy exposing services and LLM
  endpoints (Agent Network). It authenticates users (OIDC, password, PIN), applies
  access restrictions, and enforces budgets and model restrictions on LLM traffic.
- **Combined** (`combined/`): a single binary bundling management, signal, and relay.

### Attackers to consider

- An unauthenticated remote attacker reaching management, signal, relay, or proxy
  over the network.
- A local unprivileged user on a machine running the agent, talking to the daemon.
- A malicious or compromised enrolled peer, trying to reach resources its policies
  do not allow, impersonate another peer, or affect another peer's network map.
- A user or API token holder with limited permissions in one account, trying to
  escalate within the account or read or modify another account (tenant).
- A malicious peer sending crafted traffic over the overlay to another peer's agent
  (DNS forwarder, embedded SSH server, userspace forwarder, packet filter).

Operators, their configuration files, their identity provider, and the management
server itself (from the agent's point of view) are trusted. An attack that requires
admin credentials or host root is generally out of scope unless it crosses a
tenant boundary.

## Security properties and areas of interest

- **Local privilege escalation through the daemon.** Daemon RPCs must not let an
  unprivileged caller read or write root-owned files, fetch attacker-chosen URLs as
  root, change the management URL or SSH root login, or otherwise act as root.
  Inspect path handling (`ipcauth.OpenOwnedFile`), URL allowlists, and identity
  gates. Identity lookup failure must deny.
- **Peer authorization.** Network maps sent to a peer must contain only the peers,
  routes, and DNS records its policies grant. Check incremental updates, group and
  policy changes, posture checks, peer expiry and approval, and route/exit-node
  selection for stale or over-broad state.
- **Packet filtering on the agent.** Firewall rules derived from policy must
  enforce what the policy says in kernel, userspace, and netstack modes, for IPv4
  and IPv6. Look for rule-generation bugs that fail open.
- **Account isolation and RBAC in management.** Every REST handler and store query
  must scope to the caller's account and check permissions
  (`management/server/permissions/`). Check both store backends (GORM and pgx).
- **Credential handling.** Setup keys, PATs, JWT validation (issuer, audience,
  expiry), relay tokens, SSH JWT auth, and proxy sessions must enforce their
  lifetime, scope, and revocation.
- **Peer identity.** A peer must not be able to register or log in as another peer,
  take over another peer's IP, or hijack signal or relay sessions.
- **Proxy access control.** Authentication and restriction checks must not be
  bypassable, and Agent Network budgets and model restrictions must not be
  circumvented.
- **Memory safety and parsing** in packet handling (`client/firewall/uspfilter`,
  DNS, the userspace forwarder) where peers supply the input.

## Building and testing in this image

The checkout is at `/src`. Binaries are installed in `/usr/local/bin`: `netbird`
(agent), `netbird-mgmt`, `netbird-signal`, `netbird-relay`, `netbird-proxy`, and
`netbird-server` (combined). Go, module dependencies, and a warm build cache are
kept; `GOTOOLCHAIN=local`, `GOPROXY=off`, and `GOSUMDB=off` prevent downloads.

Host-safe unit tests:

```sh
cd /src
go test -tags devcert ./management/...
go test -tags devcert ./client/server/... ./client/internal/ipcauth/...
```

Tests without `-tags devcert` skip cases that need the development certificate.
`client/ui` is not built (it needs a separate frontend build). Tests tagged
`privileged` change host networking and normally run in a container with
`NET_ADMIN`; tests using Docker (testcontainers, dockertest, MySQL/Postgres/Redis
backends, `e2e/`) are not provisioned here and will skip or fail. Prefer the
SQLite store and in-process servers for reproducers; the management test suites
show how to stand up a real account, store, and gRPC server in memory.

`AGENTS.md` in the repository describes conventions, security rules (fail closed,
daemon RPC input is untrusted), and package layout. Read it and the scanned
revision's source rather than assuming paths stay fixed.

## Severity

Rate on demonstrated impact and realistic prerequisites:

- **Critical**: unauthenticated remote code execution; unauthenticated or
  cross-tenant access to management data or control; a peer gaining network access
  to other peers or networks that policy denies, at scale; authentication bypass in
  management, proxy, or embedded SSH.
- **High**: local privilege escalation to root through the daemon; a peer or
  limited user escalating privileges within its own account; peer impersonation;
  policy or firewall rules failing open for specific traffic; credential or private
  key disclosure.
- **Medium**: remote denial of service against management, signal, relay, or proxy
  that a single attacker can trigger cheaply; information disclosure of metadata
  (peer lists, IPs, hostnames) outside the caller's authorization.
- **Low**: issues requiring admin credentials or host root, local denial of
  service, and hardening gaps without a demonstrated exploit path.

## Reports

Each report should name the scanned commit, the component, the attacker's starting
position, and the full path to impact. Include a deterministic reproducer (a Go
test is ideal), expected versus actual behaviour, and a focused patch with a
regression test where possible. Group findings that share a root cause.

## Out of scope

- NetBird Cloud and other hosted infrastructure (report those to
  security@netbird.io separately).
- The dashboard, which lives in a separate repository, and `client/ui` frontend code.
- Test helpers, mocks, `e2e/`, `integration_tests/`, `tools/`, and
  `infrastructure_files/` unless they ship in a release and are reachable.
- Vulnerabilities in third-party dependencies unless reachable through NetBird
  code paths; explain the reachability.
- Debug or development-only behaviour (for example the `devcert` build tag).
