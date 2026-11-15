# How we would like reports written

Use a short title naming the component and failed security property. Keep one
report per root cause and list every affected entry point confirmed by the
evidence. Use these sections in order.

1. **Summary and impact.** Describe what fails, who can reach the affected
   API, and the consequence for a caller. Identify any required configuration
   or downstream behavior.
2. **Affected surface.** Give the tested commit or release, package, public
   entry point, runtime, and feature or policy settings. Distinguish confirmed
   affected versions from inferred ones.
3. **Evidence and root cause.** Identify the relevant source and contract.
   Give expected and observed behavior, including typed errors or output bytes
   where relevant. Use the smallest public vector or synthetic fixture that
   demonstrates the behavior. Redact raw customer data, personal information,
   and secret-bearing values.
4. **Suggested fix.** State which invariant should be restored and how a
   regression test would verify it. Include a workaround or fixed version
   when verified.

Use plain language and separate verified observations from assumptions. When
behavior differs across runtimes, state which ones were tested and which
remain unverified.
