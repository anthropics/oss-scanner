# Threat model

## What this project does and where untrusted input enters

engrams is a self-hosted service that runs AI coding agents (Claude Code, Codex) inside
Firecracker microVMs. The orchestrator (TypeScript, `orchestrator/`) is the product
surface: users, API keys, orgs, tasks, Slack/GitHub/Linear integrations, and the Connect
RPC API that the dashboard (`web/`) and the CLI (`crates/engram-cli`, `crates/engram-tui`)
call. The coordinator (`crates/engram-coordinator`) schedules sessions onto hosts over
Postgres. Each host agent (`crates/engram-host-agent`) dials the coordinator and runs the
VMs. Inside each VM, `crates/engram-agentd` runs the agent harness, commands, and file
transfers.

**The guest is hostile.** Everything inside a session VM is attacker-controlled: the
agent follows prompts that can come from untrusted pull requests, issues, Slack messages,
and web pages, and the session image is user-supplied. Treat every byte that comes from a
guest as untrusted. Untrusted input enters in these places:

- **Guest to host channels.** Replies from `engram-agentd` over vsock (the host is the
  client, but the guest controls every response: `crates/engram-agentd/src/proto.rs`,
  `crates/engram-harness-proto`, `crates/engram-transport`), the vsock port relay that
  carries app and preview traffic (`port_relay.rs`, `crates/engram-host-agent/src/proxy_port.rs`),
  file transfer and share paths, the NBD disk path (`crates/engram-host-agent/src/disk_daemon`,
  `crates/engram-host-core/src/nbd.rs`), and the userfaultfd page-fault handler
  (`crates/engram-uffd-handler`). Host memory corruption, path traversal on the host, a
  guest reading another session's disk or memory chunks, and host-side panics or unbounded
  allocation caused by guest input are in scope.
- **The egress proxy** (`crates/engram-egress-proxy`, `crates/engram-egress-proxyd`). All
  guest network traffic goes through a host-side TLS-intercepting proxy that enforces a
  hostname allow-list at SNI and substitutes secret placeholders with real values only for
  the hosts each secret is bound to (`substitute.rs`, `inject.rs`, `policy.rs`, `sni.rs`).
  In scope: reaching a host that is not on the allow-list (SNI/Host mismatch, DNS tricks,
  CONNECT or IP literals, HTTP/2 or WebSocket edge cases), making the proxy put a real
  secret in a request to a host the secret is not bound to, reading a real secret value
  from inside the guest, and the guest gateway (`guest_gateway.rs`, metadata/ADC emulation)
  giving one session another session's tokens.
- **Session images and bundles.** User-supplied OCI images are pulled, flattened, and
  packed into ext4 on the host (`crates/engram-rootfs-materializer`, `crates/engram-oci`).
  Whiteout and tar path handling, symlinks that escape the rootfs during materialization,
  and decompression bombs are in scope. Mount manifests (`crates/engram-mount-manifest`,
  `crates/engram-session-bundles`) and uploaded skill packs are untrusted.
- **Snapshot and chunk storage** (`crates/engram-chunk-store`). Chunks are content
  addressed. A session must not be able to make the host serve it chunks from another
  session, or poison a shared base-image chunk that other sessions read.
- **The orchestrator HTTP surface** (`orchestrator/src/routes`, `orchestrator/src/rpc`,
  `orchestrator/src/auth`, `orchestrator/src/authz`). Authentication (sessions, API keys,
  OAuth and OIDC, the CLI device flow), authorization across orgs (one org reading or
  driving another org's sessions, secrets, or artifacts), webhook signature checks
  (`github-events.ts`, `slack-events.ts`, `linear-events.ts`), and the session-app preview
  proxy and its login wall (`preview-proxy.ts`, `preview-ws.ts`, `orchestrator/src/apps`)
  are in scope. Session output (transcripts, tool calls, artifacts, file names) is shown in
  the dashboard and in Slack, so stored XSS from guest-controlled content is in scope.
- **Secrets at rest** (`crates/engram-crypto`, `orchestrator/src/crypto`). Org secrets and
  integration tokens are envelope encrypted. Leaks of plaintext secrets or tokens into logs,
  events, API responses, transcripts, or the guest are in scope.
- **Host to host and host to coordinator.** Live migration and peer fill
  (`migrate_peer.rs`, `peer_fill.rs`, `crates/engram-uffd-handler/src/peer.rs`) and the
  host registration path. Treat these as authenticated but report a way for a guest to
  reach or influence them.

Trusted: the operator, the Helm/Terraform configuration, environment variables, the
coordinator and orchestrator databases, the cloud KMS and blob store, and admin users.

## Components that matter most / least

- Most important: guest isolation and the egress proxy (`engram-egress-proxy`,
  `engram-egress-proxyd`, `engram-host-agent`, `engram-uffd-handler`, `engram-host-core`,
  `engram-sandbox-firecracker`), then orchestrator authentication and org authorization,
  then secret handling.
- Also in scope: `engram-agentd` (a bug there matters when it lets the guest affect the
  host or another session; the guest already has root in its own VM), the rootfs
  materializer, the chunk store, the coordinator's gRPC and HTTP APIs, the CLI's credential
  store (`crates/engram-app-client`), and the web dashboard.
- Less important: `engram-sandbox-process` (a dev-only backend with no isolation, by
  design), `engram-sandbox-vz` (macOS development only; it builds as an empty crate on Linux),
  `engram-secrets-dev`, `engram-storage-local`, `engram-git-dev`.
- Out of scope: `site/` (static docs), `deploy/terraform`, `deploy/dev`, `scripts/`,
  `docs/`, `crates/engram-sim`, `crates/engram-dst*`, `crates/engram-testkit`, test
  fixtures, `third_party/` (the Firecracker fork is a separate repository), and third-party
  crates and npm packages unless engrams uses them in an unsafe way.

## How to exercise it

- Rust binaries and unit-test binaries are built in `/src/target/debug`. Integration
  tests compile on demand (all crates are fetched).
  Rebuild offline with `cargo build --offline --locked --workspace`. Run tests with
  `cargo nextest run --offline --locked -p <crate>`. Use nextest, not `cargo test`: some
  tests set environment variables that are read once per process, so they need one
  process per test.
- Postgres is installed. Start it with `service postgresql start`. Tests marked
  `#[ignore]` that need Postgres read `ENGRAM_TEST_DATABASE_URL` (already set) and clone a
  fresh database per test: `cargo nextest run --offline -p engram-coordinator --run-ignored only`.
- The egress proxy has extensive unit tests: `cargo nextest run --offline -p engram-egress-proxy`.
  They are the fastest way to try allow-list and substitution bypasses.
- Orchestrator: `cd orchestrator && bun test <path>` and `bun run typecheck`. Web:
  `cd web && pnpm test`.
- No `/dev/kvm` is available in this image, so the Firecracker integration tests
  (`crates/engram-sandbox-firecracker/tests`) cannot run. Reason about the guest to host
  protocols from the code and the unit tests.

## How you rate severity

- Critical: guest to host escape or code execution on the host; one session reading or
  writing another session's disk, memory, or secrets; unauthenticated access to the
  orchestrator or coordinator API; one org taking over another org's sessions; a real
  secret value reaching the guest or a host it is not bound to.
- High: egress allow-list bypass; cross-org data read through the API; authentication
  bypass on the session-app preview login wall; stored XSS in the dashboard from guest
  content; webhook signature bypass that starts agent runs; plaintext secrets in logs or
  events.
- Medium: denial of service of a host agent, the coordinator, or the orchestrator from
  guest or unauthenticated input (panics, hangs, unbounded memory); a guest affecting other
  sessions on the same host through shared resources; information leaks about other
  sessions (ids, image names) without their content.
- Low: issues that need admin rights, operator configuration, or the dev-only backends;
  denial of service of a session by its own guest.

## Anything to leave alone

- Do not report that the agent can run arbitrary code inside its own VM, or that the guest
  has root there. That is the product.
- Do not report that `engram-sandbox-process` gives no isolation, or that the dev stack
  (`just dev`, `deploy/dev`, open registration, the seeded dev API key) is insecure.
- Do not report that the egress proxy intercepts TLS. The guest trusts the host's proxy CA
  by design, and the signing key never leaves the host. Problems in how it does so are in scope.
- Do not report that an allowed host can receive whatever the agent sends it. The operator
  chose the allow-list.
- Proposed patches should keep wire formats and on-disk formats stable unless the fix needs
  a change, and should say so when they change one.
