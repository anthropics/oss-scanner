# Threat model

## What this project does and where untrusted input enters
- graphql-sequelize-generator (GSG) is a Node.js library. An application hands it a declaration (its Sequelize models plus
  hooks and options) and gets back a GraphQL schema and an Apollo Server 4 instance that it mounts on its own HTTP and
  WebSocket endpoints.
- The developer's declaration, models, hooks and server configuration are trusted.
- Untrusted input is everything a GraphQL client sends to the generated API: queries and mutations over HTTP, and
  subscriptions over WebSocket (graphql-ws). That includes every argument GSG generates: `where` (a JSON filter passed to
  Sequelize), `order` (including the comma-separated and `reverse:` multi-sort and `association.field` sorting that GSG
  parses itself in `src/queryResolvers/createListResolver.ts`), `limit`, `offset`, the id and attribute arguments, and the
  input objects of create, update and delete mutations.
- Assume the client may be authenticated as an ordinary user but is not trusted beyond what the application's hooks
  allow.

## The security boundaries GSG promises
These are what we care about most. Breaking one of them is a vulnerability.
- Hooks are the application's authorization layer. The global `before` hook and the per-operation hooks (`beforeList`,
  `beforeCreate`, `beforeUpdateFetch`, `beforeUpdate`, `beforeDeleteFetch`, `beforeDelete`, and the matching `after`
  hooks, including those added with `injectHooks`) must run on every path that reads or writes that model: root list and
  count queries, lists reached by nesting through an association, mutations, subscriptions and custom or
  endpoint-scoped mutations. A path that reaches a model's rows without running its hooks, or that lets a client change
  the `findOptions` or `where` a hook returned, is an authorization bypass.
- `excludeFields` columns must never appear in a response: not at the root, not through an association, not in a
  mutation's returned entity and not in a subscription payload.
- `excludeFromRoot: true` models must have no root query.
- A profile (`profiles`) is a schema boundary. A client served a profile's schema must not reach an endpoint, an
  association, a field, a mutation, a subscription or a webhook event that the profile does not grant, by any route
  (see `src/filterDeclarationByProfile.ts`, `src/tests/profileSchema.spec.js`, `src/tests/profileServer.spec.js`).
- Update and delete mutations must only touch the one row the client named, after the hooks have run, and transactional
  mutations must not publish to subscribers or call the webhook for a write that was rolled back.

## Components that matter most / least
- Matter most: `src/schema.ts`, `src/generateApolloServer.ts`, `src/root/` (query, mutation, subscription roots),
  `src/queryResolvers/`, `src/mutationResolvers/`, `src/associations/`, `src/filterDeclarationByProfile.ts`,
  `src/removeUnusedAttributes.ts`, `src/injectHooks.ts`.
- Matter less: `src/gsg.ts` and `src/scripts/` are a developer CLI that writes boilerplate files and calls the Integromat
  (Make) API with the developer's own credentials; it never sees end-user input. Report only issues reachable from
  input the developer would not control.
- `lib/` is compiled output of `src/`; report against `src/`. `src/tests/` is the test fixture, not shipped code.
- Out of scope: bugs that live entirely in Sequelize, graphql-sequelize, Apollo Server, graphql-ws or the database
  driver. Do report a GSG bug that passes untrusted input to them in an unsafe way.

## How to exercise it
- `src/tests/testSchema.js` declares an example schema that uses every feature (hooks, profiles, excludeFields,
  excludeFromRoot, subscriptions, webhooks, transactions, custom endpoints). `src/tests/setupTestServer.js` serves it
  over HTTP with Express against an in-memory SQLite database, migrated and seeded from `src/tests/migrations` and
  `src/tests/seeders`.
- `yarn test` (jest, run in-band) runs the whole suite offline. The `*.spec.js` files under `src/tests/` show how to
  send queries with supertest and are the quickest base for a reproducer.
- `yarn build` recompiles `src/` to `lib/` after a change.

## How you rate severity
- Critical: an unauthenticated or low-privileged client writes or deletes rows it should not reach, or reads data across
  a profile boundary at scale; SQL injection through any generated argument.
- High: a route that skips an application's hooks (authorization bypass) for reads; a client reading an `excludeFields`
  column's value; a client reaching an endpoint, field or mutation its profile does not grant.
- Medium: leaks limited to existence or counts of rows the hooks would hide; a subscription or webhook firing for a
  rolled-back write.
- Low: denial of service through expensive queries (deep nesting, large `limit`, costly `where` or `order`), since GSG
  sets no default query depth or row limit and leaves that to the application; issues in the developer CLI.
- Filtering or sorting on an `excludeFields` column through `where` or `order`, which can reveal its value one guess at a
  time, is known: `excludeFields` is documented as output-side only. Report it only if it reveals the value directly or
  works across a profile boundary.

## Anything to leave alone
- The cautions listed in the README ("Cautions" section) are documented behaviour, not vulnerabilities: listing a model
  exposes its root list query whatever `actions` says, and empty mutation maps break schema building.
- Do not report that hooks are optional: an endpoint declared without hooks is intentionally open.
