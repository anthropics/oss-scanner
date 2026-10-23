# Threat model

Vyper is a compiler for Ethereum smart contracts: it turns `.vy` source into
EVM bytecode. The deployed bytecode holds user funds and cannot be patched in
place, so the security property that matters is that **correct Vyper source
compiles to bytecode with exactly the documented semantics**. The project's
[SECURITY.md](https://github.com/vyperlang/vyper/blob/master/SECURITY.md)
describes the disclosure process and the Ethereum Foundation bug bounty
scope. One deliberate difference for this scanner: the bounty excludes the
experimental Venom pipeline (`--experimental-codegen`), but we **do** want
Venom findings here, since it is intended to become the default backend.
Venom-only bugs are capped at High (see severity below).

## Where untrusted input enters

The adversary is **not** the author of the contract. Contract source is
trusted; the attacker is a third party interacting with the deployed bytecode
(calldata, call value, returndata from external calls, storage contents,
reentrancy). A vulnerability is a compiler bug that lets such an attacker
violate what a careful reader of the source would expect, for example:

- miscompilation of arithmetic, comparisons, bounds checks, or overflow checks;
- ABI encoding/decoding bugs (wrong offsets, missing length/bounds validation
  on calldata or returndata, type confusion, dirty high bits in narrow types);
- memory or storage layout bugs: overlapping allocations, stale memory reuse,
  incorrect storage slot assignment, transient-storage aliasing;
- missing or bypassable `@nonreentrant` locks, wrong `@payable`/`msg.value`
  handling, wrong default-function or `__init__` dispatch;
- optimizer passes (legacy IR optimizer and the Venom pipeline in
  `vyper/venom/`) that change program semantics;
- wrong or missing reverts on failed external calls, `raw_call`, `create_*`,
  `extcall`/`staticcall`, or interface calls;
- incorrect evaluation order or side-effect elision.

## Components that matter most / least

- Highest priority: `vyper/codegen/` (legacy IR generation),
  `vyper/ir/` (IR optimizer and assembly), `vyper/venom/` (SSA IR and passes,
  enabled with `--experimental-codegen` / `--venom-experimental`; in scope
  here, unlike the bug bounty),
  `vyper/builtins/` (builtin function implementations), and
  `vyper/semantics/` where an analysis error lets unsafe code through
  (e.g. accepting a type conversion that should be rejected).
- Medium: `vyper/ast/` parsing/folding when it changes the meaning of
  accepted programs (e.g. constant folding producing a different value than
  runtime evaluation would).
- Low: `vyper/cli/`, `docs/`, `examples/`, source maps, and other
  developer-facing output. `tests/` is out of scope.

## How to exercise it

- `vyper contract.vy` compiles a file; `-f ir`, `-f ir_runtime`, `-f asm`,
  `-f bytecode_runtime`, `-f layout` show intermediate outputs.
  Add `--experimental-codegen` to go through the Venom pipeline.
- Runtime semantics are tested by compiling and executing contracts in an
  in-process EVM: see the `get_contract` / `env` fixtures in `tests/conftest.py`
  and `tests/evm_backends/` (py-evm and pyrevm backends). A proof of concept
  should be a pytest test in that style, or a small script using
  `vyper.compile_code` plus one of those backends, that deploys the contract
  and shows the unexpected behavior.
- `pytest -n auto -m "not fuzzing" tests/` runs the suite
  (`--experimental-codegen` runs it through Venom; `--optimize none|gas|codesize`
  selects the optimization level). The image installs the checkout editably
  into a `uv` virtualenv (`.venv/bin` is on `PATH`), so patches to `vyper/`
  apply immediately.
- `examples/` contains realistic contracts (tokens, auctions, wallets) that
  make good targets for end-to-end checks.

## How we rate severity

- **Critical**: a plausible, idiomatically written contract compiles, with
  the default (legacy) pipeline, to bytecode that lets an external caller
  steal or freeze funds, bypass access control, or otherwise break a safety
  property stated in the source (e.g. a bounds check or overflow check that
  is silently dropped, a reentrancy lock that does not lock,
  calldata/returndata decoding that accepts malformed input).
- **High**: miscompilation that produces wrong results or wrong reverts in
  realistic code but needs an unusual pattern to reach, or that an attacker
  can trigger only in uncommon configurations (specific EVM version or
  optimization level). Any bug reproducible only with
  `--experimental-codegen` (Venom) is at most High, since that pipeline is
  not yet recommended for production.
- **Medium**: semantic bugs reachable only through contrived source that no
  reasonable developer would write, or that only make a contract revert
  where it should succeed (denial of service of the contract, not fund loss).
- **Low / informational**: incorrect compiler diagnostics, source map or
  metadata errors, gas inefficiency, missing validation that only affects the
  contract author.

Please state the exact compiler version/commit, EVM version, optimization
level, and whether `--experimental-codegen` was used; several bugs are
specific to one pipeline.

## Not vulnerabilities

- Crashes, hangs, excessive memory use, or unhelpful error messages when
  the compiler is fed malicious or malformed **source**. The compiler is not
  a sandbox; whoever runs it chooses what it compiles.
- Programs that are rejected but should be accepted (false compile errors).
  Report them as ordinary bugs with low severity, not security findings.
- Behavior that is explicitly documented as unsafe for the contract author
  (e.g. `raw_call` with `revert_on_failure=False`, `unsafe_add`,
  `skip_contract_check=True`, `@nonreentrant` omitted on purpose).
- Gas-cost differences or missed optimizations.
- Bugs in dependencies (py-evm, pyrevm, lark, pycryptodome) unless Vyper's
  use of them is wrong.
- Already-published issues: check
  https://github.com/vyperlang/vyper/security/advisories and the open issue
  tracker before reporting.

## Reports

Include a minimal Vyper contract, a test or script that deploys it and
demonstrates the wrong behavior (ideally exits non-zero when vulnerable and
zero when fixed), the expected vs. actual behavior with reference to the
language docs, and a patch against `master` if available. A bisection to the
introducing commit is very helpful.
