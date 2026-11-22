# Threat model

## What this project does and where untrusted input enters

Neo4j is an open-source graph database management system. This repository contains the
Community Edition sources: the database kernel and storage engine, the Cypher query
engine and its runtime, the Bolt network protocol server, the administration and import
tooling, and cypher-shell.

Assume all of the following is attacker-controlled or attacker-influenced:

- **Cypher queries** submitted by authenticated (and, where auth is misconfigured,
  unauthenticated) clients over Bolt (port 7687) and the HTTP(S) endpoints. Query text,
  query parameters, and query plan hints are all untrusted.
- **Stored data**: bytes previously written to record files, indexes, and logs, which
  may have been written by another (possibly malicious) user or an older/corrupted
  version of the store. Store-format parsing and upgrade/migration paths are in scope.
- **Files parsed at runtime**: CSV files consumed by `LOAD CSV` and the
  `neo4j-admin database import` tool, file/URL inputs reachable from queries, config
  files, and plugin/procedure JARs that administrators drop into the plugins directory
  (treat plugin loading as trusted-admin only, but the *loading mechanism* is in scope).
- **Wire-level input**: Bolt message framing and handshake, HTTP request bodies
  (transactional endpoint, import API), and routing/discovery messages. Clustering is
  an Enterprise feature and is not part of this repository.

## Components that matter most / least

- Highest value: the Cypher frontend/parser and planner-to-runtime handoff (the
  `community/cypher` tree, e.g. `front-end`, `planner`, `interpreted-runtime`), the Bolt
  server (`community/bolt`, `community/bolt-messages`), the HTTP server
  (`community/server`), authn/authz (`community/security`), procedure loading and
  sandboxing (`community/procedure`, `community/procedure-api`, `community/procedure-compiler`),
  the record store (`community/record-storage-engine`, `community/storage-engine-util`,
  `community/kernel`), CSV parsing (`community/csv`), and the import tool
  (`community/import-tool`, `community/import-api`).
- Important but lower priority: `community/io` (page cache), `community/ssl`,
  `community/dbms` (admin commands, config migration), `community/fabric`,
  `community/command-line`, `community/cypher-shell` (it is a client).
- The `packaging/` module mostly assembles distributions; only its scripts/launcher
  logic (e.g. argument handling in the Unix/Windows launchers) is interesting.
- Third-party dependencies (netty, lucene, parquet, snappy, etc.) are out of scope;
  report only vulnerabilities in Neo4j's own code in this repository.

## How to exercise it

- The build produces per-module test jars; `mvn -pl community/<module> -DskipTests=false surefire:test`
  works offline inside the image for individual modules.
- `community/kernel`, `community/community-it` and `community/neo4j-harness` contain GraphDatabaseAPI/embedded
  test harnesses that show how to start an instance programmatically.
- `cypher-shell` and the built distribution under `packaging/standalone` can start a
  real server (run with `--` flags; a loopback-only listener is fine for experiments).
- Unit-test classes under `*Test.java` in each module are good references for
  constructing stores and queries programmatically.

## How you rate severity

- **Critical**: unauthenticated remote code execution; auth bypass; escaping the
  procedure/security sandbox to execute arbitrary code or read arbitrary files;
  remote corruption or disclosure of data belonging to another database/tenant.
- **High**: injection (Cypher/HTTP), authenticated remote code execution, unrestricted
  file read/write reachable from query execution, unauthenticated DoS that crashes or
  hangs the server (not just a single query/transaction), memory-safety bugs in
  native/unsafe code paths.
- **Medium**: authenticated DoS of a single query/transaction or measurable
  performance-degradation bugs, info leaks (credentials, tokens, file paths) to
  authenticated users, store corruption on malformed-but-plausible input.
- **Low**: hardening issues, minor info leaks, client-side (cypher-shell) issues.

## Anything to leave alone

- Do not report issues that require the attacker to already have full OS-level access
  to the server, or that require an administrator to have installed a malicious plugin
  JAR (admin == trusted with the machine, by design).
- Do not report resource exhaustion that is inherent to allowing unbounded queries
  (e.g. a cross-product join) when it is bounded by documented configuration such as
  `db.transaction.timeout` (unlimited by default) or the transaction memory limits
  `db.memory.transaction.max` and `db.memory.transaction.total.max`; instead report it if
  a configured limit can be bypassed.
- Do not report missing rate limiting, brute-force-able weak passwords chosen by
  operators, or TLS configuration defaults.
- Known/already-CVE'd issues with existing fixes in the tree are not interesting.
