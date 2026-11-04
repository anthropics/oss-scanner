# OpenReplay threat model

## What it does

OpenReplay is a self-hosted session replay platform. A JavaScript tracker (`tracker/`) runs on our users' websites,
records each visitor's DOM, network calls, console and events, and sends them to the ingest services; the dashboard
(`frontend/`, replay engine in `player/`) replays them to the site owner's team. With `tracker-assist`, a dashboard
user ("agent") can also watch a visitor live through the assist server (`assist/`, socket.io), call them, draw on
their screen and take control of their page (co-browsing).

This image runs the single-tenant FOSS edition. The multi-tenant enterprise edition copies the files under `ee/` over
the same trees by path (`api/build.sh`, `backend/build.sh`, `assist/build.sh`), so every file in `api/` and `backend/`
that `ee/` does not replace runs in both. The enterprise assist server loads only its own copies (`ee/assist/app`).

## Where untrusted input enters

- **Visitors of a tracked site.** The `projectKey` is public, so anyone can start sessions and send recordings:
  everything under `/ingest/*` (the `http` worker's `/v1/web/*`, `/v1/mobile/*` including `/late`, and `/v1/sdk/*`;
  `canvases` at `/v1/web/images`; `images` at `/v1/mobile/images`, gzipped tar), processed by `ender`, `sink`,
  `storage`, `db` and `assets`. The same goes for what a visitor socket sends to assist (`/ws-assist/socket`,
  `identity=session`): the live DOM, `sessionInfo` and `UPDATE_SESSION` (shown in the live session list), and any
  other event, which the server relays to the room's other sockets (`assist/utils/socketHandlers.js`, `onAny`).
- **Agents**: the names, annotations and remote-control input that `tracker-assist` puts on the visitor's page.
- **Other pages and frames**, which can post messages to the tracker and to the spot extension.
- **Anyone, without an account**: login, signup (before the first account exists), password reset, invitation
  acceptance (`public_app` routes in `api/routers/core*.py`), spot share keys (`?key=`, `IsSpotKeyRequest` in
  `backend/pkg/server/api/request.go`), which open only the view, status and comment routes of their own spot, and
  the MCP sign-in poll (`GET /api/v1/mcp/auth-status`).
- **Dashboard users** (owner, admin, member of one organisation) through chalice (`api/`), the go `api` and `spot`.
  Admin-only in both APIs: creating, editing and deleting projects and changing their capture settings; managing
  members; changing the organisation's settings and scope; reading and rotating its API key. Owner-only: transferring
  ownership and changing the owner's account. Any member can configure webhooks, Slack, MS Teams, log and
  issue-tracker integrations, alerts, metadata and tags, and act as an agent.
- **The organisation API key**, which the customer's own servers use for the public API.

A finding has to reach code execution or cross one of the boundaries below.

## Boundaries

### Tokens and roles

- Without a dashboard, spot or MCP JWT, only the routes listed under "Anyone, without an account", ingest, the
  visitor socket, health checks and the organisation-key routes may answer. Signup works only before the first
  account; a reset or invitation link sets only its own account's password.
- Logout and a password change must end the user's dashboard and spot JWTs, access and refresh (`users.jwt_iat`,
  `spot_jwt_iat` and the refresh `jti` columns; `api/auth/auth_jwt.py`, `backend/pkg/server/user/user.go`). Any
  token, key or link used after it expired or was revoked (agent tokens, spot share keys, invitation and reset links)
  is a finding.
- The spot JWT may open only the extension's routes (`/spot/v1/*`, chalice `/api/spot/*`).
- The MCP JWT acts as its user, with that user's role, in both APIs. It goes to whoever polls `auth-status` with a
  `client_id` and `state` that a signed-in user approved (`api/chalicelib/core/mcp`); getting one for a client the
  user did not approve is a finding.
- The tracker session token (`backend/pkg/token`, signed with `TOKEN_SECRET`) binds its holder to one session: a
  forged token, or an ingest or socket write that lands in another session, is a finding.
- Chalice checks roles on the route (`OR_role`), the go `api` inside the handlers (`backend/pkg/team`, `accounts`,
  `projects/admin`). A lower role doing a higher role's action in either API is a finding.
- A route that exists in both APIs (the go copies are listed in `newApiUrls`, `frontend/app/api_client.ts`) must
  enforce the same checks in both.

### Projects and tenants

These are findings in this edition too, because the enterprise edition runs the same shared code:

- a query filtered neither by the project in the path nor by the token's tenant; a session, error, event, card,
  dashboard, alert, note or integration fetched by ID without checking its project; a spot or webhook (Slack and MS
  Teams channels included) fetched by ID without checking its tenant. Handlers that return presigned URLs (replay
  files in `backend/pkg/replays`, `backend/pkg/session` and chalice `api/chalicelib/core/mobile.py`, spot videos in
  `backend/pkg/spot/api`, assist recordings in `ee/api`) or stored integration credentials
  (`backend/pkg/integrations`, chalice `log_tools`) need this most;
- a function that takes `tenant_id` or `project_id` and never uses it in its SQL, outside the single-tenant files
  that `ee/` replaces;
- a delete or update that leaves out the ownership filter its read and edit siblings use;
- a project-scoped route whose project is not in the path parameter its authorizer reads: `projectId` (`projectKey`
  on the API-key router) for chalice's `ProjectAuthorizer` (`api/auth/auth_project.py`), `projectId` or `project` for
  go's `api.GetProject`, which the enterprise `validateProjectAccess` uses;
- a project or tenant taken from the body, a query parameter or a header instead of that path or the token;
- a `projectKey` or session token writing into another project's sessions, or an agent token used for another
  session or project.

Show cross-project issues with two projects in this image. This schema has one tenant: argue cross-tenant issues from
the code.

Notes, dashboards and saved searches can be private to their author (`is_public`; `backend/pkg/notes`,
`backend/pkg/analytics/dashboards`, `backend/pkg/analytics/saved_searches`). Another member reading, changing or
deleting a private one is a finding.

### Public API

- The go `api` serves `/v2/api/public/*` to the organisation API key, not a per-project key, as
  `Authorization: Bearer <key>` (`backend/pkg/api_key/handlers.go`): projects, tracked users and their sessions,
  session events, and deletion of a tracked user's data through jobs (`backend/pkg/jobs`). A route is a key route
  when it carries `api.PublicKeyPermission` (`backend/pkg/server/auth/auth.go`). With `{project}` (a `projectKey`) in
  the path, the project must belong to the key's tenant (`isAuthorizedApiKey`); without it only the key is checked
  (`isAuthorizedApiKeyOnly`) and the handler must scope to the key's tenant. The enterprise edition adds live assist
  routes (`ee/backend/pkg/api_key/handlers_ee.go`).
- In chalice only the sourcemap upload takes the key (`PUT /api/{projectKey}/sourcemaps`, raw key in `Authorization`;
  the `app_apikey` router in `api/routers/base.py`, `api/auth/auth_apikey.py`).
- Findings: a public route answering without a valid key or with a rotated one; the key reaching anything else;
  another tenant's `projectKey` accepted; a session, tracked user or job outside the project in the path, including
  what a deletion job deletes when it runs.

### Recorded and live content in the dashboard

- Script running in the dashboard origin is a finding, whatever recorded data carries it (DOM, CSS, network,
  console, plugin state, metadata, titles, URLs, canvas). The replay iframe, the frames rebuilt inside it and the
  heatmap minimap's copy of the replay stay `sandbox="allow-same-origin"` without `allow-scripts`
  (`player/src/web/Screen/Screen.ts`, `player/src/web/managers/DOM/sanitize.ts`; `HeatmapMinimap.tsx` and
  `pageCopy.ts` in `frontend/app/components/Session/Player/ClickMapRenderer/`).
- Recorded strings must reach the dashboard DOM as text: not through `innerHTML`, `dangerouslySetInnerHTML`,
  `srcDoc` outside a `sandbox=""` frame, or ECharts tooltip `formatter` strings without `escapeHtml`
  (`frontend/app/utils/index.ts`); a link built from a recorded URL must be http(s) only (`httpHref`). The escaping
  in `backend/pkg/analytics/sanitizer` is only a second layer.
- A heatmap card's `thumbnail` is a member-supplied copy of a recorded page (`pageSnapshot.ts` in the same folder):
  it may render only as an image or in the `sandbox=""` frame of `PageThumbnail.tsx`.
- The same holds for live sessions (`player/src/web/assist/`), where every event from the visitor's socket, WebRTC
  signalling included, is attacker input too. What an agent's dashboard sends into the room (`agentInfo`,
  `request_control`, `request_recording`) reaches the visitor and must carry no dashboard or spot JWT (`safeQuery` in
  `player/src/web/assist/utils.ts`) and no agent token; the ICE servers in its handshake `config` are meant for the
  visitor.

### The tracker on customer sites

- Script from a third party running on the site through the tracker, `tracker-assist` or the assist server is a
  finding, and so is a masked value in any recorded message, label or selector. The defaults (input values,
  passwords, emails, request and response bodies, auth headers, token-like keys in URLs and bodies) and options (the
  `data-openreplay-*` attributes, old aliases `-masked` and `-htmlmasked` included, `domSanitizer`, `privateMode`,
  the `urls` sanitizers) are in `tracker/tracker/src/main/` (`app/sanitizer.ts`, `modules/input.ts`,
  `modules/network.ts`, `modules/viewport.ts`) and `networkProxy/src`. They must hold in both DOM cores
  (`app/observer/observer.ts`, `next_observer.ts`), in `app/canvas.ts`, and in the modules that copy page text.
- The live stream, including everything `tracker-assist` sends outside the recorded batches
  (`tracker/tracker-assist/src/Assist.ts`, `Canvas.ts`), must mask the same way.
- What agents send must not run script on the page: names (`tracker/tracker-assist/src/CallWindow.ts`, `Mouse.ts`),
  annotations (`AnnotationCanvas.ts`), remote-control input (`RemoteControl.ts`).
- The cross-domain protocol (`tracker/tracker/src/main/app/index.ts`) hands child frames the session token. Only the
  iframes the site tracks with `crossdomain.enabled`, and their own parent (`crossdomain.parentDomain` when set), may
  take part: any other window receiving the token, starting or stopping a frame's tracker, or adding to the recording
  is a finding.
- The spot extension takes a token or a logout only from the dashboard it is configured for, in a top frame
  (`spot/utils/trustedOrigin.ts`, `spot/entrypoints/background.ts`, `spot/entrypoints/content`), and starts
  recordings only from its popup; the dashboard must post it (`orspot:token`) only the spot JWT of its own sign-in
  (`handleSpotJWT` in `frontend/app/utils/index.ts`, `handleSpotLogin` in `Router.tsx` and `Login.tsx`). Any other
  page giving it a token or logging it out, or any page starting a recording or reading its token or recordings, is a
  finding.

### Live assist and co-browsing

- An agent socket needs a JWT signed with `ASSIST_JWT_SECRET` for one `projectKey` and `sessionId`
  (`assist/utils/assistHelper.js`, `check`). The go `api` hands it out as `agentToken` from
  `GET /v2/api/{projectId}/assist/sessions/{sessionId}`, and from
  `GET /v2/api/{projectId}/sessions/{sessionId}/replay` when the session is live but not stored yet
  (`backend/pkg/assist`, `backend/pkg/session/api`). Joining a room as an agent without one, or with one for another
  session or project, is a finding.
- A visitor socket may act only in the room of the session its `/ingest/v1/web/start` token was issued for
  (`checkSession` in `assistHelper.js`, `sessionToken.js`, `processNewSocket` in `socketHandlers.js`). `sessionInfo`
  (`userID`, metadata) is visitor data, not identity.
- Consent (`tracker/tracker-assist/src`: `Assist.ts`, `RemoteControl.ts`, `ConfirmWindow/`): in `requestConfirm` mode
  no replay or media data may leave the page before the visitor approves (`sessionApproved`,
  `PRE_CONFIRM_ALLOWED_EVENTS`). A call (`callConfirm`) and remote control (`controlConfirm`) start only after an
  accept. Getting past a pending or denied prompt is a finding. An approval, a grant and call state carry over to the
  visitor's other tabs (the `or-assist` BroadcastChannel), and other agents may join a call the visitor accepted.
- Remote control: every handler acts only for the agent the visitor granted control to, until release
  (`RemoteControl.isAuthorized`). Input from anyone else or after release is a finding, and so is control coming back
  after a reconnect for an agent the visitor did not grant it to (`RemoteControl.reconnect`).
- Nothing a socket sends, in its handshake or its events (`UPDATE_SESSION` is deep-merged in `onUpdateEvent`), may
  pollute prototypes or stop the assist process (`assist/utils/`).

### SQL injection

In Postgres and ClickHouse, mostly in the go `api`: `backend/pkg/analytics` (`search`, `charts`, `cards`, `events`,
`users`, `saved_searches`, `filters_catalog`; `filters/` builds columns and JSON paths from property names); and in
the `tasks` worker, whose alert evaluator (`backend/pkg/alerts/evaluator.go`) runs saved alerts. Columns, operators
and sort keys built from a request or a stored definition must come from an allow-list (`sortOptions` in
`search/search.go`, `filters.ValidateSortColumnGeneric`), property names in JSON paths must be bound or escaped
(`filters.BuildJSONExtractColumn`, `charts/breakdown.go`), and values must be bound; anything else spliced into SQL
is a finding. Watch plain `string` fields in go request structs and query
parameters: filter and property `name`, `metadata_*` names, `sort`, `sortBy`, `sortOrder`, `sortField`. Stored
definitions (saved searches, cards, alerts, metadata keys) and recorded data that a later query splices in count too.
Unescaped `%` and `_` in `LIKE` patterns rate Low.

### Server-side requests

- The server fetches URLs from recordings (assets, `backend/internal/assets/cacher`; stack-frame URLs,
  `api/chalicelib/core/sourcemaps/sourcemaps.py`, then `sourcemapreader`) and from member settings: Slack and MS
  Teams test messages and shares (`api/chalicelib/core/collaborations`), the webhook, Slack and MS Teams endpoints the
  `tasks` worker posts alerts to (`backend/pkg/senders`), log integrations with a user-set host (Elasticsearch in
  `api/chalicelib/core/log_tools/elasticsearch.py`; Elasticsearch, Sentry and the Datadog `site` in
  `backend/pkg/integrations/clients`), and issue trackers (`api/chalicelib/core/issue_tracking`).
- Every such request must pass a guard when it connects: `api/chalicelib/utils/ssrf.py`,
  `backend/pkg/integrations/clients/httpclient.go` (also used by `backend/pkg/senders`),
  `backend/internal/assets/cacher/netguard.go`, `safeLookup` in `sourcemapreader/servers/sourcemaps-handler.js`, or
  the Jira host check in `api/chalicelib/core/issue_tracking/jira_cloud.py`. A request that passes none, or reaches an
  address its guard refuses, is a finding, including a URL saved unchecked and fetched later and integration "test"
  requests. Say how the response comes back: through `sessions-assets`, a test reply or error, or the sourcemap trace.

### Files, object storage and parsers

- Names from uploads (canvas frame names, tar entry names) and IDs from tokens or paths that become object-storage
  keys or file paths (`storage`, `sink`, `canvases`, `images`, `FS_DIR`) must stay inside the session's own directory
  or key prefix.
- Only `sessions-assets` may be read anonymously, and only by key: no bucket may be listable, nothing private may land
  in `sessions-assets`, and presigned URLs go out only after the ownership checks above. The edge serves the buckets
  from the dashboard's origin, so an object written from visitor, recorded-site or member input (cached assets,
  presigned uploads) must never be served as HTML, SVG or XML: that is stored XSS in the dashboard.
- Parsers of attacker-controlled bytes must cap what they unpack: the binary message decoders (`backend/pkg/messages`,
  `player/src/web/messages`), gzip bodies (`ReadCompressedBody` in `backend/pkg/server/api/request.go`,
  `backend/pkg/sessions/api/mobile`), the tar archives of mobile image uploads (`backend/pkg/images/api`), multipart
  canvas uploads (`backend/pkg/canvases/api`), sourcemaps in `sourcemapreader`, and ffmpeg on uploaded spot videos
  (`backend/pkg/spot/transcoder`), which must read nothing but the uploaded file.

### Secrets and emails

- Every secret a service uses must come from its configuration, and an internal service the edge exposes must
  authenticate requests itself.
- Member and organisation names in invitations (`api/chalicelib/utils/email_helper.py`, `email_handler.py`,
  `backend/pkg/team`) and alert names and descriptions in alert emails (`backend/pkg/alerts/email.go`,
  `backend/pkg/senders/email.go`) must be HTML-escaped.

## Components

Most: the code named under Boundaries, above all ingest (`backend/pkg/sessions/api`, `backend/pkg/sdk/api`,
`backend/pkg/server/api/request.go`, `backend/pkg/images`, `backend/pkg/canvases`) and authentication and roles
(`api/auth`, `api/or_dependencies.py`, `api/chalicelib/core/authorizers.py`, `backend/pkg/server`,
`backend/pkg/token`, `backend/pkg/spot/keys`).

Lower priority: telemetry (`backend/pkg/telemetry`), the tracker plugins and mobile SDKs (`tracker/tracker-*` other
than `tracker-assist` and `tracker-testing-playground`), the rest of `spot/`, `mcp_app/`, `sourcemap-uploader/`,
`snippet/` (the tracker's CDN bundle).

Enterprise edition (`ee/`): in scope to read, though not built here. Look for cross-tenant access, SQL injection and
unauthorized access, including acting beyond a role's permissions or project list. Start with how a request gets its
tenant, role and projects (`ee/api/auth`, `ee/api/or_dependencies.py`, `ee/backend/pkg/server`) and the tenant SQL
that `ee/backend` adds to shared queries (`*_tenant.go`, `scope.go`, `edition.go`), and read each `ee/` file together
with the FOSS files it joins.

Out of scope: `assist-server/` and `ee/assist-server/` (build files only), `min-stack/`, `scripts/` except the
schema this image loads (`scripts/schema/db/init_dbs`) and the edge routes and bucket policies the boundaries rely on
(`scripts/docker-compose/nginx.conf`, `scripts/docker-compose/migration-files/minio.sh` and their helm copies),
`docs/`, `static/`, `openspec/`, `tracker/tracker-testing-playground`, `tracker/harness`, the unused
`tracker/tracker/src/main/modules/privacy/`, tests and fixtures.

## How to exercise it

- `or-start` starts the stores and every service and stays in the foreground printing their logs; the edge is
  `http://127.0.0.1/`. Logs are in `/var/log/openreplay/<service>.log`. After a patch, kill the process: `or-start`
  restarts it. `or-db start|stop` runs the stores alone.
- Not built: `ee/`, everything under `tracker/`, `spot/`, `mcp_app/`, `sourcemap-uploader/`, `networkProxy/`,
  `snippet/`. The frontend and player are prebuilt.
- The owner is `admin@example.com` / `Password123!`, with one project; add another with `POST /api/projects`. Use
  the lowest role that works: `POST /api/client/members` (`{"email":..,"name":..,"admin":false}`) returns an
  `invitationLink` whose redirect carries `invitation` and `pass`; `POST /api/password/reset` with
  `{"invitation","pass","password"}` sets the member's password. `python3 /src/.oss-scanner/probe-member.py` does this
  and starts a tracker session.
- Edge routes: `/api/*` chalice (:8000), `/v2/api/*` go api (:8081), `/ingest/*` http worker (:8080),
  `/ingest/v1/mobile/images` images (:8083), `/spot/*` (:8082), `/ws-assist/*` assist (:9001), object storage
  (rustfs, :9300) under `/mobs`, `/sessions-assets`, `/static`, `/sourcemaps`, `/records`, `/spots`. Canvas frames go
  to canvases at `http://127.0.0.1:8084/v1/web/images`; `sourcemapreader` (:9010) is not behind the edge. Postgres
  `postgres://postgres:changeme@127.0.0.1:5432/postgres`, ClickHouse `127.0.0.1:9000` (user `default`, no password),
  valkey `127.0.0.1:6379`.
- The public API: as the owner, `GET /api/account` returns the organisation key (`apiKey`). Call
  `/v2/api/public/projects` or `/v2/api/public/<projectKey>/...` with `Authorization: Bearer <key>`.
- A tracker session: `POST /ingest/v1/web/start` with `{"projectKey":..,"trackerVersion":..}` (6.0.0 or later) and a
  browser `User-Agent` returns `token` and `sessionID`; batches go to `POST /ingest/v1/web/i` with
  `Authorization: Bearer <token>`.
- A live session: `ws` in `/src/assist/node_modules` is a plain WebSocket client, so write the socket.io frames
  yourself and answer each server `2` (ping) with `3`. As the visitor, open (with a `<tabId>` that has no `-`)
  `ws://127.0.0.1/ws-assist/socket/?EIO=4&transport=websocket&identity=session&peerId=<projectKey>-<sessionId>-<tabId>&sessionInfo=<json>`
  and send `40{"token":"<session token>"}`. While it is open, a member gets an `agentToken` from
  `GET /v2/api/{projectId}/assist/sessions/{sessionId}`. The agent connects with `identity=agent`,
  `peerId=<projectKey>-<sessionId>`, `agentInfo=<json>` and `40{"token":"Bearer <agentToken>"}`. Events are
  `42["<event>",<payload>]` frames.
- MCP sign-in cannot be exercised in this image: argue it from `api/routers/subs/mcp.py` and
  `api/chalicelib/core/mcp`. To test where an MCP JWT is accepted, sign one with the image's `JWT_MCP_SECRET` (HS512,
  `aud` `mcp:OpenReplay`, a real user's `userId`, `tenantId` 1).
- Go: sources in `/src/backend`, binaries in `/src/backend/bin` with debug info; rebuild one with
  `cd /src/backend && go build -o bin/<worker> ./cmd/<worker>`. Tests: `go test -vet=off ./...` (offline module
  cache). Some tests already fail on dev, so compare a patched run with an unpatched one. Python API: `/src/api`,
  virtualenv `/opt/venv`, no test suite. Node: `/src/assist`, `/src/sourcemapreader`.

## How we rate severity

When several entries fit, the one that names the case applies; reaching code execution is always Critical.

- **Critical**: code execution; without an account, reading recordings (sessions, spots) or stored credentials, or
  using the public API; account takeover other than by XSS, an MCP token for a client the user did not approve
  included; script execution on a customer's website through the tracker or assist; joining, watching or controlling
  a live session without an agent token for that session (one for another session or project counts as none), a
  visitor socket in another session's room included; a call or remote-control input without the visitor's current
  accept or grant; SQL injection that needs no account (a `projectKey` or recorded data is enough); another tenant's
  data through a missing tenant check; stored XSS from data any visitor of a tracked site can send, reached through
  normal use of the dashboard.
- **High**: SQL injection with an account or the organisation key; SSRF reaching internal services; another
  project's stored data, or another member's private notes, dashboards or saved searches; stored XSS a member plants
  for another member; files or object-storage keys outside the session's or project's prefix; a page or window
  breaking the cross-domain or spot extension rules (reading a recording through the extension is Critical); a member
  doing an admin- or owner-only action (reads are Medium); the organisation key reaching other routes; a token, key or
  link accepted after it expired or was revoked; a spot JWT outside the extension's routes; a forged tracker session
  token or a write into another session; an agent token reaching the visitor; a fallback secret, or an internal
  service the edge exposes without authentication; a masked value sent, recorded or live; replay or media data
  leaving the page before approval; in `ee/`, a user going beyond their role's projects or permissions.
- **Medium**: SSRF without a meaningful internal target; information disclosure across a role boundary that does not
  include recordings or credentials; XSS that needs unusual interaction; HTML injection in emails; denial of service
  of ingest, `sourcemapreader` or the assist server by a single unauthenticated client (decompression bombs,
  unbounded buffers, crashing a shared process).
- **Low**: everything else, including issues that need admin or owner privileges unless they reach another
  organisation, another member's private items or code execution (an admin doing an owner-only action is Low),
  getting past `recordingConfirm` (the recording is the agent's own screen capture), missing hardening headers, and
  user enumeration.

## Reports and patches

- Show the finding against this image where it runs (a `curl` or `ws` script); for code the image does not run, name
  the code path. Give the role it needs (none, visitor with a `projectKey`, a page on another origin, member, admin,
  owner, organisation API key) and what the attacker ends up with.
- For an `ee/` finding, name the handler or query and the missing check (tenant, project, permission, SQL binding),
  argue it from the code, and say whether the FOSS copy has the same problem.
- For a missing check, list its siblings in the same router or handler file, in the other API and in the `ee/` copy,
  and say which have it.
- `ee/assist/app` copies much of `assist/utils`. Patch the FOSS file and name the `ee/` copy with the same code; code
  only `ee/` has is patched there.
- The per-message encoders and decoders are generated from `mobs/` (`backend/pkg/messages/messages.go`,
  `read-message.go`, `filters.go`, `get-timestamp.go`, the `*.gen.ts` files in `player/` and `tracker/`, and
  `ee/connectors/msgcodec`): patch `mobs/messages.rb` (`mobs/mobile_messages.rb` for mobile messages) or the template
  in `mobs/templates`, and make the same change in every file generated from it, since `mobs/generate.sh` needs ruby,
  which this image lacks. The primitive and batch readers are hand-written.

## Anything to leave alone

- In this edition, members seeing every project of their organisation and joining its live sessions as agents, and
  any member renaming, deleting or sharing a spot of their organisation (in `ee/` the role's project list and
  permissions still apply). This does not cover the project and tenant cases above.
- With `requestConfirm` off, an agent watching a session without a prompt.
- Single-tenant code in a file that `ee/` replaces at the same path, such as `validateProjectAccess` and the go
  `permissions` middleware letting every request through, or chalice `projects.py`, `tenants.py` and `users.py`: a
  missing tenant check, or a missing enterprise permission or project-list check, there is not a finding, but a
  missing owner or admin check is; read the `ee/` copy.
- State the tracker reads back from the site's own origin (its `sessionStorage` and `localStorage` entries, the
  `BroadcastChannel` its tabs share): changing it takes script on the site.
- Listeners the edge does not route, unless a report shows a way to reach them from outside (an SSRF past the guards,
  for example).
- Rate limits, lockout and the optional captcha on login, signup and password reset.
- A known CVE in a dependency with no path from our code to the vulnerable function.
- Starting sessions with the public `projectKey`.
- Recordings of data the site owner chose not to mask.
- Operator settings that relax the SSRF guards (`WEBHOOK_ALLOWED_HOSTS`, `INTEGRATION_ALLOWED_HOSTS`,
  `ALERTS_WEBHOOK_ALLOWED_HOSTS`, `ASSETS_ALLOW_PRIVATE_NETWORKS`).
- Values the install scripts replace (`change_me_*` in the docker-compose `common.env`), and the test secrets and
  passwords this image sets.
- Content from `static.openreplay.com` or the site's `callUITemplate` URL, which `tracker-assist` loads as its call
  window.