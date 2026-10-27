# BTCPay Server threat model

BTCPay Server is a self-hosted, non-custodial Bitcoin payment processor. It is an ASP.NET Core application that serves anonymous customers, merchant users, store owners, and instance administrators. It connects to PostgreSQL, NBXplorer, Bitcoin nodes, Lightning implementations, email servers, exchange-rate providers, and other explicitly configured services.

## Scope and priorities

Prioritize vulnerabilities in the production code under `BTCPayServer/`, `BTCPayServer.Data/`, `BTCPayServer.Client/`, `BTCPayServer.Common/`, `BTCPayServer.Rating/`, and `BTCPayServer.Abstractions/`, especially:

- Authentication, account recovery, two-factor authentication, cookies, API keys, authorization policies, and privilege changes.
- Isolation between users, stores, organizations, and instance administrators. A user authorized for one store must not read or modify another store's protected data.
- Invoice, payment, refund, payout, pull-payment, wallet, signing, webhook, and payment-protocol integrity.
- Server-side requests, redirects, file and archive handling, template or markup rendering, plugin management, and stored or reflected browser content.
- Secret handling, including wallet material, Lightning credentials, API keys, connection strings, and tokens.
- Parser and state-machine behavior where adversarial payment data, webhook traffic, API input, or external service responses enter the application.

Tests and documentation may be used to understand intended behavior or build a reproducer. A weakness confined to a deliberately permissive test fixture is not a production vulnerability. Plugins shipped in this repository are in scope; unrelated third-party plugins are not.

## Attackers and trust boundaries

Treat unauthenticated Internet clients, authenticated ordinary users, store-scoped users, customers, webhook senders, uploaded files, HTTP headers, API payloads, payment data, and responses from configured remote services as potentially adversarial. Verify the actual permissions and configuration required to reach an entry point.

Instance administrators and operators with arbitrary host, database, or plugin-installation access are trusted for those intended powers. Store owners are trusted only within their own stores. Merely showing that trusted server-side code or an administrator can bypass a boundary is not a vulnerability; demonstrate an unintended privilege gain or a path from less-trusted input.

BTCPay Server generally does not hold a merchant's on-chain private keys, but it handles sensitive payment metadata and may connect to hot wallets or Lightning nodes. Findings should describe the concrete confidentiality, integrity, availability, or fund-loss impact rather than assuming custody.

## Build and offline reproduction

The scanner image contains the complete source tree, .NET 10 SDK, restored NuGet packages, and Debug build outputs. Run `btcpayserver-oss-test` from `/src` for the prepared fast test category without network access. Individual tests can be run with `dotnet test --project BTCPayServer.Tests/BTCPayServer.Tests.csproj --no-build --no-restore --configuration Debug --filter-method <fully-qualified-name>`.

Integration and Playwright suites normally require the Docker Compose environment described in `BTCPayServer.Tests/`, including PostgreSQL, NBXplorer, Bitcoin, Lightning, Tor, Mailpit, and a browser. Those external services are not prepared in this image. Prefer in-process tests or local fakes for reproducers, and do not require downloads during the offline audit.

## Findings, severity, and patches

Prioritize unauthenticated remote code execution, authentication bypass, exposure of secrets or signing capability, fund redirection or theft, and broad cross-store or administrator compromise as critical when demonstrated. Treat narrower authorization bypasses, meaningful cross-store disclosure or modification, stored script execution against privileged users, and exploitable server-side request forgery according to demonstrated reach and prerequisites. Availability issues should account for whether an unauthenticated remote attacker can reliably affect the whole instance.

For each report, include the affected commit and source locations, required configuration and permissions, the exposed entry point, a self-contained reproducer, expected versus observed behavior, and concrete impact. Prefer a focused regression test and minimal candidate patch. Group symptoms sharing one root cause and do not report dependency advisories without showing that BTCPay Server is affected and reachable.

Send reports only to the configured security contact. Do not open public issues or publish unpatched reproduction details.
