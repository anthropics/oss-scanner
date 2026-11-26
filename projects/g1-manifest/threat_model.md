# Threat Model: G1-Manifest

## What this project does and where untrusted input enters
G1-Manifest (package `estate_graph`) produces, reconciles, signs, verifies, and renders expiring dependency graphs for cloud estates and workstations. Consumers (such as G1-Warrant and G1-Docket) verify DSSEv1 Ed25519 envelopes fail-closed and use `arming_gate()` to block surgical shielding whenever an observed egress flow has not been signed off in the declared model.

Untrusted input enters via:
1. Telemetry parsers (`estate_graph/sources/`): AWS VPC Flow Logs, Cilium Hubble JSONL, OpenLineage JSON, Warrant-shaped declared estate models, Windows Uninstall Registry records, `pip` metadata, and process memory-map module paths.
2. DSSEv1 envelopes and raw graph JSON submitted to `estate_graph/verify.py`, `estate_graph/cli.py`, and `estate_graph/serve.py` (`POST /api/render`, `POST /api/scan/estate`, `POST /api/ingest/host`).
3. Node IDs, edge labels, file paths, and metadata rendered into standalone HTML/SVG witness pages (`estate_graph/render.py`) and the dashboard index (`estate_graph/serve.py`).
4. HTTP paths, query strings, and view filenames handled by `estate_graph/serve.py`.

## Components that matter most / least
* Critical / In-Scope:
  - Cryptographic DSSEv1 PAE Ed25519 signing and fail-closed verification (`estate_graph/sign.py`, `estate_graph/verify.py`), including expiry enforcement, schema version gating, and `arming_gate()`.
  - Witness HTML/SVG rendering and embedded JSON serialization (`estate_graph/render.py`) against stored XSS, script-tag breakout, or deceptive verification-badge spoofing.
  - HTTP server request parsing, path traversal prevention, view filename sanitization, and workstation scanner generation (`estate_graph/serve.py`).
  - Host reconciliation and DLL sideloading disambiguation (`estate_graph/sources/win_modules.py`, `estate_graph/host_reconcile.py`) ensuring unattributed libraries cannot be masked as OS system libraries.
* Lower Priority / Out of Scope:
  - Synthetic demo fixtures in `examples/demo_estate/` and `examples/pc_self_graph_output/`.
  - Documentation in `docs/` and Terraform foundation templates in `terraform/`.

## How you rate severity
* Critical: DSSEv1 Ed25519 signature verification bypass, expired-graph acceptance, `arming_gate()` bypass allowing undeclared egress, arbitrary code execution, or path traversal reading/writing files outside `views_dir` / `keys_dir`.
* High: Stored XSS or script injection in rendered HTML witness pages, verification badge spoofing (rendering a forged envelope as VERIFIED), or DLL sideloading attribution bypass hiding untrusted libraries as `system-library`.
* Medium: Denial of Service via malformed telemetry/JSON inputs, unhandled parser exceptions, or non-deterministic canonical JSON serialization.
