# Ferrum Nexus audit scope

Nexus is a multi-user developer portal for Ferrum Edge. Review portal authentication and sessions, RBAC and ownership enforcement, approval workflows, credential handling, audit integrity, messaging/notification input, API catalog ingestion, and the server's gateway delegation. Treat browser requests, imported API descriptions, and gateway/upstream responses as untrusted. Demonstrate the attacker's initial role and any cross-user or cross-namespace impact.

All three npm workspaces, their built outputs, development dependencies, and the E2E workspace are retained under `/src`. `npm test` and `npm run typecheck` run offline; the root scripts build `shared/` before dependent workspaces. Chromium is installed for the E2E workspace. Unit coverage of SQLite does not imply coverage of PostgreSQL, MySQL, MongoDB, SSO, or live gateway E2E fixtures; those require separately configured local services.

Use temporary SQLite databases, disposable accounts, and mock/loopback endpoints. Do not send real notifications or mutate a live gateway in reproducers.

Only `ferrum-edge/ferrum-nexus` is enrolled. The `.github` organization repository, private website, and separate `ferrum-contracts` repository or vendored `contracts/ferrum-contracts/` content are excluded from enrollment and finding ownership. Retained contracts are build/test fixtures.
