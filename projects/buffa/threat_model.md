# Threat model: buffa

## What this project does and where untrusted input enters

buffa is a pure-Rust Protocol Buffers implementation. It has a runtime (`buffa`, `buffa-types`, `buffa-descriptor`, `buffa-yaml`), a code generator (`buffa-codegen`, `buffa-build`, `protoc-gen-buffa`, `protoc-gen-buffa-packaging`), and the Rust code that the generator emits. Applications link the runtime and the generated code to decode messages that arrive from a network peer, so every byte handed to a decoder is attacker-controlled. The application's developer normally writes the schema, but projects also compile third-party `.proto` files, and `protoc-gen-buffa` also runs as a hosted remote plugin on the Buf Schema Registry (`buf.build/anthropics/buffa`), so a schema is less trusted than code. `protoc-gen-buffa-packaging` runs locally only.

Untrusted bytes reach the runtime through these entry points:

- **Binary decoding into owned messages**: `Message::decode`, `decode_from_slice`, `merge_from_slice` and `decode_length_delimited`, the same operations through `DecodeOptions`, and `DecodeOptions::decode_reader` (feature `std`).
- **Zero-copy view decoding**: the generated `FooView::decode_view`, `OwnedView::decode`, lazy views, and the conversion from a view to an owned message (`to_owned_message`). Views borrow from the input buffer, and `OwnedView` holds a view next to the `Bytes` it borrows from, so most of the `unsafe` code and the lifetime reasoning are in `buffa/src/view.rs`.
- **JSON**: the serde `Deserialize` implementations of generated messages and of the well-known types in `buffa-types` (feature `json`).
- **Text format**: `buffa::text::decode_from_str` (feature `text`).
- **YAML**: `buffa_yaml::from_str`, `from_slice` and `from_reader`.
- **Reflection**: `DescriptorPool` and `DynamicMessage` in `buffa-descriptor` (feature `reflect`), which decode binary and, with feature `json`, JSON without generated code, and the `Any` pack, unpack and expansion paths.
- **Re-encoding a decoded message**: binary encode with the cached sizes, JSON and text serialization, and unknown-field round-tripping all run over data that the peer chose.

The decoders limit what one input can cost. The defaults are a recursion limit of 100, a maximum input size of 2 GiB - 1, 1,000,000 unknown fields per decode, and 32 MiB of element memory per decode; `DecodeOptions` changes them. The section "What these limits do and do not bound" in `docs/guide.md` says which paths each limit covers.

## Components that matter most / least

Most important, in this order:

1. `buffa/src`, and above all its `unsafe` blocks: the wire decoders, views, `OwnedView`, the size cache, UTF-8 validation and the table-driven codec.
2. The generated code. The checked-in instances are `buffa-types/src/generated` and `buffa-descriptor/src/generated`, and `buffa-test` generates a large and varied set at build time. A flaw in generated code is a flaw in `buffa-codegen`, so report it against the generator.
3. `buffa-types` (well-known types, including their JSON forms and `Any`) and the reflection code in `buffa-descriptor/src/reflect`.
4. `buffa-codegen` and the plugins, when the input is a hostile schema or `CodeGeneratorRequest`.

In scope, but less important: `buffa-yaml`, `buffa-remote-derive`, `examples/buffa-smolstr`, and the `no_std` and 32-bit builds of the runtime. Lengths and offsets that fit in a `usize` on x86-64 can overflow on a 32-bit target, so the 32-bit build deserves a look of its own.

Out of scope: `benchmarks/`, `stress/`, `compat/`, `scripts/`, the other directories under `examples/`, the conformance and fuzz harnesses themselves (`conformance/src`, `fuzz/`), CI configuration, and documentation. Vulnerabilities in dependencies are out of scope unless buffa's use of the dependency is what makes them reachable.

## How to exercise it

The image runs offline, and every command in this section works offline: every dependency is in the cargo cache, `CARGO_NET_OFFLINE` is set, and the test and conformance builds below are already done in `/src`.

- **Unit and integration tests**: `cargo test --workspace`, or `cargo test -p buffa`. `buffa-test` holds the end-to-end tests of generated code.
- **Fuzz targets** (`fuzz/fuzzers/`): `decode_proto3`, `decode_proto2`, `decode_wkt`, `encode_proto3`, `json_roundtrip` and `wkt_json_strings`. The image build tries to compile them with AddressSanitizer and continues if that fails, because CI does not build `fuzz/`. `cargo +nightly-2026-02-27 fuzz build --fuzz-dir fuzz` shows whether they compile at the scanned commit, and every crate they need is already in the cache. At commit 5fed61b2 they do not: `fuzz/build.rs` needs `.allow_message_set(true)` on the proto2 `Config`, as `conformance/build.rs` has, and `fuzz/src/lib.rs` calls `compute_size()` without its `&mut SizeCache` argument. Repair the harness locally before fuzzing; its defects are not findings. Run a target with `cargo +nightly-2026-02-27 fuzz run --fuzz-dir fuzz decode_proto3 -- -max_total_time=300`. `scripts/fuzz-all.sh` runs all six, but it calls `cargo +nightly`, so replace that with the dated toolchain. The targets decode into owned messages only (`fuzz/build.rs` turns views off). View, lazy-view, text, YAML and reflective decoding have no fuzz target, so a new target there is the most useful one to write; it needs an entry in `fuzz/Cargo.toml`.
- **Miri**: `cargo +nightly-2026-02-27 miri test -p buffa -- <filter>`. The sysroot is already built. CI runs these filters under Miri: `size_cache`, `copy_into_spare`, `encode_sink::tests`, `contiguous_sink_`, `table::`, `owned_view_drop`, `owned_view_into_bytes` and `owned_view_lifetime_parametric_contract`. The view decoders, UTF-8 validation and the other `owned_view_*` tests run under Miri only when you run them. Adding `--target i686-unknown-linux-gnu` interprets the same tests as 32-bit code.
- **32-bit and `no_std`**: the `i686-unknown-linux-gnu` and `thumbv7em-none-eabihf` targets are installed, and `gcc-multilib` is present, so `cargo test -p buffa --target i686-unknown-linux-gnu` runs natively. `cargo check -p buffa --no-default-features --target thumbv7em-none-eabihf` type-checks the `no_std` build. That target cannot run tests, so the `no_std` conformance binary is the way to run `no_std` code.
- **Conformance**: `conformance_test_runner --failure_list conformance/known_failures.txt --maximum_edition 2024 conformance/target/release/conformance` runs the upstream protobuf suite. To run another mode, set one of `BUFFA_VIA_VIEW=1`, `BUFFA_VIA_LAZY=1`, `BUFFA_VIEW_JSON=1`, `BUFFA_VIA_REFLECT=1` or `BUFFA_VIA_VTABLE=1` on the same command, with the matching `conformance/known_failures_*.txt` list. For `no_std`, pass `conformance/target-nostd/release/conformance` and `conformance/known_failures_nostd.txt`. `conformance/run-conformance.sh` describes each mode, but it uses paths from another image, so do not run it. Use the suite to check that a proposed patch does not change wire behaviour.
- **Code generation**: `protoc` is installed at the version CI pins. The plugins are built at `target/debug/protoc-gen-buffa` and `target/debug/protoc-gen-buffa-packaging`, and `cargo build -p protoc-gen-buffa` rebuilds the first. Run one with `protoc --plugin=protoc-gen-buffa=target/debug/protoc-gen-buffa --buffa_out=<dir> <file>.proto`, or pipe a serialized `CodeGeneratorRequest` to its stdin. `buffa-build` drives `protoc` from a `build.rs`.

## How you rate severity

A finding counts when a program that uses only safe, documented API can be made to misbehave by input the attacker controls. The program may use the default limits and any cargo feature or codegen option that the entry-point list names.

- **Critical**: memory corruption or any other undefined behaviour reached by decoding, viewing, converting or re-encoding untrusted bytes. Examples are an out-of-bounds read or write, a use-after-free, a `&str` that holds invalid UTF-8, and a view that outlives its buffer.
- **High**: an unsound safe API that needs a particular but plausible pattern in the calling code and no hostile input. An input within the default limits that defeats them: unbounded memory or CPU amplification from a small message, or a stack overflow or other abort that the caller cannot catch. Generated code that contains something the schema did not describe, for example Rust injected through a crafted identifier, comment or option value.
- **Medium**: a panic reachable from untrusted input through a documented decode or serialize entry point, because it ends the task or the process. A parser differential: the same bytes decode to different values through the owned, view and reflective decoders, or buffa accepts input that the protobuf specification requires it to reject in a way that lets two parsers disagree about a message. A limit that undercounts by a bounded factor.
- **Low**: a panic, hang or excessive memory use in the code generator or plugins on a malformed schema or request. A defect that needs a non-default option meant for trusted input, such as a raised limit or `without_reader_size_limit`. A `debug_assert` failure with no release-mode consequence.

A conformance deviation with no security consequence is a bug and not a vulnerability; do not report it.

## How to report

- Give a reproducer that runs in this image: a Rust test that fails, or an input file plus the fuzz target or command that consumes it. For memory safety, include the AddressSanitizer or Miri output.
- Name the crate, the entry point, the cargo features and the `DecodeOptions` the reproducer needs, and say whether a release build is affected.
- Propose a minimal patch against `main` with a regression test next to the existing tests for that module. Keep unrelated refactoring out of it.
- Report one root cause once. The same flaw reachable through the owned and view decoders, or through several generated types, is one finding that lists each path.

## Anything to leave alone

- Decoding untrusted JSON or YAML into a generated message is not bounded by the `DecodeOptions` limits. `docs/guide.md` and the `buffa-yaml` crate documentation say so, and issue #330 tracks a limit for JSON. The YAML parser expands anchors and aliases, and `buffa-yaml/src/lib.rs` tells callers to bound the size of untrusted input.
- The owned and view decoders do not charge packed scalar fields against the element-memory limit. Their worst case is a 1-byte varint that becomes a 4-byte `i32`, and charging them would reject columnar payloads.
- `ReflectMessage::to_dynamic` and the `DynamicMessage::from_message` bridge scale their budgets to the encoded length, because they re-decode bytes that buffa has just encoded.
- Do not report memory or CPU use that stays within the documented default limits, or performance differences against other protobuf libraries.
- Anything under `#[doc(hidden)]` (`__private`, `__buffa_*`) is an interface between the runtime and generated code. Misuse by hand-written callers is out of scope; a fault that generated code can reach is in scope.
