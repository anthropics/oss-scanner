# gramsrv main: security audit guidance

## Project and scope

gramsrv is an independent, Apache-2.0-licensed Telegram-compatible server in Go
for self-hosted messaging networks. This enrollment targets the public `main`
branch: `cmd/telesrv` is the monolithic server and `cmd/telesrv-admin` is its
administration UI. The separate `v2` microservice architecture is not this scan's
target. The Go module and executable names remain `telesrv`.

The server processes remote MTProto traffic, account authentication, messaging,
file uploads and downloads, Bot API requests, web endpoints, and call/media
traffic. It uses PostgreSQL and Redis. Its published MTProto dependency is
`github.com/iamxvbaba/td`, as pinned in `go.mod`; its downloaded source remains
available in `/go/pkg/mod`. Dependency issues reachable through gramsrv are
relevant; identify the owning module and version in such reports.

## Adversaries, assets, and trust boundaries

Consider unauthenticated network peers, ordinary authenticated users, malicious
group/channel members and administrators with limited rights, bot owners, and
users supplying media, URLs, message entities, or malformed protocol objects.
Accounts and sessions controlled by one attacker must not gain another user's
private messages, files, auth keys, sessions, or permissions. Group/channel
membership and granular administrator rights must be enforced independently of
client-supplied IDs, access hashes, pagination cursors, or cached projections.

The host administrator, configured external service credentials, database, and
Redis deployment are trusted infrastructure. Do not assume a remote attacker
can first edit server configuration, source code, or database rows. Escalation
from a limited application/admin role to stronger privileges remains in scope.
Ordinary cloud chats are server-managed; the fact that the server can read
their plaintext is not itself an end-to-end encryption vulnerability.

## Priority components and inputs

- `internal/mtprotoedge`, `internal/rpc`, and the pinned protocol dependency:
  malformed transport/TL input, authentication binding, temporary/permanent
  keys, replay handling, session revocation, and bounded resource use.
- `internal/app/auth`, `internal/app/passkey`, `internal/app/telegramlogin`,
  `internal/telegramloginhttp`, and `internal/otpdelivery`: login, verification,
  credential recovery, rate limits, and token/session lifecycle.
- `internal/app/messages`, `channels`, `contacts`, `privacy`, `updates`,
  `secretchat`, `bots`, and `internal/store`: cross-user isolation, access
  control, membership changes, offline/replayed updates, and concurrent writes.
- `internal/app/files`, `internal/web`, and storage backends: media ownership,
  download authorization, file references, traversal, URL fetching/SSRF, upload
  limits, decompression, and subprocess argument handling.
- `internal/botapi`, `internal/adminapi`, `cmd/telesrv-admin` and its `web/` UI:
  authentication, scoped permissions, webhooks, CSRF, stored/reflected XSS, and
  attacker-controlled data displayed to a more privileged operator.
- `internal/sfu`, `internal/turnsrv`, `internal/app/groupcalls`, and
  `internal/app/livestream`: call/room authorization, relay abuse, packet
  parsing, and remotely triggered resource exhaustion.

Public development fixtures include a fixed login code and a published test RSA
key. Their documented existence is intentional. Investigate whether production
configuration can accidentally enable them, whether guards can be bypassed,
or whether test material crosses into a production trust boundary. Explain the
configuration needed to reproduce a finding; do not assume all deployments use
the demonstration settings.

## Offline build and tests

The Dockerfile keeps the checkout at `/src`, Go modules/toolchain, npm
dependencies, FFmpeg, PostgreSQL 17, and Redis in the image. Binaries are under
`/opt/gramsrv/bin`. All commands below run inside the disposable audit container;
they require no external network or production data.

Start with the normal Go suite (database-dependent tests skip unless enabled):

```sh
cd /src
go test -p 2 ./... -count=1 -timeout 10m
npm --prefix cmd/telesrv-admin/web run build
npm --prefix cmd/bots/grammystore run check
npm --prefix cmd/bots/grammystore test
```

To enable database and Redis tests, start the bundled loopback-only services:

```sh
gramsrv-test-services
export TELESRV_TEST_POSTGRES_DSN='postgres://postgres@127.0.0.1:5432/gramsrv_test?sslmode=disable'
export TELESRV_TEST_REDIS_ADDR='127.0.0.1:6379'
go test -p 1 ./internal/store/postgres ./internal/store/redisstore ./internal/rpc ./cmd/telesrv-admin -count=1 -timeout 15m
```

Use a disposable database whose name contains `test`; the PostgreSQL test
helpers apply migrations and modify records. Run integration packages serially
to avoid shared test-state interference. Targeted `go test -run ...` commands
are useful during reproduction. Tests requiring S3, real media catalogs,
official Telegram connectivity, or explicitly enabled load environments have
their own environment gates and are not provisioned here. These skips do not
establish that those feature paths are secure. Inspect the code and use local
fixtures/mocks when applicable. Deployment settings are documented in
`.env.example` and `docs/configuration.en.md`.

## Severity and useful reports

Assess severity from demonstrated attacker privileges, deployment assumptions,
reachability, victim interaction, scope, persistence, and impact. Remote code
execution, account takeover, broad unauthorized private-data access, or an
authentication bypass can warrant high/critical severity. Quantify the cost
and duration of denial of service and whether it affects one session or the
whole service. Avoid rating every crash, missing check, or malformed input as
critical without an impact chain.

Provide the affected commit and paths, root cause, exact prerequisites, and a
small self-contained reproducer or regression test. For permission findings,
show the attacker/victim roles and expected versus observed access. Suggest a
focused patch preserving protocol and data invariants, and distinguish a
proposed fix from a validated one. Group findings sharing the same root cause
and enumerate affected entry points. Report privately to the registered email.

Do not test the public project website, community servers, Telegram's servers,
or third-party accounts. Client repositories and the private development
workspace are outside this enrollment; all reproductions should be local.
