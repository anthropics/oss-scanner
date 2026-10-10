# Threat model

## What this project does and where untrusted input enters
Uppy is a modular file uploader: browser packages (`packages/@uppy/*`) plus **Companion**
(`packages/@uppy/companion`), an Express server that runs OAuth for remote providers (Google Drive,
Dropbox, Box, OneDrive, Facebook, Zoom, Unsplash, WebDAV), lists their files, imports files from
arbitrary URLs, and streams them to an upload target (Tus, multipart/XHR, S3).

Untrusted input:
- **Companion HTTP/WebSocket API**: everything an anonymous internet client sends — URLs for
  `/url/*` and WebDAV, upload targets (`endpoint`, checked against `uploadUrls`), headers, metadata,
  file IDs and paths, OAuth `state` and callback parameters, S3 keys and multipart parameters, the
  `Origin` header.
- **Responses from remote providers and from fetched URLs** (redirects, sizes, file names, JSON).
- **Browser side**: file names, file metadata, provider listings returned by Companion, and the
  responses of upload endpoints. All of these are rendered by Dashboard and the other UI plugins.

Trusted: Companion's operator configuration (env vars and options such as `secret`, `corsOrigins`,
`uploadUrls`, `allowLocalUrls`, `filePath`, provider keys), and the integrating developer's own code.

## Components that matter most / least
Most important: Companion — `src/server/controllers/*`, `helpers/request.ts` (SSRF protection,
`getProtectedHttpAgent`), `helpers/jwt.ts`, `helpers/oauth-state.ts`, `helpers/html.ts` and
`send-token.ts` (token `postMessage`), `provider/credentials.ts`, `Uploader.ts`, `download.ts`,
`controllers/s3.ts`, `header-blacklist.ts`, `middlewares.ts` (CORS).

Also in scope: `@uppy/core` (incl. `companion-client`), `@uppy/dashboard` and the other UI plugins,
`@uppy/golden-retriever`, `@uppy/transloadit`, `@uppy/aws-s3`, `@uppy/tus`, `@uppy/xhr-upload`.

Out of scope: `examples/`, `private/`, test files, `packages/@uppy/companion/infra`, and third-party
dependencies (unless Uppy uses them unsafely).

## How to exercise it
- Build: done in the image (`corepack yarn build`). Tests: `corepack yarn workspace @uppy/companion test`
  (Vitest + supertest, no external services); browser tests with
  `corepack yarn workspace @uppy/<pkg> test --browser.headless` (Chromium is preinstalled).
- Run Companion locally: `packages/@uppy/companion/src/standalone`, configured through `COMPANION_*`
  env vars (see `env_example`; `COMPANION_SECRET` is required). `COMPANION_ALLOW_LOCAL_URLS` must stay
  unset when you test SSRF.

## How you rate severity
- **Critical**: unauthenticated RCE on Companion; reading files from Companion's host; stealing
  another user's OAuth/provider tokens or Companion `secret`.
- **High**: SSRF to internal/private addresses with the default config (`allowLocalUrls` off), or a bypass of
  `uploadUrls`; XSS in Companion's own pages (e.g. the OAuth/send-token HTML); token leakage
  through `postMessage` or redirects to an untrusted origin; path traversal in `filePath`.
- **Medium**: XSS in the browser packages from attacker-controlled file names/metadata/provider
  listings; open redirects; CORS misconfiguration with real impact; DoS that an anonymous client can trigger
  with little traffic (e.g. unbounded memory/disk).
- **Low**: issues that need a non-default, documented-as-insecure configuration, or that need a malicious
  operator or integrating developer; DoS that needs large traffic.

## Anything to leave alone
- Do not report that Companion fetches arbitrary *public* URLs: that is the purpose of `/url`.
- Do not report issues that exist only with `allowLocalUrls: true`, or with `corsOrigins: true` or `*`, or
  with a weak or default `secret`: these are documented operator choices.
- Do not report outdated dependencies without a reachable exploit path in Uppy.
- Patches: keep them minimal, in TypeScript, and add a Vitest regression test next to the affected code.
