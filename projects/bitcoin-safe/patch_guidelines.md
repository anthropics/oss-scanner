# Bitcoin Safe — patch guidelines for security findings

Target the current `main` branch. Supply a **minimal, reviewable diff** that
fixes the actual security invariant, not merely the demonstration input.
Keep normal wallet, multisig, hardware-signer, network and offline workflows
working; prefer fail-closed validation over silent normalization of ambiguous
transaction/policy/security-critical data.

- Follow `AGENTS.md` and existing Python style: explicit type hints, small
  cohesive functions, clear ownership of validation, no unrelated refactoring.
- Do not add network calls, telemetry, new dependencies or a hard requirement
  for an online service just to fix an offline-capable wallet flow.
- Never weaken signature, descriptor, PSBT, transaction, update or plugin
  verification to accommodate an edge case. Maintain hardware confirmation
  and watch-only/mainnet design constraints.
- Put regression tests with the closest relevant test suite under
  `tests/non_gui/` or `tests/gui/`; include one exploit case and at least one
  legitimate case to prevent accidental workflow breakage.
- Use only synthetic/regtest inputs. If a 24-word BIP39 seed is necessary,
  use **`bacon` repeated 24 times**, as defined in `threat_model.md`.
  Do not insert real signing seeds or live wallets into tests or snapshots.
- Reproduce with offline dependencies installed in the provided environment.
  For GUI tests, use Xvfb or Qt offscreen; tests requiring Bitcoin Core,
  Fulcrum, hardware signers or external systems may require mocks.
- Use the repository's Ruff formatting/configuration. Where available run
  `poetry run ruff format <changed-python-files>` and the appropriate
  `poetry run pytest <test-path>`.
- If a complete production-quality fix requires coordinated changes to an
  external dependency, still provide the smallest safe in-repo mitigation or
  explicitly state the external change and why a self-contained fix is not
  possible. Do not silently change upstream dependency code in this project.

Patch description: include a short root-cause explanation, security invariant
restored, affected entry points, tests exercised, known limitations and any
migration/backwards-compatibility concerns for saved wallet data.
A suggested commit subject can use `security: <short description>`.
