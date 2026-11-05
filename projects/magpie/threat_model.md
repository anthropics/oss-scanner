# Apache Magpie threat model summary

This summarises the authoritative model at <https://github.com/apache/magpie/blob/main/docs/security/threat-model.md>.
Read it before reporting. Its §1.12 and §1.15 list what is not a vulnerability; the essentials are repeated below because this audit runs offline.
Where this summary and the model differ, the model wins.

## What Magpie does and where untrusted input enters

Magpie is a framework of agent skills and tool adapters that maintainers run on their own workstation, inside an agent harness, to handle project work: security reports, PR triage and review, releases, contributor growth, repository health.
It is not a service. It has no server and no listening port in its default install (§1.2).
Skills are prompts the harness loads; tools are Python, shell and Groovy programs under `tools/`, run by the agent or by a hook.

Untrusted input enters as (§1.7):

- mail bodies, headers and attachments;
- issue and PR titles, bodies, comments, diffs and attachments on forges and trackers, even on a private tracker;
- scanner reports and proofs of concept;
- fetched web pages;
- the output of other models;
- any repository the operator opens but has not adopted;
- command text, file contents and paths the LLM produces, and files the sandbox lets it write, when read by anything outside the sandbox.

## Roles, most to least trusted (§1.2, §1.10)

- **Operator:** the maintainer running the harness. Owns the machine and approves every state change.
- **Committed project config and the operator's personal layer:** trusted, and steer what a skill does.
- **Upstream Magpie releases and pinned skill sources:** trusted once pinned and verified.
- **The LLM executing a skill:** semi-trusted. It follows instructions but can be steered by external content, and can err. An injected instruction and an honest mistake are treated the same.
- **Authors of external content (reporters, PR authors, mail senders, commenters):** untrusted.
- **A hostile repository the operator opens:** untrusted. It can commit any file, including paths Magpie treats as configuration.

## The defects we want found

Each is a boundary crossing the model claims to hold (§1.11).

- External content reaching a shell argument instead of a file (C-I1).
- A steered agent reaching code execution outside the sandbox through an enforcement component: `tools/agent-guard`, `tools/vetted-ops`, `tools/container-gateway`, `tools/egress-gateway`, `tools/setup-preflight`, `tools/hook-manager`, `tools/skill-lock` (C-E1, C-E3, C-E4, C-E6).
- A container reaching host namespaces, devices, capabilities, bind mounts outside the project root, or another project's containers through `tools/container-gateway` (C-E4).
- An agent-written or repository-written file loaded as code outside the sandbox (C-E6).
- An agent-controlled argument choosing where a credential is read from or written to (C-K4).
- A credential sent in clear or to another origin by an adapter that claims otherwise: `tools/gitlab`, `tools/bitbucket`, `tools/sourcehut`, `tools/jira`, `tools/discourse`, `tools/cve-tool-vulnogram`, `tools/asf-security-dash`, `tools/typed-decision` (C-K3).
- Credential files or secret environment variables readable by the agent under the secure setup (C-K2).
- Embargoed tracker content, unpublished CVE IDs or private-list content reaching a public surface or an unapproved model (C-C1, C-C2).
- A state change on a forge, tracker, mailbox or CVE record without operator confirmation (C-G1), or mail sent rather than drafted (C-G2).
- A CVE record published before its advisory is confirmed, or a tracker URL exported to CVE `references[]` (C-I4, C-C4).
- A moved tag or mismatched archive installed silently, or a source fetched that `skill-sources.md` does not list (C-D2, C-D3, C-D4).
- A non-collaborator's text used as tool state by `tools/github-rollup` or `tools/vetted-ops` (C-I3).
- A crafted marker crashing marker folding in `tools/pr-management` (C-I7).
- Reporter-supplied code run on the host (C-I2).

## What is not a vulnerability

- **The LLM not following a skill.** Skill wording is convention, not enforcement (D1).
- **`permissions.deny` Bash patterns being bypassed.** They are advisory; the network allowlist is the control. This does not cover the harness's own file-tool denies (D2).
- **An operator relaxing the sandbox locally** (D3).
- **agent-guard not being a sandbox.** It fails open on a guard error and inspects only `gh`/`git` commands, `uv`/`uvx` launches and sandbox-excluded script spellings (D4).
- **`--caller` scoping in vetted-ops as a boundary.** It is least privilege. This does not cover the policy file (D5).
- **container-gateway as a container-runtime boundary.** Container escape to the host, raw sockets, DNS and bind time-of-check are out. Project-label filtering between projects is claimed (D6).
- **egress-gateway payload inspection.** It filters by host, only for clients honouring proxy variables, and an allowlisted host can still carry data out (D7).
- **Targeted injection by an attacker who knows a secret is in the project tree, domain fronting through an allowlisted CDN, a malicious user-scope MCP server** (D8).
- **Adapter output not being taint-marked or sanitised**, beyond the redactor on private-list bodies (D9).
- **PII identifiers being linkable:** they are deterministic hashes by design (D11). The reporter's own identity is not redacted (D10).
- **Marketplace installs lacking signature or hash verification.** They track `main` over GitHub TLS; the signed source release is the verifiable artefact (D12).
- **A listed third-party skill source shipping a hostile body** (D13).
- **What an adversarial reviewer chooses to read in the tree it is given** (D14).
- **No rate limit on inbound mail or forge traffic** (D15), **no TLS pinning** (D16).

Also outside the model (§1.3, §1.10):

- the harness's sandbox implementation, the LLM provider's infrastructure, and physical access or a compromised OS account;
- denial of service against GitHub, archives, CVE services or model APIs;
- a malicious operator, an attacker already running as the operator outside the agent, a malicious harness or provider, or an attacker breaking TLS against a public CA;
- running state-changing skills with harness prompts disabled, except `tools/spec-loop` inside its own sandbox (§1.6);
- a command the operator approves to leave the sandbox, which is the operator's own act (C-E6);
- the `git-branch` install method, the mbox stub backend, and experimental modes (§1.3).

`tools/jira-patch` and `tools/mail-patch` are documentation only, so their pinning requirement (R-I6) is not a claimed property.
A finding against a component a claim does not name is not closed by that gap: it escalates as `MODEL-GAP` (§1.17).

## Severity guidance

Rate with the ASF severity rating: <https://security.apache.org/blog/severityrating>.
The model's tiers (§1.11):

- **critical:** credential theft, code execution outside the sandbox, embargoed content made public;
- **high:** an unapproved state change on a forge, tracker, mailbox or CVE record;
- **medium:** a guard or check silently skipped;
- **low:** hardening.

Most claims assume the secure agent setup (§1.6): say whether a finding needs it to be absent.
A finding that needs the operator to approve the action, or an unsupported configuration, rates lower or routes out of the model.

## How reports and patches should look

Name the claim the finding violates, the input the attacker controls, and the adversary it assumes (§1.1 quick-start).
Give a reproducer as a test where you can: each tool is a workspace member with tests under `tools/<name>/tests`, run with `uv run --directory tools/<name> pytest -q`, or all of them with `tools/dev/run-workspace-check.sh pytest "pytest -n auto"`.
Do not run pytest from the repository root: `plugins/*/tools/` holds generated copies of `tools/`, so a root run fails at collection.
Report against `tools/`, not the copies.
Patches keep to the tool they fix. External content reaches CLIs through files, never inline in a shell argument.

Derived from https://github.com/apache/magpie/blob/main/docs/security/threat-model.md at commit 47a9a328bfcc3fbe26fff1aab63600f750a9010f.
