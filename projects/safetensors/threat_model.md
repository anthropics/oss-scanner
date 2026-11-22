# Threat model: safetensors

## What this project does and where untrusted input enters

safetensors is a file format for tensors and the libraries that read and write it: a Rust crate (`safetensors/`) and
PyO3 Python bindings (`bindings/python/`) with helpers for PyTorch, NumPy, TensorFlow, Flax, Paddle and MLX. A file is
an 8-byte little-endian header length, a JSON header (per tensor: `dtype`, `shape`, `data_offsets`; plus an optional
`__metadata__` string map), then the tensor bytes.

The format exists so that model weights downloaded from strangers (the Hugging Face Hub and elsewhere) can be loaded
without running code, as pickle allows. **Treat every byte of a `.safetensors` file as attacker-controlled.** That
covers the header length, the JSON header (keys, dtypes, shapes, offsets, metadata, duplicate keys, ordering, unicode)
and the data section (its length, alignment, and whether offsets cover it exactly).

Entry points that take a file or its bytes:

- Rust: `SafeTensors::deserialize`, `SafeTensors::read_metadata`, `Metadata`, tensor views and the slicing API in
  `slice.rs`.
- Python: `safe_open` (both the `"mmap"` and `"pread"` backends), `get_tensor`, `get_tensors`, `get_slice` and its
  indexing, `get_tensor_meta`, `metadata`, `keys`, `offset_keys`, `deserialize`, and the framework helpers
  (`safetensors.torch.load`, `load_file`, `load_model`, and the NumPy and other equivalents).
- `PrefetchLoader` (`safe_open(...).prefetch(plan, device=..., threads=...)`): a plan of tensor names and slices is
  read by background threads into host or CUDA memory and handed out through DLPack.

The index a caller passes to `get_slice` and the plan passed to `prefetch` are caller input, but downstream libraries
build them from the (untrusted) header shapes, so they are in scope together with the file.

Writing (`serialize`, `serialize_file`, `save_file`, `save_model`) takes tensors from the caller, which are trusted;
the `metadata` dict passed to save is often copied from another file, so treat it as untrusted.

## Components that matter most / least

Most important, in this order:

1. `safetensors/src/tensor.rs`: header parsing and validation (length prefix, `MAX_HEADER_SIZE`, offset and size
   arithmetic, dtype sizes, shape products, overlap and coverage checks).
2. `safetensors/src/slice.rs` and the slicing code in `bindings/python/src/lib.rs`: index arithmetic over attacker
   shapes.
3. `bindings/python/src/`: `lib.rs` (`safe_open`, storage backends, conversion to framework tensors), `view.rs`,
   `dlpack.rs` (DLPack capsules and deleters), and `engine/unix.rs` (prefetch plan, reader threads, buffer lifetime).
   These hold most of the `unsafe` code.
4. `bindings/python/py_src/safetensors/*.py`: framework helpers, notably shared-tensor handling in `torch.py`.

Lower priority: `engine/cuda.rs` and `metal.rs` (CUDA and Apple Metal paths; this image has neither a GPU nor macOS,
so findings there have to be argued from the code), `engine/windows.rs` (a stub).

Out of scope: `attacks/` (demonstrations of pickle and other formats being unsafe), `bindings/python/convert.py` and
`convert_all.py` (tools that deliberately load pickle files to convert them), `benches/`, `docs/`, tests, CI
configuration, and the `stub.py` generator. Flaws wholly inside PyTorch, NumPy or another framework belong to that
project.

## How to exercise it

Everything is built in `/src`, `CARGO_NET_OFFLINE` is set, and the Python environment is `/opt/venv` (on `PATH`) with
CPU-only PyTorch, NumPy and pytest. The extension is installed from `/src/bindings/python` with `maturin develop`;
rebuild it after a patch with `cd /src/bindings/python && maturin develop --release --uv`.

- **Rust tests**: `cargo test --locked` in `/src/safetensors` and in `/src/bindings/python`. `proptest` is available.
- **Fuzzing**: `cd /src/safetensors && cargo +nightly fuzz run fuzz_target_1` (ASan; `fuzz/fuzz_targets/` has the
  target, which calls `SafeTensors::deserialize`). New targets can use any crate already in the cargo cache.
- **Python tests**: `cd /src/bindings/python && pytest tests/ --ignore=tests/test_tf_comparison.py
  --ignore=tests/test_flax_comparison.py --ignore=tests/test_paddle_comparison.py --ignore=tests/test_mlx_comparison.py`.
- **Crafting files**: write the 8-byte length, the JSON header and the data by hand (`struct.pack("<Q", n)`), then
  load with `safetensors.safe_open(path, framework="pt")` / `"np"` or `safetensors.torch.load(bytes)`.

## How you rate severity

A finding counts when loading or slicing a crafted file through the documented API misbehaves.

- **Critical**: code execution, or memory corruption (out-of-bounds write, use-after-free, double free) from a crafted
  file, a slice over it, or a prefetch plan built from its header.
- **High**: an out-of-bounds read; a tensor that silently holds bytes from outside its declared range or from another
  tensor; a tensor handed out with a wrong dtype, shape or stride that is not rejected; a DLPack capsule whose memory
  can be freed while still referenced.
- **Medium**: a panic, abort or hang from a crafted file (one that takes down the Python process rather than raising
  `SafetensorError` is at the top of this band); memory or time far out of proportion to the file's size.
- **Low**: a file the reader accepts that the format specification says must be rejected, with no further consequence;
  misleading errors.

## How to report

- Attach a minimal crafted file (or the Python that writes it) and the exact call that loads it, with the observed
  result (ASan report, backtrace, or the wrong tensor contents).
- Propose a minimal patch against `main` with a regression test (Rust unit test or pytest). Keep refactoring out.
- One root cause is one finding, even when several entry points reach it.

## Anything to leave alone

- Memory proportional to tensor sizes the file declares and actually contains is expected; a large file is not a DoS.
- With the `"mmap"` backend, another process truncating or rewriting the file while it is mapped (SIGBUS or changed
  contents) is a property of mmap, not a vulnerability.
- Headers up to `MAX_HEADER_SIZE` (100 MB) are allowed by design.
- `__metadata__` values are opaque strings; downstream code that interprets them is outside this project.
- Loading formats other than safetensors (pickle via `torch.load` in the conversion scripts) is unsafe by design and
  out of scope.
