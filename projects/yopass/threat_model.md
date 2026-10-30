# Yopass threat model

## Purpose and trust boundaries

Yopass shares expiring secrets and files using client-side OpenPGP encryption.
The browser and Go CLI encrypt before uploading; decryption keys normally live
in the URL fragment and must not be sent to the server. Custom passwords and
optional Argon2id key derivation are also supported. The server stores
caller-supplied ciphertext in Memcached, Redis, disk storage or S3-compatible
storage. Checking OpenPGP armor does not prove a submitted payload is encrypted.

Treat HTTP requests, ciphertext, upload streams, filenames, URL parameters,
request and receipt tokens, and data returned from storage as untrusted. Review
the frontend as well as the API: an XSS can expose plaintext and decryption
keys. Secret URLs are bearer capabilities; knowing a secret ID permits fetching
its ciphertext, while decrypting it requires its key or password.

One-time retrieval, expiration, atomic claims, request fulfillment and read
receipts must enforce their documented behavior, including concurrent access.
OIDC sessions, verified email and domain restrictions, API tokens and read-only
mode must enforce the configured access policy. Receiving a shared secret is
intentionally possible without logging in; requiring authentication controls
creation as documented in docs/openid-connect.md.

Assume production uses HTTPS and the operator controls configuration, the OIDC
provider, storage credentials, trusted proxies and webhook destinations. Check
whether untrusted request data can cross those boundaries, rather than treating
an operator's ability to configure a destination as an SSRF on its own.

## Focus and scope

Prioritize pkg/server, pkg/yopass, cmd/yopass-server, cmd/yopass and website/src.
Include file path handling, streaming limits, cleanup, cryptography, session and
token validation, security headers, browser rendering, audit logging, webhook
signatures, and unintended disclosure through logs or metadata. The Lambda
adapter in deploy/cdk is also relevant. Business feature implementations are
in scope; existing Go tests exercise them with locally constructed test state,
so scanning does not need a production license or private signing key.

Use SECURITY.md and docs/ for the intended guarantees. Per SECURITY.md, do not
report brute-force enumeration of UUIDs or encryption keys, browser history or
cache retention of secret URLs, absent rate limiting, version disclosure,
temporary browser storage of ciphertext, social engineering, or build-only
dependency vulnerabilities without runtime impact. Do not test public Yopass
instances or other external services; use local fixtures and mocks.

## Build and offline testing

The image retains the checkout at /src, Go and Node toolchains, Go module
caches, website/node_modules and all three Playwright browsers. Go workspace
mode is disabled so the root module and deploy/cdk can be exercised separately.
The binaries are /usr/local/bin/yopass and /usr/local/bin/yopass-server; compiled
frontend assets are in /src/website/dist and /src/public.

In the scanner's offline shell, start the installed local databases and run:

```sh
memcached -u root -l 127.0.0.1 -p 11211 -d
redis-server --bind 127.0.0.1 --port 6379 --daemonize yes --save "" --appendonly no
cd /src
MEMCACHED=127.0.0.1:11211 REDIS_URL=redis://127.0.0.1:6379/0 go test -race ./cmd/... ./pkg/...
cd /src/deploy/cdk
go test -race ./...
cd /src/website
yarn test:unit
CI=true yarn test:e2e
```

The CDK tests that require DYNAMODB_ENDPOINT need a local DynamoDB emulator;
none is bundled, and those tests skip without the variable. S3 and OIDC tests
use local mocks. Playwright starts its own Vite server; the existing browser
tests use fixtures and are not a substitute for testing the Go API. To exercise
the application manually, run `yopass-server --memcached=127.0.0.1:11211` and
use its HTTP listener on port 1337 or the Go CLI against that local listener.

## Severity and useful reports

Prioritize demonstrated secret or key disclosure, unauthorized decryption,
remote code execution, authentication bypass, arbitrary file access, and
violations of one-time or expiration guarantees. Explain the attacker's
required knowledge and access, affected configurations and practical impact;
distinguish an intended bearer capability from an authorization bypass.
For denial of service, show disproportionate resource consumption or a crash
with a bounded input, rather than merely the absence of rate limiting.

Include a local reproducer, relevant code paths and a focused patch with a
regression test where possible. Never include real secrets, credentials or
private keys in reports or test fixtures.
