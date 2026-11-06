# Threat model

jaeger-ui is the browser interface for Jaeger. Its [SECURITY.md](https://github.com/jaegertracing/jaeger-ui/blob/main/SECURITY.md) does not set a separate policy. The whole file defers to the main repository:

<https://github.com/jaegertracing/jaeger/blob/main/SECURITY.md>

Reporting, supported versions, the dependency policy, and the automated-scanner rules all come from that file. The main threat model, architecture, assurance case, and self-assessment are the rest of the source this file adapts:

- <https://github.com/jaegertracing/jaeger/blob/main/docs/security/threat-model.md>
- <https://github.com/jaegertracing/jaeger/blob/main/docs/security/architecture.md>
- <https://github.com/jaegertracing/jaeger/blob/main/docs/security/assurance-case.md>
- <https://github.com/jaegertracing/jaeger/blob/main/docs/security/self-assessment.md>
- <https://github.com/jaegertracing/jaeger/blob/main/docs/security/security-review-2026.md>

## What this project does and where untrusted input enters

This repository is the browser side of trust boundary **B4: Query → Users** in the Jaeger threat model. That boundary is "internal service to end users", with the documented controls TLS, bearer tokens, and RBAC. The assurance case draws the same edge as Users (Browser) to Query/UI and names the same controls. The 2026 security review describes it as users reaching trace data through the Jaeger APIs and the browser UI, and it places browser environments outside the backend repository. This repository is that browser surface.

Two kinds of untrusted data are rendered here.

- **Span data from Query.** Service names, operation names, tags, logs, and other span fields are produced by instrumented applications. The threat model treats a compromised or rogue application as a threat actor that can poison trace data and inject information (T1 and T2 are the named scenarios). The UI displays those fields.
- **Uploaded trace files.** The UI parses trace JSON the user uploads, including OTLP JSON, and renders it through the same views. The project's own migration note identifies the two places a trace enters the UI cache: `hooks/useTraceLoading.ts` for traces fetched from the API, and `SearchTracePage/FileLoader.tsx` for uploaded files ([ADR-0002](https://github.com/jaegertracing/jaeger-ui/blob/main/docs/adr/0002-otlp-api-v3-migration.md)).

The assurance case lists cross-site scripting (CWE-79) as a weakness the project mitigates with "UI built with React (auto-escaping), CSP headers". A finding that untrusted span data, or an uploaded trace JSON file, executes script in the browser is a break in that control. The source documents do not further split XSS into stored, reflected, or authenticated cases, and they do not give XSS its own impact rating.

Markdown taken from span content is part of the same rendering path. The UI test `packages/jaeger-ui/src/utils/markdownOptions.test.tsx` already requires that `javascript:` and `data:` links are not turned into anchors. That is an existing control, not an extra rule.

## Components that matter most / least

- Most: `packages/jaeger-ui`, which renders span fields and parses uploaded traces, including the file loader and the trace page.
- Also here: `packages/plexus`, which draws the trace graph from that same span data.
- Not here: the collector, storage backends, and the Query API. Those are [jaegertracing/jaeger](https://github.com/jaegertracing/jaeger). Authentication and RBAC on B4 are operator configuration of Query (bearer tokens, OAuth2), as the threat model states. This repository does not redefine them.
- `SECURITY.md` in this repository adds no further in-scope or out-of-scope list beyond the deferral.

## How to exercise it

Node is the major version in `.nvmrc` (24). `package.json` `engines` requires `>=24.16.0`. The package manager is the `packageManager` field, `pnpm@12.8.2`, activated with corepack. The `preinstall` script is `npx only-allow pnpm`, so npm installs are rejected.

- `pnpm run build` builds the workspace (`pnpm -r build`).
- `pnpm run test` runs Vitest (`vitest run` in `packages/jaeger-ui` and `packages/plexus`). CI's unit-test workflow runs `make coverage`.
- The markdown link cases above, and the file-upload path in `SearchTracePage/FileLoader.tsx`, are the direct places to try untrusted span text and uploaded JSON.

## How you rate severity

Neither this repository nor the main threat model defines a general severity scale for UI bugs. Do not invent one.

The main threat model does rate two related scenarios, and only these:

- T4, unauthorized access to the Query UI or API: Impact Medium, Likelihood Medium.
- T2, sensitive data inside traces: Impact High, Likelihood Medium.
- T6, a compromised dependency in the build: Impact Critical, Likelihood Low.

It does not say how to score XSS, an open redirect, or a crash of a single browser tab.

`SECURITY.md` in the main repository still applies, including to npm dependencies, because this repository's policy is that file. Only report a finding that is applicable, and explain why. Dependency CVEs are patched when they are applicable and the project's scanning rates them high or critical. govulncheck is the documented check for Go dependency CVEs; this repository is JavaScript, so that command does not apply here, but the same reachability rule does. Unreachable npm advisories are not actionable.

## Anything to leave alone

- Collector, storage, and Query API defects. Report those against jaegertracing/jaeger.
- Raw npm audit output. The automated-scanner section of `SECURITY.md` says generic dependency findings are mostly false positives unless the vulnerable path is actually used.
- The fact that an uploaded JSON file is displayed. Uploading a trace is the feature documented in the UI. The defect would be script execution or another break of the React escaping or CSP control described in the assurance case.
- "The UI has no login form." B4's bearer tokens, OAuth2, and RBAC are configuration of the Query service in the threat model, not a second policy implemented in this package.

## Reports

Use the main repository's process in `SECURITY.md` (GitHub Security Advisories on jaegertracing/jaeger, or an encrypted message; key id `C043A4D2B3F2AC31`). This enrolment uses the same maintainers' list, `cncf-jaeger-maintainers@lists.cncf.io`. There is no `auto_ccs` list.
