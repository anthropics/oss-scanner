# How we would like reports written

## Layout and length
- Under one page, with these sections in this order: Summary, Attacker position, Affected code, Reproduction, Impact, Suggested fix.

## What every report should state
- The attacker's starting position: unauthenticated network peer, holder of a specific Talos role (e.g. `os:reader`), a Kubernetes pod (privileged or not), a malicious disk, or a malicious node talking to `talosctl`.
- The entry point: the gRPC service and method, the controller and resource, or the input parser that reaches the faulty code.
- The machine config needed to trigger it, if any (as a minimal patch).
- The commit the reproduction was run against. We support the two latest minor releases, so say whether the code is present in them if you can tell.

## Style
- Plain text and code blocks, no tables.
- One root cause per report.
- Start the title with the component: e.g. `apid: ...`, `trustd: ...`, `talosctl: ...`, `machined/network: ...`.
