# How we would like reports written

## Layout
Use the layout of the project's bug report issue template (`.github/ISSUE_TEMPLATE/bug_report.md`), with the same three headings in the same order, then three more sections for security reports.
Keep the whole report to about one page, plus the reproducer.

```
## Description
## Environment
## Steps to Reproduce
## Root Cause
## Impact and Severity
## Suggested Fix
```

### Description
Shortly describe the bug and what you expect instead: two or three sentences saying what the compiler does wrong and what a contract compiled with it does differently from its source.
State whether the compiler emitted any warning or error on the input; a silent miscompilation is much worse than one the compiler warns about.

### Environment
Fill in every line of the template's list.
Write "n/a" where a line does not apply, never leave one out.

```
- Compiler version: <full output of `solc --version`, including the commit hash>
- Compilation pipeline (legacy, IR, SSA CFG): <the ones that show the bug, and the ones tried that do not>
- Target EVM version (as per compiler settings): <value of --evm-version / settings.evmVersion, or "default (<name>)">
- Framework/IDE (e.g. Foundry, Hardhat, Remix): <normally "none (solc command line)" or "none (Standard JSON)">
- EVM execution environment / backend / blockchain client: <e.g. "evmone via soltest", or "n/a" for compile-time bugs>
- Operating system: <e.g. "Ubuntu 24.04 (scanner image)">
```

Add these lines after the template's list, since they decide how many contracts are affected:

```
- Optimizer: <on/off; --optimize-runs and custom optimizerSteps if they matter>
- ABI coder: <v1/v2, if it matters>
- Settings tried that do not show the bug: <list>
- Settings not tried: <list>
```

"IR" means `--via-ir`; "SSA CFG" means `--experimental --via-ssa-cfg`.
A statement like "only IR with the optimizer; legacy shows no bug; SSA CFG not tried" is more useful than leaving it out.

### Steps to Reproduce
- A *minimal* source example in a ` ```solidity ` (or ` ```yul `) block.
  Remove every contract, function, variable, modifier and statement not needed to trigger the bug.
- Every command-line flag needed, as one complete `solc` command, or the full Standard JSON input.
- Expected vs actual, concretely.
  For a miscompilation, show it at runtime: the call, the expected result and the actual result, in the semantic test notation our suite uses (`// f() -> 1`, `// g(uint256): 2 -> FAILURE`), ideally as a complete semantic test file.
- Where possible, a differential check: the same input with the optimizer off vs on, or legacy vs IR, giving different runtime results.
  Check `docs/frequently-reported-non-bugs.rst` first: some differences between the pipelines are documented and intentional.

### Root Cause
The file and function where the defect is, with the relevant lines quoted and their path relative to the repository root and line numbers.
If the bug comes from a recent change, name the commit.

### Impact and Severity
- The severity, with the reasoning from the threat model.
- Whether the input is code a real contract would plausibly contain, or only reachable with contrived or generated code.
- Whether the bug is in a released version or only in unreleased code on `develop`.
- If it resembles an entry in `docs/bugs.json` or one of the frequently reported non-bugs, say which and why this is different.

### Suggested Fix
A short description of the fix and any trade-off, such as bytecode or gas changes for unaffected programs.
The patch itself goes separately.

## Style
- One root cause per report.
  If several inputs hit the same defect, list them in one report.
- Title: `<Component>: <what goes wrong>`, using component names from `Changelog.md`, e.g. `Yul Optimizer: ...`, `Code Generator: ...`, `ABI Decoder: ...`, `Type Checker: ...`.
- Plain, factual language.
  Do not overstate impact: if loss of funds is not demonstrated, say what is demonstrated and what would still be needed for it.
- Do not include the template's HTML comments or its "Prerequisites" block.
