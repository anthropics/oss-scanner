# Threat model

## What this project does and where untrusted input enters
Metrolist is an Android client for YouTube Music (Kotlin, Jetpack Compose, Media3). It has no server
component in this repository. The device owner is trusted; everything below is untrusted:

- Network responses: InnerTube (YouTube Music) JSON parsed in `innertube/` and by the external
  InnerTubeX library, stream URLs and media, and lyrics from third-party providers
  (`app/src/main/kotlin/com/metrolist/music/lyrics/`, `betterlyrics/`: LRC, TTML and JSON formats).
- Listen Together (`listentogether/`): a WebSocket protocol with protobuf/JSON messages relayed from
  a server and other room members. Other participants and the relay server are untrusted.
- Discord integration (`discord/`): the gateway connection and the `metrolistdiscord://oauth2`
  redirect handled by the exported `DiscordOAuthActivity`.
- Intents from other apps: exported `MainActivity` deep links (`metrolist.cc`, youtube.com,
  music.youtube.com, youtu.be, `vnd.youtube`), the exported `MusicService` media session and media
  browser, `MediaButtonReceiver`, widget receivers and the alarm reschedule receiver.
- Files the user opens: backup restore (`viewmodels/BackupRestoreViewModel.kt`, a zip containing the
  Room database and settings) and playlist import.
- WebViews: the YouTube login screen (`ui/screens/LoginScreen.kt`) and the PoToken generator
  (`utils/potoken/`), which run remote JavaScript and pass data back into the app.
- The in-app updater (`utils/Updater.kt`), which fetches release metadata and APKs from GitHub.

## Components that matter most / least
- Most: anything another app or a remote party can reach without user action: exported components
  and intent extras, Listen Together message handling, the Discord OAuth redirect, WebView bridges,
  and the updater. Also leaks of the user's YouTube cookies, Discord token or other credentials
  stored in DataStore.
- Important: parsers for InnerTube, lyrics and backups (crashes on hostile input, path traversal
  from zip entries, SQL issues in Room queries).
- Least: purely cosmetic UI code, `fastlane/`, `assets/` and translations.

## How to exercise it
- `./gradlew :app:testFossDebugUnitTest` and `./gradlew :innertube:testDebugUnitTest` run the JVM unit tests
  (`app/src/test/`, `innertube/src/test/`). The build is offline in the scan image.
- `app/build/outputs/apk/foss/debug/` holds the debug APK. No emulator is available, so prefer JVM
  unit tests as reproducers.

## How you rate severity
- Critical: remote code execution, or theft of the user's Google/YouTube or Discord session by a
  remote party or another app without user interaction.
- High: credential or private data exposure to another app or a Listen Together peer, installing an
  unverified APK through the updater, arbitrary file write (for example zip path traversal) inside
  app storage.
- Medium: a crash or persistent denial of service reachable by a remote party (Listen Together peer,
  malicious lyrics or InnerTube response) or by another app through an exported component.
- Low: issues that need a malicious local backup file the user chose to import, or that only affect
  the user's own data on a rooted device.

## Anything to leave alone
- YouTube terms-of-service concerns, ad blocking, and the fact that the app talks to unofficial or
  undocumented APIs are by design.
- Hard-coded public client identifiers (InnerTube client keys, the Discord application ID) are
  public by design and are not secrets.
