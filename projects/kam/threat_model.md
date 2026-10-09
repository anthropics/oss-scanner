# Kam threat model

## Project and trust boundaries
Kam scaffolds, builds, signs, and packages Android root modules and exposes template and archive processing.

Treat module manifests, templates, archives, repository metadata, build configuration, and paths as untrusted. Focus on the first-party source and on the boundaries between those inputs and authenticated operations, persistent state, the filesystem, subprocesses, and outbound network requests, where applicable.

Review the template engine under `src/template_engine/`, the module commands under `src/cmds/`, and the path/archive helpers under `src/utils_support/`. A template or archive should not write outside its selected output directory unless an explicit trusted build step authorizes it. Treat upstream repository metadata as data rather than shell syntax.

Signing keys, registry credentials, and the developer's files are sensitive assets. Use disposable test keys and local archive fixtures. Report a demonstrated path from untrusted module content to disclosure or unexpected execution; ordinary execution of a build hook explicitly selected by the developer is an intended feature.

## Build and offline testing
The Dockerfile keeps the repository and development dependencies in the image at `/src`. It does not need production credentials or access to a running deployment. Run from `/src` after network access is disabled:

```sh
set -e
cargo test --locked --offline --workspace
```

Package and test fixtures use disposable directories. Intentional execution of explicitly trusted build hooks is an expected capability; untrusted metadata escaping that authorization is in scope.

Use synthetic credentials, temporary data directories, and local test fixtures. Loopback services inside the container are suitable for reproductions; do not contact production services or third-party accounts. Tests that require real hardware, external accounts, or live upstream services are separate from the offline regression suite.

## Severity and reports
Prioritize authentication or authorization bypass, exposure of secrets, path traversal across an intended boundary, command execution through data input, unsafe archive extraction, and persistent integrity violations where the code implements those features. Assess impact against the documented deployment and attacker prerequisites. An intended, explicitly authorized administrator or plugin capability is not itself a vulnerability; crossing its boundary can be.

Remote unauthenticated code execution, or a demonstrated compromise of privileged control, can be critical. Demonstrated account compromise, sensitive data disclosure, or cross-user state modification is generally high. A reliably reproducible resource-exhaustion issue is generally medium unless a concrete wider impact is established. Do not inflate severity for a hypothetical deployment or for a maintainer intentionally executing trusted code.

Provide the affected commit and source locations, the attacker's prerequisites, a minimal offline reproducer, expected and actual behavior, and a focused patch with regression coverage if possible. Deduplicate findings with the same root cause. Dependency-only issues should identify a first-party reachable path rather than repeat a version advisory. Reports should go privately to the configured contact.
