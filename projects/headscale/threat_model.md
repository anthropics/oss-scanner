# Headscale threat model

Headscale is an open-source, self-hosted implementation of the Tailscale control
server. It registers devices, assigns tailnet addresses, distributes network maps,
evaluates access policies, approves routes, and provides DERP relay coordination.
Incorrect authorization can expose private services or redirect tailnet traffic.

## Scope and trust boundaries

Audit Headscale's runtime code, including authentication, registration, HTTP
APIs (`/api/v1` and `/api/v2`), the local Unix-socket API, credential handling,
node state, policy evaluation, map generation, routes, DNS configuration, embedded
DERP, and persistence. Dependencies may be examined where necessary to prove a
vulnerability reachable through Headscale.
This enrollment does not request a separate audit of the Tailscale client.

Consider unauthenticated remote attackers, compromised or malicious enrolled
nodes, and holders of credentials with limited authorization. Treat client-supplied
registration and map requests, Hostinfo, endpoints, route advertisements, device
names, and other node metadata as untrusted. Check that a node cannot acquire
another node's identity or privileges, bypass policy, or influence another node's
network map outside its authorization.

Operators, their policy/configuration files, and their intended OIDC provider are
trusted. Still examine identity mapping, issuer validation, callback handling, and
authorization checks. Distinguish an attack requiring a full administrator key or
host compromise from one available to an ordinary enrolled node or restricted key.
Do not report intentional access granted by the configured policy as a bypass.

## Security properties and areas of interest

- Device registration, reauthentication, key rotation, expiry, and revocation must
  preserve identity and require the appropriate authorization.
- Tags and user ownership are distinct identities. Follow the ownership rules of
  the scanned revision; where available, `IsTagged()` is authoritative and a user
  ID on a tagged node may record its creator rather than its owner.
- Pre-auth keys, API keys, and OAuth credentials must enforce their configured
  lifetime, reuse, ownership, and scope constraints.
- Peer visibility and packet-filter rules must reflect policy. Inspect policy
  changes, incremental map updates, disconnect/reconnect races, and stale state.
- Route advertisement must not grant route approval. A node must not hijack an
  address, subnet, or exit-node route without the required approval.
- Malicious input must not expose secrets, cross authorization boundaries, or
  cause a practical remote denial of service.

The `State` coordinator, node cache, policy implementation, and mapper are useful
places to trace inputs through to their effect on another client. Consult the
scanned revision's `AGENTS.md` and source rather than assuming package names or
internal architecture remain fixed.

## Offline build and reproduction

The checkout is at `/src`; the server binary is `/usr/local/bin/headscale`.
The image retains Go, source, module dependencies, and build caches. No separate
Tailscale checkout or Docker daemon is installed. `GOTOOLCHAIN=local`,
`GOPROXY=off`, and `GOSUMDB=off` prevent implicit downloads during the audit.

The baseline test command is:

```sh
cd /src
go test -short -p 2 -parallel 2 -timeout 20m \
  -skip '^(TestAPIv2|TestAPIv2OAuthScopes)$' ./hscontrol/...
go test -short -p 2 -parallel 2 -timeout 10m \
  -run '^TestAPIv2$/^GoClient$' ./hscontrol/servertest
```

Image setup logs baseline test failures without aborting the build. Inspect the
test output; a successful image build alone does not prove the tests passed.

Prefer existing unit tests and, where present, `hscontrol/servertest` for
reproducers. That harness connects a real Headscale server to Tailscale's control
client in memory; using it to reproduce a Headscale bug is in scope. Scoped
`go test -race` runs are also supported by the retained Go toolchain and compiler.
Use temporary databases and locally controlled HTTP/OIDC fixtures.

The Docker-based tests in `integration/` require additional infrastructure and
are not provisioned here. Read `cmd/hi/README.md` and `integration/README.md`
before using their runner. PostgreSQL binaries are not installed; PostgreSQL
subtests may skip, so a passing baseline is not evidence of PostgreSQL coverage.
The `TestAPIv2/TSCLI`, `TestAPIv2/Terraform`, and `TestAPIv2OAuthScopes`
compatibility tests require external tools and provider plugins that this image
does not provision. The baseline excludes their parent suites and runs
`TestAPIv2/GoClient` separately against a local server. Check the scanned
revision's test guards before changing exclusions; do not assume the external
client/provider tests were exercised.

## Severity and reports

Base severity on demonstrated impact and realistic attacker prerequisites.
Unauthorized tailnet access, device takeover, credential theft, route hijacking,
or code execution can warrant high or critical severity depending on reachability
and impact. Reproducible remote denial of service is usually medium, with higher
severity requiring evidence of broader impact. A crash in an internal helper or
an artificial test without an attacker-reachable path is insufficient on its own.

Each report should identify the scanned commit, attacker capabilities, affected
configuration, entry point, and complete path to the security impact. Include a
deterministic reproducer, expected versus actual behavior, and a focused proposed
patch with a regression test where possible. Identify dependency-caused findings
separately and explain their Headscale reachability. Deduplicate reports that share
the same root cause.

Hosted Tailscale services, client GUI applications, and production deployments
are outside this enrollment. Build/test-only behavior and intentionally exposed
administrator/debug facilities need a demonstrated path affecting a supported
Headscale deployment to qualify as runtime vulnerabilities.
