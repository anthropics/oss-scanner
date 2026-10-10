# Superstables public client threat model

## Scope and reference

Audit the public Apache-2.0 client at https://github.com/superstables/superstables.
Preparation used client 0.3.1, commit d9a280c9a7ebed04d9c916afcf9093d6b8bbd480.
Enrollment tracks main, so verify assumptions against the checkout you receive.
Read docs/security.md, docs/budget.md, README.md and the relevant rail documentation first.
This threat model guides review; it does not assert the code is secure.
The current client is testnet only and uses test tokens, not real money.

## Actors and assets

The owner approves a single purchase or delegates a bounded budget through their wallet.
The coding agent discovers services and requests or executes permitted purchases.
Treat seller responses, listings, payment challenges, redirects, service descriptions,
RPC responses, hosted approval responses and agent-supplied labels as untrusted.
Consider malicious web pages, remote services and concurrent client processes.
Protect owner authorization, signing keys, agent keys, spend limits, recipient/asset/chain
binding, local approval capabilities, recovery records and accurate payment outcomes.

## Documented boundaries

- In browser-wallet mode, the owner key remains in the wallet. Signing requires owner action.
- Local-wallet mode stores a signing key. Arbitrary code executing as the same OS user
  can read that key; do not report that documented access alone as a new vulnerability.
- Budget mode deliberately gives the agent a spending key. An attacker with that key
  can spend the remaining delegated amount, and move funds held at the agent address.
  EVM and Solana budgets do not restrict recipients by themselves. Tempo has its own
  access-key controls. Verify each rail independently.
- Client spend policy is a software check, not an on-chain constraint on a compromised client.
  Host allow/deny rules use reported agent context and are documented as a convenience.
  A false host label alone is not a newly discovered enforcement bypass.
- The localhost approval URL is a capability for one request. Knowledge of the URL
  does not replace a valid wallet signature. The connected account and signature matter.
- Local budget setup is a trusted step. Its approval link can be completed with another
  owner key, so the owner must check the recorded owner address. Origin checks protect
  against other websites, not arbitrary local programs. Hosted setup has separate checks.
- Hosted approval code is outside this repository. Client validation of hosted responses
  is in scope; claims about unseen server implementation are not demonstrated findings.
- Same-user arbitrary code execution and a malicious wallet/RPC are separate assumptions.
  Describe precisely which trust boundary a proposed attack crosses.

## Review priorities

1. Bind signatures and authorizations to the actual recipient, amount, token, chain,
   nonce and validity window. Check cross-request, cross-chain and cross-rail confusion.
2. Review localhost approval and owner-approval servers for origin/Host handling,
   unauthorized state changes, capability leakage, replay and unsafe rendered input.
3. Check adversarial payment challenges and seller responses for unintended requests,
   unsafe redirects, local-network exposure, header/key leakage and unbounded resources.
4. Review budget grant, buy, revoke and recovery on EVM, Solana and Tempo. Check what
   the chain enforces versus what the client merely displays or assumes.
5. Exercise duplicate buys, interrupted execution, concurrent processes, stale locks,
   replaced files and corrupted state. An uncertain payment must not cause an automatic
   second payment or an unsupported claim that no payment occurred.
6. Review local key/state files, permissions, symlink handling and logs for access beyond
   the documented actor model. Keep keys and approval capabilities out of reports.
7. Validate hosted approval identifiers, amounts, ownership and transaction evidence.
   Distinguish seller delivery, facilitator claims, chain inclusion and chain finality.
8. Review installation/build boundaries and dependencies where an exploit reaches
   client behavior. A dependency advisory alone is not a demonstrated exploit.

Useful entry points include src/core/pay.ts, x402.ts, policy.ts, http.ts, lock.ts,
records.ts, finality.ts, settlement.ts, src/core/signer/, budget/approvals.mjs,
budget/buy-guard.mjs, budget/settlement.mjs, budget/hosted.ts, budget/once.mjs,
and the budget/evm/, budget/solana/ and budget/tempo/ directories.

## Offline environment and existing checks

The checkout and its installed dependencies are in /src. Node 22 and npm are installed.
The image builds the TypeScript client and standalone budget scripts into dist/.
The checkout belongs to the image's node user. The scanner opens a root shell;
run these checks as node so filesystem-permission tests exercise real denial:

```sh
runuser -u node -- env HOME=/home/node npm run typecheck
runuser -u node -- env HOME=/home/node npm run build
runuser -u node -- env HOME=/home/node npm test
```

Run them from /src. Running the suite as root bypasses a permission-denial test.
Inspect Git history as node too, for example
`runuser -u node -- env HOME=/home/node git rev-parse HEAD`.
Git's ownership guard rejects root commands in this node-owned checkout.
The existing default test suite excludes test/live unless SUPERSTABLES_LIVE is set.
Do not set SUPERSTABLES_LIVE. Use existing mocks and local loopback services for proofs.
No production credentials, funded wallets, hosted login or external RPC access is needed.
Do not contact live services, sign owner transactions or attempt real transfers.
The scanner runs without external networking after image preparation.

## Severity and report preferences

Severity should follow demonstrated impact and required privileges. State that current
payments use test tokens; separate current impact from possible future mainnet impact.
Prioritize unauthorized signing/spending beyond the documented grant, key extraction by
an actor without existing same-user access, and reproducible execution of attacker code.
Duplicate payment, false finality, authorization mismatch and remotely triggered denial
of service need their precise preconditions and consequences explained.
Do not inflate severity solely because this is payment software.

For each finding provide the checkout SHA, source locations, affected flow and rail,
attacker capabilities, violated boundary, expected/observed behavior, a minimal offline
reproduction and a proposed focused fix. Explain false-positive checks performed.
Use disposable synthetic keys and state. Redact real keys and approval capabilities.
Deduplicate findings by root cause and identify all affected entry points.
Submit findings privately through the program's report channel, not public issues.
Do not treat a successful scan as a complete payment or smart-contract audit.
