# mob: security context and offline analysis

## Project and scope

Mob embeds Erlang/OTP in Android and iOS applications. Elixir screen processes
produce render trees consumed by native Compose/SwiftUI bridges and NIFs. It also
provides mobile event routing and development-time Erlang distribution. Bugs at
these boundaries can affect the embedding application's data and OS-granted
permissions. This is an early-development framework, not a claim of broad adoption.

Audit the whole repository, including `lib/`, `src/mob_nif.erl`, `android/jni/`,
and `ios/`. Related projects `GenericJam/mob_new` and `GenericJam/mob_dev` supply
native host templates and deployment tooling; they are submitted separately.

## Trust boundaries

- App Elixir code and deliberately activated native plugins are executable,
  trusted application code, not sandboxed tenant programs. A proof that arbitrary
  app code can call a NIF or execute code is not itself a vulnerability. However,
  plugin declaration, signature and permission checks must uphold their stated
  guarantees; verify implementation rather than assuming design-doc promises.
- Treat externally originating deep links, notification payloads, WebView
  messages, network/discovery data, and device-originated bytes as untrusted at
  entry. Follow their actual reachability into decoding, routing, storage and
  native calls. Do not assume every native render-tree input is remotely exposed;
  show how an attacker can cause the embedding app to supply it.
- Native memory safety matters even for a trusted caller: inputs derived from
  external data must not cause corruption of the process or the embedded VM.
  Prioritize length/integer validation, JSON/term decoding, callback ownership,
  stale handles, asynchronous lifetimes, JNI/FFI contracts and thread safety.
- Development distribution intentionally grants full BEAM/RPC authority after
  cookie authentication. Investigate listener exposure, private-cookie handling,
  unintended/public-cookie fallbacks and release-versus-development startup.
  Android and simulator loopback binding is not authentication: another local
  process/app may connect. Physical iOS development connectivity can use a
  reachable network interface. Do not assume this protocol supplies TLS unless
  the app actually configures it.
- Persistent files, screen state and crash/diagnostic outputs may contain
  application data. Investigate path handling, accidental disclosure and resource
  exhaustion with realistic input sizes and attacker reachability.

Useful context: `guides/architecture.md`, `guides/events.md`,
`guides/device_capabilities.md`, `MOB_PLUGIN_SECURITY.md`, and decisions about
private distribution cookies, startup arguments and deep-link delivery. Some
security-document sections are explicitly planned rather than implemented.

## Build and offline exercises

The image contains Elixir 1.19.5 / OTP 28.0.4 and compiled dev/test environments.
The checkout is `/src`; Hex dependencies and registry data are retained locally.
No credentials, live phones or maintainer home-directory data are supplied.

The image build runs `test/mob/dist_test.exs` while Docker provides a non-loopback
interface. The scanner's offline runtime has only loopback, so run every other
host test there with:

```
find test -name '*_test.exs' ! -path 'test/mob/dist_test.exs' -print0 |
  xargs -0 mix test
```

The existing test helper excludes `:onboarding` and `:on_device`, and excludes
`:zig` when Zig is absent. This image has no Zig toolchain. These execution
limits do not exclude any source from the audit.

Three portable native harnesses compile actual iOS headers and can be rerun:

```
make -C test/native CC=clang dist_port_test dist_cookie_test init_args_test
./test/native/dist_port_test
./test/native/dist_cookie_test
./test/native/init_args_test
```

For sanitizer reproducers, clang is installed; rebuild relevant harnesses with
`-g -fno-omit-frame-pointer -fsanitize=address,undefined` where supported.
`test/native/frame_registry_test.m` requires Apple Foundation and
`stored_queue_test.c` requires Apple's `os_unfair_lock`. Full iOS/Android native
builds require platform SDKs/runtime artifacts and devices not present in this
Linux image. Those source paths remain important review targets; state whether a
finding was exercised on a portable harness or only source-analyzed.

## Findings and severity

Provide a minimal self-contained reproducer, affected public revision, input
provenance, violated invariant, deployment/configuration prerequisites and a
minimal candidate patch. Distinguish a real boundary violation from intended
trusted app/plugin execution. Deduplicate by root cause across native platforms.

Unauthenticated remotely reachable execution or broad sensitive-data compromise
can warrant critical severity. Authentication bypass, reachable memory corruption
or substantial cross-boundary data disclosure can warrant high severity; identify
what a memory-safety reproducer actually proves, not a speculative exploit chain.
Bounded crashes and developer-only/local attacks should be rated by demonstrated
impact and prerequisites, not automatically as remote critical issues. Report
security defects privately to the configured contact, not as public GitHub issues.
