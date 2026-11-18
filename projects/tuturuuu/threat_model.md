# Tuturuuu audit scope

This is audit guidance, not a claim of production configuration or tested exploitability.

## Target and source basis

Target only first-party code in https://github.com/tutur3u/platform. Paths below were checked at `ee5ae9b051f88451bed7e2d7ec255be5d992dd1d` on 2026-10-26. Enrollment follows `main`, so a later scan may differ.

The root manifest defines Bun workspaces at `apps/*` and `packages/*`. The web manifest names `@tuturuuu/web` and uses Next.js. The public tree includes workspace-addressed API routes at `apps/web/src/app/api/[wsId]/`, AI chat routes, auth session/API-key tests in `packages/auth/src/`, Supabase adapters in `packages/supabase/src/`, and database sources under `apps/database/`. These establish investigation targets; this document does not assert defects or prove the authorization implementation.

## Trust boundaries to investigate

Treat incoming HTTP bodies, query parameters, workspace IDs, resource IDs, cookies, session claims, API keys, uploaded content, and model-directed actions as adversarial when they enter first-party handlers. Trace actual callers and data flows before claiming a vulnerability.

Prioritize authentication and session handling, workspace membership and authorization, cross-workspace access, and finance, payments and billing flows: wallets, transactions, invoices and payment webhooks. Also investigate first-party database/storage access controls and first-party handling of attacker-controlled input. Trace authorization and tenant ownership, payment-webhook authenticity, and duplicate-event handling through actual first-party callers before making a finding. These priorities do not assert existing defects. Demonstrate impact on synthetic users in distinct test workspaces. Check both allowed access and denied cross-workspace access. Shared auth/Supabase code can affect several applications, but assess actual reachability separately.

## Safe execution and limits

Audit offline in an isolated sandbox after image setup. Use synthetic data, local fixtures, and mocks. The audit scope is the entire public monorepo, including every app/package, mobile and platform code, Rust/native/Wasm, SQL/RLS, workers, scripts and infrastructure. The Dockerfile retains it all at /src. It installs JS and Flutter dependencies, fetches apps/backend's Rust crates for offline reading, and runs the same workspace setup build CI runs before unit tests. It does not prebuild apps: Turbo unit tests and Flutter tests run offline from this image. apps/backend and apps/tanstack-web are paused runtimes excluded from build/test, as in CI; their source remains in scope. Linux cannot execute iOS/Xcode; Android SDK, full Supabase services and browser binaries are not provisioned. These execution limits do not narrow source scope.

Do not contact Tuturuuu production/staging, customer systems, cloud services, or third-party APIs. Do not obtain or use real credentials or customer data. SECURITY.md prohibits automated scans of live systems without permission, unnecessary access/exploitation, denial of service, and spam. This document authorizes none of those actions.

Third-party dependency defects alone are outside this first-party enrollment. Show a first-party cause or integration defect before reporting dependency-related impact. Label every finding with executed reproduction versus source inference, including native/mobile and worker paths.

## Report requirements

Provide the scanned commit, affected first-party path, reachable entry point, attacker prerequisites, violated trust boundary, and minimal offline reproducer with synthetic data. Include negative controls and distinguish observed behavior from inference. Propose the smallest fix while preserving existing security assertions and legitimate access. Deduplicate reports with a common root cause.

Severity remains subject to maintainer review. Assess demonstrated confidentiality, integrity, availability, tenant reach, and required privileges. No severity is preassigned merely because a path concerns auth, finance, or AI. Keep suspected vulnerabilities and reproducer details private with authorized maintainers until fixed or appropriately disclosed.

## Severity examples

These examples guide triage. They do not assert existing vulnerabilities. Maintainers assign final severity from demonstrated impact and prerequisites.

- Unauthorized read or mutation of another workspace's private data is high. Broad unauthenticated compromise across workspaces may be critical. A post-auth SQL injection is high if it crosses workspace or privilege boundaries. Critical requires demonstrated broader compromise, such as arbitrary code execution or access across many workspaces.
- Stored XSS is medium when its demonstrated reach is limited to a low-privilege victim in one workspace. It is high when it enables privileged actions or access to private workspace data. Critical requires demonstrated broad compromise across workspaces. Do not infer reach from a script executing alone.
- Prompt injection alone is not a vulnerability. Demonstrate that a model-directed action crosses a first-party authorization or data boundary, such as reading another workspace's private resource or executing an action that the caller cannot authorize.
- Availability reports need an offline reproduction and a credible reachable trust boundary. A test-only crash or resource-intensive maintainer operation is insufficient without a reachable attacker-controlled path. Never exercise live services.

For workspace-addressed API routes, AI chat handlers, and upload consumers, trace authentication prerequisites, tenant ownership checks, privileged database clients, and model-tool execution. Include an allowed same-workspace control and a denied cross-workspace control for authorization reports.
