# Threat model: twitter-api-v2

## What this project does and where untrusted input enters
A typed client for the X (Twitter) API v1.1 and v2, published on npm as `twitter-api-v2`. It signs and sends
HTTPS requests to `api.x.com` and `upload.x.com`, parses the responses, uploads media, runs the OAuth 1.0a and
OAuth 2.0 (PKCE) login flows, and reads the filtered and sample tweet streams.

It is a library: no listener, no CLI. It runs inside server-side applications (bots, dashboards, SaaS tools
that log their users in with X) that hold an app's credentials and often many users' tokens. Untrusted input
reaches it in three ways:

- **Arguments the application passes through from its own users.** Tweet, user, list, space and DM ids,
  usernames, search queries, tweet text, pagination tokens, media buffers, and the values X sends back to the
  OAuth callback URL (`oauth_token`, `oauth_verifier`, `code`, `state`). Assume an application forwards these
  as received, without validating them.
- **What X sends back.** Response bodies are full of user-generated content (tweets, bios, DMs). Headers
  (rate limits, `content-encoding`, `content-type`) and the chunked stream data are parsed too. Treat
  response data as untrusted for crashes, prototype pollution and unbounded memory, even though `api.x.com`
  itself is trusted.
- **Credentials the library holds.** App key and secret, access token and secret, bearer tokens, OAuth 2.0
  client secret, access and refresh tokens. These must only ever go to X, in the headers or bodies X expects.

## Components that matter most / least
Highest priority:
- `src/client-mixins/request-maker.mixin.ts` and `request-param.helper.ts`: URL building, the substitution
  of route params like `:id` into the path (`applyRequestParametersToUrl`), query and body encoding, and
  which host the auth headers go to.
- `src/client-mixins/oauth1.helper.ts`: OAuth 1.0a signing. The signature must cover exactly the method, URL,
  query and body that are sent.
- `src/client/readonly.ts` and `src/client-mixins/oauth2.helper.ts`: `generateAuthLink`, `login`, `appLogin`,
  `generateOAuth2AuthLink`, `loginWithOAuth2`, `refreshOAuth2Token`, `revokeOAuth2Token`; PKCE verifier and
  `state` generation.
- `src/client-mixins/request-handler.helper.ts`: response decoding and decompression, JSON parsing, error
  objects (`ApiResponseError`, `ApiRequestError`), rate limit headers, socket and timeout handling.

Also in scope:
- Media upload: `src/v1/media-helpers.v1.ts`, `uploadMedia` in `src/v1/client.v1.write.ts` and
  `src/v2/client.v2.write.ts` (chunking arithmetic, file handles, mime detection), and
  `src/client-mixins/form-data.helper.ts` (multipart encoding, boundaries).
- `src/stream/`: `TweetStreamParser` (CRLF-delimited JSON over chunks), `TweetStream` (reconnect, keep-alive),
  `TweetStreamEventCombiner`.
- `src/paginators/`: pagination tokens and ids read from responses and sent back in the next request.
- `src/plugins/`: the hooks plugins receive.
- `src/v2/`, `src/v1/`, `src/ads/`, `src/ads-sandbox/`, `src/v2-labs/`: endpoint wrappers. Mostly thin, but
  each one decides which route params and query fields it sends.

Lower priority: `src/types/` (TypeScript types only, no runtime code).

## How to exercise it
- `npm run build` runs tsc and emits `dist/cjs` and `dist/esm`, the only directory the npm package ships.
  The tests run the TypeScript sources directly through ts-node, so they do not need a rebuild.
- `npm test` runs the offline mocha suite in `test/*.test.ts`. Run one file with
  `npm run mocha test/<name>.test.ts`.
- `test/fake-x.ts` is a fake X API for reproducers. Its clients keep calling `https://api.x.com/...`, but
  their requests go to a local server that records them (method, URL, headers, body), checks OAuth 1.0a
  signatures like X does, and answers with the replies set with `on()`. See `test/endpoints.test.ts` and
  `test/stream.connection.test.ts` for examples. The best reproducer is a small mocha test built on it that shows
  the request actually sent, or the response that breaks the client.
- `test/live/` calls the real X API with real credentials: it cannot run in the scanner, and reports must not
  rely on it.

## How you rate severity
- **Critical**: input from the application's users, or a response from X, makes the library send the app's or
  a user's credentials (consumer secret, token secret, bearer token, OAuth 2.0 client secret, access or
  refresh token) to a host other than X; or makes it send a request of the attacker's choosing (another
  method, or a write endpoint the application did not call) signed with those credentials; or breaks the
  OAuth login flows so that an attacker can log in as, or bind their account to, another user (`state` or
  PKCE checks skipped, tokens of one login returned to another).
- **High**: a route param, query value or pagination token the application passes through redirects the
  request to another X endpoint than the method's own (path traversal or injection in `:id` and similar);
  the OAuth 1.0a signature covers different data than what is sent; predictable nonce, PKCE verifier or
  `state`; credentials in an error message string or in the URL.
- **Medium**: prototype pollution or option-object confusion reachable from response data or from parameter
  objects; credentials reachable from thrown error objects in a way that common logging would print; media
  upload reading or sending data other than the file or buffer the application gave.
- **Low**: denial of service from malformed or oversized responses or stream data (unbounded buffering,
  catastrophic regex, an uncaught exception that crashes the process); wrong rate limit parsing.
- A finding needs a reproducer that runs offline, ideally a mocha test on `test/fake-x.ts`, and should say
  which public method an application would call to reach it.

## Anything to leave alone
- `client.get()`, `post()` and the other raw request methods accept full URLs on purpose, and send the
  client's auth to them: an application choosing the URL is not a bug. The same goes for the `prefix` option,
  a custom `httpAgent`, and `uploadMedia` reading a file path the application gives it.
- `TwitterApiV2Settings.debug` logs requests, responses and headers on purpose. It is off by default.
- How X itself behaves (rate limits, server bugs, what endpoints return) is out of scope, as is the
  `@twitter-api-v2/plugin-*` packages, which live in other repositories.
- TLS and certificate checks are Node's.
- `test/`, `doc/`, `release.mjs`, `setup-oauth2.mjs` and the dev dependencies do not ship to users and are
  out of scope, unless a test hides a real bug.
- Keep patches minimal and in the existing style, with an offline regression test in `test/` next to the
  related tests.
