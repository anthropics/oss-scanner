# Threat model: Ekubo Wallet (desktop)

The repository keeps a detailed threat model in `docs/threat-model.md`, the code-oriented
boundary in `docs/security-boundary.md`, and the local agent IPC model in
`docs/mcp-security-model.md`. Read those first. This file adds the scanner-specific
priorities and severity scale.

## What this project does and where untrusted input enters
This is a GPUI desktop wallet for EVM accounts. A single tray process owns the encrypted
state (SQLCipher) and private keys. Untrusted input arrives from:
- local AI agents over the stdio MCP bridge (`crates/mcp-bridge`) and its local IPC
  connection to the wallet. Treat agent requests as attacker-controlled, including
  prompt-injected agents;
- WalletConnect dapps and session messages (`crates/walletconnect-session`);
- RPC responses, token metadata, ABI and calldata decoding, and transaction previews
  (`crates/ekubo-wallet-preview*`, `crates/erc8410*`);
- policy documents, scheduled automations and update/release metadata.

## Components that matter most
1. Signing authorization: any path that signs or broadcasts a transaction or message
   without the policy allowing it, or without the owner's native review when policy says
   `review`. This includes policy matcher bypass and confusion between what is previewed
   and what is signed.
2. Key and state custody in `crates/ekubo-wallet-core`: key derivation and storage,
   SQLCipher key handling, recovery phrase handling, and memory exposure.
3. MCP and IPC boundary: peer authentication, connection hijacking, and request
   smuggling between agents or sessions.
4. WalletConnect: origin and session confusion, and chain or account spoofing.
5. Transaction previews: a decoder or preview that misrepresents recipient, amount,
   approval or spender.
6. Updater and release verification.

## Out of scope and known limitations
- The documented Windows/Linux credential-store limitation: same-user malware can read
  keys from the OS credential service. Report only new ways around it, not the limitation
  itself.
- Attacks that assume full control of the user's OS account, beyond what is described
  above.
- `examples/`, `contrib/`, `tests/` fixtures and `docs/`.

## How we rate severity
- Critical: signing or sending without authorization, key or recovery-phrase disclosure
  to a remote party or another local process outside the documented limitation, or
  remote code execution.
- High: a policy or review bypass with preconditions; a preview that misstates the
  recipient, amount or approval of a signed transaction; cross-session or cross-agent
  impersonation.
- Medium: denial of service of the wallet process; leaks of local metadata such as
  addresses, balances or history.
- Low: UI inconsistencies without signing impact.

## How to exercise it
Run `cargo test --locked --workspace --all-features --lib --offline`. Put reproducers in
unit tests inside the affected crate.
