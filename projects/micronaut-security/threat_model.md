# Threat model: micronaut-security

## What this project does and where untrusted input enters

Micronaut Security is the official authentication and authorization solution for applications built on the
Micronaut Framework. It is a library: an application adds it and configures it, and every HTTP request the
application serves then passes through its filter chain. Its modules:

- `security`: the HTTP filter, security rules (`@Secured`, intercept-URL map, IP patterns), authentication
  providers and fetchers, basic auth, login/logout controllers, token propagation, redirects.
- `security-jwt`: JSON Web Token generation and validation (signatures, encryption, claims, expiry), JWKS
  fetching and caching, cookie and header token readers, refresh tokens.
- `security-oauth2`: OAuth 2.0 and OpenID Connect client flows (authorization code, client credentials,
  password), state, nonce and PKCE handling, ID token validation, OpenID discovery, end-session.
- `security-session`: session-based authentication; `security-csrf`: CSRF token generation and validation;
  `security-ldap`: LDAP authentication; `security-password` and `security-password-argon2-bouncycastle`:
  password hashing and verification; `security-html-sanitizer`; `security-reporting`; `security-aot`;
  `security-processor`/`security-annotations`: compile-time support.

Untrusted input reaches the library at runtime through:

- **HTTP requests**: `Authorization` headers (bearer and basic), cookies carrying JWTs, sessions or CSRF
  tokens, form logins, the request path and method the rules are evaluated against, headers used for
  redirects (`Host`, `Referer`, `X-Forwarded-*`), and the parameters of OAuth 2.0 / OIDC callbacks (`code`,
  `state`, `error`, `nonce`).
- **Tokens**: JWTs presented by clients are fully attacker-controlled bytes until validated.
- **Responses from identity providers**: JWKS documents, OpenID discovery documents, token and userinfo
  endpoint responses, and the LDAP server. A compromised or malicious provider should not be able to do more
  than deny service or control its own users' identities.

Trusted input: application source code and configuration (`application.yml`: secrets, issuers, client IDs,
intercept-URL maps), and the environment. Bugs that need a malicious application developer or a malicious
configuration are out of scope.

## Components that matter most / least

Most important: `security` (rules evaluation and filter ordering: a request that reaches a controller without
the configured rule allowing it is the worst case), `security-jwt` (signature and claim validation, JWKS key
selection, `alg`/`kid` handling, token readers), `security-oauth2` (state/nonce/PKCE validation, ID token
validation, redirect handling), `security-session`, `security-csrf`, `security-ldap` (query construction),
`security-password*`.

Still in scope but less exposed: `security-html-sanitizer`, `security-reporting`, `security-aot`,
`security-ojdbc-extensions`.

Out of scope: `test-suite-*` modules, `buildSrc` and build logic, documentation (`src/main/docs`), the
behaviour of external identity providers (Keycloak, Okta, ...), and vulnerabilities in dependencies such as
Nimbus JOSE+JWT, Bouncy Castle or the LDAP SDK. Report those upstream, unless Micronaut Security's use of the
dependency is what makes them exploitable (for example not calling a validation the library expects callers
to perform).

## How to exercise it

- The image compiled every module and its tests and cached every dependency. The scan has no network, so
  Gradle is forced offline by `/root/.gradle/init.d/oss-scanner-offline.gradle`; passing `--offline` as well
  is fine. Always pass `-Dtestcontainers=false` so that tests needing Docker are skipped.
- Run a module's tests with `./gradlew --offline -Dtestcontainers=false :micronaut-security-jwt:test` (Gradle project names carry the `micronaut-` prefix: `:micronaut-security:test`, `:micronaut-security-oauth2:test`, ...), a single class with
  `--tests 'io.micronaut.security.token.jwt.SomeSpec'`. Tests are Spock (Groovy) and JUnit 5, mostly starting an
  `EmbeddedServer` with a small controller and an `HttpClient`; `test-suite` and `test-suite-jwt-tck` hold
  cross-module scenarios.
- `test-suite-keycloak-docker`, `test-suite-ldap` (where it needs a container), and the Geb browser tests
  cannot run in the scanner and should be skipped, not reported.
- The scan machine is small (2 CPUs, 8 GB): run one module at a time; `--max-workers=2` helps.
- Tests start an embedded server on $HOSTNAME; the image sets `HOSTNAME=localhost` because the container's own
  hostname does not resolve without a network. If a test fails with "Temporary failure in name resolution",
  run it with `HOSTNAME=localhost` in the environment.

## How you rate severity

- **Critical**: authentication bypass (a token accepted without a valid signature, with `alg=none`, with a key
  it should not be verified against, when expired, or for the wrong issuer or audience where configured; an
  OAuth 2.0 / OIDC flow that lets an attacker log a victim in as the attacker or complete the callback with a
  forged `state`/`nonce`); authorization bypass (a rule, intercept-URL pattern or path matching that lets an
  unauthenticated or under-privileged request reach a protected route); leakage of signing secrets or client
  secrets.
- **High**: CSRF protection bypass; session fixation; open redirect in login, logout, or OAuth callbacks; token
  or credential leakage through logs, error responses or redirects; SSRF through JWKS, discovery or token
  endpoints when the URL comes from untrusted data; LDAP injection; practical timing attacks on token or
  password comparison.
- **Medium**: denial of service from a small request (oversized tokens, expensive key lookups per request,
  unbounded JWKS refreshes); user enumeration through differing responses; weaknesses that need a non-default
  but documented configuration.
- **Low / informational**: issues that need a malicious application developer, a malicious configuration,
  local access, or a non-public API; hardening suggestions.

Default configuration matters: an issue reachable with the defaults rates one level higher than the same issue
that needs the developer to opt in.

## Reports and patches

- Patches should target the default branch (the current `5.x.x` line), use Java 25, keep binary compatibility
  of public API (add, deprecate; do not change signatures), and follow the surrounding code style. Mark
  internal API `@Internal`.
- Please include a failing Spock or JUnit 5 test next to the existing tests of the module, exercising both the
  accepted and the rejected path, and the exact request or token that reproduces the issue.

## Anything to leave alone

- Tokens, keys and credentials in test fixtures are intentional non-secret fixtures.
- Findings that amount to "a dependency has a CVE": Dependabot and Renovate cover that.
- Behaviour of the identity provider itself, and of Micronaut core's HTTP layer: report those to the
  respective projects (micronaut-core is enrolled separately).
