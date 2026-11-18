# Threat model

## What this project does and where untrusted input enters

Folo is a feed reader. This repository holds its clients and the small services around them:

- `apps/desktop`: the Electron app for macOS, Windows and Linux. `layer/main/src` is the main process,
  `layer/main/preload` the preload script and `layer/renderer` the React renderer. The same renderer, built with
  `WEB_BUILD=1`, is the web app at app.folo.is.
- `apps/mobile`: the Expo / React Native app for iOS and Android. Entry HTML is rendered by the page in
  `web-app/html-renderer`, loaded into a native WebView (`native/`, `src/components/native/webview`).
- `apps/ssr`: share pages, login pages and Open Graph images, on Cloudflare Workers (Hono) and Vercel (Fastify).
- `apps/ota`: the Cloudflare Worker that serves update manifests and bundles (ota.folo.is) and signs Expo manifests.
- `apps/landing` (the folo.is site), `apps/cli` (the `folocli` command), `api/` (a Vercel webhook), and the shared
  code in `packages/internal/*` and `packages/readability`.

The backend API (api.folo.is) is not in this repository; the clients reach it through `@follow-app/client-sdk`.
Treat the API itself as trusted, but not the user-generated content its responses carry.

Untrusted input:

- **Feed content.** Entry HTML, titles, authors, links, media and enclosure URLs, and feed and site icons come from
  arbitrary RSS, Atom and JSON feeds and from RSSHub routes, so whoever controls a feed controls them. The desktop and
  web renderer and the mobile WebView render them; the readability, text-to-speech, translation and AI features
  process them.
- **Pages the app opens.** An entry's URL shown in a `<webview>` or `<iframe>`, and pages fetched for readability.
- **Content from other users.** List and profile names and descriptions, and anything else shared through the API.
- **AI output.** Summaries, translations and chat answers about feed content, which prompt injection in that content
  can steer.
- **Deep links.** `folo://` and `follow://` URLs, which any website or app can open, including the authentication
  callbacks.
- **Requests to the network-facing services** in `apps/ssr`, `apps/ota`, `apps/landing` and `api/`.
- **Update metadata and bundles** that the desktop updater, the renderer hot updater and the mobile OTA client
  download.

Trusted: the Folo API and its operators, the release pipeline and its signing keys, and settings the user enters for
themselves, such as their own custom CSS or the integrations they configure.

## What must hold

- Feed content, other users' content, AI output and pages the app opens must never run script in the app's origin.
  Treat script execution in the desktop renderer as code execution on the user's machine.
- Content and deep links must not reach the native capabilities behind the preload bridge and the IPC handlers
  (`layer/main/src/ipc/services/`): writing files, reading local files, opening external applications or URL schemes,
  downloads, arbitrary network requests, login-item and proxy settings. Those need a deliberate user action.
- Session tokens and cookies must not leak to feed hosts, image hosts, embedded pages or other third parties, and an
  attacker must not be able to set or replace them, for example by logging the user into the attacker's account
  through a deep link or callback.
- Windows that hold the app's privileges must not navigate to attacker-controlled pages, and local files must not be
  readable by content or by remote pages.
- Updates (desktop binaries, renderer hot-update bundles, mobile OTA bundles) must only install what Folo's release
  pipeline published.
- The web services must not allow SSRF to internal addresses, script injection on Folo's origins, leaks of the
  visitor's session token, or access to internal endpoints without their token.

## Components that matter most / least

- Most: the desktop main process and preload (`apps/desktop/layer/main/`, especially `src/manager/`, `src/ipc/`,
  `src/lib/router.ts`, `src/updater/`, `preload/`), the HTML pipeline (`packages/internal/utils/src/html.ts` and
  `apps/desktop/layer/renderer/src/lib/parse-html.ts`), the renderer code that shows AI output
  (`apps/desktop/layer/renderer/src/modules/ai-chat/`), and the components that embed entry pages.
- Next: the mobile WebView and its bridge (`apps/mobile/web-app/html-renderer`, `apps/mobile/src/components/native/`,
  `apps/mobile/native/`), mobile deep links and token storage, `packages/readability`, `apps/ssr`, `apps/ota`.
- Lower: `apps/landing`, `apps/cli` (token storage and its localhost login callback), `api/`.
- Out of scope: `store-assets/`, `docs/`, `wiki/`, `icons/`, `locales/` (other than as rendered text), `.github/`,
  test files, development-only code paths (`DEV` builds, local debugging tools), the backend API, and third-party
  dependencies unless Folo uses them unsafely.

## How to exercise it

- The image has the checkout at `/src` with Node.js 22, pnpm (from `packageManager`) and all dependencies installed,
  `packages/` built, the Electron main, preload and renderer bundles in `apps/desktop/dist/`, the web build in
  `apps/desktop/out/web/`, the SSR build in `apps/ssr/dist/`, and the main process's type declarations in
  `apps/desktop/layer/main/dist/`.
- There is no display, so the Electron app does not start. Reason from the main-process source and drive its
  handlers from Vitest, as the existing tests under `apps/desktop/layer/main/src` do.
- Every workspace's tests: `pnpm exec turbo run test`. One package: `pnpm --filter @follow/electron-main test`,
  `@follow/web` (renderer, type-checked), `@follow/utils` (includes the sanitizer), `@follow/ssr`, `@follow/ota`,
  `@follow/mobile`, `@follow/rn-micro-web-app-html-renderer`, `@follow-app/readability`, `@follow/store`, `folocli`.
  They need no network.
- To test content handling, feed a crafted entry through the sanitizer and `parse-html.ts` in a Vitest test, or
  through the mobile `html-renderer` parser, and inspect the elements and attributes that come out.
- The API is not reachable offline. Mock its responses, using the types in `@follow-app/client-sdk`.

## How you rate severity

- **Critical:** code execution on a user's machine from content they view or a link they open (a feed entry, AI
  output about it, a page opened in the app, a deep link), including script execution in the desktop renderer;
  reading arbitrary local files from content; installing an update Folo did not publish.
- **High:** script execution on app.folo.is or another Folo web origin from feed or user content; theft of a session
  token or of credentials the user stored for integrations; logging a user into an attacker's account; writing files
  outside the app's data directory; SSRF from the web services that returns internal responses; reaching an internal
  OTA endpoint without its token.
- **Medium:** content or deep links that trigger privileged actions without consent but without code execution (for
  example opening a URL scheme, starting a download, subscribing); content that reaches the mobile WebView bridge
  beyond its intended messages; CSS from feed content that covers the app's own UI convincingly or reads data out
  of it; open redirects on Folo origins.
- **Low:** a malformed feed that crashes or hangs a client; issues that need the user to paste or write attacker code
  themselves (self-XSS, their own custom CSS); issues that need a malicious API or a local attacker who already has
  access to the user's account on the machine.

## Anything to leave alone

- The backend API and its authorization logic are not in this repository. Report client-side bugs only.
- Loading the images, video and iframes an entry embeds reveals the reader's IP address to their hosts. That is
  how feed readers work, and not a finding by itself.
- Opening an entry's http(s) link in the system browser after the user clicks it is intended.
- Settings the user controls for themselves, and development-only behaviour that release builds do not ship.
- Outdated dependencies without a reachable exploit path in Folo.

## How reports should look

Name the input an attacker controls (a feed entry, a deep link, a page, a request), the path it takes (for example
sanitizer → `parse-html.ts` → renderer, or deep link → main-process handler → IPC), which clients it affects
(desktop, web, iOS, Android) and the user interaction it needs. Prefer a reproducer that is a crafted feed entry or
deep link together with a Vitest test against the code that handles it. Keep patches minimal, in TypeScript (or
Swift/Kotlin for `apps/mobile/native`), with a regression test where feasible.
