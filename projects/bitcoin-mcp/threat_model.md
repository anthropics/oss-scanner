# bitcoin-mcp threat model

## Purpose and trust boundaries

bitcoin-mcp is an MIT-licensed Python MCP server distributed on PyPI. It gives
agent clients Bitcoin analysis tools backed by an operator-configured Bitcoin
Core/Knots node or compatible remote API. The default transport is local stdio.
The maintainer-operated hosted API is paused; no live service is needed to audit
this repository.

Treat MCP tool arguments, transactions, PSBTs, addresses, scripts, BOLT11
invoices, remote API responses and L402 challenges as untrusted. Configured RPC
credentials, wallet private keys and Lightning credentials are sensitive.
An operator choosing a node or endpoint is a trusted configuration action;
untrusted tool arguments or responses must not expand that authority.

## Priorities

- `src/bitcoin_mcp/server.py`: RPC/API routing, input validation, response
  parsing, bounded resource use and isolation between calls.
- `src/bitcoin_mcp/address_validation.py`: malformed address handling.
- PSBT and invoice parsing: crashes, incorrect security conclusions and unsafe
  treatment of private-key material.
- `src/bitcoin_mcp/l402_client.py`: payment limits, challenge/invoice consistency,
  token reuse, redirects and credential disclosure. Include optional Lightning
  integration and key-generation behavior in the audit.

## Build and exercise

The checkout and an installed development package are in `/src`. Runtime,
test and optional L402 dependencies are installed during the Docker build.
Run `python -m pytest tests/ -q`. Fixtures mock RPC and HTTP/Lightning calls;
no Bitcoin node, external API, funded wallet or credentials are required.
The wheel is in `/src/dist`. Use synthetic keys and invoices for reproducers.

## Severity and scope

Remote-input-driven code execution, private-key/credential disclosure, or
unauthorized spending are high or critical according to reachable impact.
Payment-limit bypass requires a demonstrated path to a payment beyond the
operator's configured authority. A reproducible persistent denial of service
is normally medium; raise it only with a clear wider impact. Informational
analysis errors need a concrete security consequence to be rated high.

Operator-directed access to an explicitly selected backend is intended.
Do not assume stdio is an unauthenticated Internet endpoint, or report a
malicious operator's chosen URL as an SSRF vulnerability by itself. A finding
that crosses this boundary through untrusted arguments or redirects is in
scope. Dependency findings should explain this project's reachable use.
Reports should identify the entry point, preconditions and affected revision,
include an offline reproducer, and propose a minimal fix and regression test.
