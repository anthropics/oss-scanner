# Report format

Use plain Markdown and aim for a page of prose. Start the title with the crate
or adapter and name the security consequence. Include the scanner report ID
when available. Use one report per root cause and group entry points that share
that cause.

Use these sections in order.

1. **Summary and impact.** Name the failed security property and who or what
   could be affected. Give the proposed severity and a short rationale using
   `threat_model.md`.
2. **Affected versions and configuration.** Record the tested commit or release,
   affected package, public entry point, runtime lane, Cargo features, and
   provider. State the required caller privileges, control over inputs, and
   deployment prerequisites. Separate confirmed affected versions from any
   inferred range.
3. **Evidence and root cause.** Cite the relevant source location and standard
   or project contract. Record the expected and observed behavior. Say which
   checks ran and what remains uncertain. Use public vectors or synthetic
   fixtures for test evidence. Redact customer data and secret-bearing values.
4. **Suggested fix.** Identify the change that restores the security property
   and the regression check that would verify it. Include a fixed version or
   workaround when verified.
