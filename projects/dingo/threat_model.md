# Threat model

## What this project does and where untrusted input enters

Dingo is a Go implementation of a Cardano node. Treat data received from
network peers, including protocol messages, headers, blocks, and transactions,
as untrusted. Also consider client requests handled by configured APIs and
snapshot or imported ledger data.

## Components that matter most / least

Prioritize Ouroboros protocol handling and peer management, block and ledger
validation, ledger-state import and bootstrap, transaction-pool processing,
storage, and API request handling. Consider whether malformed inputs can cause
resource exhaustion, bypass validation or access controls, corrupt persistent
state, or interrupt node operation. All production code is in scope.

## How to exercise it

The repository's Go tests exercise node, protocol, ledger, database, and API
behavior. The standard test target is `make test`, which enables race detection
and the `dingo_extra_plugins` build tag.

## How you rate severity

Base severity on a demonstrated attack path, required peer or caller access,
and practical impact. Distinguish a local availability issue from effects on
ledger integrity or broader node operation, and include a minimal reproducer
where possible.

## Anything to leave alone

Do not report protocol or ledger correctness differences without explaining
their security impact and a reachable attack path.
