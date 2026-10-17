# Threat model: Bead Me Up, Scotty

## What this project does and where untrusted input enters

Scotty is a single-user web UI for the `bd` (beads) issue tracker, built on the Next.js 16 App Router. It runs on the user's own machine and binds to localhost by default. It reads and writes issues by running `bd` as a subprocess with argument arrays (`lib/bd.ts`, `execFile`, never a shell) inside project directories the user has registered.

Untrusted input:

- **Issue ("bead") content**: titles, descriptions, notes, design, comments, labels and links. AI coding agents and collaborators write this content and sync it through git. It is rendered as Markdown in the browser (`components/description-content.tsx`).
- **Attachment files** under `<project>/.beads/attachments/`. They come from the same sources and are served by `app/api/p/[projectId]/attachments/[...path]/route.ts`.
- **Requests from other origins.** Any web page the user visits can send requests to `localhost`, either as cross-site requests or through DNS rebinding.
- **Paths and folder-browser input** sent to `/api/projects` and `/api/fs`.

The local user, their shell environment and their filesystem are trusted. Docker users may bind `0.0.0.0` inside a container.

## Intended protections

- `proxy.ts` and `lib/request-guard.ts` form the cross-site guard. Browser writes (non-GET) whose Origin is not the addressed Host are refused, as are writes marked `Sec-Fetch-Site: cross-site`. Only the hosts `localhost`, `*.localhost` and IP literals are answered, unless the user names others in `SCOTTY_ALLOWED_HOSTS`. `SCOTTY_ALLOWED_HOSTS=*` relaxes the host check only; cross-site writes stay refused.
- Attachments are served with `Content-Security-Policy: default-src 'none'; ...; sandbox` and `X-Content-Type-Options: nosniff`. The route also confines reads to `.beads/attachments`.
- Markdown is rendered without raw HTML, and link and image URLs are limited to `http(s)`, `mailto` and `attachment://`.
- `SCOTTY_READ_ONLY` is a viewing preference enforced on `/api/p/**` writes. It is not authentication.

## Components that matter most / least

- **Most:**
  - The API: `app/api/**`, especially the mutations under `app/api/p/[projectId]/**`.
  - The guards: `proxy.ts`, `lib/request-guard.ts`.
  - Command and file boundaries: `lib/bd.ts` (subprocess arguments), `lib/config.ts` with the project registry and `app/api/fs` (folder browser).
  - Rendering of untrusted content: Markdown and link rendering, and attachment serving.
  - `lib/self-update.ts` (the `/api/update/run` path that runs git and npm), and the "Refine with AI" CLI invocation (`app/api/p/[projectId]/beads/[id]/assist`).
- **Less:** `lib/showcase/**`. The static-site publisher renders the user's own beads into a local folder through Eleventy.
- **Out of scope:**
  - `design/`, `graphify-out/` and `scripts/test-*.mjs` (test harnesses).
  - Telemetry to PostHog, which is intentional and can be turned off.

## How to exercise it

- Demo data, with no `bd` repository needed: `BEADS_DEMO=1 npx next start -p 3917 -H 127.0.0.1`.
- Real data: `git init /tmp/p && cd /tmp/p && bd init --prefix t`, then `POST /api/projects {"path":"/tmp/p"}` and use the returned id under `/api/p/<id>/...`.
- The regression scripts in `scripts/test-*.mjs` run with `SCOTTY_TEST_URL=<server>`. `test-request-guard`, `test-attachment-hardening` and `test-close-actor` exercise the security-relevant paths.

## How we rate severity

- **Critical:** A web page the user merely visits, or content inside a bead or attachment, achieves any of:
  - command execution;
  - reading or writing files outside registered projects;
  - triggering the self-updater.
- **High:**
  - Stored XSS on the app origin from bead content or attachments.
  - Any bypass of the cross-site guard that lets another site write data or read data.
  - Path traversal outside `.beads/attachments` or a registered project.
  - Argument injection into `bd`, `git`, or the AI CLI.
- **Medium:**
  - Bypassing read-only enforcement.
  - Issues that require a malicious process already running on the machine.
  - Denial of service from large or crafted bead content.
- **Low:** Issues limited to the development server (`next dev`).

## Anything to leave alone

- The lack of login or authentication is by design: this is a single-user local app, and read-only mode is not an access control.
- `bd` running with the local user's permissions in their own projects is by design.
- Usage telemetry (PostHog, opt-out in Settings, or `POSTHOG_KEY=` empty) is intentional.
- Patches should be minimal and should come with a regression script in the style of `scripts/test-*.mjs` where practical.
