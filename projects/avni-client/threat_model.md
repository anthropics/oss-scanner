# Threat model

The scanner reads this file before it starts. It covers avni-client, Avni's Android app.

## What this project does and where untrusted input enters

Avni is an open-source platform that NGOs and governments use for field work in health, nutrition, water, education
and social welfare. Field workers collect data on an offline-first Android app that syncs with a central server. The
server stores personal and health data about the people those organisations serve, and one deployment holds many
organisations (tenants). Reading or changing another organisation's data is the most serious class of finding in
every Avni component.

avni-client is the field worker's app (React Native, in `packages/openchs-android`). It keeps a local database of
the subjects in the worker's catchment (Realm, with a migration to SQLite under way), works offline, and syncs with
avni-server using a Cognito or Keycloak token. Phones are shared, low-cost and often rooted or lost, and many field
users of one organisation share a catchment.

Untrusted input reaches it through:

- **Sync responses and downloaded files**: entities, forms, rule code, translations, extension and custom-card HTML,
  media, and the "fast sync" database dump that a new device restores for its catchment. Rule code and HTML from the
  organisation's configuration run inside the app; a field user must not be able to plant code or settings that
  another user's app then runs or trusts.
- **Restored backups and databases**, including the settings they carry (server URL, tokens).
- **Other devices nearby**: the clinic-sharing feature exchanges records between phones over the local network after
  a QR code scan.
- **Other apps and the device**: intents, exported components, files on shared storage, the clipboard, logs and
  crash reports.
- **Values typed by the user**, which rules and regular expressions from the configuration process.

### Trust model

- The signed-in field user is trusted with the data of their own catchment and nothing else. Other field users,
  other apps on the phone and whoever holds a lost phone are untrusted. Organisation administrators are trusted for
  their organisation's configuration. Avni's operators and the build configuration are trusted.

## Components that matter most / least

### Highest priority

1. Backup, restore and fast-sync (`src/service/BackupRestore*Service.js`): what a restored database can change
   (server URL, tokens, rules, settings) and what an uploaded dump discloses.
2. Authentication and token storage (`src/service/*AuthService.js`, `SettingsService.js`), and what remains on the
   device after sign-out.
3. Evaluation of rule code and HTML from configuration (`RuleEvaluationService.js`, extension and custom-card
   views, WebViews).
4. Clinic sharing: pairing, what a peer can read and write, and what later syncs to the server.
5. Local data at rest: database encryption, files on shared storage, logs and crash reports.
6. The Android manifest and native modules under `packages/openchs-android/android`: exported components, intent
   handling, network security configuration.

### Lower priority and out of scope

- Out of scope: tests, `docs/`, `specs/`, `scripts/`, `tools/`, iOS files, build and CI configuration, and
  attacks that need a rooted device with the app unlocked unless they defeat a protection the app claims to provide.

## How to exercise it

- `/src` is the checkout. The image ran `make deps_ci` (`npm install --legacy-peer-deps`, patches and
  autolinking in `packages/openchs-android`) and `make ci test-android` on Node 20.19.5. The Android SDK, NDK and
  Gradle are not installed, so the APK is not built and nothing runs on a device or emulator.
- Run the unit tests with `cd packages/openchs-android && npm run test-ci` (Jest). A proof of concept is a Jest test
  that drives the service involved with hostile data, or a precise description of the files, intents or network
  messages that trigger the issue. avni-server is not available in the image.

## How you rate severity

- **Critical**: one field user (or anyone without an account) running code in another user's app, taking their
  token, or redirecting their app to another server; reading another organisation's data.
- **High**: reading another user's token or local database through a file the app shares or uploads; a nearby
  device or another app on the phone reading or changing records without the user's consent.
- **Medium**: personal data or tokens left in logs, crash reports or shared storage; data that survives sign-out;
  weaknesses that need physical possession of an unlocked phone.
- **Low**: issues that need a rooted device; hardening gaps with no demonstrated outcome.

## Anything to leave alone

- Development defaults that deployments replace (default passwords, keys and URLs in configuration templates and
  Makefiles). Do report a default that is used where no setting exists to replace it.
- Vulnerabilities in third-party dependencies unless this project's code reaches them in an exploitable way.
- Missing rate limiting and missing security headers, unless they combine into one of the outcomes above.

### Reports and patches

- One report per root cause, listing every affected endpoint, file or class.
- State who the attacker is (unauthenticated, field user, organisation administrator) and whether the effect crosses
  organisations.
- Include a reproducer (a test beside the existing ones, or the exact requests) and a minimal patch with a
  regression test.
