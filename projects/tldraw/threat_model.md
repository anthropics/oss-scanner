# Threat model

## What tldraw is and where untrusted input enters

tldraw is an infinite canvas SDK for React. The repository holds three things that matter for security:

* **The SDK** (`packages/*`, published to npm as `tldraw`, `@tldraw/editor`, `@tldraw/sync`, `@tldraw/sync-core`
  and friends). It is embedded by many web applications, and runs in the page of the application that embeds it.
* **The multiplayer sync server library** (`packages/sync-core`, server side: `TLSocketRoom`, `TLSyncRoom`). SDK
  users run it in Node.js, Bun or Cloudflare Durable Objects and connect browsers to it over WebSockets.
* **tldraw.com** (`apps/dotcom/*`): our own product, built on the SDK. The client is a React app
  (`apps/dotcom/client`); the backend is Cloudflare Workers and Durable Objects (`apps/dotcom/sync-worker`,
  `asset-upload-worker`, `image-resize-worker`, `tldrawusercontent-worker`), with shared helpers in
  `packages/worker-shared` and Postgres plus Zero for app data (`apps/dotcom/zero-cache`, `sync-worker/src/zero`).

The application embedding the SDK, and the options it passes to `<Tldraw>`, `Editor` and `TLSocketRoom`, are
trusted. Everything below is untrusted.

**Document content.** A tldraw document is a set of records (shapes, bindings, assets, pages, ...) validated by
`packages/tlschema` (record validators, built on `packages/validate`) and migrated by `packages/store`. Documents
arrive from other users in a multiplayer room, from `.tldr` files (`packages/tldraw/src/lib/utils/tldr/file.ts`,
including legacy v1 files in `buildFromV1Document.ts`), from snapshots passed to `loadSnapshot`, and from tldraw
clipboard payloads. Every field is attacker-controlled: shape props, rich text (TipTap JSON, rendered by
`packages/tldraw/src/lib/utils/text/richText.ts`), URLs on link, bookmark, embed, image and video shapes, asset
`src` values, and free-form `meta`. Someone who opens or joins a document must be safe from its author.

**Pasted and dropped content.** `packages/tldraw/src/lib/defaultExternalContentHandlers.ts` and
`packages/tldraw/src/lib/utils/clipboard.ts` turn clipboard and drag-and-drop data into shapes: HTML, plain text,
URLs, SVG (sanitized by `packages/tldraw/src/lib/utils/svg/sanitizeSvg.ts`), images, videos, Excalidraw data
(`utils/excalidraw`) and Mermaid diagrams (`packages/mermaid`). A user who pastes content copied from a hostile
page must be safe from that page.

**Embeds.** `packages/tldraw/src/lib/defaultEmbedDefinitions.ts` and `utils/embeds/embeds.ts` turn a URL into an
`<iframe>` src for known services. A URL must not produce an iframe on an origin the definition does not allow, a
`javascript:` or `data:` src, or sandbox permissions wider than the definition asks for.

**Exports.** `packages/tldraw/src/lib/utils/export/` produces SVG and PNG from document content. An exported
SVG is often opened directly by another person, so document content must not inject script or external fetches
into it beyond what the shapes intend.

**Sync protocol.** `TLSocketRoom` (`packages/sync-core/src/lib/TLSocketRoom.ts`, `TLSyncRoom.ts`, `protocol.ts`,
`chunk.ts`, `diff.ts`, `recordDiff.ts`) processes messages from untrusted clients. A malicious client must not be
able to:
- crash the server process or the room, or wedge it so other clients cannot sync;
- store records that fail validation, or that crash or corrupt other clients when they load them;
- write in a session the server opened as read-only, or change records the room does not allow;
- read or affect another room;
- pollute prototypes through record ids, props or diff operations.

`TLSyncClient` (`packages/sync-core/src/lib/TLSyncClient.ts`) processes the server's messages. The server is
trusted, but messages relayed from other clients are not.

**tldraw.com backend.** The routes are in `apps/dotcom/sync-worker/src/worker.ts`. Authentication is through
Clerk. File access is decided in `authorizeFileRecord.ts` and the Zero mutators and queries
(`/app/zero/mutate`, `/app/zero/query`). Notable surfaces: file, history, snapshot, publish and readonly-slug
routes; invites (`/app/invite/:token`); uploads (`/app/uploads/:objectName`, `packages/worker-shared/src/userAssetUploads.ts`);
URL unfurling (`/unfurl`, `packages/worker-shared/src/bookmarks.ts`), which fetches arbitrary URLs; the image
resize worker, which fetches images by URL; the MCP endpoints under `/app/mcp`; and the admin routes
(`adminRoutes.ts`). User uploads are served from a separate origin by `tldrawusercontent-worker` so that they
cannot run script on tldraw.com.

**VS Code extension.** `apps/vscode` opens `.tldr` files from any folder in a webview. Opening a hostile `.tldr`
file from a cloned repository must not run code in the extension host or reach the user's files.

## Components that matter most and least

Most important:
* script execution from document content or pasted content: text and rich text rendering, link handling,
  embeds, SVG import and export, image and video asset URLs, bookmark metadata;
* the sync server's handling of client messages (`packages/sync-core`, server side);
* authorization in the tldraw.com backend: reading, writing or deleting another user's files, assets, comments
  or workspace data; escalating from viewer to editor; using an invite token beyond its scope;
* server-side request forgery from `/unfurl` and the image resize worker.

Less important, but in scope:
* denial of service against one browser tab from a pathological document (huge numbers of shapes, degenerate
  geometry, deeply nested groups);
* the collaboration, commenting and mentions packages (`packages/collaboration`, `packages/commenting`,
  `packages/mentions`, `packages/sync-collaboration`);
* `apps/mcp-app` and `apps/bemo-worker` (our hosted demo sync server).

Out of scope:
* `apps/docs`, `apps/examples`, `templates/`: documentation, demos and starter projects. Bugs there only matter
  if they show that the SDK itself is unsafe to use as documented.
* `internal/` (build and release scripts), `apps/analytics*`, `.github/`, e2e tests, test fixtures and
  `*.test.ts` files.
* The license key check (`packages/editor/src/lib/license`): getting around it is not a security issue for users.
* Vulnerabilities that live entirely in third-party dependencies (TipTap, React, Mermaid, Cloudflare runtime)
  unless tldraw's own code makes them reachable.
* Running arbitrary JavaScript through `apps/mcp-app`'s `exec` tool: that is what it is for. Escaping the sandbox
  of its `search` tool is in scope.

## How to exercise it

* `pnpm test-ci` runs every vitest suite; `cd packages/tldraw && pnpm test run <file>` runs one. Tests sit next to
  the source as `*.test.ts`; integration tests for the full SDK are in `packages/tldraw/src/test/`.
* `packages/tldraw/src/test/TestEditor.ts` is a headless editor (jsdom) for driving pastes, shape creation,
  snapshot loading and exports from a test.
* `packages/sync-core/src/test/` has `TestServer.ts`, `TestSocketPair.ts` and a sync fuzzer (`syncFuzz.test.ts`,
  `FuzzEditor.ts`) for running a `TLSocketRoom` with real clients in-process. `TLSocketRoom.test.ts` shows how to
  send raw protocol messages.
* The tldraw.com workers have vitest suites next to their sources (`apps/dotcom/sync-worker/src/*.test.ts`,
  `packages/worker-shared/src/*.test.ts`).
* `pnpm dev` serves the examples app at http://localhost:5420; `/develop` is a full editor with `window.editor`
  exposed. Playwright Chromium is installed in `$PLAYWRIGHT_BROWSERS_PATH`, so a script can load a document or
  simulate a paste there and check whether script runs. The e2e suites are in `apps/examples/e2e`
  (`cd apps/examples && pnpm e2e`).

## How we rate severity

* Critical: script execution on tldraw.com, or in a page embedding the SDK with default options, triggered by
  opening or joining a document; reading or modifying another tldraw.com user's private files without their
  permission; remote code execution in a worker or in a server running `TLSocketRoom`.
* High: script execution that needs one ordinary user action (pasting content, clicking a link or embed in a
  document); writing to a read-only room or another room through the sync protocol; storing a record that
  crashes every client that loads the document, permanently; server-side request forgery reaching internal
  services; a hostile `.tldr` file running code in the VS Code extension host.
* Medium: one client message crashing the whole sync server process (all rooms) without corrupting data;
  leaking another user's email address, file names or other private metadata; open redirects; CSRF on
  state-changing tldraw.com routes; escaping an embed's iframe sandbox without script execution on our origin.
* Low: a pathological document hanging or crashing the tab of the person who opens it; UI spoofing; issues that
  need the embedding application to pass clearly unsafe options or to turn off validation.

## Reports

Please include a document (`.tldr` JSON or a snapshot), a clipboard payload, a protocol message sequence or an HTTP
request that reproduces the issue; a vitest test or Playwright script against this image where possible; and a
minimal patch against `packages/` or `apps/dotcom/` with a test. Group findings with the same root cause into one
report.
