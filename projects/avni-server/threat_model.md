# Threat model

The scanner reads this file before it starts. It covers avni-server, the backend of Avni.

## What this project does and where untrusted input enters

Avni is an open-source platform that NGOs and governments use for field work in health, nutrition, water, education
and social welfare. Field workers collect data on an offline-first Android app that syncs with this server.
avni-server (Java 21, Spring Boot, PostgreSQL) is the security boundary of the platform. It stores personal and
health data about the people those organisations serve, and one server holds many organisations.

Tenant isolation is the most important property. Every organisation's rows live in the same tables. The server
connects as one database user and, for each request, switches to the organisation's database role
(`SetOrganisationJdbcInterceptor`); PostgreSQL row-level security policies then limit that role to its own rows.
Anything that reads or writes another organisation's data, or that runs SQL without the organisation's role set, is
the most serious class of finding.

Untrusted input reaches the server through:

- **Unauthenticated HTTP**: the paths in `ResourceProtectionStatus.UnprotectedResources` (identity-provider details,
  `/config`, `/ping`, `/web/media`, `/api/user/generateToken`, `/open`, static assets), and whatever
  `AuthenticationFilter` and `ApiSecurity` let through before a token is checked.
- **The token itself**: a Cognito or Keycloak JWT in the `AUTH-TOKEN` header or cookie, with the `ORGANISATION-UUID`
  and `USER-NAME` headers. Treat every claim and header as attacker-controlled until verified.
- **Any authenticated field user**: the sync API (the `Sync*` controllers and every entity controller's `GET` by
  `lastModifiedDateTime` and `POST` save), which accepts whole entities with client-chosen uuids and JSON
  observations; media upload and download URLs; search.
- **Organisation administrators and web users**: the `/web/**` and other admin endpoints. They author forms,
  concepts, subject types, report cards, dashboards, custom queries, message templates, JavaScript rules, bulk CSV
  uploads, and metadata bundles (zip import and export). The names, uuids and rule text they store are later pasted
  into SQL, views, files, exports and messages, and are evaluated or rendered for other users.
- **The external API** under `/api/**`, used by other systems with a user's token.
- **Stored content processed later**: scheduled jobs, Spring Batch jobs (exports, bulk uploads) and background
  threads that read what users stored and run without a request.
- **Responses to outbound calls**: the identity provider, S3-compatible storage, the rules server, the reporting
  tools (Metabase, Superset), messaging providers, and any URL the server fetches on a user's behalf.

### Trust model

- **Unauthenticated clients** are untrusted.
- **Field users** have only the privileges of their user groups and see only the subjects in their catchment and
  sync settings. They are numerous, use shared low-cost phones, and must be assumed hostile.
- **Organisation administrators** are trusted with their own organisation's configuration and data, and with
  nothing else. An organisation can be created by self-signup, so "administrator of some organisation" is a position
  an attacker can obtain. An administrator reaching another organisation, the server host, or the database outside
  their own role is a full finding.
- **Account administrators** manage a set of organisations and are trusted only within that set.
- **Super administrators** are Avni's operators and are trusted. `application.properties` and the environment are
  trusted operator input.

## Components that matter most / least

### Highest priority

1. Tenant isolation: `SetOrganisationJdbcInterceptor`, `DbRoleRepository`, the row-level security policies and grants
   in `avni-server-api/src/main/resources/db/migration/`, and every place that runs SQL without a user context
   (`@Scheduled` jobs, batch jobs, `@Async`, startup code).
2. Authentication: `framework/security/` (`AuthenticationFilter`, `AuthService`, `AuthTokenManager`, `ApiSecurity`),
   the `*IAMService` and `*IdpService` classes for Cognito and Keycloak, and user creation and password flows.
3. Authorisation: `AccessControlService` and the privilege checks in each controller, including endpoints that have
   none; repositories exported by Spring Data REST; object-level access by id or uuid.
4. SQL built from strings: subject search (`dao/search/`), export (`exporter/`, `ObservationService`), reporting
   views (`reporting/`), custom queries, storage management, and any `JdbcTemplate`, native query or `String.format`
   that takes a stored name, a uuid or a request value.
5. Files and URLs: bundle and extension zip handling, bulk upload, media and S3 key handling (`StorageService`,
   `AWSS3Service`, `MediaController`), and server-side URL fetches.
6. Rule execution: calls to the rules server and how rule text and its results are handled.
7. Caches and background state keyed without the organisation.

### Lower priority and out of scope

- Lower priority: `avni-rule-server` (an experimental module that the API module does not depend on).
- Out of scope: tests (`**/src/test/**`), `perf/`, `postman/`, `scripts/`, `docker/`, `infra/`, `makefiles/`,
  `dummy/`, the root `Dockerfile` (unused), patches and notes at the repository root, and CI configuration.

## How to exercise it

- `/src` is the checkout. The image ran `./gradlew clean build testClasses -x test` and then `./gradlew test`, so the
  Gradle distribution and all dependencies are cached under `/root/.gradle`. Use `--offline`.
- PostgreSQL 16 is installed in the image but not running. Start it with `avni-test-db`, which also makes sure the
  `openchs_test` database exists (user `openchs`, password `password`, extensions `uuid-ossp`, `ltree`, `hstore`).
  `avni-test-db reset` gives an empty database. Flyway applies all migrations when the first integration test starts.
- Run one test class with
  `OPENCHS_MODE=test ./gradlew --offline test --tests "org.avni.server.<package>.<Class>"`.
  `*Test.java` are unit tests (JUnit 4, Mockito). `*IntegrationTest.java` start the Spring context against the
  database; they extend `AbstractControllerIntegrationTest` and set the acting user with `setUser(...)`, which is the
  easiest way to act as a user of a particular organisation.
- Write a proof of concept as an integration test that creates two organisations with the test builders
  (`org.avni.server.domain.factory`, `TestDataSetupService` and related classes under
  `avni-server-api/src/test/java/org/avni/server/service/builder/`) and shows one reading or changing the other's
  rows. For SQL issues, show the query the server runs and the role it runs under.
- To run the server itself: `OPENCHS_DATABASE=openchs_test AVNI_IDP_TYPE=none ./gradlew --offline bootRun`. With
  `AVNI_IDP_TYPE=none` the server takes the user from the `USER-NAME` header; that mode is for development only and
  is not a finding. S3, Cognito, Keycloak, the rules server and the reporting tools are not available in the image.

## How you rate severity

- **Critical**: any unauthenticated read or write of organisation data; authentication bypass or becoming another
  user; any user, including an organisation administrator, reading or writing another organisation's data
  (cross-tenant), running SQL outside their organisation's database role, or running code on the server host.
- **High**: a field user reading or changing data in their own organisation beyond their catchment and privileges at
  scale, or gaining administrator privileges; SQL injection that stays inside the caller's own organisation role;
  SSRF that returns the response; reading secrets (credentials, keys, tokens) from the server; path traversal or zip
  handling that writes or reads files outside the intended directory.
- **Medium**: a missing privilege check that exposes or changes a limited part of the caller's own organisation;
  blind SSRF; stored XSS or formula injection that reaches other users through data the server should have
  sanitised; CSRF on a state-changing endpoint; tokens or personal data written to logs; a non-administrator
  crashing or stalling the server for everyone.
- **Low**: information disclosure without personal data or secrets (versions, stack traces, user enumeration);
  denial of service that needs administrator rights or very high request volumes; hardening gaps with no
  demonstrated outcome.

Post-authentication SQL injection is at least High, and Critical whenever it can leave the organisation's role. A
finding that only works in Keycloak mode or only in Cognito mode keeps its rating: both are used in production.

## Anything to leave alone

- Development defaults that deployments replace: the `AVNI_IDP_TYPE=none` mode, and default passwords and keys in
  `application.properties` and the Makefile. Do report it if the server keeps using a default after the operator has
  set a value, or if a default is used where no setting exists to replace it.
- Vulnerabilities in third-party dependencies unless avni-server code reaches them in an exploitable way.
- Missing rate limiting and missing security headers, unless they combine into one of the outcomes above.
- Organisation administrators changing their own organisation's forms, rules, users and data: that is the product.

### Reports and patches

- One report per root cause, listing every affected endpoint or class.
- State the user needed (unauthenticated, field user, organisation administrator, account administrator), the
  identity provider mode if it matters, and whether the effect crosses organisations.
- Include a reproducer (an integration test as described above, or the exact HTTP requests) and a minimal patch
  against `master` with a regression test.
