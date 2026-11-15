# jid security review

## Purpose and trust boundaries

jid is a local interactive JSON exploration tool written in Go. Users may pipe
responses from remote services or open JSON files from untrusted sources. It is
not a network server and does not itself fetch URLs.

Treat JSON bytes, keys, values, nesting, sizes, and encodings as attacker-controlled.
Review JSON parsing, dot-path and JMESPath evaluation, completion, and terminal
rendering. Queries normally come from the local user, but users may paste queries
from elsewhere; distinguish this from automatic processing of hostile JSON.
Review history persistence and configuration loading with explicit filesystem
and local-user assumptions. User-owned configuration is normally trusted.

## Environment and exercising the project

Source is in `/src`; the built command is `/usr/local/bin/jid`. Go and all module
sources remain available in the image. Run `go test -count=1 ./...` in `/src`.
The CLI requires a TTY for interactive operation. `jid -help` works without one.
Tests in the repository cover parsing, queries, completion, rendering, history,
and configuration. Additional regression tests and Go fuzz targets can run offline.

## Impact and reporting

Prioritize attacker-controlled input causing unintended command execution,
arbitrary file access or writes, meaningful terminal-control injection, or
disclosure of local data. Explain any terminal emulator behavior required.
For resource exhaustion, give payload sizes, runtime and memory measurements;
classify a local CLI crash separately from a remotely reachable service outage.
Do not assume an attacker can modify the victim's trusted configuration or code
without explaining an additional trust boundary crossed by the finding.

Provide a minimal reproducer, affected source locations, realistic prerequisites,
and a focused patch with a regression test when possible. Treat severity guidance
here as review priorities rather than an automatic severity assignment. Deduplicate
findings by root cause. Documentation-site issues and unrelated dependency flaws
without a reachable path through jid are lower priority.
