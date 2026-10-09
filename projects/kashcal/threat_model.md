# Threat model

## What this project does and where untrusted input enters

KashCal is an offline-first Android calendar app (Kotlin, min API 31). It syncs calendars over
CalDAV and contacts over CardDAV with servers the user signs in to (iCloud, Nextcloud, Radicale,
Baikal, SOGo, Stalwart, Zoho, Fastmail and others), subscribes to ICS feeds, imports and exports
ICS files, and reads and writes the Android calendar and contacts providers. It has no backend
of its own; every network request goes to a server or URL the user configured, or to one those
servers point to.

Trust boundaries:

- **Event and contact content is untrusted.** Invitations, shared calendars, ICS feeds and
  contacts are written by third parties and arrive through the user's server. An attacker can
  put arbitrary ICS (RRULE, VTIMEZONE, ATTENDEE, VALARM, X- properties) or vCard on the user's
  calendar just by sending an invitation.
- **The user's own server is trusted with that account's data, nothing more.** A malicious or
  compromised server must not be able to obtain credentials for other accounts, read device
  files, reach the device's local network, run code, or damage data in other accounts.
- **Other installed apps are untrusted.** They can send intents to exported components and
  write events into the Android calendar provider through their own sync adapters.
- **The network is untrusted for https accounts.** An account the user set up with an http://
  address has chosen cleartext for that account only.

Entry points (all paths under `app/src/main/kotlin/org/onekash/kashcal/` unless noted):

- ICS parsing and generation: `icaldav-core/` (built on ical4j), `sync/parser/icaldav/`
  (`ICalEventMapper`, `IcsPatcher`, `RawIcsParser`), recurrence expansion in
  `domain/generator/` (`IcalDavRRuleEngine`, `OccurrenceGenerator`).
- WebDAV XML responses (PROPFIND, REPORT, multistatus, scheduling outbox):
  `sync/parser/CalDavXmlParser.kt`, `sync/carddav/CardDavXmlParser.kt`,
  `network/DavMultistatus.kt`, `sync/client/model/OutboxResponse.kt`.
- HTTP client behaviour: `sync/client/OkHttpCalDavClient.kt`, `sync/carddav/OkHttpCardDavClient.kt`,
  redirects and cleartext policy in `network/DavTransportGuard.kt`, digest auth in
  `sync/client/DigestAuthenticator.kt`, missing-intermediate repair in
  `network/AiaCertificateChainCompleter.kt` (fetches a URL taken from a server certificate).
- Account discovery: `sync/discovery/`, DNS SRV/TXT wire parsing in `network/dns/`.
- vCard: `vcard-core/` (built on ez-vcard), `sync/contacts/`, including contact photos
  downloaded from URLs inside a vCard (`ContactPhotoFetcher`, `ContactPhotoTranscoder`).
- ICS subscriptions: `data/ics/IcsFetcher.kt`, `data/ics/IcsParserService.kt`.
- Intents into the exported `MainActivity`: `VIEW`/`SEND` of `text/calendar`, `application/ics`,
  `text/x-vcalendar`, `content://` and `file://` URIs, `webcal://` and `webcals://` links,
  calendar-provider `INSERT`/`EDIT`/`VIEW` intents, and shared plain text.
- Settings backup import (JSON): `domain/backup/SettingsBackupImporter.kt`.
- Natural-language Quick Add text: `domain/quickadd/QuickAddParser.kt`. The user types it, and
  any app can send it through the `SEND text/plain` share.

## Components that matter most / least

Most important:

1. Anything that leaks sync credentials (passwords, app-specific passwords, auth headers):
   sent to a different host after a redirect or discovery step, sent over http for an https
   account, written to logs, exported, or readable by another app.
2. Parsing of ICS, WebDAV XML, vCard and DNS data from the network.
3. Sync logic that a crafted server response or invitation can turn into deleting or overwriting
   the user's events or contacts on the server, or in another account or calendar.
4. Exported components and intent handling.

Less important: UI rendering, widgets, reminder notifications, the date/time pickers.

Out of scope: `app/src/test/`, `icaldav-core/src/test/`, `vcard-core/src/test/`,
`fastlane/`, `images/`, and the Gradle build scripts.

## How to exercise it

The image is built and every unit test has run once. There is no network, so pass `--offline`
to Gradle. The machine is small, so run one module or one test class at a time; the full app
suite is slow there.

- Pure-JVM parser modules, fast:
  `./gradlew --offline :icaldav-core:test` and `./gradlew --offline :vcard-core:test`
- App unit tests (JUnit 4, Robolectric, MockK, OkHttp `MockWebServer`), one class at a time:
  `./gradlew --offline :app:testDebugUnitTest --tests '*CalDavXmlParserTest'`
- Existing hostile-input tests worth starting from: `ICalParserAdversarialTest`,
  `ICalEventMapperFuzzTest`, `RRuleAdversarialTest`, `RRuleDifferentialFuzzTest`,
  `QuickAddParserAdversarialTest`, `DigestChallengeFuzzTest`, `CredentialAdversarialTest`,
  `DeepLinkAdversarialTest`, `DavTransportGuardTest`, `AiaCertificateChainCompleterTest`,
  `SrvWireParserTest`, `CardDavXmlParserTest`, `SettingsBackupImporterParseTest`.
- `MockWebServer` is the way to play a malicious CalDAV/CardDAV server against the real
  clients. Tests under `app/src/test/**/integration/` need live servers and credentials;
  they are excluded by default and cannot run here.

## How you rate severity

- **Critical:** code execution in the app, or theft of stored sync credentials, triggered by a
  remote party (an invitation, an ICS feed, a server response) with no user action beyond a
  normal sync or opening a file or link.
- **High:** credentials sent to any host other than the account's own server, or over http for
  an account set up with https; TLS certificate or hostname validation bypassed; another app
  reading or changing KashCal's events, contacts or credentials without holding the matching
  Android permission; remote input that makes KashCal delete or overwrite the user's data on a
  server or in another account; file read or write outside the app's own storage through
  import, export or share.
- **Medium:** remote input that crashes or hangs the app on every sync or on every launch
  (persistent denial of service); server-controlled URLs (AIA, contact photos, discovery
  redirects) that reach the device's local network or loopback; sensitive data (passwords,
  tokens, full account emails) written to logs.
- **Low:** a one-time crash from a file or link the user opens; excessive memory or CPU that
  recovers on its own; anything that needs root, physical access, or a debug build.

## How reports should look

Please include a JVM unit test that fails today and passes with the patch, and show how the
input reaches that code in practice: which server response, ICS or vCard content, intent or file
produces it. A finding that depends on a state no parser, server or caller can produce (for
example a database row the app never writes) is not a vulnerability for this project.
Patches should be minimal and keep the existing structure.

## Anything to leave alone

- Cleartext HTTP is allowed in `network_security_config.xml` on purpose, for self-hosted
  servers on a LAN. `DavTransportGuard` limits it to accounts the user set up with http://.
  Report only cleartext that reaches an https account.
- No certificate pinning: users choose their own servers.
- The `debug-overrides` user-CA trust applies to debug builds only.
- The many exported `activity-alias` entries are launcher icon variants; the widget receivers
  and sync-adapter/authenticator services are guarded by the system. Report them only if a
  third-party app can make them do something meaningful.
- Vulnerabilities in dependencies (ical4j, ez-vcard, OkHttp, AndroidX) with no reachable path
  through KashCal code: report those upstream.
- Test fixtures, fake credentials and `@example.test` addresses in test sources.
