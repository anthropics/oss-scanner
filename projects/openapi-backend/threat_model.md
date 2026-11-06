# openapi-backend: notes for the scanner

The full threat model lives in the checkout at `/src/docs/threat-model.md` (62 KB, versioned with the code) and the disclosure policy at `/src/SECURITY.md`. This file is the short version for an automated auditor. Where the two disagree, the repository wins. Every claim is tagged the same way as in the full model: *(documented)*, *(maintainer, 2026-09)*, *(tested, 5.21.2)* or *(proposed, 2026-10)* for rubric values I haven't ruled on yet.

Read in the full model first: §3 (trust boundary), §5 (inputs), §6 (attacker), §7 (guarantees P1 to P8), §8 (what the library does not do), §10a (reports that aren't bugs) and §12 (triage dispositions and the advisory log).

## What is this and where does untrusted input enter?

openapi-backend is an in-process OpenAPI router, request validator and security-requirement evaluator for Node.js ≥ 20. One OpenAPI 3 document you control drives routing, Ajv validation and which security handlers get consulted. It sits behind Express, Koa, Hapi, Fastify, AWS Lambda, Azure Functions and the like, and doubles as a mock server for API development. Roughly 400k npm downloads a month, increasingly under MCP servers and agent tooling, i.e. it is the thing standing between the network and your handler.

**The trust boundary at runtime is the `Request` object passed to `handleRequest`, `matchOperation` or `validateRequest`. That's it.** Its five fields are attacker-controlled: `method`, `path`, `headers`, `query`, `body`. Everything else the library reads is on the trusted side: the OpenAPI definition, constructor options (`strict`, `quick`, `ajvOpts`, `apiRoot`, ...), every handler and security handler, `handlerArgs` and the arguments to `mockResponseForOperation` and `validateResponse*` *(maintainer, 2026-09)*.

The attacker is the unauthenticated network client. It can put any bytes in the five fields within the host framework's limits, repeat keys, use prototype-named keys, `qs` bracket syntax and JSON in `content: application/json` query params. It can send as many requests as it likes, too. What it wants: reach an operation handler without satisfying its security requirements, reach a handler with data the schema should have rejected, get routed to a different operation than the path and method say, make `handleRequest` throw or hang, or pull definition content it shouldn't see *(maintainer, 2026-09)*. A finding that needs a capability not on this list is out of model.

The second in-scope boundary is the release pipeline (§14 in the full model): a malicious npm release runs inside every consumer at once, no request needed. R1 to R3 cover it.

## Which components matter?

| Priority | Files | Why |
| --- | --- | --- |
| **1** | `src/backend.ts` (`handleRequest`, security handler evaluation, the enforcement gates) | Two of five advisories broke P1 here, one of them a regression from the other's fix. Test any change against every row of the P1 table (§7), not just the reported one. |
| **1** | `src/router.ts` (`matchOperation`, `normalizePath`, `parseRequest`, `parseRequestQuery`) | Route confusion and path aliasing. GHSA-m748-x4gc-4w5w lived here. |
| **1** | `src/validation.ts` (`validateRequest`, `buildRequestValidatorsForOperation`, Ajv setup) | Validation bypass reachable from the five `Request` fields. |
| 2 | `src/utils.ts` | Helpers the three above use. |
| 3 | `src/refparser.ts`, definition loading in `init` / `loadDocument` | Reads files and fetches URLs to resolve `$ref`s. **Trusted input**: the definition is my config, not the client's. In scope only if client bytes can reach it at request time. |
| 3 | Response validation, `mockResponseForOperation` | Trusted arguments. Correctness only. |
| out | `examples` branch, `__tests__/resources`, `sbom/`, `scripts/`, devDependencies | Not runtime code (§2). |

Runtime dependencies that ever see client data: `ajv`, `qs`, `cookie`, `bath-es5`, `lodash`. The rest (`@apidevtools/json-schema-ref-parser`, `dereference-json-schema`, `openapi-schema-validator`, `mock-json-schema`, `openapi-types`) only see the definition. An advisory in one of those, or in a devDependency, is not a vulnerability in this library *(maintainer, 2026-09)*.

## How to exercise it?

- Built output sits at the repository root: `/src/index.js`, `/src/backend.js`, `/src/router.js`, `/src/validation.js` (tsc, with source maps). `require('/src')` exports `OpenAPIBackend` (also the default export).
- Tests: `npm test` runs vitest over `src/*.test.ts`. `router.test.ts` and `validation.test.ts` hold the regression cases for the advisories.
- Show, don't hypothesise: a minimal reproducer is a definition, the options, the handlers and one request. SECURITY.md asks for exactly that and so does the triage rule in §12.

```js
const { OpenAPIBackend } = require('/src');
const api = new OpenAPIBackend({
  quick: true,
  definition: {
    openapi: '3.0.0', info: { title: 'poc', version: '1' },
    components: { securitySchemes: { ApiKey: { type: 'apiKey', in: 'header', name: 'x-api-key' } } },
    paths: { '/pets': { get: { operationId: 'getPets', security: [{ ApiKey: [] }], responses: { 200: { description: 'ok' } } } } },
  },
});
api.register({ getPets: () => 'handler ran', unauthorizedHandler: () => 401 });
api.registerSecurityHandler('ApiKey', (c) => c.request.headers['x-api-key'] === 'secret');
api.init().then(() => api.handleRequest({ method: 'GET', path: '/pets', headers: {}, query: {}, body: undefined }))
  .then(console.log, console.error); // expected: 401
```

No network needed. The `examples` branch (`git -C /src show examples:README.md`) holds 14 framework integrations, but their dependencies aren't installed in this image and they're out of scope anyways.

## How do I rate severity?

A finding is `VALID` only if it breaks P1 to P8 (runtime) or R1 to R3 (release) through the client adversary and an in-model input. Where an advisory exists, its severity is the precedent.

| Break | Severity | Basis |
| --- | --- | --- |
| **P1** security requirement semantics: `authorized === true` when a required scheme's handler returned falsy, returned `{ error }`, threw, rejected or was never registered | **High** | GHSA-j939-289f-wq4w and GHSA-fwvf-w25j-mj87 were both High *(documented)* |
| **P2** enforcement gate: operation handler runs despite `authorized === false` with `unauthorizedHandler` registered or `strict: true` | **High** | Same class as P1, so same rating *(proposed, 2026-10)* |
| **P3** routing fidelity: a request reaches an operation its template doesn't match, or the router adds a path alias of its own | **Medium**. **High** when it changes which `security` list applies or dodges a path rule in a proxy or WAF in front | GHSA-m748-x4gc-4w5w was Medium *(documented)* |
| **P4** validation gate: handler called with input the schema rejects, with `validationFail` registered or `strict: true` | **Medium** by default, **High** when the bypassed check guards something auth-adjacent | *(proposed, 2026-10)* |
| **P7** client bytes evaluated as code, built into a `RegExp` or used as a file path or URL (default `ajvOpts`) | **High**, **Critical** if it reaches code execution | *(proposed, 2026-10)* |
| **P8** hang, process crash or super-linear CPU or memory on a size-bounded request | **Medium** | *(proposed, 2026-10)* |
| **P6** `handleRequest` rejects on malformed client input before validation (should become a validation error) | **Low** | GHSA-4v89-4c72-fxv7 was Low *(documented)* |
| **P5** the library mutates the operator's objects with default `ajvOpts` | Correctness, not security | *(documented)* |
| **R1 to R3** a change to the published tarball that doesn't come from a tagged commit on `main` through the trusted-publishing workflow | **High** | §14 *(maintainer, 2026-09)* |

Only the latest 5.x gets fixes. Reproduces only on an older release? `OUT-OF-MODEL: unsupported-version`.

## What not to report

All of these are in the full model's §2, §8 and §10a, and every one of them has been reported before:

- **Non-strict fall-through.** With `strict: false` (default) and no `unauthorizedHandler`, a request that fails its security requirements reaches the operation handler after a once-only warning. Same for validation without `validationFail`. By design in 5.x, hardened in 5.21.0, fails closed in 6.0 (GHSA-7mmm-8m7g-cp5g). The single most common report shape against this project, and not a finding unless `strict: true` or the handler is registered.
- **Anything that needs a hostile definition, options, handler code or `handlerArgs`.** That covers SSRF or local file read through external `$ref`s, ReDoS through schema `pattern`s, quadratic `uniqueItems`, slow Ajv compiles and `new RegExp` built from path templates (operator-authored, literal parts escaped since 5.21.2).
- **No content-type enforcement.** Only JSON bodies get schema-validated. `text/plain`, XML and multipart go to the handler as is. Documented.
- **Coercion differential.** With `coerceTypes: false` (default) a query param validates as `integer` but the handler gets the raw string. Documented, false friend 3.
- **A security handler returning an `Error` object counts as passed.** Open question Q5 in §13, not a finding today.
- **`handleRequest` rejecting in strict mode, or on a handler's own throw.** Rejection is the documented error channel (P6). Catching it is the integrator's job.
- **Prototype pollution through the query string.** `qs` defaults drop prototype keys *(tested, 5.21.2)*. Object `req.query` and `req.body` are whatever the host framework's parser produced, and that parser's problem.
- **Unknown headers and cookies are allowed.** `additionalProperties: false` applies to path and query only.
- **`console.warn` messages.** Operator-facing, never carry client data.
- **Missing request size, depth, rate limits or timeouts.** Framework or platform layer. So is path canonicalisation (`..`, `//`, `%2F`): the router does none and says so.
- **Advisories in devDependencies, in `examples/*` or in runtime dependencies that only see the definition.**

A finding that doesn't route to exactly one §12 disposition? Say so. That's a `MODEL-GAP`, and useful on its own.

## How a report might look like

Per SECURITY.md: the version tested (latest 5.x), which guarantee it breaks (P1 to P8, R1 to R3), a runnable proof of concept (definition, `OpenAPIBackend` options, handlers, request) and the impact in a few sentences. One issue per report. Skip the CVSS essay: a reproducer beats it.

Patches: TypeScript in `src/`, with a vitest case in the matching `*.test.ts` that fails before and passes after. Keep 5.x semantics, the non-strict fall-through stays until 6.0. Any change to security requirement evaluation needs the whole P1 table covered, not just the reported row. Check the §12 advisory log before reporting a duplicate: five GHSAs so far, and five out of five routed cleanly. 🙏
