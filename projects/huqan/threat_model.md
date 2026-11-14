# HUQAN threat model (for the scanner)

HUQAN sits on the execution path of an AI agent. It classifies a proposed action,
allows it, holds it for a human, or blocks it, and records every decision as a
verifiable Trust Receipt. The product is local-first: no model, no cloud, no API
key. The scanner's value here is the gate, the stores and the receipt verifier —
the code that decides whether an action runs.

## What this project does and where untrusted input enters

- An **AI agent** is the untrusted principal. Its tool calls (shell, git,
  infrastructure, memory writes, MCP calls, A2A exchanges) are untrusted input to
  the gate. The whole premise of the product is that the agent must not be able to
  approve its own protected action.
- An **HTTP/REST caller** to `server.js` and the **MCP client** to `mcpServer.js`
  are untrusted. Request bodies, headers, tool arguments and ingest payloads are
  untrusted input.
- **Memory content and claims** ingested from any source are untrusted until the
  admission gate scores them; provenance is attacker-controlled.
- **Files on disk** that the runtime reads — config, policy, plugin manifests,
  receipts, the authority pin — are trusted only to the degree their location is
  trusted (see below).

## Components that matter most

- **Action gate and risk classification:** `lib/agent-action-firewall.js`,
  `lib/action-risk-classifier.js`, `lib/tool-call-gate.js`,
  `lib/mcp-gate-adapter.js`, `lib/command-exec-gate.js`,
  `lib/external-action-guard*.js`, `lib/code-change-gate.js`. A bypass here is the
  worst outcome the product can have: a protected action runs unapproved.
- **Approval authority:** `lib/authority/*`, `lib/approval-flow.js`,
  `lib/human-oversight-approval-runtime*.js`. The invariant is that a decision
  admitting a protected action carries an envelope signed by a pinned authority
  under its own OS user; the agent's user cannot mint one. On POSIX the pin path
  trust (`lib/authority/posix-path-trust.js`) refuses a pin the agent could rewrite.
  The design is **fail-closed**: with no installed authority, or inside a container
  (a container is no OS boundary, ADR-021), the runtime refuses and reports
  `AUTHORITY_UNAVAILABLE` rather than falling back.
- **Path and sandbox boundaries:** `lib/path-safety.js`,
  `lib/sandbox-isolation.js`, `sandboxRunner*.js`. Workspace escapes are in scope.
- **Trust Receipts and provenance:** `lib/verify.js`, `lib/receipt/*`,
  `lib/trust-evidence-ledger.js`, `lib/receipt-chain-order-matches-stamp` paths.
  Receipt chain ordering, stamping and tamper detection are in scope; a receipt
  that verifies when it should not is a finding.
- **Plugin loader:** `plugin.js`, `lib/plugin-verification.js`. Manifest hash and
  HMAC verification, and production enforcement, are in scope. Note the documented
  boundary: **signed is not sandboxed** — a verified plugin still runs as
  in-process Node with full host privileges (`docs/core-plugin-boundary-contract.md`).
  Do not report "a plugin can require fs" as a vulnerability; report a way to get an
  unverified or tampered plugin loaded, or to defeat the hash/signature check.
- **Memory admission:** `lib/memory-admission-gate.js`, `lib/semantic-score.js`,
  `lib/trust-score-aggregator.js`, `lib/memory-mutation-gate/`.

## Components that matter less / out of scope

- The web UI under `public/` is a local operator console, not a multi-tenant
  service. Self-XSS in the operator's own browser, on their own machine, is not a
  finding unless it leads to a privileged action the gate would otherwise refuse.
- `benchmarks/`, `demo/`, `docs/`, and the `test/` corpus are not the shipped
  attack surface. A flaw that only reproduces with a fixture is not a finding.
- The `nlp/` language packs and the local semantic-model artifacts are data, not
  parsers of untrusted input; a bad score is a correctness bug, not a CVE.
- **Out of scope by design:** anything that requires the agent and the operator to
  share an OS user *and* an installed authority to already be broken; anything that
  assumes the OS, the Node runtime, or `npm` dependencies are compromised; anything
  that assumes the operator voluntarily runs an unsigned plugin with enforcement
  disabled. `THREAT_MODEL.md` at the repo root states these boundaries in full —
  treat its "accepted property" notes as non-findings.

## How to exercise it

- `node scripts/run-tests.js <file...>` runs `node --test` against a throwaway
  state root (`scripts/run-tests.js` → `scripts/test-state-sandbox.js`), so tests
  never touch a live gate state. `npm test` runs the whole suite.
- The MCP surface: `node bin/huqan-mcp.js`; the gate adapter is
  `lib/mcp-gate-adapter.js`. The risk classifier is pure and easy to drive directly
  (`lib/action-risk-classifier.js` takes a call and returns a decision).
- The gate is exercised end to end by `node cli.js` subcommands
  (`huqan gate`, `huqan approve`, `huqan verify`); `huqan quickstart` is the
  30-second tour.
- Note for the scanner environment: the approval authority is **fail-closed inside
  a container**. Tests that assert the approval flow in-process work; tests that
  require a real installed authority to be reachable will report
  `AUTHORITY_UNAVAILABLE` and that is correct behaviour, not a bug (ADR-020, #4494).
- `SECURITY_INVARIANTS.md` maps the seven invariants to the tests that prove them;
  `npm run check:security-invariants` holds the mapping honest.

## How we rate severity

- **Any way to make a protected action run without an approved decision is
  critical**, regardless of how narrow: gate bypass, forged approval envelope,
  authority pin the agent can rewrite, emergency-stop bypass, receipt that admits
  a mutation the gate refused.
- **A path-escape from the authorized workspace root, or an unverified plugin
  load, is high.** A receipt-chain integrity break (reordering or restamping
  material that then verifies) is high.
- **Untrusted content promoted to canonical memory without an admission decision
  is high**; a scoring weakness that changes a verdict is medium unless it reaches
  a gate decision, in which case it follows the gate.
- **Denial of service on a local, single-operator process is low to medium.** The
  gate runs on the operator's own machine; "the operator's own agent can exhaust
  the operator's own memory" is not high. Reaching it *before* the gate decision,
  so the gate never runs, is high.
- **Post-auth issues do not exist here**: there is no auth boundary between the
  operator and their own runtime. Do not rate an operator-level issue as if it were
  a privilege boundary the product claims to enforce.

## Anything to leave alone

- Do not report the documented "signed is not sandboxed" plugin property, the
  absence of a numeric per-tool privilege level, or the trust-source allowlist gap;
  all three are written up in `THREAT_MODEL.md` as known and accepted, with reasons.
- Do not report the container `AUTHORITY_UNAVAILABLE` behaviour as a defect — it is
  the fail-closed design (ADR-021).
- Do not report Windows/`os-service` escalation notes that `huqan doctor` already
  surfaces in its `escalation` field; the product reports them rather than assuming
  the boundary holds (ADR-020 §11).
