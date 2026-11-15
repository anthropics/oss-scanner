# Threat model

## What this project does and where untrusted input enters
- `id` is a Python library and CLI tool (`python -m id`) for detecting and retrieving ambient OpenID Connect (OIDC) identity tokens in CI/CD and cloud environments (GitHub Actions, Google Cloud Platform, Buildkite, GitLab CI/CD, and CircleCI).
- Untrusted or external input can enter via:
  - The `audience` parameter supplied to `id.detect_credential(audience)` or the CLI entrypoint (`python -m id <audience>` / `ID_OIDC_AUDIENCE`).
  - Environment variables read during ambient credential detection (`GITHUB_ACTIONS`, `ACTIONS_ID_TOKEN_REQUEST_TOKEN`, `ACTIONS_ID_TOKEN_REQUEST_URL`, `GOOGLE_SERVICE_ACCOUNT_NAME`, `BUILDKITE`, `GITLAB_CI`, `<AUD>_ID_TOKEN`, `CIRCLECI`).
  - OIDC token responses returned by HTTP metadata/token endpoints (`urllib3` responses in `detect_github` and `detect_gcp`), CLI subprocess output (`buildkite-agent` and `circleci`), or environment variables (`detect_gitlab`), including JWT payloads decoded by `_validate_credential` and `decode_oidc_token`.

## Components that matter most / least
- `id/__init__.py` (`detect_credential`, `_validate_credential`, `decode_oidc_token`) and `id/_internal/oidc/ambient.py` (environment detectors, HTTP requests, subprocess execution) are the core components in scope.
- `id/__main__.py` (CLI argument parsing and output handling) is also in scope.
- `test/` and CI configuration files under `.github/` and `.circleci/` are out of scope.

## How to exercise it
- Run the unit test suite offline with `make test` or `pytest`.
- Run the linter and static analysis suite with `make lint`.
- Exercise the CLI with `python -m id <audience>`.

## How you rate severity
- Critical / High: Command or argument injection in subprocess invocations (`detect_buildkite`, `detect_circleci`), credential or bearer token leakage/exfiltration to unintended hosts, SSRF or URL manipulation when requesting tokens, or bypasses of audience claim validation in `_validate_credential`.
- Medium / Low: Unexpected unhandled exceptions outside the `IdentityError` / `AmbientCredentialError` hierarchy when parsing malformed tokens or HTTP responses, or sensitive token material leaked in error messages or logs.

## Anything to leave alone
- Do not report that `_validate_credential` or `decode_oidc_token` does not verify JWT cryptographic signatures. `id` is an OIDC token client that retrieves ambient credentials to present to a relying party; cryptographic signature verification is the responsibility of the relying party.
- Do not report trusting `PATH` to resolve `buildkite-agent` or `circleci`, or trusting standard CI environment variables when the local execution environment is already untrusted.
