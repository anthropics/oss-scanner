# Indigo threat model

## Project and trust boundaries

Indigo contains Go implementations of AT Protocol services, protocol libraries,
and developer tools. It is separate from the TypeScript `bluesky-social/atproto`
repository. This enrollment includes the complete Indigo checkout, not just one
daemon.

Treat remote PDS instances, firehose peers, ordinary HTTP/WebSocket clients,
repository archives and events, blobs, records, handles, DID documents, OAuth
metadata, and moderation subjects as potentially malicious. A valid signature
from an attacker-controlled identity does not grant authority over another
identity or account. Public repository records and public firehose data are
intentionally readable; public availability alone is not a confidentiality bug.

## Priorities and intended behavior

- `cmd/relay`: upstream discovery and subscriptions, repository and identity
  verification, hostile CAR/CBOR and event handling, replay and sequencing,
  resource limits, administrative authentication, and the admin UI. Relay checks
  repository integrity and signatures but intentionally does not validate public
  records against application Lexicon schemas; that omission alone is not a bug.
- `cmd/tap`: synchronization and backfill, repository verification, administrative
  access, filtering, event delivery and acknowledgments, and webhook behavior.
  Distinguish an authorization bypass in a configured authenticated deployment
  from an operator deliberately running an unauthenticated local instance.
- `cmd/rainbow` and `events`: firehose subscription and fan-out, malformed frames,
  consumer isolation, connection handling, and remotely induced resource use.
  Rainbow intentionally passes through upstream events without independently
  validating their signatures, repository trees, or hashes; evaluate its intended
  upstream trust boundary rather than treating that behavior alone as a bug.
- `cmd/hepa`, `cmd/beemo`, and `automod`: processing attacker-controlled account
  and record data, credential handling, and the boundary between a moderation
  subject's input and privileged moderation actions.
- `cmd/bluepages`, `atproto/identity`, `atproto/auth/oauth`, `util/ssrf`, and
  `xrpc`: DID/handle binding, remote metadata, redirects, DNS and HTTP trust
  boundaries, SSRF, OAuth state and token handling, and credential leakage.
- `atproto/repo`, `atproto/repo/mst`, `atproto/atcrypto`, `atproto/atdata`,
  `atproto/lexicon`, and the older `repo`, `mst`, and `carstore` packages:
  signatures, CID/content integrity, malformed archives and trees, key parsing,
  schema validation, and disproportionate parser or storage costs. Trace which
  implementation an affected daemon actually uses rather than assuming the
  modern and older packages have identical reachability.

Other commands and libraries remain available for analysis. Prioritize remotely
reachable code and shared protocol code over development-only stress tools and
examples. Operators and ordinary remote users are different attacker classes;
an operator's intentional configuration changes are not authorization bypasses.
Third-party advisories need a demonstrated affected path through Indigo.
Generated code is checked in; propose fixes to its source or generator when
appropriate, not just to a generated artifact.

## Build and offline testing

The Dockerfile keeps the checkout and generated code in `/src`, the Go toolchain,
C compiler and development libraries for CGO/SQLite, the Go module and build
caches, and Node.js 22 with Yarn. It compiles all Go packages, installs every
command under `/usr/local/bin` (on `PATH`), and compiles the test packages before
network access is removed. That compile-only step executes no individual tests
and is not a substitute for running them.

The Relay admin UI retains its source, installed dependencies, and generated
assets in `/src/cmd/relay/relay-admin-ui`. Its deployment assets are also copied
to `/src/public`, as in the repository's Relay build instructions. Sources and
debug information are retained; this is not a stripped production image.

Run the following inside the built image with external networking disabled:

```sh
cd /src
export GOPROXY=off GOSUMDB=off
go test -count=1 -p 2 -timeout 10m \
  -skip '^(ExampleGet|TestLiveHostChecker)$' ./...
```

Examples of targeted protocol and service suites:

```sh
go test -count=1 -p 2 -skip '^(ExampleGet|TestLiveHostChecker)$' \
  ./atproto/... ./repo/... ./mst/... ./carstore/... ./util/ssrf/...
go test -count=1 -p 2 -skip '^(ExampleGet|TestLiveHostChecker)$' \
  ./cmd/relay/... ./cmd/tap/... ./cmd/rainbow/... ./automod/...
```

Loopback services are still available without external networking. Tap's test
helpers use SQLite and a mocked identity directory with local HTTP/WebSocket
servers. Prefer existing test fixtures and local mocked upstreams to live PDS,
PLC, DNS, Redis, or search services. The command explicitly excludes two live
network checks: `ExampleGet` in `atproto/atclient` calls the public Bluesky API,
and `TestLiveHostChecker` in `cmd/relay/relay` resolves real identities and calls
public PDS hosts. These fail when external networking is disabled; replace their
upstreams with local fixtures for a targeted reproduction, not production access.
Other upstream tests are explicitly skipped
because they require live services; retain those skips rather than enabling
production network access. The `localinterop` build tag requires additional
locally running services and is not part of the default test command above.

The admin UI can be rebuilt without fetching dependencies:

```sh
cd /src/cmd/relay/relay-admin-ui
yarn --offline build
```

Start binaries with `--help` to discover current flags. For service reproductions,
use temporary data directories, test-only credentials, loopback listeners, and
local attacker-controlled peers. Do not run a global crawl or subscribe to the
live network from the scanner environment.

## Impact and reporting

Prioritize accepted forged or cross-identity repository data, remote code
execution, credential/signing-key exposure, administrative authorization bypass,
SSRF to protected resources, and remotely triggered service-wide denial of
service. Show the attacker's privileges and cost, the actual acceptance or access
path, and the extent of the impact; a malformed-input panic in a local developer
tool is not equivalent to crashing a publicly reachable daemon.

Reports should include the affected daemon or consumer and source path, minimal
offline reproduction steps, observed versus intended behavior, concrete impact,
and a focused patch with a regression test where possible. Preserve AT Protocol
interoperability and explain any behavior change.

Send findings privately to `security@bsky.app`. Do not open public vulnerability
issues or test against live Bluesky or third-party services.
