# Threat model

## What this project does and where untrusted input enters

gOuroboros is a Go framework for applications that communicate with Cardano
nodes and process Cardano blocks and transactions. Treat peer-provided protocol
frames, messages, CBOR, blocks, and transactions as untrusted input.

## Components that matter most / least

Prioritize CBOR decoding, muxer framing and resource limits, handshake and
mini-protocol state machines, and decoding of ledger objects received from a
peer. Consider whether malformed or oversized inputs can cause memory or CPU
exhaustion, panics, protocol desynchronization, or acceptance of invalid data.
All production code is in scope.

## How to exercise it

Use the Go test suites in each module. Tests should exercise malformed input
and protocol state transitions; examples show how applications compose the
protocol clients.

## How you rate severity

Base severity on a demonstrated attack path, required peer or caller access,
and practical impact. Distinguish effects on one client from effects that can
affect node or chain operation, and include a minimal reproducer where possible.

## Anything to leave alone

Do not report a protocol or ledger correctness difference without explaining
its security impact and a reachable attack path.
