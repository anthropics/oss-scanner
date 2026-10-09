# OniMods threat model

## Project and trust boundaries
OniMods includes an ONI mod-development CLI and the OniMcp HTTP/MCP server, protocol parsing, game-operation admission, and local mod tooling.

Treat HTTP headers/bodies, MCP messages, session identifiers, tool/resource arguments, mod manifests, filesystem paths, and publishing parameters as untrusted. Focus on the first-party source and on the boundaries between those inputs and authenticated operations, persistent state, the filesystem, subprocesses, and outbound network requests, where applicable.

Review `mods/OniMcp/Server/` for HTTP admission, authentication, session lifetime, and protocol-version handling; `mods/OniMcp/Core/` and `Tools/` for dispatch and game-operation permissions; and `Config/` for token handling. An unauthenticated or expired session must not obtain access to operations reserved for a valid session. Malformed protocol messages should not bypass admission or exhaust persistent server state.

Game save state, authentication tokens, and the developer's files are sensitive assets. Local publishing tools and mod metadata are separate filesystem/process boundaries. Reproduce these with stubs and temporary directories; do not upload a mod or require a live Steam account to establish a finding.

## Build and offline testing
The Dockerfile keeps the repository and development dependencies in the image at `/src`. It does not need production credentials or access to a running deployment. Run from `/src` after network access is disabled:

```sh
set -e
cargo test --locked --offline
for project in tests/*/*.csproj; do dotnet run --no-build --no-restore --project "$project"; done
```

The .NET test harnesses compile first-party code against repository-provided game stubs, not proprietary ONI binaries. This does not validate a running game, Steam Workshop publishing, or the complete mod assemblies against commercial game assets. Do not start Steam or upload content from a reproducer.

Use synthetic credentials, temporary data directories, and local test fixtures. Loopback services inside the container are suitable for reproductions; do not contact production services or third-party accounts. Tests that require real hardware, external accounts, or live upstream services are separate from the offline regression suite.

## Severity and reports
Prioritize authentication or authorization bypass, exposure of secrets, path traversal across an intended boundary, command execution through data input, unsafe archive extraction, and persistent integrity violations where the code implements those features. Assess impact against the documented deployment and attacker prerequisites. An intended, explicitly authorized administrator or plugin capability is not itself a vulnerability; crossing its boundary can be.

Remote unauthenticated code execution, or a demonstrated compromise of privileged control, can be critical. Demonstrated account compromise, sensitive data disclosure, or cross-user state modification is generally high. A reliably reproducible resource-exhaustion issue is generally medium unless a concrete wider impact is established. Do not inflate severity for a hypothetical deployment or for a maintainer intentionally executing trusted code.

Provide the affected commit and source locations, the attacker's prerequisites, a minimal offline reproducer, expected and actual behavior, and a focused patch with regression coverage if possible. Deduplicate findings with the same root cause. Dependency-only issues should identify a first-party reachable path rather than repeat a version advisory. Reports should go privately to the configured contact.
