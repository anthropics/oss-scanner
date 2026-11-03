# Threat model: tokenizers

## What this project does and where untrusted input enters

tokenizers turns text into token ids and back for language models. `main` is the v1 rewrite: a Rust workspace under
`tokenizers/` (`tk-encode` runs the pipeline, `tk-serialize` reads and writes `tokenizer.json`, `tk-convert` upgrades
legacy configs, `tk-train` trains vocabularies, `bitcannon` is the SIMD pre-tokenizer) and PyO3 Python bindings under
`bindings/python/`. It runs inside inference servers, training pipelines and every `transformers` model load.

Two inputs are attacker-controlled:

- **The tokenizer config.** `tokenizer.json` files come from the Hugging Face Hub, uploaded by anyone, and are loaded
  through `Tokenizer.from_pretrained`, `from_file`, `from_str`, `tk_serialize::from_json` and `tk_convert::canonicalize_*`.
  Treat every field as hostile: vocabularies and merges (sizes, duplicates, ids out of range, empty or invalid UTF-8
  tokens), added and special tokens, normalizers (including the base64 `precompiled_charsmap`), pre-tokenizer regexes,
  post-processor templates, decoders, padding and truncation settings.
- **The text.** Inference servers encode end-user prompts with a trusted tokenizer. Treat any string, pair or batch
  passed to `encode`, `encode_batch` and `tokenize` as hostile, including invalid or adversarial Unicode, very long
  inputs and inputs crafted to hit SIMD block boundaries. Token ids passed to `decode` and `decode_tokens` come from a
  model, and may be out of range.

Training corpora (`tk-train`) and options a program sets on itself (padding, truncation, offsets) are lower priority.

## Components that matter most / least

Most important, in this order:

1. The encode path: `tk-encode/src` (models, normalizers, pre-tokenizers, the pipeline in `tokenizer/pipeline/`,
   vocab buckets, the word cache) and `bitcannon/src` (SIMD classification and bitstream pre-tokenization). Most of the
   `unsafe` code is here: `bitcannon/src/classify/{avx,neon,wasm}.rs`, `bitcannon/src/simd/`, `bitcannon/src/literal.rs`,
   `tk-encode/src/models/bpe/{model,tables}.rs`, `tokenizer/pipeline/{parallel,pre_tokenizer}.rs`.
2. Config loading: `tk-serialize/src/from_json/` and `vendored.rs`, `tk-convert/src/convert.rs`, and how loaded
   values reach the encode path (a config that the reader accepts must not later drive an index out of range).
3. Decoding and post-processing (offsets, special tokens, templates), and the Python bindings in
   `bindings/python/src/` (input conversion, NumPy arrays, threading).
4. `tk-train`.

The x86-64 scanner can run the scalar, SSSE3, AVX2 and (on a capable CPU) AVX-512 paths; the NEON and wasm paths must be
argued from the code. Out of scope: `bitmap_gen` (a code generator for checked-in tables), benches, `docs/`, the Node
and wasm bindings, CI configuration, and the stub generator under `bindings/python/tools/`. Flaws wholly inside a
dependency (fancy-regex, onig, rayon, serde_json, hf-hub) belong to that project unless tokenizers' use makes them
reachable.

## How to exercise it

The workspace is built in `/src/tokenizers` with all features, `CARGO_NET_OFFLINE` and `HF_HUB_OFFLINE` are set, and
the fixtures are in `/src/tokenizers/data` and `/src/bindings/python/data` (GPT-2, Llama 3, BERT, ALBERT, RoBERTa,
DeepSeek, Unigram and more).

- **Rust tests**: `cd /src/tokenizers && cargo test --workspace --no-fail-fast`. `bitcannon/tests/parity.rs` checks the
  SIMD pre-tokenizer against oniguruma, and `cargo test -p tk-convert --features bench-baseline --test oracle` compares
  encodings with the last released crate. Both are good differential oracles.
- **Python**: the bindings are installed into `/src/bindings/python/.venv` (on `PATH`). `cd /src/bindings/python &&
  pytest -m "not network" tests`. After a patch, rebuild with `maturin develop --release --uv`.
- **Quick driver**: `python -c 'from tokenizers import Tokenizer; t = Tokenizer.from_file("/src/tokenizers/data/llama-3-tokenizer.json").compile(); print(t.encode("..."))'`.

## How you rate severity

- **Critical**: memory corruption or out-of-bounds access reachable from input text with a well-formed tokenizer, or
  from a crafted `tokenizer.json`.
- **High**: a panic, abort, hang or unbounded memory use reachable from input text with a well-formed tokenizer (this
  takes down inference servers).
- **Medium**: a panic or hang from a crafted `tokenizer.json`; work superlinear in input length; out-of-range ids in
  `decode` that panic instead of erroring; a SIMD path that tokenizes differently from the scalar path or the oracle in
  a way that changes token boundaries.
- **Low**: excessive memory or time loading a large but well-formed config; panics in training on a crafted corpus.

## How to report

- Give the tokenizer file (a fixture or a minimal crafted one) and the exact text or ids, with the call and the observed
  result (ASan report, backtrace, timing against input size, or the diverging ids).
- Name the CPU features the reproducer needs if it only triggers on one SIMD path.
- Propose a minimal patch against `main` with a regression test. One root cause is one finding.

## Anything to leave alone

- Added and special tokens are matched in raw text by default, as in every prior release; text that contains
  `<|endoftext|>` encoding to its special id is documented behaviour, not injection.
- Intended behaviour changes from the 0.x releases (v1 is a rewrite, and the README lists features still to return)
  are not vulnerabilities; the oracle test is the reference for what must match.
- Memory proportional to a large vocabulary or input is expected.
- Hub download behaviour (authentication, caching, TLS) belongs to `huggingface_hub` and `hf-hub`.
