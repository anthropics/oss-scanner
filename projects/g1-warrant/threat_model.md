# Threat Model: G1-Warrant

## What this project does and where untrusted input enters
G1-Warrant is a deterministic remediation, eBPF workload containment, and cryptographic attestation control plane for Kubernetes and Cilium. It enforces pre-negotiated dual-human DSSE standing warrants before executing changes or triggering containment bridges, sealing NIST OSCAL 1.1.2 audit receipts.

Untrusted input enters via:
1. Untrusted estate loader scanner findings and vulnerability JSON feeds.
2. Webhook endpoints receiving Kubernetes audit logs or admissions callbacks.
3. Declarative REST endpoint managers and JSON mapping sheets.
4. Serialized DSSE warrant signatures and clone-twin execution receipts.

## Components that matter most / least
* Critical / In-Scope:
  - Two-of-two human DSSE Standing Warrant cryptographic verification kernel.
  - OPA Rego policy enforcement logic (AC-5 credential separation, Tier C scanner fencing).
  - PostgreSQL WORM trigger validation and hash-chained ledger chain verification (VerifyAllLedgerChains).
  - eBPF containment bridge dispatch logic (ensuring no unauthorized network isolation triggers).
* Lower Priority / Out of Scope:
  - Mock fixtures in testdata/ and wire-protocol double drivers.
  - Documentation and static assets in web/ unrelated to authentication/authorization.

## How you rate severity
* Critical: Dual-key DSSE signature verification bypass, unauthorized policy dispatch, bypass of OPA credential separation (e.g. read tokens dispatching warrants), or arbitrary code execution in the control plane kernel.
* High: Hash-chain ledger tampering without detection, denial of eBPF emergency containment bridges, or privilege escalation across handler families.
* Medium: Denial of Service on non-critical reporting endpoints or parsing errors in scanner corroboration feeds.
