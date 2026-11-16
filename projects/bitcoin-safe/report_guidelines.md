# Bitcoin Safe — security report guidelines

Prefer concise, actionable reports with **one independently fixable root cause**
per finding. A clear fund-loss or wallet-integrity impact is more valuable than
broad speculative claims. Do not publish vulnerability details as public issues.

Use these sections:

1. **Title & severity** — component, security consequence, proposed severity.
2. **Executive summary** — two or three sentences naming the actual security
   boundary crossed and the realistic user consequence.
3. **Affected code** — current branch/commit, precise file(s), function(s),
   line range(s), and relevant settings/platform/backend.
4. **Attacker prerequisites** — remote peer/server, malicious file or PSBT,
   local file access, installed plugin, user confirmation, or physical signer.
5. **Root cause and trace** — untrusted input -> affected parser/handler ->
   trust-boundary crossing -> observable impact; distinguish this project from
   third-party implementation defects.
6. **Deterministic reproducer** — exact isolated commands/fixture and expected
   vs. observed outcome. Use regtest, synthetic data and offline mocks.
7. **Impact and limits** — fund-loss conditions, wallet integrity, metadata
   exposure, crash/DoS; clarify mitigating hardware-device confirmations.
8. **Recommended fix** — smallest defensible change and regression test(s).

For each report, state whether the exploit succeeds without authentication,
requires the user to import/open something, requires plugin installation, or
requires privileged local access. Identify assumptions explicitly. Do not
invent wallet seed exposure from a watch-only implementation.

A PoC should contain no real wallet seeds, private user data or irreversible
network actions. If a BIP39 mnemonic is needed for a reproducible test, use
only the **public `bacon` × 24 mnemonic** defined in `threat_model.md`
(and only on regtest). Prefer a small Python/pytest reproduction. A proposed patch
should be called *proposed* until verified by tests and maintainer review.

Deduplicate by underlying defect/mitigation; give several concrete paths in
one report where a single fix resolves all of them. Do not combine unrelated
issues just because they occur in the same module. Do not report lint-only,
unsupported-platform or non-security test failures as vulnerabilities.
