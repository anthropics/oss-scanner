# VDO.Ninja

VDO.Ninja is browser-based real-time audio, video, screen-sharing, and data transport infrastructure. Its embed and iframe APIs support SDKs, browser extensions, broadcast tools, and downstream applications including Social Stream Ninja. A flaw in its participant or embed boundaries can affect those integrations as well as direct users.

## Scope and trust boundaries

Audit the code in this repository, especially `main.js`, `lib.js`, `webrtc.js`, room/director interfaces, and iframe/embed interfaces. Treat URL parameters, signaling messages, remote participant data-channel messages, chat, metadata, and cross-window messages as untrusted. Check participant authorization, room/session access, director and remote-control permissions, origin validation, DOM injection, sensitive-data exposure, and whether media capture or device access can occur without the intended consent.

Room and stream identifiers and optional passwords can act as capabilities. Possessing a deliberately shared capability may intentionally grant access; demonstrate a bypass of the actual access model rather than assuming all joins require an account. Distinguish user-selected custom code or URLs from attacker-controlled input that crosses a trust boundary. Browser-enforced media permissions do not replace application-level participant authorization.

The hosted signaling, TURN, relay, and API services, downstream repositories, and independent third-party dependencies are not audit targets. Do not connect modified clients, enumerate rooms, or send test traffic to public infrastructure. Use local fixtures or isolated mock services with synthetic participants. Investigate first-party misuse of a dependency when the fault is in this repository.

## Offline environment

The checkout is at `/src`. The frontend has no package installation or compilation step. Serve it with `python3 -m http.server 8080 --bind 127.0.0.1`. Chromium is `/usr/bin/chromium`; Playwright Core is installed in `/opt/oss-scanner-tools/node_modules` and exposed through `NODE_PATH`. In a disposable root container, Chromium needs `--no-sandbox`; that is an audit-container launch option, not a proposed product setting.

The browser pages can be examined offline, but complete media sessions require signaling and consenting peers. Replace external services with isolated fixtures for reproductions. Do not interpret a failed external connection as a security issue. Existing translation checks are `node .github/ci-validateTranslations.js` and `node .github/ci-checkTranslationKeys.js`.

## Findings

Prioritize unauthorized media disclosure, session takeover, unauthorized participant/director control, and injection that crosses origins or exposes session capabilities. Rate impact according to the demonstrated attacker prerequisites, affected users, and data or controls reached. A self-only failure or local tab denial of service has lower impact than compromise of another participant.

Provide the affected revision, entry point, prerequisites, safe local reproduction, expected and observed behavior, and a narrow suggested patch. Group reports sharing a root cause. Preserve existing connection, cleanup, and browser-compatibility behavior when proposing fixes.
