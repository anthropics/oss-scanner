# How we would like reports written

## Layout and length

Under one page. These sections, in this order:

1. Summary — one paragraph: what is wrong and what an attacker gains.
2. Severity — one line, with the rating and the invariant it breaks (e.g. "high,
   SI-01 approval authority").
3. Affected code — the file and function, with the commit or release you tested.
4. Reproduction — the exact steps, commands or inputs. A test or a short script we
   can paste and run is better than prose.
5. Suggested fix — the smallest change that closes it, if you have one.

## What every report should state

- The **preconditions**: what the attacker already controls, and whether the
  operator or the agent is the adversary. HUQAN's threat model distinguishes the
  two, and a finding that assumes the operator is malicious is usually out of scope.
- Whether the finding reaches a **gate decision**. A defect that stays inside the
  scoring or storage layer is rated differently from one that lets a protected
  action run. Say which, explicitly.
- Whether the path is reachable **from an untrusted entry point** (an agent tool
  call, an MCP call, an HTTP request, ingested content) or only from the operator's
  own code. Name the entry point.
- The **version**: `package.json` version, or the commit SHA, and whether it is the
  published npm release or `main`.

## Style

- Plain text or Markdown. No tables of severity matrices.
- One root cause per report. If two bugs share a fix, say so; if they do not, send
  two reports.
- Start the title with the component's name, then the defect:
  `action-risk-classifier: policy override downgrades critical to allow`.
- Quote the code you are pointing at, with the file path and line. Do not paste a
  whole file.
- Do not include a proof-of-concept that runs destructive commands on a real host.
  A reproduction that stays inside a temporary directory, or a test file, is enough.
- If you believe the behaviour is intended, say so and skip the report — the
  accepted properties are listed in `THREAT_MODEL.md` and in our threat model for
  the scanner, and we would rather not spend a review cycle on them.
