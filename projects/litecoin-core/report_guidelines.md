# How we would like reports written

Litecoin Core has a small maintainer team, so a report should let one person decide quickly whether it is real,
how bad it is, and whether it is already fixed.

## Layout and length

- Title: `<component>: <what goes wrong>`, using the component prefixes from our commit history (`mweb`, `libmw`,
  `validation`, `net`, `mempool`, `policy`, `mining`, `wallet`, `rpc`, `secp256k1-zkp`, ...). For example:
  `mweb: block with duplicate pegin kernel passes HogEx input check`.
- Sections, in this order:
  1. Summary: two or three sentences. What is wrong, who can trigger it, and what happens.
  2. Severity: the rating and a one-line reason, using the scale in the threat model.
  3. Attacker requirements: connection direction and number of peers, whether a mined block (and its proof of work)
     or fee-paying transactions are needed, whether MWEB must be active, and any non-default options.
  4. Affected code: the scanned revision, `file:line` and function names, and, if you checked, the commit or release
     that introduced the bug and whether the same code is on the `24.x` branch.
  5. Root cause: why the code is wrong, with concrete values where possible.
  6. Reproduction: the exact commands, the full test file if you wrote one, the observed output, the expected output,
     and which build you used (`/src/build` or `/src/build_asan`).
  7. Duplicate check: what you looked at (`git log`, the release notes in `doc/litecoin-release-notes/`, existing
     tests) and the result. If the issue matches a publicly disclosed Bitcoin Core advisory, name it and the upstream
     fix.
  8. Suggested fix: a short description; the patch itself goes with the report.
- Aim for at most two pages, not counting the reproducer and the patch.

## What every report should state

- Clearly, near the top, whether the finding was reproduced against the build in the image or reasoned from the
  source only. Keep what you observed separate from what you inferred.
- Amounts in litoshis, with the LTC value in brackets where it helps. Block heights for consensus rules and
  activation points.
- For anything touching consensus: whether a fix would tighten the rules (a soft fork), loosen them (a hard fork), or
  only change policy.

## Style

- Plain, factual and specific. No marketing language and no speculation presented as fact.
- One root cause per report. If the same root cause shows up at several call sites, list them all in one report.
- Code, log lines and test output in fenced code blocks; keep logs to the lines that matter.
