# Threat model — AirTranslate

## What this project does and where untrusted input enters
AirTranslate is a macOS app (Swift, SwiftUI/AppKit) that captures system audio via ScreenCaptureKit, transcribes it
live (Apple Speech by default) and optionally translates it, showing floating captions. Optional cloud engines
(OpenAI, Gemini, Meta, Azure MAI, Nari, xAI Grok, Alibaba Qwen, OpenRouter, TypeSafe) are used only with the user's
own API keys. There is no account system, no developer-operated relay server and no hardcoded provider keys.

Untrusted input:
- Responses from third-party provider APIs: HTTP/JSON bodies, server-sent event streams and WebSocket realtime
  messages (transcripts, translations, audio chunks, error payloads). Treat every provider response as adversarial.
- Captured audio and the recognized/translated text derived from it (attacker-controlled media playing on the Mac).
- User-supplied settings such as custom endpoints (e.g. Azure resource URL) and public HTTPS audio URLs.
- Saved transcript files read back from disk.

## Components that matter most / least
- Most: realtime/streaming parsers and session state machines in Sources/AirTranslate/Services; API key handling
  (macOS Keychain, Security framework) — any key leakage to logs, files, the wrong host, or another provider;
  transcript persistence (path handling, file writes); TLS/endpoint construction for user-supplied URLs.
- Less: SwiftUI views and layout code; Release/ packaging scripts; docs/ and intro.html static pages.
- Out of scope: third-party provider services themselves.

## How to exercise it
- The full app and its swift-testing suite (Tests/AirTranslateCoreTests, which depends on the app target) require
  macOS 26+ and cannot run in the Linux scanner image; review them as source.
- The image builds AirTranslateCore (Foundation-only) with debug info using `swift build --target AirTranslateCore
  -c debug -Xswiftc -g`. The full checkout remains at /src. The core can be rebuilt with the same command offline.
- Python unit tests for latency trace tooling run with `python3 -m unittest discover -s script/tests -v` from /src,
  including offline after setup. Both the core build and these tests must succeed for the Dockerfile to build.

## How you rate severity
- Critical: exfiltration of a stored provider API key or captured audio/transcripts to an unintended host, or code
  execution from a provider response.
- High: Keychain key exposure in logs/plaintext files; path traversal or arbitrary file write via transcript
  saving; TLS/host validation bypass for provider endpoints.
- Medium: crashes or hangs triggered by malformed provider responses (DoS of the local app only).
- Low: issues requiring local admin access or an already-compromised Mac.

## Anything to leave alone
- API usage cost, model quality/accuracy, and UI behaviour are not security issues.
