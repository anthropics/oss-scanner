# AT Protocol threat model

## Project and trust boundaries

This repository is the TypeScript reference implementation of AT Protocol, the
decentralized social protocol used by Bluesky. It includes the Personal Data
Server (PDS), the Bluesky AppView, Ozone moderation tooling, OAuth implementations,
and libraries used by other AT Protocol applications.

Treat unauthenticated HTTP clients, authenticated ordinary users, OAuth clients,
remote PDS instances, repository and firehose events, blobs, records, handles,
DID documents, and remote metadata as potentially malicious. Federation does not
make remote servers trusted. A user controlling their own account or server must
not gain another account's credentials, private data, signing keys, or authority.

Public repository records and public social data are intentionally readable;
public availability alone is not a confidentiality defect. Administrative and
moderation APIs have separate authorization requirements. Distinguish a malicious
ordinary user from an attacker who already possesses operator credentials or
controls the local host.

## Priorities

- `packages/pds`: authentication, account creation and recovery, app passwords,
  OAuth integration, repository writes, blob handling, proxying, and account
  isolation. Include private account data and privileged operations.
- `packages/oauth`: OAuth provider and clients, authorization and consent,
  redirect validation, client metadata, token issuance and refresh, DPoP, key
  handling, and enforcement of scopes and account permissions.
- `packages/repo`, `packages/crypto`, `packages/lex`, and `packages/lexicon`:
  repository signatures, Merkle Search Trees, CAR/CBOR decoding, validation of
  untrusted records, and malformed input that defeats integrity checks or causes
  disproportionate resource consumption.
- `packages/identity`, `packages/did`, and the resolver and fetch implementations
  in `packages/internal`: handle/DID resolution, SSRF defenses, redirects,
  DNS-related trust boundaries, and remote metadata processing. Use local fixtures
  to model attacker-controlled resolution and responses.
- `packages/xrpc`, `packages/xrpc-server`, `packages/lex/lex-server`,
  `packages/sync`, `packages/bsync`, and `packages/bsky`: request validation,
  service authentication, hostile federation input, ingestion, authorization, and
  isolation across users and upstream servers.
- `packages/ozone`: moderation and administrative authorization, including access
  to non-public moderation data.

Service entry points are under `services/`; implementation code is primarily
under `packages/`. Canonical protocol schemas are under `lexicons/`. Review the
source that produces generated files rather than proposing generated-only fixes.
Third-party dependencies are relevant when a defect is reachable through this
project, but a dependency advisory without a demonstrated affected code path is
not an actionable project finding. Production infrastructure and secrets are not
available in this checkout and are not necessary for a reproducer.

## Build and offline tests

The Dockerfile keeps the full checkout, development dependencies, generated code,
and build outputs in `/src`. It uses Node.js 24, installs the pnpm version specified
by `package.json`, and runs `pnpm install --frozen-lockfile` and `pnpm run build`
while networking is available. PostgreSQL, Redis, and Chromium are installed for
local service and browser reproductions; Puppeteer uses the system Chromium
instead of downloading a browser at test time.

Run tests from `/src` with external networking disabled. Loopback services and
locally hosted attacker fixtures are still usable.

The root Vitest suite covers the configured library projects without requiring
the Docker-based development infrastructure:

```sh
cd /src
pnpm test:unit --maxWorkers=2
```

Examples of Jest suites that do not require PostgreSQL or Redis:

```sh
cd /src/packages/crypto && pnpm test --runInBand
cd /src/packages/lexicon && pnpm test --runInBand
cd /src/packages/repo && pnpm test --runInBand
cd /src/packages/xrpc-server && pnpm test --runInBand
```

For service tests, start disposable databases inside the container. These are
test-only credentials, not deployment settings:

```sh
pg_conftool 15 main set port 5433
pg_ctlcluster 15 main start
runuser -u postgres -- psql -p 5433 -v ON_ERROR_STOP=1 \
  -c "CREATE ROLE pg WITH LOGIN SUPERUSER PASSWORD 'password';"
redis-server --port 6380 --daemonize yes --save '' --appendonly no
export DB_POSTGRES_URL=postgresql://pg:password@127.0.0.1:5433/postgres
export REDIS_HOST=127.0.0.1:6380
export LOG_ENABLED=false
export NODE_OPTIONS=--experimental-vm-modules
```

Invoke the runners directly to avoid Docker Compose wrappers and browser download
pretest hooks. Tests create local services and database schemas using
`packages/dev-env`; do not point them at production services or databases.

```sh
cd /src/packages/pds && pnpm exec jest --runInBand \
  --testPathIgnorePatterns 'account-manager.test.ts|oauth.test.ts|oauth-deactivation.test.ts'
cd /src/packages/bsky && pnpm exec vitest run --maxWorkers=1
cd /src/packages/identity && pnpm exec jest --runInBand
```

The excluded PDS tests launch Chromium. Running them requires an unprivileged
user with writable test directories and a working Chromium sandbox; do not
interpret a root-user browser sandbox error as a project vulnerability. The
browser source and system browser remain available for targeted reproductions.
Use existing tests and `interop-test-files/` as fixtures. Any reproducer that
normally resolves public hosts must instead use local mocked DNS/HTTP responses
in the offline environment.

## Impact and reporting

Prioritize demonstrated account takeover, cross-account or cross-service
authorization bypass, credential or signing-key exposure, forgery of accepted
repository data, remote code execution, and SSRF that reaches otherwise protected
resources. For denial of service, demonstrate the remote attacker's cost, the
resources exhausted, and whether the impact affects one request, one account, or
the whole service. Do not assign a severity based only on a theoretical primitive.

Reports should identify the affected source and entry point, attacker privileges
and prerequisites, a minimal offline reproducer, observed versus intended
behavior, and concrete impact. Where possible, include a focused source patch and
a regression test that preserves protocol interoperability.

Send findings privately to `security@bsky.app`, as specified by `SECURITY.md`.
Do not open public issues or test against live Bluesky or third-party services.
