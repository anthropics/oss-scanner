# mob_dev: security context and offline analysis

## Project and scope

mob_dev is the development/build/deployment tooling for Mob, a framework that
embeds Erlang/OTP in Android and iOS applications. It builds native artifacts,
retrieves runtimes, connects to devices, pushes executable BEAM modules, manages
plugin trust, and exposes a Phoenix development dashboard. It runs with the
maintainer's workstation permissions and can handle app signing/publishing
credentials. It is an early-development project; no large adoption claim is made.

Audit the whole repository, especially `lib/mob_dev/`, `lib/mix/tasks/`,
`priv/` and native/build support. `GenericJam/mob` and `GenericJam/mob_new`
are separately submitted related projects. An auxiliary mob_new checkout at
`/opt/mob_new` supplies adoption templates, just as in CI; the enrolled repository
is `/src`, not the auxiliary checkout.

## Assets, attackers and trust boundaries

- Protect workstation files, signing keys, publishing credentials, private
  distribution cookies and integrity of code sent to an app. Investigate
  unauthorized dashboard/deploy access and credential leakage through logs,
  generated files, responses or overly permissive file modes.
- Project `mix.exs`, intentionally executable project configuration, build scripts
  and deliberately trusted native dependencies already run code on the developer's
  workstation. Do not report their expected code execution as sandbox escape.
  This does not excuse a bypass of plugin signature/trust gates or execution of a
  manifest before the gate promised to authenticate it.
- Treat plugin manifests, signed envelopes and downloaded archives/artifacts as
  adversarial until their relevant checks succeed. Review
  `lib/mob_dev/plugin/{signature_gate,verify,sign,manifest,trust_store}.ex`,
  download/runtime extraction and path/symlink handling. Distinguish authenticity
  of a trusted author's code from a promise that such code is harmless; activated
  native plugins execute in-process with application privileges.
- Network-originating discovery responses and data from devices, HTTP clients
  and WebSocket clients are not automatically trusted. Trace inputs into
  `lib/mob_dev/server/`, `discovery/`, `connector.ex`, `tunnel.ex`,
  `hot_push.ex` and `dist_cookie.ex`. Show actual bind address, transport,
  authentication and configuration in a reproducer; "development-only" is not
  proof that an interface is inaccessible to another local or LAN attacker.
- Distribution/RPC and hot-push deliberately grant full authority to a properly
  authenticated development peer. Prioritize unintended listeners, public-cookie
  fallbacks, wrong-target deployment, authentication bypass and release-build
  exposure rather than treating authorized RPC as a flaw.
- CLI arguments, generated shell/build commands, device identifiers, paths and
  archive entries require context-specific quoting and containment. Establish
  whether the adversary controls the value independently of already owning the
  trusted project or workstation.
- Review publishing credential persistence and command invocation in
  `lib/mob_dev/google_play/` and `release/`; no real store credentials are present
  and no external publishing should be attempted during a scan.

Read `README.md`, `guides/security_scan.md`, `guides/nifs.md`, relevant
`decisions/`, and Mob's `MOB_PLUGIN_SECURITY.md` for intended contracts. Separate
implemented checks from design proposals and validate any claimed guarantee
against the current code.

## Offline build and exercises

The image builds dev and test environments using Elixir 1.19.5 / OTP 28.0.4.
Hex packages and registry cache remain available. `MOB_NEW_DIR=/opt/mob_new`
points native adoption tests at source templates. Run the Linux CI-equivalent
host suite:

```
MIX_ENV=test mix test --exclude macos_only --exclude requires_zig
```

`test/test_helper.exs` additionally excludes integration, acceptance and
Xcode-live cases. The dev build is retained because HotPush tests inspect its
BEAM output. Useful test areas include `test/mob_dev/`, `test/mix/` and the
fixtures/support directories. Normal Mix tasks and parser/verification APIs can
be exercised with `MIX_ENV=dev mix run` offline without a device.

No Android SDK, Zig, Xcode, mobile runtime binaries, physical devices or store
credentials are supplied. Linux-host tests use project conventions for platform
exclusions; those exclusions are not source-audit exclusions. Report native or
platform findings with their execution limits, and use self-contained host
reproducers for decoding, archive, signature and command-construction boundaries
where possible. Do not invoke a deployment or publication against real services.

## Report requirements and severity

Include affected revision, a minimal reproducer, exact attacker-controlled input,
violated security guarantee, required configuration and privilege, demonstrated
impact and a minimal candidate patch. Deduplicate common roots across deployment
platforms/tasks. Avoid speculative chains from trusted project execution.

Unauthenticated remotely reachable execution or broad secret compromise can be
critical. A reachable authentication/signature bypass, sensitive credential theft
or arbitrary file overwrite outside the intended boundary can be high, depending
on prerequisites. Local/developer-only resource exhaustion and attacks requiring
already-trusted arbitrary code should not be inflated to remote critical issues.
Disclose privately to the configured primary contact, not in public GitHub issues.
