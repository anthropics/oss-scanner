# Threat model

## What this project does and where untrusted input enters
- Netherrack (`nc_netherrack/` in the repository) is a Nextcloud app for Markdown notes, spreadsheets (`.ods`), canvases (`.canvas`), bases (`.base`) and voice notes stored as normal files in the user's Nextcloud.
- Untrusted input: every HTTP request to the app's routes (`appinfo/routes.php`, OCS API under `/ocs/v2.php/apps/nc_netherrack/api/v1/...`) from any logged-in user, and the public, unauthenticated pages of published notes (`PublicController`).
- File contents are untrusted too: notes, `.ods`, `.canvas`, `.base` files and attachments can be written by other users through shares, WebDAV or sync clients, and are parsed by the indexer (`lib/Service`, file event listeners) and rendered in the browser (`src/`).
- Voice notes are uploaded audio that is converted with ffmpeg and transcribed with whisper.cpp in a background job (disabled by default, admin setting).

## Components that matter most / least
- Most important: access control between users (reading, writing, renaming or deleting another user's notes, bypassing share permissions, leaking data via search, backlinks, graph, query/bases, mentions, embeds or the public pages), path handling inside the user's notes folder, SQL built in `lib/Db` and `lib/Service/QueryRun.php`, and stored XSS in the Markdown/table/canvas rendering.
- Also in scope: command execution around ffmpeg/whisper (`lib/Service`, `lib/BackgroundJob`), CSRF on routes marked `#[NoCSRFRequired]`, and file locking.
- Out of scope: Nextcloud server itself, `vendor/`, `node_modules/`, `docker-dev/`, `tests/e2e/`, release scripts.

## How to exercise it
- The image has Nextcloud with SQLite at `/var/www/html`, the app linked into `custom_apps` and enabled. Start apache with `apachectl start`; users `admin`/`admin`, `alice`/`alice`, `bob`/`bob`.
- `occ ...` runs Nextcloud's CLI as www-data (e.g. `occ netherrack:index:rebuild alice`). Notes live in each user's `Netherrack/` folder.
- PHP unit tests: `cd /src/nc_netherrack && as-www-data vendor/bin/phpunit`; JS unit tests: `npm run test:unit`.

## How you rate severity
- Critical: unauthenticated access to or modification of notes, or remote code execution.
- High: an authenticated user reads or modifies another user's data without a share, SQL injection, stored XSS that runs in another user's session or on a public page.
- Medium: bypassing share permissions (e.g. writing through a read-only share), reflected XSS, CSRF with real impact, information leaks of metadata (titles, paths, tags) of other users.
- Low: DoS by a logged-in user, issues requiring admin rights, self-XSS.

## Anything to leave alone
- Admin-only settings that let an admin point to executables (whisper/ffmpeg paths) are trusted configuration.
