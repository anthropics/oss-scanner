# Threat model

## What this project does and where untrusted input enters

ADE is an open source development environment for coding agents. It runs on a
user's machine and can connect to other machines. It reads Git repositories,
starts shells and agent processes, and handles account, provider, and GitHub
credentials.

Treat repository files and Git metadata, agent and provider output, browser
content, remote runtime messages, sync and relay payloads, and OAuth callback
data as untrusted. Important boundaries include renderer-to-main IPC, brain RPC
authorization, account and device pairing, project and lane filesystem access,
credential storage, and remote process control.

## Components that matter most and least

Prioritize authentication and authorization, credential handling, path and
process boundaries, IPC and RPC handlers, account and device pairing, sync and
relay routing, and browser or renderer handling of untrusted content.

Users intentionally run commands and coding agents against repositories they
choose. Do not report that behavior by itself as a vulnerability. A prompt
injection or malicious repository is in scope when it crosses an ADE-enforced
boundary, such as accessing another project, exposing credentials, or causing
an action outside the user's granted authority.

## How to exercise it

The repository has service, UI, and worker tests. Use the checked-in test
fixtures and local test commands. Do not depend on live accounts, provider
credentials, or production services. The scanner image builds the Linux
Node-based products; iOS and native Swift targets require macOS.

The `tools/check` shell starts as root. Run permission-sensitive desktop tests
as the unprivileged `node` user so tests that exercise filesystem permissions
and username redaction see normal user behavior. On Linux, skip
`apps/desktop/src/main/services/ios/iosSimulatorService.test.ts`: it launches
the macOS Simulator with `open -a Simulator`, which is unavailable in this
image. Treat those spawn errors as an unsupported test environment, not an ADE
runtime result. The CLI login-shell test fixture also delegates to `/bin/sh`
with Bash-only login flags on Debian; validate the actual shell behavior before
attributing that fixture failure to ADE.

The CTO memory suite has order-sensitive failures in the Linux run. Keep those
results visible, and confirm any security finding with a reproducer that shows
a project, lane, account, or credential boundary being crossed.

The sync address test assumes the device has a reachable LAN address. The
network-isolated scanner container can refresh the saved host to its container
hostname while the pairing builder prefers seeded LAN candidates. Do not treat
that fixture mismatch as a finding without reproducing it on a supported host
network.

## How you rate severity

- Critical: a reproducible unauthenticated remote compromise, machine takeover,
  or broad exposure of user code or credentials.
- High: an authorization bypass, credential disclosure, or arbitrary code or
  file access across a project or machine boundary with a practical attack path.
- Medium: a meaningful denial of service or a security impact that requires
  substantial user interaction or an already trusted local account.
- Low: a defense-in-depth issue without a demonstrated security impact.

Base severity on a working reproducer and the boundary it crosses. Do not rate
an issue highly based only on theoretical impact.

## Anything to leave alone

Do not report expected limits of third-party agent models or providers unless
they cause ADE code to violate an enforced security boundary. Do not use real
credentials, contact live services, or run tests that modify a user's home
directory.
