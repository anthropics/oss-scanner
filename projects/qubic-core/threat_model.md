# Threat model — Qubic Core

## What this project does and where untrusted input enters
Qubic Core is the node software for the Qubic network: a feeless, delegated-proof-of-work
Layer-1 that runs on bare metal (UEFI). A node reaches consensus with up to 676 computors,
gossips with arbitrary peers, and executes on-chain smart contracts.

Untrusted input, in rough order of exposure:
- **Peer network traffic.** Every packet from a remote peer is untrusted and
  attacker-controlled: the message header plus all request/response payloads
  (`src/network_messages/**`, request processing in `src/`). This is the primary
  attack surface — a remote, unauthenticated peer can send arbitrary bytes.
- **Transactions and their payloads**, including smart-contract input structs
  submitted by anyone.
- **Tick/quorum data** relayed between peers (votes, tick data, transaction sets).
- **Assets, spectrum and contract state** reconstructed from peer-supplied data.

## Components that matter most / least
- **Most critical:** parsing and dispatch of network messages (bounds/length handling,
  type confusion, integer overflow in size math); transaction and tick validation;
  the cryptography wrappers (KangarooTwelve, FourQ / `src/four_q`, signature checks);
  smart-contract execution and the QPI surface (`src/contracts/**`, `src/contract_core/**`);
  spectrum/asset accounting.
- **In scope but lower priority:** operator tooling, logging, benchmark paths.
- **Out of scope:** the `test/` suite and `tools/` helpers themselves (as targets),
  third-party code under `lib/` where it is clearly vendored.

## How to exercise it
- The `test/` directory holds the C++/GoogleTest suite; `src/network_messages/` defines the
  on-wire message formats — the most valuable place to reason about malformed input.
- Build note: the production node is built with the UEFI/MSVC toolchain. The Linux/Clang
  build in the Dockerfile is a partial test harness — the Clang port is still being
  completed upstream (README_CLANG.md lists several "Pending" modules that do not yet compile
  under Clang), so the image sets up the toolchain, fetches dependencies and exports a
  `compile_commands.json` for precise source navigation, and compiles/runs the modules that
  port cleanly. Treat the **source** as the source of truth; the same consensus/validation and
  crypto logic is what the UEFI node runs. The image targets the AVX/AVX2 baseline.

## How you rate severity
- Any memory-safety defect (buffer overflow, OOB read/write, use-after-free, double free,
  type confusion) reachable from **peer network input or a transaction** is **critical** —
  it is remotely triggerable against validator infrastructure and funds.
- The same defect reachable only from local/operator input is **high**.
- A remotely triggerable panic/assert/crash or consensus divergence (nodes disagreeing on
  state) is **high** (network-wide liveness/safety impact).
- Integer overflow or unchecked length that does not (yet) reach a memory error is **medium**
  pending a demonstrated corruption.

## Anything to leave alone
- Findings that require a malicious/compromised operator with physical or root access to
  their own node are generally out of scope — assume the operator is trusted on their own box.
- The Clang Linux build is a test harness; code paths that exist only to make tests compile
  (not present in the production UEFI build) are not interesting.
