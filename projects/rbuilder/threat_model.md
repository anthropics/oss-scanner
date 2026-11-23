
# Threat model

## What this project does

rbuilder is Flashbots' open-source framework for building blocks from transactions and bundles. It is deployed in the pipeline of PBS for Ethereum, where block builders receive transactions or bundles from users or MEV searchers, and produce block proposals to downstream relays and validators.

rbuilder takes as input a sequence of transactions and bundles and produces as outcome blocks, which include input transactions and bundles.

## Scope and trust boundaries

An attacker can only send transactions and bundles to rbuilder via the RPC interface (e.g., `eth_sendRawTransaction()` and `eth_sendBundle()` ). At the same time, there are normal transactions and bundles sent to the rbuilder. A bundle is a group of transactions. In other words, some or all transactions or bundles sent to rbuilder are untrusted.

The attacker’s goal is to deny rbuilder’s service, by making it produce blocks including no normal transactions and as few adversarial transactions. Ideally, the rbuilder under attack produces no blocks at all or produces blocks with zero transactions in them.

When setting up, you may run rbuilder on a commodity computer or server-grade computer.

## Components that matter most / least

- The code related to how a transaction or bundle is executed matters. Transaction execution is done by invoking EVM.
- Two-round rbuilder: [https://github.com/flashbots/rbuilder/](https://github.com/flashbots/rbuilder/)
- Three-round rbuilder: [https://github.com/flashbots/rbuilder/blob/develop/crates/rbuilder/src/building/builders/parallel_builder/](https://github.com/flashbots/rbuilder/blob/develop/crates/rbuilder/src/building/builders/parallel_builder/)
- REVM: [https://github.com/bluealloy/revm](https://github.com/bluealloy/revm)

## How to exercise it

- Set up rbuilder on an isolated Ethereum devnet using the [rbuilder end-to-end local testing guide](https://github.com/flashbots/rbuilder/blob/develop/README.md#end-to-end-local-testing).
- Submit a fixed set of normal transactions and bundles through the RPC interface to establish a baseline. Use the same normal workload, builder configuration, and resource limits in follow-up runs.
- For each slot, record whether the builder produced a block before the deadline. If it produced a block, record the total number of transactions and how many came from the normal workload. Record slots with no block separately from slots with an empty block.

## How you rate severity

- An attack sequence of bundles or transactions that can force the rbuilder to produce no blocks or empty blocks (with no transactions in them) is considered severe.
- Suppose an attack sequence of bundles or transactions that can make the rbuilder produce blocks of some transactions. The fewer transactions in the produced blocks, the more severe.
- An attack that produces blocks including only adversarial transactions is considered more severe than the attack producing blocks with the same amount of normal transactions.
- Send bug report to [ambercove.turk@gmail.com](mailto:ambercove.turk@gmail.com) .

# Report_guidelines

Use EF’s bug bounty format for this document: report_guidelines.md.
