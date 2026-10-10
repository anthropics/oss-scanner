# EtherCalc threat model (for OSS Scanner)

## What this project does and where untrusted input enters

EtherCalc is a multi-user realtime spreadsheet: TypeScript on Cloudflare
Workers (Hono + Durable Objects + D1/KV/R2), self-hosted via standalone
`workerd` (Docker/Helm/CLI/Sandstorm), in production at
https://ethercalc.net. Clients are a single-sheet UI and a React
multi-sheet UI.

Anonymous read/write on public rooms is the product core: knowing a room
URL means ability to read and edit it. That is intentional and must not
be reported as a vulnerability. The attacks that matter are bypasses of
the configured gates (key auth, private-room ACLs, room-index gate,
per-message auth) and injection into other users' sessions.

Untrusted input enters through:

- HTTP room API: create (`POST /_`, `/_new`, `/_from/:template`),
  overwrite (`PUT`/`POST /_/:room`), cell-command posts, append-rows,
  `DELETE /_/:room`, CSV/SocialCalc/Excel-XML import,
  multi-sheet ZIP import, exports (`:room.xlsx|.ods|.fods|.csv|.html|
  .json`), chat, room-index endpoints (`/_rooms*`, `/_exists`).
- Gated operator routes: `/_migrate/*` (bearer token),
  `/_timetrigger` (gate secret + scheduler), `/_do/*` (DO-to-DO).
- WebSocket + legacy `/socket.io/*` shim (kept indefinitely and
  exposed): cell commands, presence/huddle, per-message auth.
- `/_auth/*` WebAuthn (passkey) registration/login ceremonies and the
  `__Host-ec_sess` session cookie.
- Client-side: cross-sheet `postMessage`, table-of-contents handling,
  graph panel rendering, attachment rooms.

## Trust boundaries (do not propose moving them)

- The RoomDO (Durable Object) is the SOLE authorization enforcement
  boundary. Top-level rooms use local `meta:access`/`meta:acl`;
  parented workbook children derive the verdict from an immutable
  `meta:parent` (parent RoomDO authoritative via `/_do/access`,
  fail-closed; a parent marker plus a local ACL denies).
- The singleton AuthDO is the WebAuthn relying party; RP_ID/RP_NAME/
  ORIGIN trust anchors come from env only. `ETHERCALC_KEY` never signs
  sessions; on private rooms ACL membership replaces legacy `?auth=`
  tokens outright (deny-overrides).
- The Worker cookie-to-`X-EC-Uid` mapping is UX only; `doFetch` strips
  inbound identity/capability spoof headers before RoomDO sees them.
- Private rooms answer 403 on every read/write/export/WS path for
  non-members, are excluded from room mirrors, and leave an anti-squat
  tombstone on delete (reclaimed only by `ETHERCALC_EXPIRE` TTL).
- In anonymous mode (no `ETHERCALC_KEY`), anyone can wipe any public
  room. That is the documented contract, not a finding.

## Components that matter most / least

Highest value, in scope:

- `packages/worker/src/lib/authorize.ts`, `auth*.ts`,
  `session*.ts`, `webauthn-ops.ts`, `auth-do.ts` (authn/z, sessions)
- `packages/worker/src/room.ts`, `lib/ws-*.ts`,
  `lib/do-dispatch.ts` (RoomDO, WS dispatch, per-message auth,
  attachment-room binding)
- `packages/worker/src/routes/` + `src/handlers/` (HTTP surface:
  exports, migrate, timetrigger, legacy-socketio, rooms)
- `packages/worker/src/lib/{csv,csv-parse,csv-encode,xlsx-import,
  xlsx-build,multi-sheet-import,loadclipboard,cross-sheet,
  html-sanitize,md,command-limits,formdata-sibling}.ts` (parsers,
  sanitizers, ingestion caps)
- `packages/worker/src/lib/{csp,robots,rate-limit,
  room-create-limit,room-index-access,sandstorm-access}.ts`
  (security-policy edge)
- `packages/shared/src/` (WS protocol, frame/chat/cell caps) and
  `packages/socketio-shim/` (legacy compat, exposed)

Lower value / out of scope:

- `packages/oracle-harness/`, `tests/oracle/`, `tests/e2e` fixtures
  (dev record/replay tooling, not shipped)
- `packages/docs/` (Starlight site), `lemma/` (Dafny/Lean proof
  pump), `spikes/` (research notes), `packages/e2e/` (Playwright;
  browsers are NOT prefetched in this image, so e2e is not runnable
  here)
- `deploy/`, `helm/`, `docker-compose*.yml` (operator config with
  restricted defaults already)
- Do not report: absent TLS/rate-limit/DDoS on a bare self-host
  (documented operator responsibility; the mandatory nginx proxy
  recipe ships in `docker-compose.proxy.yml`, and
  `ETHERCALC_RATELIMIT` is intentionally default-off on hosted);
  `script-src 'unsafe-inline'` (required by SocialCalc's toolbar);
  anonymous write/delete semantics; oracle-compat behaviors marked
  intentional in code.

## How to exercise it

From `/src`, offline (`vp` ships in `node_modules/.bin`):

- `./node_modules/.bin/vp run @ethercalc/shared#test`
- `./node_modules/.bin/vp run @ethercalc/worker#test:node`
  (pure-Node suite; the security core: authz, sessions, WS, parsers)
- `./node_modules/.bin/vp run @ethercalc/worker#test:workers`
  (Miniflare/workerd suite; uses the prefetched workerd binary)
- `./node_modules/.bin/vp run @ethercalc/socketio-shim#test`
- `./node_modules/.bin/vp run @ethercalc/worker#build:dry`
  (`wrangler deploy --dry-run`, no Cloudflare account needed)
- Typecheck a package: `bun run --cwd packages/worker typecheck`

Source layout pointers: Worker entry `packages/worker/src/index.ts`,
RoomDO `packages/worker/src/room.ts`, auth/policy helpers under
`packages/worker/src/lib/`, protocol caps in `packages/shared/src/`.

## How we rate severity

- Critical: private-room ACL/auth bypass (read or write as a
  non-member), session forgery/fixation, AuthDO signing-secret
  disclosure, RCE/LFI via import/export/chat/WS handling, RoomDO
  boundary escape (one room reaching another's state), `?auth=`
  demotion bypass on private rooms.
- High: stored XSS (client render or HTML export), WebAuthn ceremony
  bypass, `/_migrate` token bypass, `/_timetrigger` forgery that fires
  callbacks, CSV/XLSX formula-injection defang bypass, identity
  spoof (`X-EC-Uid`/capability headers) reaching RoomDO, Sandstorm
  viewer-to-editor escalation.
- Medium: reflected XSS, DoS above the documented caps (128 WS
  conns/room, 1 MiB frames, 25 MiB bodies, 200k-cell XLSX import,
  chat/audit trims), room existence/enumeration oracle while the
  room-index gate is ON, cache poisoning via Host-spoofed CSP.
- Low: informational headers, verbose errors without secret
  disclosure, DoS within documented caps.
- Not vulnerabilities: anonymous read/write/delete on public rooms;
  room discovery with the index gate OFF (operator choice); findings
  requiring a compromised edge, config, or operator secret.

## Anything to leave alone

- Do not propose a default `ETHERCALC_KEY`, auth gates on
  PUT/POST/WS-execute, loopback binds, or in-workerd TLS. All are
  explicitly rejected; see `docs/SELFHOST_HARDENING.md` section 5.
- SocialCalc's engine is 1-based upstream while EtherCalc facades are
  0-based; do not "unify" them without the 0<->1 shim.
- Patches should be minimal with a regression test colocated in the
  owning package's suite; gated packages hold 100% line/branch/
  function/statement coverage, so untested new branches fail CI.
