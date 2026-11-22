# How we would like reports written

## Layout and length
- Under one page, with these sections in this order: Summary, Preconditions, Reproduction, Impact,
  Suggested fix.
- One root cause per report. If one parser bug has several call paths, list them in the same report.

## What every report should state
- The affected module and function, with file and line numbers at the scanned commit, and that commit's hash.
- Preconditions exactly: transport (UDP, TCP, TLS, WS, WSS), whether it needs an established dialog or a
  prior message exchange, and any non-default build or runtime option.
- What happens on well-formed traffic (usually nothing) separately from what the crafted input does.
- The exact bytes of the triggering message or DNS response (as a C string or hex dump), and the
  command that reproduces it against a program in the image, with the sanitizer output.
- Whether FreeSWITCH reaches the code path through `mod_sofia` in a default configuration, if known.

## Style
- Plain text and short code blocks; no Markdown tables.
- Title in the form "module: what goes wrong", for example "sip: Via parser reads past the header end".
- State facts; leave out speculation about exploitability beyond what the reproduction shows.
