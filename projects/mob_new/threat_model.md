# mob_new: security context and offline analysis

## Project and scope

mob_new is the Mix archive/project generator for Mob, an early-development
Elixir framework embedding Erlang/OTP inside Android and iOS apps. A security
mistake in a template propagates to generated applications. Audit both the
Elixir generator (`lib/`) and shipped runtime/build templates
(`priv/templates/mob.new/`), not only CLI option parsing.

Related `GenericJam/mob` and `GenericJam/mob_dev` are enrolled separately. Their
auxiliary checkouts at `/opt/mob` and `/opt/mob_dev` support the generator's
existing --local tests; `/src` is the enrolled target.

## Trust boundaries and important surfaces

- Generator invocation intentionally writes a project to the user-selected
  destination. Review app/module/bundle names, paths and interpolation for writes
  outside that destination or unintended code/command injection. Trusted template
  and project Elixir code is executable by design, not a sandboxed tenant. A
  malicious existing `mix.exs` executing under Mix is not itself a generator flaw.
- Treat generated defaults as a security contract. Review release-versus-dev
  startup, distribution cookie handling, listener binding, private storage and
  handling of generated secrets. Development RPC deliberately permits arbitrary
  BEAM operations after authentication, but public or predictable credentials,
  accidental unauthenticated exposure and release-mode enabling of development
  access warrant investigation. Loopback does not authenticate other local apps.
- Native templates bridge outside data into the embedded VM. Important paths:
  `android/app/src/main/java/{MainActivity,MobBridge,MobJson,MobNode}.kt.eex`,
  `android/app/src/main/jni/beam_jni.c.eex`, `AndroidManifest.xml.eex`,
  and `ios/{AppDelegate,beam_main}.m.eex`. Investigate deep links, notification
  intents, WebView messages and callbacks; malformed JSON, integer/length checks,
  native-memory/handle ownership and thread/lifetime boundaries. Establish a
  realistic external route to an input; a trusted render tree is not inherently
  remotely reachable merely because the native parser can parse it.
- Generated LiveView/WebView integration has distinct web trust boundaries:
  content origin, JS-to-native bridge authority, transport and authentication.
  Inspect injected hooks/configuration and navigation behavior; do not presume
  deliberately loaded app code is untrusted third-party web content.
- Optional --deliver projects generate an update-signing key and trusted public
  key configuration. Review entropy, private-key permissions/git exclusions and
  safe trust defaults. The OTA implementation lives in separate mob_deliver
  packages; demonstrate defects attributable to this generator's wiring rather
  than assigning all downstream implementation vulnerabilities here.
- Generated native dependencies and activated plugins are trusted executable app
  code; their expected access to the process/app permissions is not a sandbox
  escape. Unexpected capability/permission activation or credential disclosure
  remains relevant.

Use `README.md`, `decisions/`, generator docstrings and template tests as context.
Check current emitted output instead of relying on stale documentation examples.

## Offline build and exercises

The image builds dev and test environments with Elixir 1.19.5 / OTP 28.0.4 and
installs the Phoenix project-generator archive before removing network access.
Hex cache/registry records remain available. `MOB_DIR` and `MOB_DEV_DIR` point at
auxiliary sources, matching the --local path-resolution setup used by CI.

Run the suite with `MIX_ENV=test mix test --exclude requires_android_ndk`. It
includes project generation, LiveView patching and packed-archive tests. The
Docker build runs this suite once with network access so generated projects'
dependency graphs and Hex package archives remain available; `HEX_OFFLINE=1`
then requires later runs to use that retained cache. The excluded NDK compile
test is still in source-audit scope and its structural companion runs on Linux.

Exercise the actual CLI without installing generated dependencies:

```
MIX_ENV=dev mix mob.new scan_example --no-install --dest /tmp/mob-scan
```

Inspect generated files in `/tmp/mob-scan/scan_example`. A version-check notice
may try the network and fail harmlessly; generation itself must succeed. Use a
fresh destination for each invocation. `--liveview` uses the preinstalled phx_new
archive. Source tests are in `test/mob_new/` and `test/mix/`; emitted Kotlin JSON
parser tests are in the template's `android/app/src/test/java/` tree.

The Linux image has no Android SDK, Gradle dependency cache, embedded mobile
runtime binaries, Zig or Xcode. It does not claim to build/run the emitted
Android/iOS application or Kotlin tests. Generated native source remains in
scope; give portable reproducers or clearly identify source-only analysis and
platform execution prerequisites. No physical device access is available.

## Findings and severity

Include the affected revision, input and its attacker control, emitted file(s),
minimal reproducer, actual deployment/configuration prerequisites, violated
invariant and a small candidate patch. Where relevant, show both generator input
and vulnerable generated output. Deduplicate shared template bugs by root cause.

Unauthenticated reachable runtime execution or broad data compromise can be
critical; reachable native corruption, authentication bypass or substantial
cross-boundary secret/file compromise can be high when demonstrated. Severity
must reflect whether the adversary is a remote app user, another local app,
or a developer already able to execute trusted project code. Do not rate all
local-generator issues as remote critical. Send findings privately to the primary
contact, not as public GitHub issues.
