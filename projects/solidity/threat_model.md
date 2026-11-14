# Solidity compiler: threat model

## What the project is

`solc` compiles Solidity and Yul source into EVM bytecode.
That bytecode is deployed to public blockchains, where it usually holds or controls funds and cannot be changed after deployment.
The compiler matters for security because of **the code it emits**: a contract that behaves differently from its source can lose funds for everyone who uses it, and nobody can patch it afterwards.
How the `solc` process itself behaves (crashes, memory errors) is not what we are looking for.

The project's security policy (`SECURITY.md`) sets the scope: *only bugs that have a demonstrable security impact on smart contracts are in scope. For example, a Solidity program whose optimization is incorrect (e.g., leads to an incorrect output) qualifies as a security bug.*

## Attacker and where their input enters

The attacker is **a user of a deployed contract**.
They control calldata, call value, the order of transactions, and the contracts they call from (including reentrant calls back into the contract).
They exploit contracts that the compiler emitted incorrectly.
Bugs in the code the compiler generates to decode calldata, check bounds, do checked arithmetic or enforce types are reached by them directly.

The contract's source and compiler settings are trusted.
They are written by an honest developer, in ordinary code, who compiles and deploys the contract with the command line, Standard JSON settings, environment and filesystem of their choice.
The attacker controls none of these: their only input is the transactions they send to the deployed contract.
A finding must therefore start from source an honest developer would plausibly write, and show the transaction that makes the deployed contract misbehave.

## What the compiler guarantees

A finding is a vulnerability when the emitted code breaks one of these properties for a program that follows the language rules (see "Programmer's responsibility" below):

- **The optimizer does not change observable behaviour.**
  With the evmasm optimizer, the Yul optimizer, or any `optimizerSteps` sequence, the contract must give the same results as without it, compared where other code can observe them:
  - the storage and transient storage contents when the call ends successfully, and before every external call, `delegatecall`, `staticcall` or contract creation (the callee or a reentrant call can read them);
  - return data, whether the call reverts, and the revert data;
  - logs, in the same order with the same topics and data;
  - external calls and contract creations, in the same order, with the same target, value and input data;
  - `selfdestruct` and its beneficiary.
  Individual stores are not observable.
  Removing an `sstore` / `tstore` that is overwritten before anyone can read it or that is followed only by a revert, removing a store of a value already in the slot, and removing, merging or reordering memory writes are all correct optimizations, not bugs.
  Gas usage may change, and so may behaviour that depends on gas (`gasleft()`, the gas forwarded to calls, running out of gas).
- **Checks the language promises are emitted.**
  The following panics documented in `docs/control-structures.rst` must happen when their condition holds, and not otherwise: arithmetic overflow/underflow outside `unchecked` (0x11), division or modulo by zero (0x12), out-of-range enum conversion (0x21), invalid storage byte array encoding (0x22), `.pop()` on an empty array (0x31), out-of-bounds index (0x32), too large memory allocation (0x41), calling a zero-initialized internal function variable (0x51).
  The same holds for `require`, `revert` and custom errors.
- **ABI decoding is safe.**
  Generated decoders never read beyond `calldatasize()` (or beyond the returned data for return values) and validate values of types narrower than 32 bytes as documented.
  Encoders produce the encoding the ABI specification describes.
- **Data locations are respected.**
  Writes go only to the storage slots, transient storage slots, memory and calldata the source refers to.
  Copies between storage, memory and calldata copy, and clean up, exactly what the language says.
  Storage and transient storage layouts match the documented layout (`storageLayout` output) so that upgrades and inheritance work.
- **`view` / `pure` and call semantics.**
  When the target EVM version is Byzantium or later, calls to `view` and `pure` functions of other contracts use `STATICCALL` (on earlier versions they use `CALL`, as documented in `docs/050-breaking-changes.rst`); `delegatecall`, `call`, `try`/`catch` and function selectors behave as documented.

## What matters most

1. Optimizers: the Yul optimizer (`libyul/optimiser/`) and the evmasm optimizer (`libevmasm/`).
   Most high-severity bugs in `docs/bugs.json` are here.
2. Code generation: legacy (`libsolidity/codegen/`) and via-IR (`libsolidity/codegen/ir/`, Yul to EVM code transform in `libyul/backends/evm/`), including stack layout and spilling to memory.
3. ABI encoder and decoder generation (`libsolidity/codegen/ABIFunctions.cpp`, `libsolidity/codegen/YulUtilFunctions.cpp`).
4. Storage, transient storage and memory layout; copying and cleanup between data locations.
5. Type checking and other analysis (`libsolidity/analysis/`) that, if wrong, lets a program compile that the language says is invalid, with code that does something unexpected.

The settings that a bug needs determine how many contracts it reaches.
Every finding must state them: optimizer on/off, legacy or `viaIR`, target `evmVersion`, ABI coder version, and custom `optimizerSteps` if used.
`docs/bugs.json` shows how the project records them.

## Programmer's responsibility (not compiler bugs)

The language leaves some behaviour to the programmer.
Code that breaks these rules has undefined or unspecified behaviour, and whatever the compiler emits for it is not a bug:

- Inline assembly marked `memory-safe` that accesses memory outside what `docs/assembly.rst` allows.
  The optimizer is entitled to rely on the annotation.
- `verbatim` bytecode that breaks the restrictions listed in `docs/yul.rst`.
- Writing through dangling references into storage arrays (`docs/types/reference-types.rst`, `docs/frequently-reported-non-bugs.rst`).
- Depending on the evaluation order of expressions, which is unspecified apart from statement order and short-circuiting of `&&` and `||`.
- Depending on the legacy and via-IR pipelines agreeing where `docs/ir-breaking-changes.rst` documents that they differ (for example cleanup behaviour).
- Expecting non-canonical ABI-encoded calldata to be rejected: the decoder does not enforce strict encoding; it only guarantees not to read beyond `calldatasize()`.

The reverse is in scope: if a program follows these rules (for example its assembly really is memory-safe) and the compiler still breaks it, that is a bug.

## Severity

The project rates its own published bugs (`docs/bugs.json`, definitions in `docs/bugs.rst`) by *discoverability in contract tests, likelihood of occurrence and potential damage by exploits*.
Use the same three factors here.
Rate by what the attacker can achieve by sending transactions, and by how likely honest contracts are to contain the triggering code.
A silent miscompilation (no error, no warning) is always worse than one the compiler warns about.

- **Critical**: silent miscompilation triggered by ordinary, commonly written code under default or widely used settings, that is unlikely to be caught by normal contract tests, and where loss of funds or broken access control is a plausible result.
- **High**:
  - silent miscompilation with plausible security impact that needs a less common but realistic code pattern or setting (for example `viaIR` with the optimizer, or a specific EVM version);
  - generated ABI decoding that reads beyond `calldatasize()` or skips a documented validation.
- **Medium**:
  - miscompilation that needs unusual code to trigger, or with limited effect (for example a missing revert on a rare path, or wrong gas use that can make a function always run out of gas);
  - analysis that accepts a program the language says is invalid, when the resulting code behaves unexpectedly and the attacker can trigger it.
- **Low**:
  - miscompilation that is very hard to reach from real code, or that the simplest test of the affected contract would catch;
  - compiler crashes on input a real contract would plausibly contain (see below).

**Experimental features**: rate one level lower, and at most medium, when the bug only occurs with an option that needs `--experimental` (the list is `experimentalOptionNames()` in `solc/CommandLineParser.cpp`: `--import-ast`, `--import-asm-json`, `--via-ssa-cfg`, the `ir-ast-json`, `ir-optimized-ast-json` and ethdebug outputs) or with an experimental EVM version (newer than the current default, see `EVMVersion::isExperimental()` in `liblangutil/EVMVersion.h`).
In Standard JSON the same features (`viaSSACFG`, the `irAst`, `irOptimizedAst` and ethdebug outputs, `SolidityAST` / `EVMAssembly` input, experimental EVM versions) need `settings.experimental: true`; rate them the same way.

**Unreleased code**: the scanned branch is `develop`.
If the faulty code is not in any release yet (its change is listed under the `(unreleased)` heading at the top of `Changelog.md`, or is not in the latest release tag), say so.
Keep the severity the bug would have once released; we want to fix it before it ships.

## Not vulnerabilities

Do not report these at all:

- **Memory-safety defects in the `solc` process**: segmentation faults, out-of-bounds reads or writes, use-after-free, null dereferences, and AddressSanitizer or other sanitizer reports.
  Report one only if it changes the emitted bytecode, as a miscompilation.
- Wrong or missing error messages and warnings, wrong source locations, cosmetic issues in output such as the AST JSON or assembly text.
- Higher gas usage than expected, unless it can make a contract unusable (see medium above).
- Miscompilations that only source written on purpose to trigger them would hit, such as deliberately hidden backdoors or underhanded code.
  The source is trusted; if no honest developer would write the triggering code, no deployed contract is exposed to the attacker.
- Anything that needs control of the source, the compiler's command line, settings, environment, filesystem or import callback.
  This includes reading files outside the allowed paths (`docs/path-resolution.rst`, *Allowed Paths*): the developer running `solc` chooses `--allow-paths`, remappings and the callback.
- Problems with reproducibility or metadata (non-deterministic bytecode, a setting missing from the metadata), unless the bytecode itself is also miscompiled.
- The SMTChecker and other formal verification results being wrong or incomplete.
  They are analysis aids and do not change the emitted bytecode.
- Bugs in third-party dependencies (Boost, nlohmann-json, fmt, range-v3, Z3, CVC5, Eldarica) unless they cause a Solidity-specific bug as above.
- Tools that are not the compiler: test drivers (`soltest`, `isoltest`), fuzzers, `yulrun`, scripts and documentation.
- Anything in "Programmer's responsibility" above.
- Anything already listed in `docs/bugs.json`, or already fixed in `Changelog.md`.

Report these as low at most:

- **Internal compiler errors (ICEs), failed `solAssert` / `yulAssert`, uncaught exceptions, stack overflows, timeouts and excessive memory use.**
  When the compiler stops, no bytecode is produced, so no contract is affected.
  Report one only if the input is something a real contract would plausibly contain.

## Testing in this image

- Compiler: `/src/build/solc/solc`.
  Compare the bytecode or runtime behaviour across `--optimize`, `--via-ir` and `--evm-version` settings to find miscompilations.
- Runtime behaviour: write a semantic test (format of the files under `test/libsolidity/semanticTests/`) and run it with `/src/build/test/soltest -t 'semanticTests/<dir>/<name>' -- --testpath /src/test`.
  It runs on evmone (`/usr/lib/libevmone.so`, also in `$ETH_EVMONE`).
  By default a semantic test runs on both the legacy and via-IR pipelines; add `--optimize` after `--` to enable the optimizer, and `--evm-version <name>` to change the target.
- Yul optimizer steps can be tested on their own with the tests under `test/libyul/yulOptimizerTests/`, run by `soltest -t 'yulOptimizerTests/<step>/*'`.
