# Threat model

## Description

The specifications for Ethereum consensus-layer clients, written as Markdown
files with executable Python code. A bug here is a protocol bug that every
client following the specifications inherits.

## Priorities

1. [Stable specifications](https://github.com/ethereum/consensus-specs#stable-specifications).
2. [Unstable specifications](https://github.com/ethereum/consensus-specs#unstable-specifications).

## Out of scope

- Typos and editorial issues.
- General infrastructure and testing issues.
- Bugs that are no longer applicable to mainnet.
- Performance issues, unless caused by a design flaw.
- Attacks through the Beacon API or Engine API.
- High-effort denial of service issues.
- Issues in feature specifications.

## Untrusted inputs

A node receives untrusted data from peers through gossip and req/resp messages.
This includes blocks, attestations, slashings, voluntary exits, sync committee
messages, blobs, data columns, etc. Execution requests from the execution layer
are also untrusted.

## Severities

**Critical**

- Completely halting the chain.
- Finalizing an invalid block.
- Creating, destroying, or stealing ETH.
- Slashing a majority of honest validators.

**High**

- Ambiguities about the validity of objects.
- Preventing finality with less than a third of the stake.
- Easily reorging confirmed blocks.
- Cheaply taking down many nodes.
- Slashing many honest validators.

**Medium**

- Reorging recent blocks with a small amount of stake.
- Financially penalizing honest validators.
- Reliably causing missed proposals.
- Cheaply taking down a few nodes.
- Slashing a few honest validators.

**Low**

- Causing an attestation to be included later.
- Censoring specific validators or transactions.
- Mismatched constants with little practical impact.
- Issues that need very unlikely conditions.
- Cheaply taking down a single node.

## Reports

Each report should state the affected specification, the affected component,
how to trigger the issue, and its impact. When practical, include a test that
demonstrates the issue and a patch that fixes it. The test must be realistic
and not hardcode values or states that cannot occur on mainnet.
