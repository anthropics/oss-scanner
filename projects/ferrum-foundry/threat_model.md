# Ferrum Foundry audit scope

Foundry is the React administration UI and Fastify backend for Ferrum Edge. Review session authentication, CSRF, namespace/role authorization, JWT delegation to the gateway, proxy request construction, input parsing, and rendering of gateway-controlled data. The browser reaches the gateway through the backend; demonstrate violations of that boundary or of the authenticated actor's permissions.

The complete checkout, development dependencies, `dist/`, and `dist-server/` are retained under `/src`. Run `npm test` and `npm run typecheck` offline. Chromium is preinstalled for Playwright; E2E tests still need the repository's disposable fixture services. The bundled `scripts/mock-admin-gateway.mjs` can support isolated backend exercises. Full gateway contract and deployment suites need separate setup.

Use local fixtures and development-only credentials. Do not connect to a real administrator's gateway or browser session. Report any deployment assumptions, including trusted proxy configuration.

Only `ferrum-edge/ferrum-foundry` is enrolled. The `.github` organization repository, private website, and separate `ferrum-contracts` repository or vendored `contracts/ferrum-contracts/` content are excluded from enrollment and finding ownership. Contract fixtures are retained only as application build/test dependencies.
