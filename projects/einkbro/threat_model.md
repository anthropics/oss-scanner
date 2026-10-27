# EinkBro threat model

EinkBro is a GPL-3.0-or-later Android browser for e-ink devices, maintained since
2020 and distributed through GitHub and F-Droid. It processes arbitrary remote
web content while holding browsing history, bookmarks, credentials for optional
services, and user-selected documents. Its Android/Kotlin application, injected
JavaScript and native ad-blocking integration are the scan target.

## Trust boundaries and priorities

- Treat websites, frames, redirects, downloaded files, response headers, filter
  lists, and external Android intents and content URIs as untrusted. Review URL
  handling, navigation and origin checks, TLS decisions, file access, downloads,
  exported components and FileProvider grants.
- Prioritize WebView JavaScript interfaces in `app/src/main/java/info/plateaukao/einkbro/browser/`
  and `view/EBWebView.kt`, plus injected code in `app/src/main/assets/` and
  `ad-filter/`. A page must not gain native app privileges, read private app
  data or obtain service/API credentials merely by being visited.
- Userscripts are deliberately installed executable JavaScript. Review their
  matching, enablement and per-API grant enforcement, especially the GM bridge.
  Distinguish explicitly granted behavior from a website or ungranted script
  obtaining the same capabilities. Installing a userscript is not blanket
  authorization to access every native API.
- Review backup ZIP/JSON imports, bookmark and userscript imports, EPUB handling,
  and device-to-device transfer for path traversal, unsafe parsing, unintended
  data exposure and authorization failures. Document any required user action.
- Review Google Drive OAuth/PKCE, redirect validation and token handling, and
  optional translation/AI integrations for leaks across origins or to unintended
  endpoints. The bundled installed-app OAuth client ID is public configuration;
  user tokens and API keys are sensitive.
- Review `adblock-client/` JNI and native parsing for memory safety issues
  reachable through browser inputs or filter lists. Explain the app-level entry
  point and prerequisites for any issue involving bundled third-party code.

## Scope and severity

Focus on vulnerabilities in this repository and its integration of dependencies.
Android OS, system WebView/Chromium and remote service internals are outside the
target. A dependency version or upstream advisory alone is not a demonstrated
EinkBro vulnerability. Root access, a compromised OS, or prior arbitrary code
execution in the app process are not useful starting assumptions.

Critical findings include demonstrated remote code execution or broad private
data/credential theft from ordinary browsing. High findings include exploitable
native memory corruption or crossing the web-to-native, origin or file-access
boundary with substantial impact. Limited denial of service, narrowly scoped
data exposure or substantial required user interaction usually lowers severity;
explain exploitability, persistence and prerequisites rather than relying only on
the weakness category. Expected JavaScript execution in a website, intentional
sharing/export, or explicitly authorized userscript behavior alone is not a bug.

## Build, tests and reports

The checkout is `/src`. The image builds `assembleDebug` and runs JVM unit tests
for all three modules with Java 17, Android SDK 36, NDK 27.0.12077973 and CMake
3.22.1. Dependencies and the Gradle wrapper are cached in `/root/.gradle`.

Offline commands:

```sh
./gradlew --offline --no-daemon assembleDebug testDebugUnitTest
cd /src/js-tests && npm test -- --runInBand
```

JVM reports are in each module's `build/reports/tests/`; APKs are in
`app/build/outputs/apk/debug/`. JavaScript tests exercise the real translation
assets under jsdom. No emulator, physical device, private signing keys, live
accounts or API keys are included. Use local fixtures and mock services, and
state when a proof of concept requires Android runtime validation.

At enrollment, the Android build and JVM tests pass, but the existing translation
jsdom suite reports 9 failing and 4 passing tests across 5 suites on `main` at
`03632653f362e97f37b0fd86955841ee5b9c63b4`. The Dockerfile logs those failures
without aborting the image build. Treat these as baseline test failures rather
than proof of a newly discovered security vulnerability.

Provide the attacker-controlled input, entry point, affected files and lines,
required user actions, expected versus observed behavior, and a minimal
reproducer or regression test. Group findings with the same root cause and
include a focused candidate patch where practical. Keep sensitive findings
private and send reports to the configured primary contact.
