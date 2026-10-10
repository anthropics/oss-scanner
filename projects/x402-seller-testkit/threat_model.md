# x402-seller-testkit threat model

## Purpose and trust boundaries

x402-seller-testkit is an Apache-2.0-licensed TypeScript CLI and library for
seller-side payment conformance/regression checks. It consumes HTTP responses
from an explicitly selected target and validates challenge, rejection and
success behavior. It is a testing tool; it is not a production payment
facilitator or a proof that a seller is safe for arbitrary real payments.

Target responses, payment headers/payloads and external facilitator responses
are untrusted. CLI arguments and the choice of target/report path are supplied
by the trusted local operator. Optional wallet/facilitator environment values
are sensitive and must not leak into requests to unrelated origins, errors or
JSON reports. Mock payments do not authorize actual spending.

## Priorities

- `src/checks/`, `src/core/runner.ts` and `src/core/headers.ts`: malformed challenge and
  payment data, misleading passes, unbounded responses and error handling.
- `src/core/config.ts` and `src/core/report.ts`: secret handling, target/profile
  boundaries and serialization of untrusted response data.
- `src/fixtures/local-mock.ts` and `examples/local-express/`: precise mock
  verification, malformed-payment rejection and receipt correctness. Explain
  whether an issue affects the local example, harness or a real integration.
- `src/profiles/basic-evm.ts`: paid-path gating and handling of missing config.

## Build and exercise

The checkout, pnpm 10.32.1 and locked dependencies are installed in `/src`.
Run `pnpm check` and `pnpm build`, or `pnpm test` for just the deterministic
suite. Built CLI files live in `/src/dist`. Tests inject mocked fetch responses.
The local Express example can be exercised entirely on container loopback
using the `local-mock` profile. No wallet keys, external facilitator, live
payment or network connection are needed for the audit.

## Severity and scope

Untrusted-response-driven local code execution, credential/private-key
disclosure or unauthorized real spending is high or critical depending on
impact and reachability. A false pass is high only when a concrete production
security decision relies on it; otherwise classify it as a conformance defect.
Practical resource exhaustion is normally medium. Treat mock-payment defects
according to their demonstrated effect rather than assuming real-funds theft.

An operator-selected target URL/report output path is intended functionality.
Show an untrusted response crossing an origin or filesystem boundary before
reporting SSRF/arbitrary file write. Third-party SDK reports need a reachable
first-party call path. Use synthetic data in offline reproducers and include
the affected revision, assumptions, minimal patch and regression test.
