# Sani threat model

Sani is a self-hosted link shortener with text/code and file sharing. One Go
binary embeds a Svelte admin app and stores state in SQLite. Instances may be
reachable from the public Internet. There is one administrator, not a multi-user
or multi-tenant authorization model.

## Scope and trust boundaries

- Unauthenticated visitors control HTTP paths, query strings, headers, cookies,
  request bodies and request timing. Review redirects, visitor/share pages,
  authentication, first-run setup, rate limits and resource consumption.
- Admin sessions and API tokens grant full administration. Check authentication
  bypass, CSRF, session issuance/revocation, setup races and token handling.
  Ordinary authorized link/share management is intended behavior.
- Treat fetched HTML, icon bytes, DNS replies and redirect chains as hostile,
  even when an administrator starts the fetch. Review SSRF checks at resolution
  and connection time, proxy routing, limits and stored/reflected content.
- Uploaded files, text/code, filenames and imported link data may contain hostile
  content. Check escaping, MIME handling, response headers, path traversal,
  chunk-upload ownership, expiry, cleanup and database/filesystem consistency.
- Raw shares must be isolated on the separately configured files host. The
  files host must not expose the admin app or API, receive admin cookies, or
  allow active content to escape its response sandbox. Public share links are
  bearer URLs: knowledge of a valid URL permits access by design.
- Check SQLite queries, concurrent updates, redirect-cache invalidation and
  click aggregation where they affect confidentiality, integrity or practical
  availability. A race detector finding needs an explanation of its impact.
- Environment variables, CLI arguments, local data-directory permissions and
  reverse-proxy configuration are controlled by the operator. Evaluate security
  with the documented deployment configuration; do not assume a malicious host
  administrator as the initial attacker. Local file access gained through a
  remotely reachable flaw remains in scope.

The standard environment HTTP(S) proxy is operator-trusted and may resolve and
connect to destinations itself. Dedicated metadata proxies have a different
boundary: verified public destination IPs are pinned through CONNECT/SOCKS5.
The fake-IP range 198.18.0.0/15 is intentionally supported. Assess bypasses
against these documented distinctions, rather than assuming all proxy modes
enforce identical guarantees.

See `SECURITY.md` and `docs/en/internals/security.md` for the maintained security
contract, and `docs/en/reference/configuration.md` for configuration semantics.
Key implementation paths are `cmd/sani`, `internal/server`, `internal/meta`,
`internal/links`, `internal/store`, `internal/cache`, `internal/clicks` and
`web/src`. Deployment and release workflows are relevant when a finding has a
concrete effect on shipped software. Do not probe public deployments or external
services; reproduce issues with disposable local instances and test servers.

## Offline build and tests

The image keeps the checkout at `/src`, the built server at `/src/bin/sani`,
Go and pnpm dependencies, and Chromium at `/opt/playwright`. Go, Node and pnpm
versions match the project's `mise.toml` at enrollment. The production binary
is built without cgo; a C compiler remains available for Go's race detector.

From `/src`, without Internet access:

```sh
make check test
make e2e smoke
make bench
```

`make e2e` starts a fresh local server on 127.0.0.1:18765 with temporary data.
`make smoke` exercises real-process shutdown, backup and restore using disposable
data. To rebuild after a patch, run `make build`. Use local fixtures for network
behavior; live Internet reachability is not a requirement of the offline image.

## Reports and severity

Provide the affected revision, attacker prerequisites, reachable entry point,
root cause, demonstrated impact and a deterministic local reproducer. Prefer a
small regression test and focused patch; keep security boundaries and existing
API/deployment behavior intact. Deduplicate by root cause, listing affected
endpoints together unless they require separate fixes.

Assess severity using actual privileges and deployment prerequisites. Remote
code execution, unauthenticated administrator takeover or broad sensitive-data
exposure can be critical/high. SSRF, cross-origin isolation failures, stored XSS
and denial of service need evidence of reachable targets, required interaction,
resource cost and resulting impact. Do not assign a fixed severity from the
bug class alone, or report intended public redirects/share access as a bypass.
Clearly separate demonstrated findings from hypotheses requiring validation.

Send findings privately through the scanner's configured contact. Do not post
unpatched vulnerability details in public issues or enrollment pull requests.
