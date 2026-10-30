# Threat model

## Description

The Ethereum Execution Layer Specification (EELS): the specification for
Ethereum execution-layer clients, written as executable Python. Each fork is a
complete, self-contained package under `src/ethereum/forks/`. The repository
also contains the testing framework (`packages/testing`) and the tests
(`tests/`) that generate the reference fixtures every execution client
(Geth, Nethermind, Besu, Erigon, Reth, etc.) is tested against. A bug in the
specification is a protocol bug that every client following it inherits, and a
bug in the tests can hide a client bug.

## Priorities

Each fork's status is listed in the tables of `docs/specs/protocol_history.md`;
read it there rather than assuming a fork's status from its name.

1. The live fork and scheduled forks, with equal priority. The live fork is
   the entry with the highest timestamp that the current Unix time has passed.
   Scheduled forks are entries, in either table, whose timestamp is still in
   the future. Clients must ship a release for any change to either, so both
   are treated as live.
2. The next fork: the first entry under "Unstable specifications" whose
   timestamp is still TBD.
3. Forks after the next fork: the remaining TBD entries under "Unstable
   specifications", in order.
4. Tests and the testing framework, where a bug lets an invalid client
   behavior pass the generated fixtures.

Historical forks are the entries under "Stable specifications" before the live
fork. Clients still execute them when syncing, but every release is tested by
syncing the existing mainnet chain, so an issue that the mainnet chain never
triggered cannot affect clients in practice.

## Out of scope

- Typos and editorial issues.
- Issues limited to running EELS itself as a local client, such as crashes in
  the `ethereum_spec_tools` sync or t8n tooling that do not reflect a protocol
  bug.
- General infrastructure, CI, and documentation issues.
- Performance issues, unless caused by a design flaw in the protocol (for
  example, mispriced gas).
- Attacks through the Engine API, JSON-RPC, or devp2p, which are not specified
  here.
- High-effort denial of service issues.

## Untrusted inputs

A node receives untrusted blocks and transactions from peers and users. This
includes block headers, transaction payloads and signatures, EVM bytecode and
calldata, RLP encodings, withdrawals, execution requests, blob transactions,
authorization lists, and block access lists. Anything an attacker can put in a
transaction or a block is untrusted.

## Severities

**Critical**

- Accepting an invalid block, or rejecting a valid one (consensus split).
- Creating, destroying, or stealing ETH.
- Bypassing signature, nonce, or balance checks.

**High**

- Ambiguities about the validity of a block or transaction.
- Gas mispricing that lets a block cheaply take down many nodes.
- State root or receipt mismatches reachable on mainnet.
- Tests that pass a client with a consensus-breaking bug for a live fork.

**Medium**

- Gas mispricing with a limited practical impact.
- Gas charge ordering that is visible but untested.
- Incorrect behavior that needs uncommon but reachable conditions.
- Tests that miss a consensus-breaking bug in the next fork.
- Issues in the test framework that lead to an incorrect or ineffective
  test.

**Low**

- Mismatched constants with little practical impact.
- Issues that need impossible conditions on mainnet or testnets.
- Issues in forks after the next fork.
- Issues in historical forks that the mainnet chain never triggered.

## Reports

Each report should state the affected fork, the affected component (for
example, an opcode, a precompile, or transaction validation), how to trigger
the issue, and its impact. When practical, include a test written with the
testing framework under `tests/` that demonstrates the issue and a patch that
fixes it. The test must be realistic and not hardcode values or states that
cannot occur on mainnet.
