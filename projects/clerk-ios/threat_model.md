# Threat model

## What this project does and where untrusted input enters

Clerk is the official authentication SDK for Apple platforms (iOS, iPadOS, macOS, watchOS, tvOS, visionOS). App developers embed it to sign users up and in, manage sessions, users and organizations, and to show Clerk's prebuilt SwiftUI views. It talks to Clerk's Frontend API, a hosted backend that is closed source and not part of this repository.

- `Sources/ClerkKit` is the core SDK: networking, session and token handling, Keychain storage, and the sign-in and sign-up flows (password, codes, magic links, OAuth and SSO, passkeys, Sign in with Apple, biometrics).
- `Sources/ClerkKitUI` holds the prebuilt SwiftUI views built on ClerkKit.

We trust the integrating app's configuration: the publishable key, `proxyUrl`, redirect configuration, Keychain access group and custom middleware. We also trust text the developer writes, such as custom row titles. Values the app collects from its users and passes to the SDK are not trusted. We trust Clerk's Frontend API over TLS.

Untrusted input enters at:

- **Values end users type.** Identifiers, passwords, codes and profile fields the app passes to the authentication and user APIs (for example `Auth.signIn(_:)`), or that users enter in ClerkKitUI's forms.
- **Inbound URLs.** `Clerk.handle(_:)` routes deep links and universal links (`Core/ClerkURLRoute.swift`, `Domains/Auth/MagicLink.swift`). Any app or web page can open a URL with the app's scheme.
- **OAuth, SSO and hosted-auth callbacks.** `ASWebAuthenticationSession` returns them (`Utils/WebAuthentication.swift`, `Utils/ExternalAuthUtils.swift`, `Core/Auth+HostedAuth.swift`, `Domains/Auth/HostedAuth.swift`, the `handleRedirectCallbackUrl` paths in `SignIn.swift` and `SignUp.swift`).
- **Content from other end users.** Names, organization names, emails, avatar and logo URLs, and custom fields come back from the API and are rendered in ClerkKitUI (Nuke `LazyImage`, `SafariView`, markdown in `LocalizedStringKey`).
- **Other processes on the same device.** The Darwin `notify` channel (`Identity/SharedIdentityNotifier.swift`), Keychain items in a shared access group, and WatchConnectivity payloads (`WatchSync/`).
- **Response headers.** The `Authorization` response header replaces the stored device token (`Networking/Middleware/ClerkDeviceTokenResponseMiddleware.swift`, `ClerkClientSyncResponseMiddleware.swift`).

## Components that matter most / least

Most important:
- Anything that can leak the device token (the `Authorization` client token), a session JWT, a PKCE verifier or a passkey or biometric assertion to a host other than the configured Frontend API or proxy (`Networking/`, `Networking/Middleware/`, `Dependencies/DependencyContainer.swift`).
- Session-fixation, login CSRF or account-linking flaws in OAuth, SSO, hosted-auth and magic-link callbacks, including missing or bypassable `state`, nonce or PKCE checks.
- Keychain storage (`Storage/Keychain/`): accessibility classes, access groups, and what is persisted (the cached `Client` holds each session's last session JWT).
- Session token caching and invalidation (`Domains/Auth/Session/SessionTokenFetcher.swift`, `Identity/`), for example serving a token for the wrong session or user after sign-out or account switching.
- Passkeys, Sign in with Apple and biometric credentials (`Helpers/`, `Core/BiometricCredentials.swift`, `Domains/Auth/BiometricCredential/`).

In scope, lower priority:
- Publishable key parsing (`Configuration/ConfigurationManager.swift`).
- Telemetry (`Telemetry/`, development instances only).
- Logging redaction (`Networking/Middleware/ClerkLoggingMiddleware.swift`).
- ClerkKitUI handling of server-supplied URLs and text.

Out of scope:
- `Examples/`, `Tests/`, `e2e-tests/`, `scripts/` and `.github/`.
- Mock and preview code: `Sources/ClerkKit/Mocks/` and `#Preview` blocks. `Clerk+Preview` is public, but only for SwiftUI previews.
- Clerk's backend. Report backend issues to security@clerk.dev, not as findings against this repository.
- Vulnerabilities in third-party dependencies (Nuke, PhoneNumberKit) unless the way this SDK uses them makes them exploitable.

## How to exercise it

The package only builds with Xcode on macOS. In this image ClerkKit and ClerkKitUI do not compile, because they import Apple-only frameworks (Security, AuthenticationServices, LocalAuthentication, CryptoKit, WatchConnectivity, SwiftUI, UIKit, AppKit). Every package dependency is checked out under `.build/checkouts`.

- Some Foundation-only files typecheck with the Linux toolchain on their own or in small groups, for example `swiftc -parse-as-library -typecheck Sources/ClerkKit/Utils/ProxyConfiguration.swift` or `Utils/JSON.swift` with `Utils/JSON+MergePatch.swift`. To test parsing logic (URL routing, callback parsing, key decoding, proxy URL normalisation), copy the relevant functions into a small standalone Swift file and run it with `swift`.
- Code that depends on Apple frameworks has to be reviewed by reading it. Say in the report when a reproducer could not be run.
- The unit tests in `Tests/` use `FakeTransport` and Mocker to stub network responses. They show how each flow is meant to behave, and a regression test for a patch belongs there.

## How you rate severity

The attacker is a remote party, another app on the same device, or another end user of the same Clerk application. They cannot break TLS and do not control the integrating app or Clerk's backend.

- **Critical:** Remote session or account takeover of an app's user with no user interaction, or the device token or a session JWT sent to an attacker-controlled host.
- **High:**
  - Session or account takeover that needs one ordinary user action, such as opening a crafted link or completing a normal sign-in.
  - Bypass of a sign-in factor, a second factor, or a callback `state`, nonce or PKCE check.
  - Session tokens served for the wrong user after sign-out or account switching.
  - Secrets persisted with weaker Keychain protection than `AfterFirstUnlockThisDeviceOnly`.
- **Medium:**
  - Login CSRF that signs the victim into the attacker's account.
  - Spoofing or phishing in the prebuilt views using content from another end user.
  - Secrets written to logs in a release build.
- **Low:**
  - Crashes or denial of service from malformed input.
  - Issues that need a malicious Clerk backend, a compromised or jailbroken device, or a developer misconfiguration (for example an `http://` proxy URL).
  - Debug-only logging.

## How we would like reports and patches

- Name the file, the function and the attacker position, and give a concrete input, such as the exact URL or response, that triggers the issue.
- Patches should be minimal Swift changes in the style of the surrounding code, with a test in `Tests/` that uses the existing `FakeTransport` and Mocker helpers.
- Say whether you ran the reproducer, or reasoned about it statically because it needs Apple frameworks.

## Anything to leave alone

- Do not report that ClerkKit decodes JWTs without verifying their signature (`Utils/JWTDecoder.swift`). The SDK only decodes tokens it received from the Frontend API over TLS.
- Do not report that a user can bypass the `Session.has(...)` checks (`Domains/Auth/Session/Session+CheckAuthorization.swift`) on their own device. It reads the `fea`, `pla` and `fva` claims without verifying them because it only gates UI, and apps must enforce authorization on their own backend. Do report a way for an attacker other than the device's own user to make `has()` trust a token they supplied.
- Do not report that the publishable key and the Frontend API host are public. They are designed to ship in apps.
