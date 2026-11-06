# Whiteboard threat model

Whiteboard is an open-source desktop canvas for software design and code review,
built on a maintained Code - OSS fork. It combines a React canvas, local HTTP
services, CLI/MCP access, Git diffs, imported reviews and traces, and SSH remote
hosts. The product still uses `review` in many package names and paths.

## Scope and trust boundaries

Prioritize Whiteboard-owned code in `packages/review`, `packages/review-protocol`,
`packages/review-share-protocol`, `packages/trace-*`, and
`apps/review-desktop/code-oss/src/vs/review`, including integration with the
workbench, Electron main process, and remote server.

Treat repository contents, filenames, Git metadata, diffs, imported reviews,
markdown, diagrams, trace payloads, shared content, and remote-host responses as
potentially hostile. Follow those inputs through rendering, file access,
archive extraction, subprocess invocation, bridge calls, and persistence.

Examine local API authentication and origin handling, renderer-to-host
capabilities, deep links, SSH argument handling, remote installation and
artifact verification, path confinement, and leakage of credentials or private
source. A hostile website or another local user must not gain the owner's API
or host privileges. Treat a remote workspace as a separate trust domain when
assessing whether its data or responses can execute commands on the local host.

The owner can deliberately run commands, start agents, install extensions, and
connect to SSH hosts. Show how attacker-controlled input crosses an additional
boundary; the owner's explicitly authorized execution alone is not a finding.
Distinguish a malicious repository from a malicious extension already granted
host execution rights. Do not assume opening a workspace authorizes every
command encoded in its content.

Unmodified third-party Code - OSS, Electron, and dependencies are not the primary
target. Report Whiteboard-specific integration flaws with reachable impact;
identify upstream-origin issues separately rather than attributing them to
Whiteboard. Cloud deployments and third-party services are outside this image.

## Build and local exercise

The checkout is at `/src`. The Dockerfile installs workspace and native Code - OSS
dependencies, builds Desktop and the canvas, and downloads Chromium before the
scanner removes network access. No account credentials or release signing keys
are required. The image is a development build, not a signed release package.

From `/src`:

- `pnpm --filter @dev.fast/whiteboard test` exercises the local service and CLI.
- `pnpm --filter @dev.fast/review-desktop test` exercises Desktop scripts and
  Whiteboard host/remote code; its pretest generates the protocol copy.
- `pnpm --filter @dev.fast/review-canvas test:node` runs canvas Node tests.
- `pnpm --filter @dev.fast/review-canvas test:browser` runs Chromium canvas tests.
Desktop UI exercise also needs a virtual display (Xvfb) and a non-root user
or container-specific Electron sandbox setup. The headless service and host
tests above do not require an interactive Desktop session.

Keep all reproductions local with disposable workspaces, test identities, and
fake credentials. Do not contact production services or third-party accounts.
Tests that require an external service are not evidence of an offline failure
in the product. Browser-only tests do not prove Desktop host integration.

## Report expectations

Include the source revision, affected code paths, attacker-controlled input,
required interaction and privileges, violated boundary, minimal local
reproducer, observed impact, and a narrowly scoped patch when possible.
Separate demonstrated impact from hypotheses, and deduplicate reports that
share a root cause.

Severity should reflect reachability and impact. Untrusted content or an
unauthenticated client gaining host command execution or broad access to
private source or credentials is high or critical depending on preconditions.
A reliable authentication bypass or arbitrary file write across a real trust
boundary is high. A bounded denial of service is generally medium; self-impact
from an intentionally authorized command is not a security boundary violation.
Missing hardening, dependency version matches, and theoretical paths without a
reachable exploit should not be presented as confirmed vulnerabilities.

Deliver findings privately to the enrollment contact. The repository's
`SECURITY.md` also directs vulnerability reports to private GitHub advisories.
