# Lodestar scanner guidance

Lodestar is a TypeScript Ethereum consensus client, including a beacon node,
validator client, and reusable consensus libraries. It processes
adversarial network traffic and helps protect Ethereum consensus and validator
funds. Scan the `unstable` branch.

## Security objectives and boundaries

- Preserve consensus safety and liveness: reject invalid blocks, attestations,
  signatures, proofs, and unavailable data; implement the pinned consensus
  specification correctly across fork transitions.
- Preserve validator signing safety and key confidentiality. Slashing protection,
  duty selection, signing roots and domains, and optimistic execution status must
  prevent unsafe signing.
- Bound resources consumed by untrusted peers and API callers. Investigate
  malformed SSZ and Snappy input, request framing, gossip validation, queues,
  caches, peer scoring, and cancellation or timeout handling.
- Treat peer traffic, externally supplied API payloads, builder responses, and
  unauthenticated checkpoint bytes as untrusted at their respective entry points.
  Trace authentication, provenance checks, and validation before relying on them.
- Operator-selected configuration, local credentials, and trusted execution
  engines or signers have different authority from arbitrary peers. Identify the
  actual trust boundary crossed; do not assume a public key-manager API or a
  malicious operator without demonstrating a supported deployment path.
- Check that rejected candidates cannot corrupt shared caches, admitted chain
  state, or fork-choice state. Execution invalidation must propagate correctly.
- Check dependency, build, and release boundaries for paths that could compromise
  distributed artifacts or expose publishing credentials.

Prioritize `packages/beacon-node`, `packages/state-transition`,
`packages/fork-choice`, `packages/validator`, `packages/reqresp`, `packages/api`,
`packages/types`, and their dependencies. The native
`@chainsafe/lodestar-z` dependency is separately enrolled; distinguish faults in
that library from unsafe use by this repository. Generated `packages/*/lib`
files are build outputs. Proposed fixes belong in source files.

## Reproducing findings offline

The checkout and all development dependencies are in `/src`. The image includes
Node.js, the repository-selected pnpm, Zig 0.16.0, built packages, and the spec
test fixtures fetched by `pnpm download-spec-tests`.

Run targeted tests from `/src`, for example:

```sh
pnpm vitest run --project unit packages/reqresp/test/unit/encodingStrategies/sszSnappy/decode.test.ts
pnpm vitest run --project unit packages/validator/test/unit/slashingProtection/block.test.ts
pnpm vitest run --project spec-minimal packages/beacon-node/test/spec/presets/transition.test.ts -t transition_with_voluntary_exit_right_after_fork
```

Use the project's local mocks and test utilities. Browser binaries, Docker-backed
end-to-end environments, live networks, and large historical-chain datasets are
not provisioned. Keep reproducers deterministic and local. Check both presets
when an issue depends on mainnet versus minimal limits.

## Reporting and severity

For each finding, identify the affected commit, least-privileged attacker,
reachable entry point, validation already performed, violated invariant, and
concrete impact. Include a minimal regression test and a source patch where
possible. Quantify input size, required stake or peer access, repetition, resource
amplification, and recovery for denial of service. Separate currently reachable
vulnerabilities from future-fork readiness issues and ordinary correctness bugs.

Prioritize remotely reachable consensus divergence, unsafe validator signing,
key disclosure, and code execution. Judge availability issues by realistic cost,
reach, and persistence. Do not claim theft, slashing, or network-wide impact from
a local crash alone. Report uncertain reachability explicitly rather than
discarding a candidate. Group reports that share one root cause.

Send vulnerability details privately to the configured security contact. Follow
`SECURITY.md`; do not open public vulnerability issues.
