# inqwise-indexer

## Purpose and trust boundaries

inqwise-indexer maintains derived document indexes and exposes typed reports for
applications and AI agents. The repository includes Vert.x services, indexing
and load workflows, provider-neutral query contracts, an operator web console,
and a Hacker News reference integration.

Treat HTTP request bodies, paths, query parameters, submitted document JSON,
report parameters, and external source responses as untrusted. Pay particular
attention to validation before action acceptance, document transformations,
query planning, report execution, and rendering data in the web console.

Caller identity and consumer scope must come from trusted server-side context.
User parameters must not widen mandatory report filters or choose physical
indexes, queues, provider query objects, target IDs, or indexer IDs. Assess
whether the intersection of report scope, consumer scope, and user filters is
preserved through codecs, service dispatch, and provider execution.

## Areas to examine

- REST and EventBus service boundaries, input validation, and error handling.
- Report scope enforcement, published-index resolution, and information exposure.
- Target-action preparation, routing, lifecycle commands, retries, and cleanup.
- Load workflows and externally supplied data that can exhaust resources.
- Web-console rendering and proxy behavior across API boundaries.
- Provider discovery and composition, distinguishing trusted packaged Java
  providers from untrusted request data.

Authentication, authorization policy, and trusted caller resolution are supplied
by the embedding application or gateway. The documented local deployment uses
in-memory storage, queues, and repositories and is intended for evaluation.
Account for those assumptions when demonstrating impact. Report security
boundary failures with the required deployment and attacker access stated
explicitly; distinguish expected in-memory data loss from a vulnerability.

## Build and exercise

The checkout is at `/src`. The Dockerfile builds every Maven module with JDK 21,
installs reactor artifacts into the local Maven repository, and retains the
frontend plugin's Node/npm installation and dependency caches.

Run the Java tests offline from `/src`:

```sh
npm_config_offline=true mvn -B -ntp -o test
```

Run the frontend tests:

```sh
cd /src/indexer-web/src/main/frontend
PATH="/src/indexer-web/target/node:$PATH" npm test
```

Build offline with `npm_config_offline=true mvn -B -ntp -o package -DskipTests`.
Test reports are under each module's `target/surefire-reports`. The combined
reference application is
`indexer-example-hacker-news-node-application/target/inqwise-hacker-news-indexer-node.jar`.
The README documents its launch arguments and the local endpoint configuration
in `deployment/local`. External Hacker News access is unavailable during the
audit; use local fixtures or a local mock source for reproductions.

During enrollment verification, the reference application's
`HackerNewsIndexerNodeApplicationVerticleTest.startsNodeBeforeIngestionAndStopsInReverseOrder`
failed its shutdown-order assertion both during image setup and with networking
disabled. The image retains the test reports; this baseline failure does not
prevent building the project or running the remaining tests.

## Findings

Include the affected entry point, attacker-controlled values, deployment
assumptions, expected boundary, and demonstrated impact. Prefer a minimal local
reproducer and a focused regression test or patch. Assess severity from the
demonstrated confidentiality, integrity, or availability impact, stating any
authentication or privileged access requirements. Avoid relying on hypothetical
production adapters that are absent from this repository.
