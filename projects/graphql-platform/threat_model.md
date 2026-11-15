# ChilliCream GraphQL Platform

This repository holds the .NET GraphQL libraries Hot Chocolate (server), Fusion (gateway), Green Donut (DataLoader), and Strawberry Shake (client), and the Mocha messaging library (message bus, mediator, and sagas), published to NuGet.org under the `HotChocolate.*`, `GreenDonut.*`, `StrawberryShake.*`, `Mocha.*`, and `ChilliCream.*` package IDs. Applications embed the GraphQL libraries in ASP.NET Core and expose a GraphQL endpoint, usually to the internet, and use Mocha to exchange messages with other services through a broker. Scan the default branch, `main`; `SECURITY.md` lists the release lines that receive security fixes.

## What this project does and where untrusted input enters

Treat everything a client sends to a GraphQL endpoint as untrusted:

- HTTP GET and POST requests, and HTTP QUERY requests when the application sets `EnableQueryRequests` (off by default): the operation document, `operationName`, `variables`, `extensions`, persisted operation IDs and hashes, query string parameters, and headers such as `GraphQL-Preflight` and `Accept`.
- Multipart requests that follow the GraphQL multipart request spec, including the `operations` and `map` fields and the uploaded files.
- WebSocket connections that speak `graphql-transport-ws` or `graphql-ws`, including the `connection_init` payload and every later message.
- Operations that request streamed responses through `@defer`, `@stream`, subscriptions, or server-sent events.
- Requests that arrive through the MCP and OpenAPI adapters (`src/HotChocolate/Adapters`), which translate tool calls and REST requests into GraphQL operations.

Trusted: the application developer's schema, resolvers, and configuration; the Fusion gateway configuration and the source schema SDL it was composed from; the contents of a persisted operation store, which a build pipeline writes; and the GraphQL documents and schema that Strawberry Shake generates code from.

Partly trusted: a Fusion source schema is operated by the gateway owner, so its data is trusted. A source schema response that crashes the gateway, or that places data in another client's response, is still in scope. Strawberry Shake parses responses from servers the client application chose to call. A Mocha message arrives from any producer that can publish to the broker, which is often a different service; a producer can set every header and the body of the messages it sends. Messages sent through the Mocha mediator stay in the process and come from application code.

### Default security policy

`AddGraphQLServer()` (`src/HotChocolate/AspNetCore/src/AspNetCore/Extensions/HotChocolateAspNetCoreServiceCollectionExtensions.cs`) and `AddGraphQLGateway()` (`src/HotChocolate/Fusion/src/Fusion.AspNetCore/DependencyInjection/`) apply a default security policy unless the application passes `disableDefaultSecurity: true`. The policy enforces cost limits, disables introspection outside the Development environment, and adds a field cycle depth rule. The request size limit defaults to `ServerDefaults.MaxAllowedRequestSize`. Multipart requests require the `GraphQL-Preflight` header by default (`GraphQLServerOptions`). Exception details appear in responses only when `IncludeExceptionDetails` is set, which defaults to `Debugger.IsAttached`. The parser enforces the limits in `ParserOptions` (`src/HotChocolate/Language/src/Language.Utf8/ParserOptions.cs`).

Judge each finding against this default configuration. When a finding needs a non-default option, name the option.

## Components that matter most / least

Highest priority, in order:

1. The lexer and parser in `src/HotChocolate/Language/src/`: unbounded recursion, unbounded allocation, and limit bypasses.
2. The ASP.NET Core transport in `src/HotChocolate/AspNetCore/src/`: request parsing, multipart handling, WebSocket protocol handling, the SSE and incremental delivery formatters, and the per-request limits.
3. Validation (`src/HotChocolate/Core/src/Validation/`) and cost analysis (`src/HotChocolate/CostAnalysis/src/`): an operation that passes both and still consumes resources far beyond its computed cost, for example through fragments, aliases, directives, list inputs, variable coercion, `@defer`, or `@stream`.
4. Authorization in `src/HotChocolate/Core/src/Authorization/` and `src/HotChocolate/AspNetCore/src/AspNetCore.Authorization/`: reaching data protected with `@authorize` or `[Authorize]` through another path, such as the `node` and `nodes` fields, interfaces and unions, subscriptions, the gateway, or filtering, sorting, and projections on a protected field.
5. Persisted operations (`src/HotChocolate/PersistedOperations/src/`): running a document that is not in the store while `OnlyAllowPersistedDocuments` is on, and path traversal through an operation ID in the file system store.
6. Isolation between requests: Hot Chocolate pools and reuses execution objects such as the request and operation contexts, and Green Donut caches DataLoader results. Data from one request or user that appears in another's response is in scope, as is a `Cache-Control` header from `src/HotChocolate/Caching/` that lets a shared cache store a private response.
7. The Fusion gateway (`src/HotChocolate/Fusion/src/Fusion.Execution/` and `Fusion.AspNetCore/`): building source schema requests from client input, propagating headers, merging source schema results, and resource use during planning and execution.
8. The MCP and OpenAPI adapters, and the Apollo Federation subgraph support in `src/HotChocolate/ApolloFederation/`, in particular the `_entities` field.
9. Mocha's handling of inbound messages: the envelope parsers in `src/Mocha/src/Mocha.Transport.*/`, resolving a message type from the `MessageType` and `EnclosedMessageTypes` headers, deserialization in `src/Mocha/src/Mocha/Serialization/`, request and reply correlation, the inbox, and saga state. A crafted message that reaches a consumer it was not routed to, materializes a type the application did not register, changes another conversation's saga or reply, or stops the consumer host is in scope.

Lower priority but in scope: the data integrations in `src/HotChocolate/Data/`, `MongoDb/`, `Raven/`, `Marten/`, and `Spatial/`; the Strawberry Shake client runtime in `src/StrawberryShake/Client/src/`; and the Nitro command-line tool in `src/Nitro/`.

Out of scope: `src/Mocha/src/mocha-visualizer/` (an npm visualization component, not covered by the security policy), `website/`, `templates/`, benchmarks, examples, test projects, and `src/CookieCrumble/` (test utilities). Strawberry Shake code generation and Fusion schema composition run on developer machines and in build pipelines with trusted input, so they are in scope only when an issue reaches a running application.

## How to exercise it

The image has the .NET SDK that `global.json` pins, with its `net11.0` runtimes. Every project in `src/All.slnx` is restored for every target framework, so any of them builds offline; tests run on `net11.0`, the framework CI builds and tests. The test projects CI runs, every `*.Tests.csproj` in `src/All.slnx`, are prebuilt in Debug for `net11.0`, and `/opt/graphql-platform/test-projects.txt` lists them.

- Run every prebuilt suite: `graphql-platform-test`. Run one or more: `graphql-platform-test <path to csproj> ...`. Results go to `/tmp/graphql-platform-test-results`.
- Run one project directly: `dotnet test --project <csproj> --framework net11.0 --no-build`. Tests run on xUnit v3 under Microsoft Testing Platform, so select tests with `--filter-class <full class name>` or `--filter-method <full method name>`, not `--filter`.
- After editing a project: `dotnet build <csproj> --no-restore --framework net11.0`. The build treats warnings as errors and enforces code style, so keep new code warning-free.
- Snapshot tests use CookieCrumble. A missing snapshot is written on the first run, and a mismatch is written to `__snapshots__/__mismatch__/` next to the test file.
- A server-side reproducer is usually a test in `src/HotChocolate/Core/test/Execution.Tests/` that builds a schema with `new ServiceCollection().AddGraphQL()` and calls `ExecuteRequestAsync`. A transport reproducer goes in `src/HotChocolate/AspNetCore/test/AspNetCore.Tests/`, built on `ServerTestBase` and an in-process `TestServer`. A gateway reproducer goes in `src/HotChocolate/Fusion/test/Fusion.AspNetCore.Tests/`. A Mocha reproducer goes in `src/Mocha/test/Mocha.Tests/`, or in `src/Mocha/test/Mocha.Transport.InMemory.Tests/` when the message has to pass through a transport.

The image has no Docker and no network. Tests whose fixtures start a service container through Testcontainers, such as the PostgreSQL, MongoDB, and NATS fixtures in the `CookieCrumble.Resources.*` projects, fail when the fixture starts, and so do tests that download from the network. For a finding in one of those integrations, reproduce it with an in-memory or SQLite equivalent where one exists, or show it from the code and state the service the reproducer needs.

## How you rate severity

Two published advisories set the scale: GHSA-qr3m-xw4c-jqw3, a parser stack overflow from deeply nested documents, was rated critical, and GHSA-vvgm-mr25-hvr2, memory exhaustion from unbounded WebSocket message buffering, was rated high.

- Critical: remote code execution; a single unauthenticated request that terminates the server process in the default configuration, such as a `StackOverflowException`; reading or changing data protected with `@authorize` or `[Authorize]` without the required authorization, in the default configuration; one client's data in another client's response.
- High: unauthenticated exhaustion of memory or CPU through a few requests that stay within the default limits; a bypass of the default security policy, the request size limit, or `OnlyAllowPersistedDocuments`; path traversal in a persisted operation store; an authorization bypass that needs a documented, non-default but common option; a Mocha message that reaches a consumer it was not routed to, materializes a type the application did not register, or changes another conversation's saga or reply.
- Medium: denial of service that needs sustained traffic or an option such as `disableDefaultSecurity: true` or request batching; exception details or schema details disclosed while the defaults hide them; a bypass of the `GraphQL-Preflight` check; a single Mocha message that stops the consumer host or blocks its endpoint.
- Low: a crash of the Strawberry Shake client caused by a malformed server response; an issue that needs the application to use an option the documentation describes as unsafe.

Rate a finding by what an attacker can demonstrate against the default configuration, and state any configuration the finding depends on.

## Anything to leave alone

- Introspection in the Development environment, and exception details shown while a debugger is attached or after the application enabled them.
- Fields or types that the application left without authorization: the schema and resolvers belong to the application developer.
- Denial of service that requires control over the schema, the resolvers, or the gateway configuration.
- A vulnerable NuGet dependency without a reachable path through these libraries.
- Test failures that come from the missing network or Docker, described under "How to exercise it".

## Reports and patches

For each finding, give the affected package, the source location, the entry point a client reaches, the configuration it needs, and a reproducer, preferably a test in one of the prebuilt test projects. Propose the smallest patch that fixes the root cause, with a regression test. Do not raise or remove a limit, weaken authorization, or delete a failing test to make a reproducer pass. Group findings that share a root cause.
