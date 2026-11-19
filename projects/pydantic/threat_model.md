# Threat model: Pydantic

The maintainers' threat model is the "Threat model" section of `/src/SECURITY.md`. Read it first: it defines
the trust boundaries, the scope and the denial-of-service bar, with examples. This file summarises it and
adds what the scanner needs. Where the two differ, `SECURITY.md` wins.

## What this project does and where untrusted input enters
Pydantic is a data validation library. This repository holds two packages:
- `pydantic` (`pydantic/`): builds a core schema from type hints (models, dataclasses, `TypeAdapter`).
- `pydantic-core` (`pydantic-core/`): the Rust implementation of validation and serialization, exposed to
  Python with PyO3. It parses JSON itself, with the `jiter` crate.

The only untrusted input is the data being validated, when it is user-controlled:
- Every JSON input (`model_validate_json()`, `validate_json()`).
- Python input made only of native types: `dict`, `list`, `tuple`, `str`, `bytes`, `int`, `float`, `bool`
  and `None` (`model_validate()`, `validate_python()`).

Everything the application defines is trusted: type hints, schemas, configuration, custom validators and
serializers, custom types, and instances of any type other than the native ones above.

## Components that matter most
1. **Validators**: `pydantic-core/src/validators/` and `pydantic-core/src/input/` (Python, JSON and string
   inputs), `pydantic-core/src/url.rs`, `pydantic-core/src/lookup_key.rs`, and the Python validators in
   `pydantic/_internal/_validators.py`, `pydantic/types.py` and `pydantic/networks.py`. Of interest:
   - **Validation bypass**: input accepted that the schema and the documented behaviour reject (a constraint
     such as `max_length`, `gt`, `pattern` or `strict` not enforced; a discriminated union or an `extra='forbid'`
     model that lets data through). Coercions in lax mode are documented and are not bypasses.
   - **Denial of service**: validation time or memory that grows super-linearly with the input size, and is
     significant in practice, for a schema that could plausibly exist in production.
2. **Memory safety in pydantic-core**: all of `pydantic-core/src/`, including `serializers/`. Unsound `unsafe`
   code or PyO3 misuse that leads to memory corruption is in scope whatever the component or input,
   including reference-count errors, use-after-free with re-entrant Python callbacks, and garbage collection
   (`py_gc.rs`).
3. **Recursion and nesting**: `pydantic-core/src/recursion_guard.rs` and deeply nested JSON. A stack overflow
   that crashes the interpreter from user-controlled input is in scope.

## How to exercise it
- Run `pytest tests` from `/src` for both packages; `tests/pydantic_core/` and `pydantic-core/tests/` cover
  the Rust core. `pytest tests/pydantic_core -x -q` is the fast loop.
- The image builds pydantic-core with the `dev` profile: unoptimized, with debug info, debug assertions and
  overflow checks. A panic that only a debug assertion or an overflow check raises must be confirmed on a
  release build before it is reported: `cd /src/pydantic-core && maturin develop --uv --release`. Every
  crate is already fetched, and `CARGO_NET_OFFLINE=true` is set.
- PoCs should be a few lines: a `TypeAdapter` or a `BaseModel`, and one call to `validate_json()` or
  `validate_python()`. Follow the reporting rules in `SECURITY.md`: a minimal reproducible example, and the
  section of the threat model the issue falls under.

## How we rate severity
- **Critical**: memory corruption in pydantic-core reachable from user-controlled input with a schema that
  could plausibly exist in production.
- **High**: a validation bypass, or a super-linear denial of service that meets the bar in `SECURITY.md`,
  with a common schema and the default configuration; an interpreter crash (stack overflow, abort) from
  user-controlled input.
- **Medium**: the same issues when they need an unusual but documented schema or option; memory corruption
  that needs application-defined objects or trusted schemas to trigger.
- **Low**: a Rust panic that surfaces as a Python `PanicException`, with no memory corruption.

## Anything to leave alone
`SECURITY.md` lists these as out of scope, except for memory corruption:
- Serialization and JSON Schema generation: they work on data and schemas the application defines.
- Schemas, configuration or type hints built from untrusted data (`create_model()`, a `pattern` from user
  input).
- Code the application provides: custom validators and serializers, `__get_pydantic_core_schema__()`.
- `@validate_call`, and private or undocumented APIs.
- Validation cost that grows linearly with the input, even with a large constant; super-linear cost inherent
  to a schema that does not follow best practices (recursive untagged unions) or to the object produced
  (a `dict` or `set` built from colliding integers).
- Crafted instances of non-native types passed as Python input.
- `pydantic/mypy.py`, `docs/`, `release/` and `pydantic-core/wasm-preview/`.
