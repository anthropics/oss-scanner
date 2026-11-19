# LDK

LDK is a Lightning Network implementation shipped as a Rust library, not as a node. The application that embeds it provides networking (or uses `lightning-net-tokio`), persistence, blockchain data, fee estimates, transaction broadcast and keys through traits, and calls into LDK; LDK never spawns threads or acts on its own.

## High-Level Security Model

Lightning is an online hot wallet with access to Bitcoin accepting and routing payments from and to untrusted third parties that must remain online regularly to ensure it can enforce state changes on-chain. This makes its security both critically important and very challenging. Many past critical vulnerabilities have been cases where a malicious counterparty can cause a node to forward a payment, provide the downstream node the funds through the claim path, but fail to claim the upstream funds itself. Denial-of-service issues which can trigger outages which cannot be recovered from easily can also lead to similar funds-loss and may also be critical, though when human intervention is possible may only be high severity.

LDK makes this threat environment even more challenging - LDK has a large API surface and many APIs, most of which are security-critical. If an API exposes a feature with incomplete documentation that leads a downstream application to integrate LDK in an unsafe way it may lead to funds-loss as well! Edge-cases in the payment logic which are not clearly documented or which are easy to misuse may be medium- to high-severity issues.

LDK currently has rather complicated persistence restart infrastructure which may lead to loss - payments must be durably complete when the API to downstream logic says they are and must be claimed when the downstream code thinks they will be.

## Generally Non-Issues

The application driving LDK *is* the wallet, and is thus trusted to behave correctly according to the LDK API documentation. If the API documentation is unclear or hard to use correctly its potentially a vulnerability, but the downstream application simply misusing an obvious interface is not a vulnerability in LDK.

While LDK generally attempts to ensure it can properly detect and fail to load in the face of corrupted on-disk state, the state storage is fully trusted - if the state storage were malicious it could simply remove all our state and the node would certainly lose funds.

Similarly with the blockchain data source - a malicious chain source could simply stop providing us with new blockchain data and we would be vulnerable to funds-theft. We assume that the blockchain data source is online at least regularly enough that we can do on-chain enforcement when required and honestly provides us with the latest state of the blockchain.

While debug-build failures and panics are a concern and considered bugs, we do not generally consider them security issues. Similar for any features hidden behind an explicit non-feature `cfg` flag.

While lightning protocol-level issues are concerning, well known issues don't need to be reported. This includes issues such as channel jamming (HTLC slot and liquidity griefing), a counterparty holding HTLCs until they expire, probing and balance discovery, transaction pinning and replacement cycling, the fee exposure of non-anchor channels, a counterparty force-closing or refusing to cooperate on its own channel with us, and timing or fingerprinting attacks on privacy. They count only where LDK departs from the BOLTs or from a mitigation it documents.

See `REVIEWERS.md` in the `rust-lightning` repo for more information on specific things which are out of scope.
