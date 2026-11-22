# Threat model

## What this project does and where untrusted input enters
`@nestjs/graphql` integrates GraphQL into NestJS applications. It builds a schema from decorated
classes (code first) or from SDL files (schema first), binds resolvers to Nest providers, and runs
them through Nest's guards / interceptors / pipes / exception filters pipeline. `@nestjs/apollo` and
`@nestjs/mercurius` are the drivers that put that schema behind Apollo Server (Express or Fastify)
and Mercurius (Fastify). Untrusted input is the GraphQL request itself: the query document,
variables, operation name, HTTP headers, and WebSocket messages for subscriptions.

- **Resolver argument binding**: `packages/graphql/lib/services` (`gql-execution-context`,
  `gql-arguments-host`, `resolvers-explorer.service`), `packages/graphql/lib/factories/params.factory.ts`
  and the parameter decorators in `packages/graphql/lib/decorators` (`@Args`, `@Context`, `@Info`,
  `@Parent`, `@Root`). Anything that lets client data reach a resolver in a shape the declared types
  or pipes should have rejected, or lets a request skip a guard or interceptor attached to a
  resolver or field, is in scope.
- **Field resolvers and field middleware**: `@ResolveField`, `@ResolveReference` (federation) and
  field middleware in `packages/graphql/lib/utils/decorate-field-resolver.util.ts`.
- **Code-first schema generation**: `packages/graphql/lib/schema-builder` (type, input and argument
  factories, default values, scalars, enums, unions). The schema decides what the server validates,
  so generation bugs that drop a non-null constraint, an enum restriction or a `@HideField` are
  in scope.
- **Built-in scalars**: `packages/graphql/lib/scalars` (`DateTime`, `Timestamp`) parse client
  literals and variables.
- **Subscriptions**: `packages/graphql/lib/services/gql-subscription.service.ts` (graphql-ws), plus
  the subscription wiring in the Apollo and Mercurius drivers: connection params, `onConnect`
  authentication hooks and per-message context.
- **Errors**: `packages/apollo/lib/drivers/apollo-base.driver.ts` and the Mercurius driver map Nest
  exceptions to GraphQL errors. Leaking stack traces or internal error details that the documented
  defaults hide is in scope.
- **Federation and gateway**: `packages/graphql/lib/federation`, `packages/apollo/lib/drivers/apollo-federation.driver.ts`,
  `apollo-gateway.driver.ts`, `packages/mercurius/lib/drivers/mercurius-federation.driver.ts` and
  `mercurius-gateway.driver.ts` (entity references and `_entities` resolution).

## Components that matter most / least
- Most: resolver binding and execution context in `packages/graphql/lib/services`, the parameter
  decorators, code-first schema generation, subscriptions, and the Apollo and Mercurius drivers'
  request, context and error handling.
- Less: GraphiQL page (`packages/apollo/lib/graphiql`), built from module options, not request
  data; schema-first typings generation (`graphql-definitions.factory.ts`,
  `graphql-ast.explorer.ts`) and the compiler plugin (`packages/graphql/lib/plugin`), which run at
  build or start time over the developer's own SDL and source.
- Out of scope: `packages/*/tests` (test suites and fixtures), and vulnerabilities that live entirely
  in third-party dependencies (graphql-js, Apollo Server, Mercurius, graphql-ws, Express, Fastify)
  unless this project's code makes them reachable.

## How to exercise it
- After the Docker build, every package is compiled in place under `packages/*`. Tests:
  `yarn test:e2e:graphql`, `yarn test:e2e:apollo`, `yarn test:e2e:mercurius` (vitest).
- `packages/*/tests` contain complete Nest applications (code first, schema first, federation,
  subscriptions, guards and interceptors on resolvers) booted in-process. They are the quickest
  starting point for a reproducer.

## How you rate severity
- Critical: remote code execution, or a request that skips a guard on a resolver or field, or reaches
  a different resolver than the one requested, with default configuration and no authentication.
- High: client input that bypasses a type, non-null, enum or pipe check the schema declares;
  prototype pollution from query arguments or variables; a subscription connection that skips the
  documented authentication hook; a single request or message that crashes the process.
- Medium: information disclosure through default error responses (stack traces, internal
  exception messages); resource exhaustion that needs sustained traffic; issues that need an
  uncommon but supported configuration (federation, gateway, a specific driver option).
- Low: issues that need the application developer to opt in to clearly unsafe behaviour.

## Anything to leave alone
- Do not report that introspection or GraphiQL is enabled, that there is no query depth or
  complexity limit, or that a resolver has no guard. These are application choices and the
  framework does not enforce them by default.
- Do not report DoS that only exists because the application sets no body size, depth or
  complexity limit.
- Reports should include a minimal Nest application or test (in the style of `packages/*/tests`)
  that reproduces the issue against the packages built in this image, and a patch against
  `packages/` where possible.
