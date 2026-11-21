# Report format

One report per issue. Plain text or Markdown, under 1500 words, no attachments.

Use these sections, in this order:

1. Title: `<component>: <defect>`, for example `parser: OSC payload not bounded`.
2. Severity: critical, high, medium or low, with the sentence from threat_model.md that decides it.
3. Location: the file and line at the scanned commit (for example
   `crates/gpty-core/src/parser.rs:412`), plus the crate.
4. Trust boundary: which boundary from threat_model.md the defect crosses, and who controls the
   input.
5. Reproducer: exact commands against the image, the input bytes (hex or a file under /tmp), and
   the observed result. A report without a reproducer or a precise code path is not a finding.
6. Observed vs expected: what happened, and what should have happened.
7. Impact: what an attacker gains, and what they must already control.
8. Proposed patch: the smallest fix, or "no patch proposed".

Rules:

- Say when a behaviour was inferred from reading code rather than executed.
- Separate confirmed facts from hypotheses. Do not pad a report with impacts the reproducer does not
  show.
- One issue per report. Related issues may reference each other by title.
- Do not report dependency advisories (`cargo audit` and `cargo deny` cover them) unless gPTY's own
  code makes the advisory reachable; then report that code path.
- Do not include secrets, tokens or personal data in a report.
