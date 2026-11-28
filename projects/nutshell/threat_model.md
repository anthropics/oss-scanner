# Nutshell threat model

## Project and scope

Nutshell is a Python implementation of the Cashu ecash protocol: a network-facing
mint, a wallet and CLI, and Lightning backend integrations. Protocol specifications
are maintained separately at https://github.com/cashubtc/nuts. Findings should
identify a defect in this repository, rather than only in another implementation
or a third-party dependency.

Review the mint API and ledger (`cashu/mint/`), wallet (`cashu/wallet/`), shared
models, cryptography and spending conditions (`cashu/core/`), and backend
integration logic (`cashu/lightning/`). Management interfaces, authentication,
database state transitions, and websocket subscriptions are also relevant.

## Trust boundaries and security goals

- Public mint HTTP and websocket clients may be malicious and unauthenticated.
  Treat request fields, proofs, blinded messages, quotes, and concurrent or
  replayed requests as adversarial.
- Wallets may receive malicious tokens, payment requests, and mint responses.
  Check parsing, cryptographic verification, spending conditions, and handling
  of secrets across these boundaries.
- A mint must not issue value without the required backing payment, redeem more
  than the available value, or permit proofs to be spent more than once.
  Transaction failures, retries, concurrency, and asynchronous payment updates
  must preserve these invariants.
- Protect mint signing keys and wallet seeds and secrets. Enforce signatures,
  DLEQ verification where required by the protocol, P2PK/HTLC conditions, and
  intended authentication and authorization boundaries.
- Mint operators necessarily control their mint and its reserves. The protocol
  does not make a dishonest mint solvent or prevent it from refusing service.
  Distinguish that trust assumption from wallet vulnerabilities exploitable by
  a malicious mint.
- Lightning backends are configured by the operator. Assess Nutshell's handling
  of payment results and failures, but do not assume an attacker already has
  administrative access, the mint seed, or backend credentials.

## Reproduction environment

The scanner image installs Python 3.12, Poetry, and runtime and development
dependencies. The checkout is at `/src`. Run:

```sh
poetry run pytest tests -q --ignore=tests/fuzz \
  --deselect=tests/mint/test_mint_operations.py::test_melt_preserves_change_signatures_order_integration
```

The default environment uses FakeWallet for sat and USD, SQLite, and disables
Tor. The test fixtures start a local mint and create disposable test databases.
Loopback connections are expected; Internet access and real funds are not needed
for this baseline. The deselected integration test calls `docker exec` to obtain
an invoice from an external LND regtest container, despite using FakeWallet; that
container is not available in the offline image. Randomized Hypothesis tests in
`tests/fuzz` are available separately with `poetry run pytest tests/fuzz -q`;
they are excluded from the baseline because the fuzz suite exhibited an
intermittent failure during enrollment verification. FakeWallet deliberately
simulates payments and is not a
production backend: behavior unique to its simulation is not itself a security
finding.

Live Lightning/Spark regtest, Tor, Redis, Keycloak, and PostgreSQL integration
environments are not provisioned by this image. Review the corresponding code,
but clearly distinguish mocked reproduction from validation against those
services. Do not contact public mints or use real credentials or funds.

## Severity and report guidance

Prioritize demonstrated unauthorized issuance or redemption, double spending,
loss of mint reserves or wallet funds, signing-key or seed disclosure, spending
condition bypass, and authentication or authorization bypass. Explain the
attacker's access, prerequisites, affected configuration, and financial or
availability impact; do not infer a critical impact from a suspicious code path
alone. Distinguish remotely triggerable denial of service from ordinary operator
misconfiguration or expected resource consumption.

Prefer a minimal, deterministic pytest regression test using FakeWallet and
temporary databases. For race conditions, describe the necessary interleaving
and demonstrate the violated invariant. Include affected code, reproduction
steps, expected and observed behavior, and a focused patch where possible.
Group manifestations of the same root cause and explain any remaining limitations
of a proposed fix. Keep vulnerability details in private reports to the project's
security contact until disclosure is coordinated.
