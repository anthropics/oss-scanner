# zstd-rs security review

zstd-rs provides the zstd, zstd-safe, and zstd-sys Rust crates for Zstandard
compression and decompression. Applications may use these libraries to process
untrusted files, network responses, compressed frames, and dictionary bytes.

## Review priorities

Prioritize the safe Rust APIs in src/ and zstd-safe/src/, and the contracts they
establish across the C FFI boundary. Check buffer lengths and initialization,
integer conversions, context and dictionary lifetimes, aliasing, thread safety,
error handling, and streaming progress with truncated or malformed input and
short reads or writes. Include feature-gated APIs, particularly experimental,
seekable, multithreaded compression, and Rust allocator callbacks.

The bundled C source under zstd-safe/zstd-sys/zstd is relevant to reproductions.
Distinguish defects in the Rust bindings from defects in upstream facebook/zstd;
identify the responsible component and bundled upstream revision in each report.
Unsafe zstd-sys APIs require callers to meet the documented C API preconditions.
Misuse of an unsafe API alone does not demonstrate unsoundness in a safe wrapper.

## Resource usage and severity

Distinguish legitimate decompression expansion and caller-selected large resource
limits from unexpected allocations, integer overflows, failure to honor configured
limits, or nontermination. The convenience APIs that return all decompressed bytes
do not promise a fixed output-size budget. Explain the application assumptions
needed for a denial-of-service claim.

For memory-safety findings, provide a reproducer using a safe public API where
possible. Separate observed corruption or undefined behavior from any claim of
code execution; explain attacker control and required features. Describe realistic
impact rather than inferring severity solely from the use of unsafe code.

## Reproductions and tests

The checkout is at /src. Rust, C/C++ compilers, libclang, CMake, the zstd command,
and Cargo dependencies are installed. Cargo is configured for offline operation.
The project is not a Cargo workspace: test the nested manifests explicitly.
Run the zstd-safe tests separately with the default C allocator and with the
Rust allocator enabled to cover both allocation paths.

```
cargo test
cargo test --features experimental,zstdmt,with-rust-allocator
cargo test --manifest-path zstd-safe/Cargo.toml --features std,seekable
cargo test --manifest-path zstd-safe/Cargo.toml --features std,seekable,with-rust-allocator
cargo test --manifest-path zstd-safe/zstd-sys/Cargo.toml --features bindgen,experimental,seekable,zstdmt
```

Provide the affected crate, revision, feature set, minimal input, exact command,
expected and observed behavior, and root cause. Prefer small regression tests and
focused patches that preserve the public API. Deduplicate findings that share the
same root cause across wrappers or feature combinations.
