# libsecp256k1 threat model

libsecp256k1 implements signatures, key operations and related cryptographic protocols on the secp256k1 curve.
Protect mathematical correctness, interoperability, private keys and nonces, memory safety, and the guarantees made to supported callers.

## Project guidance and scope

Read the scanned checkout's `SECURITY.md`, `README.md`, `CONTRIBUTING.md`, public headers under `include/`, and the relevant module documentation and examples, including `doc/musig.md`, `doc/ellswift.md` and `doc/safegcd_implementation.md`.
The project's documented contracts and policies take precedence over this summary.
The public security contact is published in [SECURITY.md](https://github.com/bitcoin-core/secp256k1/blob/master/SECURITY.md).

The whole repository is in scope for source review, including optional modules, internal arithmetic, generated tables, tests, examples and build tools.
The image enables ECDH, recovery, extrakeys, Schnorr signatures, MuSig, ElligatorSwift and Silent Payments through the development preset and current module defaults.
Identify experimental or unreleased code and its release exposure separately from its correctness.
On x86-64 with the image's GCC and Clang toolchains, the default build uses native int128 arithmetic and x86-64 scalar assembly.
The forced `int64` build uses 10x26 field and 8x32 scalar arithmetic with assembly disabled.
An `int128_struct` build exercises the separate wide-integer implementation with small precomputed tables.
Other platforms, 32-bit execution and additional backend configurations need separate environments. These are execution limits, not source-review exclusions.

## Callers and trust boundaries

Untrusted input can reach public key, signature and protocol-data parsing, verification, key agreement, tweaks, aggregate-key operations and signing sessions through an application's callers.
A public C API does not itself establish a network entry point. Trace any remote or Bitcoin Core consequence through the actual consumer and its input checks.
Keep a supported library-contract violation distinct from a demonstrated application failure.
A supported call returning an incorrect result is a bug even without a network attacker.

Respect documented argument, alignment, buffer size, aliasing, context, ownership and thread-safety requirements.
Construct opaque objects through supported APIs and preserve their invariants.
A documented illegal-argument callback, forbidden overlap or a fabricated invalid opaque object is not evidence of a failure reachable by supported callers.
Caller-provided nonce, hash, SHA256 compression, Silent Payments label-lookup and error callbacks execute in the caller's process. Record their documented capabilities and failure semantics before claiming additional authority.

Check return values and promised output contents on failure, including whether the caller can accidentally reuse stale state.
Review context creation, cloning, preallocated storage, randomization and destruction, as well as concurrent use and callback lifetimes.

For Bitcoin Core integration, inspect the consumer revision's `cmake/secp256k1.cmake`, `src/key.cpp`, `src/pubkey.cpp` and `src/common/bip352.cpp`.
Core disables the ECDH module and enables recovery and MuSig. An ECDH-only API defect therefore needs a different consumer path, while shared internal code may still affect Core.
Prioritize ElligatorSwift decoding and XDH reached through unauthenticated BIP324 handshakes, and the ECDSA, Schnorr and x-only tweak checks used during validation.
Core normalizes ECDSA signatures before verification and uses its own lax DER parser on that path. Do not attribute a strict-DER-parser defect to consensus without another demonstrated path.
Recovery supports message-signature workflows, and Silent Payments integration is in `src/common/bip352.cpp`.
Verify these paths and enabled modules against the exact consumer version before claiming exposure.

## Investigation priorities

Prioritize incorrect acceptance or rejection, wrong public keys or shared secrets, invalid signatures, nonce reuse, memory corruption under supported calls, and secret-dependent leakage with a realistic observer.
Give supported-use nonce reuse, partial signing-state failures, incorrect signatures, ignored errors and signing-intent violations priority over constant-time changes that add assurance without demonstrated leakage.
Check arithmetic and serialization against independent expected values and the applicable specifications.
Compare field and scalar backends, scalar edge cases, modular inversion, point multiplication, precomputed tables and exceptional points.

Review ECDSA and Schnorr nonce generation and signing, MuSig nonce consumption and session state, aggregate keys, partial signatures and error propagation.
For ElligatorSwift, check the specified decoding and key-agreement behavior for arbitrary encoded input.
For Silent Payments, check agreement between sender and receiver derivations and their specified failure cases.
Review internal scratch-space accounting and rollback according to the internal caller contract, without describing those helpers as public APIs.

Check that `secp256k1_context_set_sha256_compression` is preserved across cloning, rejects the static context, and is honored by context-aware nonce derivation, tagged hashing, default ECDH/XDH hashing and Silent Payments operations.
The replacement must implement SHA256 compression exactly. Direct calls to exposed nonce-function pointers without a context intentionally use the built-in implementation, as documented in `include/secp256k1.h`.

Constant-time claims depend on the secret, operation, compiler and target.
Variable-time processing of public or invalid data is not itself a secret leak.
Distinguish source patterns, compiled secret-dependent behavior, observable leakage and successful extraction.
Secret residue needs a plausible reader before it establishes disclosure. Memory-clearing or constant-time hardening alone does not establish a completed attack.

## Build and bounded offline tests

The checkout is `/src`. The image retains source, compilers, debug information and compilation databases for all five builds.
`/src/build` is the normal GCC build with Valgrind test support, `/src/build-asan` uses Clang with AddressSanitizer and UndefinedBehaviorSanitizer, and `/src/build-int64` forces the alternate arithmetic backend with assembly disabled.
`/src/build-int128-struct` uses the structured int128 implementation, a 2 KiB generator table and verification window size 4.
`/src/build-msan` uses Clang with MemorySanitizer and constant-time tests. Its sanitizer flags are configured through `CMAKE_C_FLAGS` so the build system detects MSan and disables memory parameter and return-value instrumentation for constant-time testing.
All five build the enabled modules, ordinary and exhaustive tests, benchmarks and examples.
The normal build also contains `/src/build/bin/ctime_tests`, which must be run under Valgrind separately from CTest.
The MSan constant-time binary runs directly, without Valgrind.
There are no in-tree libFuzzer harnesses in this revision. Do not report fuzz coverage from the presence of ordinary tests.

Use disposable processes, temporary files, synthetic keys and deterministic local inputs.
Never use real private keys or funds, connect to public networks, or contact third parties during reproduction.
Keep recompilation and test parallelism at two jobs in the scanner environment, and bound runtime and memory.

```sh
ctest --test-dir /src/build --output-on-failure -j2 --timeout 300
ctest --test-dir /src/build-asan --output-on-failure -j2 --timeout 300
ctest --test-dir /src/build-int64 --output-on-failure -j2 --timeout 300
ctest --test-dir /src/build-int128-struct --output-on-failure -j2 --timeout 300
ctest --test-dir /src/build-msan --output-on-failure -j2 --timeout 300
timeout --kill-after=5 300 valgrind --error-exitcode=42 /src/build/bin/ctime_tests
timeout --kill-after=5 300 /src/build-msan/bin/ctime_tests
```

List tests and modules, then select a bounded subset when investigating a specific operation:

```sh
/src/build/bin/tests -l
timeout --kill-after=5 300 /src/build/bin/tests -t=musig -i=16 -j=2
```

`SECP256K1_TEST_ITERS` also sets the iteration count. Explicit `-i` takes precedence.

Check for skipped or disabled tests and record the configuration actually exercised.
Valgrind and sanitizer results support investigation but do not prove an ordinary-build failure, production leakage or key recovery.
Reproduce the claimed consequence under the relevant supported build and caller contract.

## Evidence and reporting

State the broken contract, smallest supported call sequence, actual and expected results, attacker or observer capabilities, and demonstrated harm.
Record the exact commit, module, compiler, optimization, arithmetic backend, architecture and test configuration.
Distinguish released versions from development-only regressions and experimental modules.
`SECURITY.md` specifies a reporting route but no severity scale. Explain the library impact first and any demonstrated consumer impact separately, without importing another project's rating.
Do not invent CVEs, affected versions, CVSS scores, key recovery or transaction-level consequences.

Use repository-native tests with an independent oracle, and keep proposed changes focused and consistent with the project's contribution rules.
Compare related public history and existing tests for the same root cause before presenting a new report.
Send findings privately to `secp256k1-security@bitcoincore.org` as directed by the project's security policy.
Do not publish suspected vulnerabilities or reproducer details in public issues or PRs. Disclosure decisions belong to the project's security contacts.
