# openapi-client-axios: notes for the scanner

> DRAFT, 2026-10. openapi-client-axios has no written threat model yet, unlike its sibling openapi-backend (`docs/threat-model.md` over there). Everything marked *(proposed)* is my working position for the scanner, not a published guarantee. SECURITY.md in the checkout is the disclosure policy.

## What is this and where does untrusted input enter?

A runtime OpenAPI 3 client on top of axios. No code generation: the definition gets parsed at `init()` and every operation becomes a method on the client (`client.getPetById(1)`). Isomorphic, so it runs in browsers and in Node ≥ 20. Roughly 890k npm downloads a month. It ships inside Microsoft's M365 Agents Toolkit templates and under MCP servers, which means the values an application passes into an operation method pretty often originate from an end user or a language model.

Three inputs, in decreasing order of trust:

| Input | Who controls it | Trust *(proposed)* |
| --- | --- | --- |
| **The OpenAPI definition** (`definition:` as object, file path or URL fetched with axios at `init()`), then dereferenced with `dereference-json-schema` | The API operator, chosen by the application | Trusted by contract, same ruling as openapi-backend: the application picked it. A definition that does more than shape requests (code execution, prototype pollution of `Object.prototype`, an unbounded loop) is still worth reporting as hardening, because definitions get pulled from third-party servers at runtime all the time. |
| **Operation arguments** (path and query parameters, request body, per-call axios config) | The application, which frequently forwards end-user or model-generated values | **Semi-trusted. The main thing to look at.** The property the library should hold: a parameter value lands only in the location its operation declares. A path parameter must not escape its path segment, a query value must not inject extra parameters and nothing in the arguments may change the host the request goes to unless the application set `baseURL` or `baseURLVariables` itself. |
| **HTTP responses** | The remote server | Untrusted. The library hands them through axios to the caller. No response byte should get evaluated or steer anything beyond status and body passthrough. |

Out of scope: axios itself (report upstream), TLS and certificate handling (axios and the platform), CORS (the browser), how the application stores the credentials it puts into axios headers and the TypeScript definitions `typegen` produces (development-time output). Node's built-in fetch and `axiosRunner` replacements belong to the application.

## Which components matter?

| Priority | Files | Why |
| --- | --- | --- |
| **1** | `src/client.ts`: `getRequestConfigForOperation`, path templating through `bath-es5`, `getBaseURL` and server-variable substitution, header parameters | Where operation arguments become a URL. Path parameter values are stringified and percent-encoded by `bath-es5` (`encodeURIComponent` in its `path.js`, 3.0.3), so `/`, `?` and `#` stay inside the segment *(source, 2026-10)*. Still worth checking: server-variable substitution for `baseURL`, header parameter values with CR or LF and anything that reaches `url` without going through the builder. |
| **1** | `src/query-serializer.ts` | Query parameter serialisation per OpenAPI `style` / `explode`. Values are `encodeURIComponent`-ed. Verify every branch. |
| 2 | `init()` / `initSync()`: definition loading and `dereferenceSync` | Hostile definition hardening (see above). |
| 3 | `src/types/*` | Types only, not loaded at runtime. |
| out | `examples/` if present, `__tests__` fixtures | Not runtime code. |

Runtime dependencies that see operation arguments: `bath-es5` (path templating) and `axios` (the request). `dereference-json-schema` only sees the definition. `openapi-types` is types only.

## How to exercise it?

- Built output sits at the repository root (`/src/index.js`, `/src/client.js`, `/src/query-serializer.js`). `require('/src').default` is `OpenAPIClientAxios`.
- Tests: `npm test` runs jest. HTTP is mocked with `msw`, so nothing needs a network.
- Reproducer: a definition object, `new OpenAPIClientAxios({ definition })`, `await api.init()`, then `api.getRequestConfigForOperation('operationId', [params, body, config])` and inspect the resulting `url`, `path`, `query` and `headers`. No request has to be sent to show a parameter escaping its location.
- Known to hold already: `client.getPetById('1/../admin')` requests `/pets/1%2F..%2Fadmin`, not `/pets/1/../admin`.

## How do I rate severity? *(proposed)*

| Finding | Severity |
| --- | --- |
| Definition or response bytes reach code execution (`eval`, `Function`, template evaluation) | **Critical** |
| An operation argument changes the host or scheme of the outgoing request without the application setting it | **High** |
| An operation argument escapes its declared location within the same API (path segment, query, header) | **Medium** |
| Prototype pollution of a shared prototype from a definition or a response | **Medium** |
| Crash or hang on a hostile definition (unbounded `$ref` loop, ReDoS in server-variable handling) | **Low**. The application chose the definition. |
| Missing validation of request bodies or responses against the schema | Not a finding. The client doesn't validate, openapi-backend does. |

## What not to report

- The library sends whatever headers the application configured, credentials included, to whatever `baseURL` the definition's `servers` list names. That is the contract.
- The definition is fetched over plain axios with the application's defaults. Verifying it is the application's job.
- Missing response validation, retries, timeouts or rate limiting. Not features of this library.
- Advisories in devDependencies.

## How a report might look like

Per SECURITY.md: package version, a minimal reproducer (definition and the call) and the impact. One issue per report. Patches in TypeScript under `src/`, with a jest case that fails before and passes after.
