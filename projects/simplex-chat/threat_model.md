# Threat model

## What simplex-chat is and where untrusted input enters

simplex-chat is the SimpleX Chat client core: the chat protocol on top of the SimpleX network (contacts, groups,
channels with chat relays, files, calls, remote desktop control), its encrypted SQLite store, the terminal CLI,
the bot API and the service bots (directory service, badge service, broadcast and support bots). The same
Haskell core is compiled into the Android and desktop apps (Kotlin Multiplatform, `apps/multiplatform`) and the iOS
app (Swift, `apps/ios`), which call it through the C API in `src/Simplex/Chat/Mobile.hs` with JSON commands and
events. The network layer, end-to-end encryption and the SMP agent come from simplexmq
(`https://github.com/simplex-chat/simplexmq`), pinned in `cabal.project`.

The chat protocol is specified in `docs/protocol/simplex-chat.md`, with channels, names and badges in
`docs/protocol/`. The security policy and threat model are in `docs/SECURITY.md` and simplexmq's
`protocol/security.md`.

Untrusted input enters from:

* contacts and group members: every chat protocol message after decryption (`src/Simplex/Chat/Protocol.hs`),
  including profiles, message content, markdown, link previews, file and call invitations, group and channel
  management events, and forwarded messages;
* chat relays and channel owners, for channels; group members relaying messages for other members;
* connection links, short links, contact addresses and group links, which users receive out of band;
* received files and their descriptions;
* the remote control peer (`src/Simplex/Chat/Remote*`), a mobile or desktop app connecting over the network;
* for service bots, any SimpleX user messaging them; for the badge service web checkout, HTTP clients and
  payment provider responses and callbacks (`apps/simplex-badge-service`);
* in the apps: links opened from other apps and websites (the `simplex:` scheme and the `https` hosts in
  `apps/multiplatform/android/src/main/AndroidManifest.xml`), content shared from other apps (Android share
  intents, the iOS share extension), web pages fetched for link previews, the WebRTC call page and its messages to
  the app, and other local processes reaching the desktop call server on localhost.

The local user, the chat API caller (UI, CLI user or bot controller), the local database and the host operating
system are trusted.

## Components that matter most and least

Most important:

* `src/Simplex/Chat/Library/` (`Subscriber.hs` processes received messages, `Commands.hs` and `Internal.hs`):
  authorization of member roles, group and channel membership changes, message forwarding, deduplication;
* `src/Simplex/Chat/Protocol.hs`, `Messages*`, `Markdown.hs`: parsing of peer-controlled data;
* `src/Simplex/Chat/Files.hs` and file handling in the library: paths derived from received names, sizes, chunks;
* `src/Simplex/Chat/Remote*`: remote control pairing and session protocol;
* `src/Simplex/Chat/Store*`: SQL built from received data, consistency of state after malicious messages;
* `apps/simplex-directory-service`, `apps/simplex-badge-service`, `src/Simplex/Chat/Badges*`,
  `src/Simplex/Chat/PaymentService*`: services that run unattended and talk to arbitrary users;
* in `apps/multiplatform/common/src/*/kotlin/chat/simplex/common/`: `views/call/` with the call page in
  `packages/simplex-chat-webrtc`, `views/helpers/LinkPreviews.kt`, link and share handling, `platform/Files.kt`
  (opening and saving received files), `AppLock.kt` and `views/localauth/` (passcode and app lock),
  `platform/Cryptor.kt` (database passphrase in the Android Keystore), `views/remote/`, `platform/Core.kt` and
  `model/SimpleXAPI.kt` (the boundary to the core);
* in `apps/ios`: `SimpleXChat/` (core API, `KeyChain.swift`, file handling), `SimpleX NSE` (decrypts messages for
  notifications), `SimpleX SE` (share extension), and the call and link handling in `Shared/`.

Lower priority:

* `src/Simplex/Chat/View.hs` and `Terminal*`: the CLI rendering;
* UI layout and theming code in the apps;
* other bots in `apps/` and `bots/`; `packages/` other than `simplex-chat-webrtc` (client libraries for Node.js,
  Python and TypeScript).

Out of scope:

* `website/`, `blog/`, `docs/` other than the protocol documents, and `tests/` with its fixtures;
* simplexmq itself, which is scanned as its own project, except where simplex-chat misuses it.

## How to exercise it

The image is built with `cabal.project.local` enabling tests, so `cabal build` and `cabal test` work offline
without rebuilding dependencies.

* Tests: `$(cabal list-bin simplex-chat-test) -m "<describe path>"`, for example `-m "SimpleX chat protocol"`
  or `-m "group tests"`. Functional tests start local SMP and XFTP servers and several chat clients in one
  process, so two-party and group scenarios run offline. Test helpers are in `tests/ChatClient.hs` and
  `tests/ChatTests/Utils.hs`.
* CLI: `$(cabal list-bin simplex-chat) -d <db prefix>`; it needs a reachable SMP server, which offline means
  one started by the tests or `smp-server` from simplexmq.
* Android and desktop apps: in `apps/multiplatform`, run `./gradlew --offline`. Every dependency is cached and
  `:common`, `:desktop` and both Android flavors are already compiled, for example `:common:compileKotlinDesktop` or
  `:android:compileFossDebugKotlin`. Unit tests: `:common:desktopTest` and `:android:testFossDebugUnitTest`.
  Android APKs cannot be assembled, because the core for Android is cross-compiled with Nix and is not in the image.
* Desktop app with the core: `scripts/desktop/build-lib-linux.sh` (run from `/src`) rebuilds simplexmq and
  simplex-chat as `libsimplex.so` and copies it, with its GHC libraries, into
  `apps/multiplatform/common/src/commonMain/cpp/desktop/libs/linux-x86_64/`. Its last step downloads VLC and fails
  offline, which only affects video playback. Then `./gradlew --offline :desktop:compileKotlinJvm` also builds the
  JNI library that links the core.
* iOS app: source only; it needs macOS and Xcode to build.

## How we rate severity

We use the levels in `docs/SECURITY.md`:

* Critical: affects common configurations, low or medium difficulty. For example, disclosure of users' messages or
  files, or remote compromise of private keys.
* High: as critical but in less common configurations or with high difficulty. Also any remote code execution, any
  way for a contact or group member to read or write files outside the app's file storage, to act with a role or
  identity it does not have, or to impersonate another member.
* Medium: crashes of client applications caused by received messages or files, flaws in rarely used features,
  local flaws.
* Low: issues that only affect the CLI app, unlikely configurations, or medium issues that are very hard to exploit.

A report should name the attacker (contact, group member, chat relay, router, remote control peer, or a website
or other app on the device for app issues) and show the messages, links or content it sends.

## Anything to leave alone

* Anything simplexmq's `protocol/security.md` lists under what an adversary *can* do, such as routers learning
  metadata or dropping all messages to a queue.
* CPU and hardware flaws, physical side channels, and access to data on the user's device with the user's or root
  privileges, including the database and its key if stored on the device.
* Behaviour that requires the user to run commands given to them by an attacker in the CLI or the bot API.
