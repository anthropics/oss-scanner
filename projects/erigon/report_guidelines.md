# How we would like reports written

## Layout and length
- Plain Markdown, about one page, with these sections in this order: Summary, Impact, Affected
  code and versions, Reproduction, Root cause, Suggested fix.
- Summary: two or three sentences a maintainer can triage from without reading further.
- Title: start with the Erigon package path, then the defect, for example
  `p2p/discover: unbounded allocation when decoding a findnode response`.

## What every report should state
- The attacker position: remote devp2p peer, libp2p/gossip peer, block proposer or transaction
  sender, BitTorrent peer, public RPC client, Engine API caller, or the beacon endpoint used by
  `capcli`.
- The chain and fork the issue applies to (for example mainnet from Prague), and the flags or
  configuration it needs, saying whether they are defaults.
- The concrete effect on a node: crash, halt, consensus divergence, resource exhaustion, key
  exposure, or other. Give measured numbers (memory, CPU time, message count) where relevant.
- The scanned commit, and the entry point an attacker reaches: the wire message, RPC method, gossip
  topic, or file type.
- Whether the same code exists in go-ethereum or another Ethereum client, with the corresponding
  file if known, because the fix may need coordinated disclosure.

## Reproduction
- Prefer a self-contained Go test in the affected package that fails on the scanned commit, with the
  exact `go test` command to run it.
- If the issue needs a running node, give the exact `erigon` command line and the input to send. Do
  not assume a synced chain or downloaded snapshots unless the issue requires them; say so if it does.

## Style
- One root cause per report.
- Quote only the code lines that matter, with file paths relative to the repository root.
- Factual tone. Separate what was observed from what is inferred.
