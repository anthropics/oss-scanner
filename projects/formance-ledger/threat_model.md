# Formance Ledger threat model

## Purpose and untrusted input

Formance Ledger is an MIT-licensed Go service for recording financial transactions,
account balances, and immutable ledger logs in PostgreSQL. Applications use its HTTP
APIs and Numscript language to describe transfers. It records money movements; it
does not itself hold funds or execute bank payments.

Treat HTTP paths, headers, JSON bodies, pagination cursors, query filters, account
addresses, asset names, amounts, metadata, imported logs, and Numscript programs and
variables as untrusted. Concurrent requests, retries, bulk operations, and cancellation
are relevant attacker-controlled conditions.

Deployment configuration, database credentials, configured OIDC issuers, and operator
access are trusted. Evaluate authentication with JWT/OIDC authentication enabled.
An intentionally unauthenticated development deployment is not an authentication
bypass. Do not assume that every authenticated caller is permitted to access every
ledger: inspect the configured scope checks and document the permissions needed.

## Priority components and security goals

- `internal/api/` and `cmd/`: request validation, JWT integration, ledger selection,
  scope enforcement, query handling, bulk requests, and import/export endpoints.
- `internal/controller/` and `internal/storage/`: isolation between ledgers and
  buckets, SQL construction, transaction atomicity, idempotency, balance consistency,
  locking, and preservation of the audit log across retries and failures.
- `internal/machine/`, `internal/queries/`, and `pkg/`: Numscript execution, account
  and asset validation, integer handling, query substitution, and resource bounds.
- `internal/replication/`: export destinations, credential handling, HTTP exporters,
  and replication inputs. Distinguish a trusted administrator choosing a destination
  from a less privileged caller reaching services or credentials they cannot access.

Prioritize reproducible authorization bypass, SQL injection, cross-ledger disclosure
or modification, and attacker-triggered corruption of financial state. For financial
invariants, show how the input violates the intended rules for that ledger; deliberately
permitted overdrafts and movements involving the special `world` account are not by
themselves vulnerabilities.

The separately maintained Formance Gateway, Operator, Console, and cloud control plane
are outside this repository's scope. Inspect dependencies when Ledger exposes the
vulnerable behavior, but identify the affected component precisely.

## Build and local reproduction

The checkout is at `/src`; the built executable is `/usr/local/bin/ledger`. Go, its
module cache, PostgreSQL, Python, curl, and jq remain in the image. Go build symbols
are retained. The service unit tests and the local client module tests run during the build.
Repeat them offline with:

```sh
cd /src
GOPROXY=off go test -count=1 -timeout=10m . ./cmd/... ./internal/... ./pkg/...
cd /src/pkg/client
GOPROXY=off go test -count=1 -timeout=5m ./...
```

Use `ledger serve --help` and `ledger --help` for current configuration flags. For
manual database-backed reproducers, start the packaged PostgreSQL instance with
`service postgresql start` and create a disposable local role and database as the
`postgres` user. Inspect `test/e2e/` for API and authentication examples.

Tests behind the `it` tag require a Docker daemon and service images, including
PostgreSQL, NATS, and ClickHouse. `test/migrations` also requires Docker even without
the `it` tag. These tests are not part of the offline test path;
do not assume those services or downloadable images are available in the scanner.
Never use production services, credentials, or real customer data for reproduction.

## Severity and report expectations

Assess severity from demonstrated impact, reachability, and required permissions.
Unauthenticated code execution, broad authorization bypass, or arbitrary financial
state modification may be critical. Reproducible SQL injection, unauthorized access
to another ledger, or financial-state corruption by a restricted caller is high
impact; explain any privileges and deployment conditions that limit it. Availability
issues should distinguish a failed request from sustained service-wide denial of
service and quantify the resources required.

Provide a minimal reproducer, affected revision and files, configuration and permissions,
expected versus actual behavior, and a proposed regression test or patch where possible.
Separate confirmed findings from hypotheses. Keep reports private to the configured
security contact.
