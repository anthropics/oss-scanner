# Threat model — ainumbers

## What this project is

A static, serverless repository: 765 deterministic financial-calculus kernels
(ESM JavaScript modules, each exporting one pure `compute()` function, under
`chaingraph/kernels/`) and roughly 740 static HTML calculator pages
(`chaingraph/*.html`). Pages are served as static files; every computation
happens in the visitor's browser, or in Node when a kernel is imported as a
module. There is no server-side execution, no database, no authentication and
no session state anywhere in this repository.

## In scope

- `chaingraph/kernels/*.kernel.mjs` — numeric/logic correctness that has
  security relevance for consumers relying on the computed financial figures.
- Client-side JavaScript embedded in `chaingraph/*.html` and the assets those
  pages load.

## Out of scope (reports here will be closed as out-of-scope)

- CI, build and deployment tooling: `.github/`, `.githooks/`, `oss/`,
  `agent-kit/`, `deploy-*` scripts.
- Documentation, vendored regulatory source texts, site chrome and static
  content.
- Anything that only manifests when a third party modifies files locally.

## Where untrusted input enters

Kernel inputs are caller-supplied JSON argument objects. Pages read
query-string parameters and form fields. Nothing is persisted anywhere.

## Severity calibration we would like

- Numeric or logic defects in kernels that produce wrong financial outputs:
  **high**.
- Client-side XSS contained to a single static calculator page: **medium**,
  unless impact beyond that page is demonstrated.
- Findings in out-of-scope paths: **informational**.
- Prototype-pollution style findings that require an attacker-controlled
  property name to matter: please demonstrate an end-to-end path, not just the
  sink.

## Reports and patches

Self-contained reproducers (a `node` one-liner or exact browser steps) are
preferred; we re-run every reproducer locally before acting on it. Proposed
patches that change a kernel's numeric output are only useful alongside a
derivation or fixture showing the old and new results.
