# How we would like reports written

## Layout and length
- Keep each report to one or two pages.
- Use these sections, in this order: Summary, Severity and confidence, Attacker position, Affected code, Data flow,
  Reproduction, Impact, Suggested fix.
- Summary: two or three sentences that say what an attacker can do and through which entry point.
- Data flow: a numbered list from the source (the request field, event property, queue payload, file or tool output)
  to the sink (the query, response, outbound request, file write or tool call). Give `path/to/file:line` for each
  step and name the missing control.

## What every report should state
- The commit of `master` that the finding applies to.
- The attacker's starting position: anonymous, a new account in another organization, a member with a given
  organization level or access-control role, or a credential with given scopes (personal API key, project secret
  API key, OAuth token, sharing token).
- The entry point: the HTTP method and route, the capture or flags endpoint, the Hog function or HogQL query, the
  Temporal workflow, the Kafka topic, or the agent or MCP tool.
- The deployment it applies to: PostHog Cloud, self-hosted, or both. Name each setting, feature flag or plan
  feature that the path needs.
- A reproduction that a maintainer can run as is. Prefer a pytest, Jest or cargo test that uses the existing test
  bases and fixtures. Otherwise give exact HTTP requests with the expected result and the observed result.
- If the reproduction ran in the scanner environment, include its output. If it did not run, say that the finding
  comes from reading the source.
- A confidence from 1 to 5. Use 5 when you traced the path end to end and ran it. Use 3 when reachability or impact
  depends on a fact that the repository does not show. Do not send a report below 3.
- For a tenant-isolation finding, name the two projects or organizations in the reproduction and show which one owns
  each object.

## Style
- One root cause per report. List every affected route, action and service in that report.
- Start the title with the area in brackets, for example `[hogql] ...`, `[data-warehouse] ...`, `[capture] ...`.
- Use plain, factual language for a security-literate reader. Do not explain common vulnerability classes.
- Say clearly when the impact is inferred and not demonstrated.
- Put code, requests and stack traces in code blocks. Trim stack traces to the frames inside this repository.
- Use invented identifiers, `example.com` hosts and obviously fake tokens in every example.
