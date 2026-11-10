# Threat model: cardano-base

## What this project does and where untrusted input enters

cardano-base is a set of Haskell libraries used by the Cardano node (consensus, ledger, networking) and by Plutus. It
provides the cryptographic primitives that secure the chain, CBOR serialisation and other core utilities. Most of
the crypto calls C libraries (libsodium and IOG's fork of it, blst, libsecp256k1), and the VRF implementation is C
code kept in this repository.

Every node runs this code on bytes that come from the network: blocks, block headers and transactions from untrusted
peers. All nodes must also reach **exactly the same** result on the same input, so these properties matter as well
as memory safety:

- **Determinism and agreement.** A decoder or verifier must accept or reject the same input on every platform, GHC
  version and C library build. Two nodes that disagree split the network.
- **Canonical, exact decoding.** A decoder must reject input it does not fully understand. Past incidents involved
  decoders that accepted extra data and threw it away, so the same value had several encodings, or the bytes that
  were hashed or signed were not the bytes the node acted on. Trailing bytes, non-canonical lengths, duplicate or
  unordered map keys, wrong tags, oversized or undersized byte strings, and indefinite-length forms where a definite
  one is expected are all in scope.
- **Malleability.** Anyone who can change a signature, proof or encoding without invalidating it can change
  transaction or block IDs.
- **Secret key hygiene.** Block producers keep KES and VRF signing keys in memory for a long time. KES keys must
  be held in mlocked memory, never copied to the GC heap and erased when they evolve (`forgetSignKeyKES`), since
  forward security depends on old keys being gone.
- **Bounded cost.** Plutus exposes many of these primitives as builtins whose arguments are fully attacker-chosen,
  and charges for them with a cost model based on input size. Running time that depends on input in a way the cost
  model does not expect, a hang, or a crash in a builtin is a denial of service against every node.

Assume all serialised input (CBOR, raw key, signature, proof and hash bytes, and Plutus builtin arguments) is
hostile. Callers are trusted to pass well-formed *types* (for example, they choose which algorithm to use), but not
well-formed *bytes*.

## Components that matter most / least

### Highest priority: cardano-crypto-class and cardano-crypto-praos

Scrutinise these heavily, both the Haskell bindings and the C code.

- **Ed25519 DSIGN** (`DSIGN/Ed25519.hs`): transaction and certificate witnesses. Look for acceptance of non-canonical
  signatures or keys, length handling in raw deserialisers, and secret material leaking out of mlocked memory.
- **KES** (`KES/Sum.hs`, `KES/CompactSum.hs`, `KES/Single.hs`, `KES/CompactSingle.hs`): sign block headers. Check
  evolution and period arithmetic (off-by-one errors, signing for the wrong period, verifying a signature with the
  wrong period), the encoding of the verification-key tree, and that forgotten keys are really erased.
- **VRF Praos, IETF draft-03** (`VRF/Praos.hs`, `cbits/vrf03/`, `cbits/crypto_vrf.c`): leader election. Check proof
  and key validation (small-order points, non-canonical encodings), output derivation, and memory safety in the C
  code. This C code is maintained here, not upstream, so it is in scope in full.
- **Hashes** (`Hash/*.hs`): Blake2b-224 and Blake2b-256 are used throughout the chain. SHA-256, SHA-512, SHA3-256,
  Keccak-256 and RIPEMD-160 are exposed to Plutus. Check length checks in `hashFromBytes` and similar functions,
  and the sized-hash decoders.
- **secp256k1 ECDSA and Schnorr** (`DSIGN/EcdsaSecp256k1.hs`, `DSIGN/SchnorrSecp256k1.hs`, `SECP256K1/C.hs`): Plutus
  builtins. Check message and key length validation, ECDSA high-S/low-S handling, and FFI buffer sizes.
- **BLS12-381** (`EllipticCurve/BLS12_381/`, `DSIGN/BLS12381/`, `cbits/blst_util.c`): the curve operations are Plutus
  builtins. Check that uncompression and deserialisation enforce curve and subgroup membership, the handling of the
  point at infinity, hash-to-curve domain separation tags, scalar range and reduction, and multi-scalar
  multiplication with mismatched or empty inputs. The DSIGN layer (PoP ciphersuite, key and signature aggregation)
  is used by Peras and Leios (see below). Rogue-key and infinity-key issues there matter.
- **Memory and FFI plumbing** (`Libsodium/`, `MLockedBytes`, `PinnedSizedBytes`, `PackedBytes`, `DirectSerialise`):
  look for buffer size mismatches between Haskell and C, use after free of foreign pointers, missing `touchForeignPtr`
  or `keepAlive`, unchecked raw pointer copies in `DirectSerialise`, and secret data that reaches the unpinned heap.

### Equally high priority: cardano-binary and cardano-base

These utilities are used by every serialised type in the ledger and consensus, so a weakness here is a weakness
everywhere.

- **cardano-binary**: `decodeFull`/`decodeFull'` (trailing-byte rejection), `decodeNestedCbor` (CBOR in CBOR, tag 24),
  `enforceSize`/`matchSize`, `decodeMapSkel` and `decodeSetSkel` (strictly increasing keys, tag 258),
  `decodeMaybe`, list decoders, the tuple and integer instances, and `FixedSizeCodec`. Look for any path that
  accepts more than one encoding of a value, ignores data, or accepts a length different from the one it expects.
  Encoder/decoder pairs must round-trip exactly, and `serialize` followed by `decodeFull` must be the identity.
- **cardano-base**: `Bytes` (`slice`, `splitsAt`, conversion between `ByteArray` and `ByteString`), `IP` (address
  parsing and JSON instances), `Aeson` helpers and `FeatureFlags`. Look for silent truncation, out-of-bounds
  slicing that returns a short result instead of failing, and parsers that accept malformed input.

### In scope, normal priority

- **cardano-strict-containers** (`StrictMaybe`, `StrictSeq`, `StrictFingerTree`): small utilities, but used widely.
  Report fundamental mistakes: strictness that is not actually strict (thunks building up under adversarial input),
  wrong `Foldable`/`Traversable`/indexing semantics, or serialisation instances that disagree with the lazy versions.
- **cardano-crypto-peras and cardano-crypto-leios**: not yet live on mainnet. They verify BLS certificates and
  committee votes, so certificate forgery, weight or threshold arithmetic errors and committee-selection bugs are
  worth reporting before deployment.
- **cardano-slotting**: lightweight slot, epoch and time arithmetic. Report overflow or underflow on attacker-chosen
  slot numbers, and `EpochInfo` conversions that disagree at era boundaries.

### Low priority

- **Byron-era code**, including **cardano-crypto-wallet** (encrypted HD wallet keys and the vendored ed25519-donna
  code). It is still built but matters much less.
- **VRF draft-13 batch-compatible code** (`VRF/PraosBatchCompat.hs`, `cbits/vrf13_batchcompat/`). It is not in use
  on chain.
- **Ed448** (`DSIGN/Ed448.hs`).
- **heapwords, measures, cardano-git-rev, base-deriving-via, orphans-deriving-via**: used for testing, development,
  memory accounting or release tooling.

## How to exercise it

The image has the project's Nix dev shell saved in `/etc/cardano-env.sh`, which `/root/.bashrc` sources, so `ghc` and
`cabal` work offline. Everything is already built in `/src/dist-newstyle`.

- `cabal test cardano-crypto-class`, `cabal test cardano-crypto-praos`, `cabal test cardano-binary` and
  `cabal test cardano-base` run the main suites. Use `--test-options='-p <pattern>'` to select tests.
- `cabal repl cardano-binary` or `cabal repl cardano-crypto-class` is the quickest way to feed crafted bytes to a
  decoder, for example `decodeFull' @(Map Word8 Word8) "\xa2..."` or `rawDeserialiseVerKeyDSIGN @Ed25519DSIGN`.
- Test vectors are in `cardano-crypto-praos/test_vectors/` (VRF) and `cardano-crypto-class/bls12-381-test-vectors/`.
  The property tests for the crypto classes are in `cardano-crypto-class/testlib/`.
- For C-level bugs, a small C driver linked against the cbits and the dev shell's libsodium, blst and libsecp256k1
  (all under `/nix/store`), or a Haskell test built with `-fsanitize=address` in `ghc-options`, works with gdb and
  valgrind.

## How we rate severity

- **Critical**: on code that is live on mainnet, forging a signature, KES signature, VRF proof or BLS
  signature or point check; recovering a secret key; a decoder or verifier that accepts input in a way that lets two
  correctly built nodes disagree (consensus split); or memory corruption in C code reachable from network or Plutus
  input that is plausibly exploitable.
- **High**: a decoder that accepts non-canonical or extra data on a live type, even if no attack is shown yet;
  signature, proof or encoding malleability; secret key material that leaks (left in memory after forgetting, copied
  to the heap, or exposed through timing in signing); a crash, abort, uncaught exception or hang reachable from a
  single block, header, transaction or Plutus builtin call. Any of these takes down many nodes at once, so it is
  not "just" denial of service. Out-of-bounds reads in C code without a shown exploit are at least High.
- **Medium**: Plutus builtin cost that grows faster than its input size in a way that could beat the cost model;
  resource exhaustion that needs unusually large input; a fundamental bug in cardano-strict-containers or
  cardano-slotting; a serious flaw in Peras or Leios code before deployment.
- **Low**: issues in Byron-only code, batch VRF, Ed448 or the development and testing packages; defensive hardening
  with no reachable trigger.

## Anything to leave alone

- Mock, Simple and NeverUsed instances (`*/Mock.hs`, `*/Simple.hs`, `*/NeverUsed.hs`), `testlib/`, `benchlib/` and
  benchmarks are test-only. Do not report weak crypto in them.
- Bugs inside libsodium, blst or libsecp256k1 are upstream issues. Report how this repository *calls* them (buffer
  sizes, missing validation, wrong flags), not their internals. The VRF C code in `cardano-crypto-praos/cbits/` is
  ours and is in scope.
- Partial functions documented as `unsafe*`, or `error` calls on inputs that only trusted callers construct (such as
  key generation from a seed of a fixed, type-checked size), are not findings unless untrusted bytes can reach them.
