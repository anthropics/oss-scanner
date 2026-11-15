# Threat model

## What this project does and where untrusted input enters
`@nestjs/swagger` generates an OpenAPI document from a NestJS application's controllers, DTOs and
decorators, and serves it: as JSON and YAML endpoints and through a bundled Swagger UI page
(`SwaggerModule.setup()`), on both Express and Fastify. Document generation runs at startup over the
developer's own code. The runtime surface is the set of HTTP routes the module registers, which are
often reachable without authentication in production.

- **Served routes**: `lib/swagger-module.ts` (`serveStatic`, `serveDocuments`, `serveSwaggerUi`,
  `serveDefinitions`) registers the UI page, `swagger-ui-init.js`, the JSON/YAML document URLs and
  the static Swagger UI assets (via `useStaticAssets` on Express and `@fastify/static` on Fastify).
  Path handling, route normalisation with `useGlobalPrefix`, and serving files outside the
  Swagger UI asset directory are in scope.
- **Swagger UI page and init script**: `lib/swagger-ui` (`constants.ts` HTML template,
  `swagger-ui.ts`, `helpers.ts`) builds HTML and JavaScript from module options and from the
  document. Script or markup injection into the page, from any value that can contain text that
  did not come from the developer, is in scope.
- **`patchDocumentOnRequest`**: lets an application change the document per request, so request
  data can reach the serialised document and the init script. The serialisation around that hook
  (JSON, YAML, embedding in `swagger-ui-init.js`) is in scope.
- **Document generation**: `lib/swagger-scanner.ts`, `lib/swagger-explorer.ts`, `lib/explorers`,
  `lib/services` (schema object factory, parameter and response mappers, Standard Schema to OpenAPI
  conversion), `lib/type-helpers`. Inputs are the developer's own decorators and DTOs, so bugs here
  are mainly correctness issues. They matter for security when the published document
  misdescribes a security requirement (e.g. drops `@ApiSecurity` / `@ApiBearerAuth`), or exposes an
  endpoint or property that `@ApiExcludeEndpoint`, `@ApiExcludeController`, `@ApiHideProperty` or
  include filters were meant to hide.

## Components that matter most / least
- Most: `lib/swagger-module.ts` (route registration and serving), `lib/swagger-ui`, the
  exclusion and include logic in `lib/explorers` and `lib/swagger-scanner.ts`.
- Less: the rest of document generation (`lib/services`, `lib/type-helpers`, `lib/decorators`),
  `lib/document-builder.ts`, and the compiler plugin in `lib/plugin`, which runs at build time over
  the developer's own source.
- Out of scope: `test/` and `e2e/` (test suites, fixtures and the sample app in `e2e/src`), and
  vulnerabilities that live entirely in `swagger-ui-dist`, `js-yaml`, Express or Fastify unless this
  package's own code makes them reachable.

## How to exercise it
- After the Docker build, the library is compiled into `dist/`. Tests: `npm run test` (unit, in
  `test/`) and `npm run test:e2e` (in `e2e/`, boots the sample app in `e2e/src` on Express and
  Fastify and requests the served routes).
- The e2e specs are the easiest base for a reproducer against the served UI and document routes.

## How you rate severity
- Critical: remote code execution, or reading arbitrary files from the server through the routes
  `SwaggerModule.setup()` registers, with default options.
- High: script injection (XSS) on the Swagger UI page from data an unauthenticated client controls
  (the URL, query string, headers, or a document patched with request data via
  `patchDocumentOnRequest`); path traversal out of the Swagger UI asset directory; a route that
  makes the application serve a handler other than the one registered.
- Medium: endpoints or properties marked as excluded or hidden still appear in the served document;
  security requirements missing from the generated document; injection that needs an uncommon but
  supported option.
- Low: injection through options only the developer sets (`customCss`, `customJs`, `customJsStr`,
  `customSiteTitle`, `customfavIcon`, `swaggerOptions`), and other issues that need the developer
  to opt in to clearly unsafe behaviour.

## Anything to leave alone
- Do not report that the document or Swagger UI is reachable without authentication. Whether to
  expose it, and behind what, is the application's choice.
- Do not report that the served document lists the application's routes and schemas. That is its
  purpose.
- Reports should include a minimal Nest application or e2e spec (in the style of `e2e/`) that
  reproduces the issue against the build in this image, and a patch against `lib/` where possible.
