# How we would like reports written

## Layout and length

Keep the main report concise. Put longer logs or measurements in a separate evidence section or attachment. Use these headings in order:

1. **Title**
2. **Affected version or commit**
3. **Severity**
4. **Short description**
5. **Attack scenario**
6. **Impact**
7. **Affected components**
8. **Verification evidence**
9. **Suggested fix** (optional)
10. **Additional information** (optional)

## What every report should state

- **Title and version.** Name the affected component. Give the tested release, tag, or commit SHA and any configuration relevant to the finding.
- **Severity.** State the assigned severity and give a brief rationale using the criteria in `threat_model.md`.
- **Short description.** Summarize the finding and its effect in one sentence.
- **Attack scenario.** Describe the relevant trust boundary and the access the submitter needs.
- **Impact.** State the expected behavior and the observed behavior. Quantify the observed effect where measurements are available. For builder availability findings, report whether blocks were produced and how many normal and adversarial transactions they contained, when known.
- **Affected components.** Identify the relevant files, functions, and line numbers. Explain the root cause if the evidence supports one.
- **Verification evidence.** Cite the existing test results, logs, or measurements that support the finding. Identify the tested configuration and distinguish observed results from assumptions.
- **Suggested fix.** Describe the proposed change and the behavior it should restore, when available.

## Style

Use short paragraphs and direct language. Keep the summary understandable without the logs. Label uncertain claims clearly.
