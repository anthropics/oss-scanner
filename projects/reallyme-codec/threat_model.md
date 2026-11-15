# ReallyMe Codec threat model

ReallyMe Codec encodes and decodes data used for keys, content identifiers,
and digital credentials. The Rust workspace implements the codec behavior
and exposes it through a protobuf operation contract, a native C ABI and
JNI bridge, and WebAssembly. Swift, Kotlin, Java, and TypeScript packages
provide facades over those implementations.

## Trust boundaries

Treat bytes, strings, and serialized operation requests received through
the Rust API, protobuf dispatch, native ABI, JNI, or WASM as untrusted.
Relevant inputs include CBOR, JCS JSON, PEM, DER and TLV framing,
multibase, multikey and multicodec values, and content identifiers. For a
native ABI finding, identify the documented obligations on buffer lifetime,
length, ownership, and aliasing and whether the caller meets them.

## Security properties

- Enforce canonical encoding where the selected operation or profile
  requires it. General parsing and prefix framing have their own contracts.
  Preserve original byte spans when the contract exposes them, and require
  full consumption in exact-input operations.
- Bound parsing and serialization work according to the selected limits.
  Check sizes, offsets, conversions, buffer capacity, and nesting before
  operating on the data. Malformed input returns a typed failure.
- Preserve the documented policy, bytes, metadata, and typed errors across
  native and SDK entry points for the same operation and configuration.
- Respect ownership and buffer cleanup at the language boundaries. Error
  values and diagnostics must avoid exposing raw inputs, secret material,
  personal data, and backend exception text. Evaluate erasure against the
  guarantees in `SECURITY_MEMORY_MODEL.md` and the caller's obligations.

## Scope

Include Codec's primitive crates, dispatch, protobuf envelope and schema,
native ABI, JNI and WASM adapters, and authored SDK boundary code. Include
Codec's CID computation, provider integrity checks, and the way Codec invokes
dependencies. Application-specific trust decisions and cryptographic primitives,
signing, key generation, and encryption implemented in other repositories belong
to their owning projects.

## Severity

- **Critical** requires a demonstrated route from ordinary unauthenticated
  input to code execution, broad disclosure of sensitive data, or a comparable
  compromise of a downstream trust boundary.
- **High** includes remotely reachable memory corruption, substantial
  disclosure, or an encoding or interpretation error with a demonstrated path
  to downstream verification or identity-binding failure.
- **Medium** includes bounded but material denial of service, a security
  property violation dependent on a particular configuration or caller
  behavior, or constrained disclosure with a demonstrated impact.
- **Low** includes security-relevant contract or diagnostic failures with
  limited impact. Rate parser and interoperability issues by the reachable
  consequence in the supported operation and explain any assumptions about
  downstream use.
