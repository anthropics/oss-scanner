# OpenNHP — threat model for the OSS Scanner

## What OpenNHP is

OpenNHP is a Go implementation of a Zero Trust "network-infrastructure
hiding" architecture (NIST ZTA aligned). It implements two protocols:

- **NHP (Network-infrastructure Hiding Protocol)** — hides server ports, IPs
  and domains behind a single-packet-authorization "knock". Until a client
  proves identity, the protected service is not reachable (default-drop).
- **DHP (Data-content Hiding Protocol)** — data protection via encryption /
  confidential computing (the `nhp-db` data broker and `kbs/` key-broker
  code).

All on-wire NHP messages are authenticated and encrypted with the Noise
Protocol Framework over UDP. Two cipher suites exist and are security-equal
targets: `CIPHER_SCHEME_CURVE` (Curve25519 + AES-256-GCM + BLAKE2s) and
`CIPHER_SCHEME_GMSM` (SM2 + SM4-GCM + SM3).

## Components and processes

- `endpoints/server` — **nhp-serverd**, the authenticator/authorizer. Highest
  value. Terminates the Noise handshake, runs auth plugins, drives the AC.
- `endpoints/ac` — **nhp-acd**, the access controller that opens/closes the
  firewall for an authorized client.
- `endpoints/relay` — **nhp-relayd**, a public HTTPS→UDP bridge that lets
  browser ("JS web agent") traffic reach the server as `NHP_RLY` envelopes.
- `endpoints/agent` — **nhp-agentd**, the client that sends knocks and runs
  interactive OTP→REG enrollment.
- `endpoints/db` — **nhp-db**, DHP data broker; `endpoints/server/kbs` — key
  broker service.
- `nhp/core` — the protocol core: packet parse, Noise handshake, replay/flood
  gates, cookie logic, cipher suites. A bug here affects every daemon.

## Trust boundaries & where untrusted input enters

Rank findings by proximity to these entry points:

1. **The UDP knock port on nhp-serverd / nhp-acd (highest).** Fully
   unauthenticated, Internet-facing, attacker-chosen bytes. Everything in
   `nhp/core` reachable before `validatePeer` succeeds is pre-auth attack
   surface: header/packet parsing (`nhp/core/packet.go`, `responder.go`),
   magic/length checks, the cookie path under overload, and the
   replay/flood/threat-block state machine. Memory-safety is largely Go's
   job, but look hard at: slice bounds on parsing attacker-sized fields,
   nil-dereference on malformed packets, unbounded allocation/CPU per packet
   (DoS amplification), integer handling of length/counter fields, and any
   place a single source can drive expensive crypto (ECDH) before a cheap
   check rejects it.

2. **The relay HTTPS ingress (`endpoints/relay`, high).** `POST /` accepts an
   unauthenticated request body that the relay wraps into an authenticated
   `NHP_RLY` envelope and forwards to the server over a shared UDP
   connection. Treat the HTTP boundary and the shared-connection
   multiplexing model as untrusted: availability issues where one client (or
   unauthenticated request) degrades the shared relay→server path for other
   users are in scope and should be rated on availability impact. (A prior
   issue of exactly this shape — GHSA-674q-j8fh-972c — was fixed by exempting
   multiplexed `NHP_RLY` from per-connection replay/flood gates; regressions
   or sibling cases are valuable.)

3. **`NHP_RLY` inner packets & SourceAddr handling (high).** The server
   decodes a relay-supplied `SourceAddr` and re-injects the inner packet
   keyed by the claimed real-client address (`endpoints/server/msghandler.go`,
   `HandleRelayForward`). Look for spoofed/fabricated SourceAddr leading to
   connection-map poisoning, cross-client state corruption, or bypass of
   per-client rate/replay isolation.

4. **Config & peer files (`etc/*.toml`), and the `xdp.toml` whitelist.**
   Operator-controlled, lower trust, but parsing bugs that fail *open* matter
   — e.g. the eBPF/XDP ingress filter is fail-open by design, and an empty or
   malformed relay whitelist must refuse to attach rather than close SSH for
   everyone. Flag fail-open-to-exposure regressions.

5. **demoapp (`demoapp/`, medium/contextual).** An example web app
   (password/OIDC/GitHub login, session cookies, per-user NHP key sealing).
   Standard web surface: authn/session, CSRF, the OTP email path, key-at-rest
   sealing (`KeyEnvelopeKey`). It is a demo, not a shipped product — rate web
   findings accordingly unless they reveal a core-library flaw.

## Out of scope / lower priority

- The public demo's **keys are intentionally demo keys** (committed/rendered
  for `server.opennhp.org`); "hardcoded secret" findings on demo material are
  not interesting. Real deployments generate their own keys.
- `terraform/`, `.github/`, `deploy/`, `docker/` — infra/CI, not the shipped
  binaries. Report only if they expose a credential or materially weaken a
  default users inherit.
- Example plugins under `examples/` are references, not production auth.
- Availability of a *single-tenant* self-hosted server from its own operator
  is not a vulnerability; cross-tenant / cross-client impact is.

## Severity guidance

- **Critical:** pre-auth RCE/memory corruption in a daemon; authentication or
  Noise-handshake bypass (knock without valid identity); private-key
  disclosure; cross-client data exposure via the relay.
- **High:** pre-auth remote DoS reachable from the Internet that denies
  service to *other* clients (not just self), especially via the shared relay
  path; replay/anti-flood bypass; SourceAddr spoofing that corrupts shared
  server state; auth-plugin loading that admits an unauthenticated peer.
- **Medium:** post-auth or operator-triggered issues; fail-open config
  regressions that widen exposure under a plausible misconfiguration; demoapp
  authn/session/CSRF.
- **Low / informational:** issues requiring an already-privileged operator,
  demo-only material, or defense-in-depth hardening with no concrete break.

## What good reports look like

Please include a reproducer against a locally-built daemon (the Dockerfile
produces unstripped binaries in `/out`). For `nhp/core` parsing/handshake
findings, a failing Go test or a crafted-packet harness under `nhp/test` is
ideal. Patches that preserve both cipher suites (CURVE and GMSM) and keep the
native-peer vs. relay-multiplexed distinction intact are strongly preferred.
