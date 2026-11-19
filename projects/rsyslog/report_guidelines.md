# How we would like reports written

## Layout and length
- One root cause per report. If the same root cause is reachable from several
  modules, list all of them in one report.
- Sections in this order: Summary, Affected component, Preconditions,
  Reproduction, Impact, Suggested fix.
- Keep it short: about one page plus the reproducer.

## What every report should state
- The affected module or core file, and whether that module is loaded by
  default, commonly configured, or optional/contrib.
- The minimal rsyslog configuration that reaches the code, and which settings
  differ from upstream defaults (for example a larger maxMessageSize).
- Who controls the input: remote unauthenticated peer, authenticated TLS peer,
  local user, file writer, downstream service, or administrator.
- The exact sink (file and function), the missing or insufficient guard, and
  the demonstrated impact.
- A reproducer that runs against the in-tree build: the configuration, the
  input bytes (hex or a small script, for example using tests/tcpflood), the
  command line, and the sanitizer output or other observed result.
- The rsyslog git commit that was tested.

## Style
- Plain text or simple Markdown. Start the title with the module name, for
  example "imtcp: ...".
- Use wording that matches the proof. If a step is not demonstrated, say so
  instead of assuming it. Do not use "RCE" or "arbitrary code execution"
  unless it has been shown.
