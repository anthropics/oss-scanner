# HFS threat model

HFS is an internet-facing HTTP file server. Treat all remote HTTP and WebSocket
traffic, paths, headers, uploaded files, archive contents, and plugin-provided
frontend input as untrusted.

## Security boundaries

- Remote users must not read, write, delete, move, or enumerate files outside
  the permissions and virtual filesystem paths granted to them.
- Authentication, sessions, account permissions, URL signing, administration
  APIs, reverse-proxy handling, and update delivery are security-sensitive.
- Upload, archive extraction and generation, WebDAV, serving active content,
  and filesystem path normalization are high-priority attack surfaces.
- An unauthenticated user must not gain administrative or operating-system code
  execution.

## Trusted features and exclusions

- Administrators intentionally have broad control over the server and shared
  files. Findings that require an administrator to act against their own server
  are low priority unless a normal remote user can trigger the result.
- Installed plugins, server-side custom code, and custom HTML/JavaScript are
  trusted extensions and may intentionally execute with broad privileges.
  Privilege escalation from an untrusted remote user into these facilities is
  in scope.
- Legacy HFS 2.x is a separate codebase and is out of scope.

## Exercising the project

- `npm test` runs the server-side test suite against an already running test
  server; `npm run test-with-server` builds and starts that server itself.
- `npm run test-ui` runs the Playwright suites and requires browser binaries,
  which are not included in this image.
- Focused server tests can be selected with
  `npm test -- --test-name-pattern="<pattern>"`.

## Severity guidance

- Critical: unauthenticated remote code execution or a broadly exploitable
  update/signing compromise.
- High: authentication or authorization bypass; unauthorized filesystem access
  outside configured shares; arbitrary file write with meaningful impact; or
  administrator compromise from ordinary remote interaction.
- Medium: cross-user data exposure, stored script execution without a path to
  administrator compromise, or practical unauthenticated denial of service.
- Low: issues requiring trusted administrator-controlled configuration or with
  negligible security impact.

Reports should include a realistic reproducer using public HTTP or browser
flows where possible. Proposed patches should be minimal and preserve existing
behavior outside the vulnerability.
