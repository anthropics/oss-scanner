# BTCPayServer.Lightning threat model

BTCPayServer.Lightning is a C# client library that exposes common interfaces for Lightning implementations, including LND, Core Lightning, Eclair, LNDHub, and Phoenixd. Applications use it to parse invoices and connection settings, create and pay invoices, manage channels, and process HTTP, WebSocket, and JSON-RPC responses and events. It is a library embedded in a calling application, not a public server on its own.

## Scope and trust boundaries

Prioritize production code under `src/BTCPayServer.Lightning.Common/`, `src/BTCPayServer.Lightning.All/`, and each backend client package. Review BOLT11 and Bech32 parsing, amounts and fee calculations, connection string handlers, credential loading, TLS validation, HTTP authentication, JSON serialization, RPC framing, event listeners, and concurrency around payment operations. Generated client code is in scope when its behavior is reachable through a supported client configuration.

Treat invoice strings and data received from remote nodes or services as potentially adversarial. Establish whether an attacker controls a payment request, a backend response, a network intermediary, or a connection setting in the actual calling application. Applications choose backend endpoints and credentials; an administrator's ability to configure a privileged connection does not by itself demonstrate a library vulnerability. If connection strings or file paths are assumed to come from an untrusted caller, identify the realistic workflow that accepts them.

Credentials may authorize invoice creation, payments, channel operations, or broader node administration. Assess what a specific credential permits. The library does not itself custody a wallet, but its clients can trigger financial operations using the configured backend's authority.

## Security priorities

- Invoice parsing, signature and network validation, payment destinations, payment hashes and preimages, expiry handling, and correct units and bounds for amounts and fees.
- Unintended credential disclosure or reuse across requests, redirects, WebSockets, logs, error messages, or serialized connection settings.
- Enforcement of configured certificate and thumbprint validation, endpoint selection, and authentication. Explicitly setting `allowinsecure=true` opts out of normal transport protection; demonstrate a bypass of the protection the caller actually selected.
- Response and event parsing, request framing, cancellation, stream termination, resource consumption, and synchronization where malicious input can affect the embedding application's availability or payment state.
- Backend-specific differences that turn a common API request into an unintended payment, excessive fee, incorrect success result, or broader privileged operation.

Show how an issue in this library causes impact beyond the authority a malicious backend already has. Vulnerabilities solely inside Lightning node implementations or calling applications belong to those projects unless the library introduces the failure. Dependency findings need an affected, reachable path rather than only a version match.

## Build and offline reproduction

The scanner image contains the source tree at `/src`, the .NET 10 SDK, restored NuGet packages, and Debug build outputs for the solution, including `net10.0` and `netstandard2.0` library targets and the test assembly.

Run `btcpayserver-lightning-oss-test` for the existing tests that need no external services: invoice and connection string parsing, amounts, JSON conversion, Phoenixd credential files, injected WebSocket HTTP handlers, duplicate locks, and Core Lightning request and fee serialization against temporary loopback servers. The wrapper has a five-minute timeout and uses `--no-build --no-restore`.

For a focused reproducer, use `dotnet test tests/BTCPayServer.Lightning.Tests.csproj --no-build --no-restore --configuration Debug --filter '<test filter>'`. After changing code, rebuild with `dotnet build BTCPayServer.Lightning.sln --no-restore --configuration Debug` using the cached dependencies.

The integration tests in `CommonTests` and `LndListenStreamTests` require the Bitcoin and Lightning services described in `tests/docker-compose.yml`; these are not running in the scanner image. The offline wrapper selects only the standalone methods from `CommonTests` and excludes live-node listener tests. Use local fixtures, injected HTTP handlers, or loopback servers for additional reproducers; do not depend on downloading images, contacting public nodes, or using real funds.

## Findings and severity

Assess severity from demonstrated attacker control and impact in a realistic embedding application. Remote code execution, disclosure of credentials that enable theft, or unintended payments with meaningful fund loss can be critical when reachable. Rate fee errors, narrower credential exposure, incorrect payment state, and denial of service according to the required privileges, affected operations, and practical reach. A parser exception alone is not evidence that the caller's process terminates or that the service becomes unavailable.

Include the affected commit and source locations, attacker input, backend and client configuration, credential capabilities, required calling behavior, a self-contained reproducer, expected versus observed behavior, and concrete impact. Use dummy credentials and isolated fixtures. Group symptoms sharing one root cause and propose a minimal patch and regression test where practical.

Disclose findings privately through the configured GitHub security advisory or security email channel. Do not open public issues or publish unpatched reproduction details.
