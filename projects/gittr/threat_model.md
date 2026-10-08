# Threat model

## What this project does and where untrusted input enters

gittr is a public web forge for git repositories announced on Nostr. This repository is both the website and the Go git server in `ui/gitnostr` (`git-nostr-bridge`, `git-nostr-ssh`, `git-nostr-cli`). The service at gittr.space runs this code.

Treat the following as untrusted:

- Git packs, refs, and protocol bytes sent to the bridge over SSH or HTTPS
- Repository files, names, and README text shown in the website
- Issue, pull request, and discussion text
- Repositories imported from another forge
- Files published as static Pages
- Nostr events the server or the browser accepts (repository announcements, profiles, comments)

Someone with no account can open public pages and can attempt a git connection. Signed-in actions use a Nostr identity. The browser may hold signing material. Assume repository content and event text are written by an adversary.

Reproduce bugs against this source tree or the binaries in the image. Do not probe gittr.space or its subdomains, and do not touch repositories that other people store on the forge.

## Components that matter most / least

Matter most:

- `ui/gitnostr`: parsing git input, deciding who may push, and anything a push causes the server to do
- Rendering of repository markdown and HTML file preview (`ui/src/lib/security/` and the repo file view)
- Sign-in and session handling, including remote signing
- Server routes that proxy git, notifications, or payments
- Any bug that lets one person read or use another person's repository, signing material, or payment credentials

HTML file preview is intentionally shown in a sandbox that can run script and is not given same-origin access to the forge page. Script that stays inside that sandbox is the designed behavior. Script that reaches the parent page, keys, or another person's data is in scope.

Matter less, and still in this repository: layout, themes, search snippets, and catalog browsing.

Out of scope:

- A third-party package that is only named in a lockfile. Dependency advisories are already reviewed separately. Report one only when this repository's own code reaches the affected behavior.
- Repositories other people host on the forge. A finding whose only effect is on someone else's project is out of scope.
- The public `/lab` page. It shows a static snapshot of dependency relationships. It does not run untrusted code. Do not investigate it.
- A denial of service that needs a large volume of traffic.
- The live service. This image has no route to it, and findings must be shown locally.

## How to exercise it

- Website: `ui/`. Dependencies come from Yarn v1 (`ui/yarn.lock`). Unit tests: `yarn test:unit` from `ui/`. Markdown handling tests are under `ui/src/lib/security/`.
- Git server: binaries are at `/usr/local/bin/git-nostr-bridge`, `/usr/local/bin/git-nostr-ssh`, and `/usr/local/bin/git-nostr-cli`. Source is `ui/gitnostr`.
- After this image is built there is no internet. Do not rely on relays, GitHub, npm, or the live forge.

## How you rate severity

- Critical: remote code execution on the bridge or the website without already owning the target account; a bug that exposes or uses another person's signing material, session, or Lightning credentials; an authorization bypass that reads or writes a private repository.
- High: stored cross-site scripting in repository content, issues, or comments that runs in another visitor's forge session; a git or SSH check that lets the wrong key push; a payment or publish action performed as the wrong person.
- Medium: a denial of service that one request can trigger reliably; an injection that is real but does not cross a user or key boundary.
- Low: the attacker must already be the victim; a missing header with no concrete bug; a guess with no reachable path.
- Do not report style, speculative hardening, or a dependency advisory with no call path in this code.

## Reports and patches

- One bug per report. Include a short way to show it on this source tree or the built binaries.
- The patch should be the smallest change that fixes that bug and keeps the existing tests passing. Name the test you ran.
- Do not include steps aimed at the live site, or steps that would affect other people's repositories.
- If a report depends on something marked out of scope above, skip it.

## Dedup

- Same bug, same sink, same trust boundary: one report. List extra call sites in that report.
- A different sink or a different trust boundary is a separate report.
