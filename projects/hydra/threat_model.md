# Hydra threat model

## Purpose and downstream importance

Hydra composes hierarchical configuration, parses command-line overrides,
instantiates Python objects, and orchestrates application runs and parameter
sweeps. It is used in machine-learning training, research, and other configurable
Python applications. Configuration errors or boundary violations can affect the
files, credentials, compute resources, and processes of those applications.
Hydra uses OmegaConf for configuration containers, YAML, and interpolation.
No current download count or criticality score is asserted here.

## Inputs and trust boundaries

Review the current checkout's `website/docs/advanced/execution_whitelist.md`
and `website/docs/advanced/execution_whitelist/authorization_rules.md` first.
Declarative instantiation configuration can be untrusted. Installed Python code,
logging configuration, live Python objects supplied by trusted callers, and
execution-whitelist policy supplied by trusted Python code are trusted. Hydra
is not a general Python sandbox, a network service, or a filesystem sandbox.
Remote exposure depends on a downstream application accepting attacker input.

Inputs include YAML configuration, defaults lists, CLI overrides, interpolation,
config-source paths, and selected targets and arguments. Describe which of these
the attacker controls; do not silently give the attacker control over trusted
Python code, installed packages, logging configuration, or policy.

Object creation and invocation of authorized callables are intended capabilities.
The current execution policy restricts configured names, resolved identities,
indirectly selected callables, callable results, and deferred partial invocation.
Exact-name authorization deliberately supports public re-exports; wildcard
authorization has different canonical-identity checks. Evaluate behavior against
the documented rules, not an assumed blanket prohibition on Python execution.
`UNSAFE_DISABLE_EXECUTION_CHECKS` deliberately opts out for trusted configurations.
A demonstration relying on that opt-out is not by itself a policy bypass.

Direct calls to `get_class`, `get_method`, `get_static_method`, and `get_object`
require trusted paths and do not enforce the execution policy; their use as
instantiation targets has additional authorization checks. Logging configuration
is trusted, and the whitelist does not restrict log-file destinations. Calls to
Python logging APIs made directly by application code are outside Hydra's policy.
Config search paths, output paths, plugins, resolvers, and permitted functions can
intentionally read/write files or execute application code. Show a violated
documented restriction before classifying such behavior as a vulnerability.

## Review priorities and scope

Prioritize execution authorization and its propagation into launched jobs,
instantiation and partials, logging integration, config loading/composition,
override parsing and completion, and interpolation at the OmegaConf boundary.
Look for policy bypasses from declarative input without changing trusted code,
unexpected shell interpretation, unintended disclosure, and disproportionate
resource consumption. Report prerequisite configuration and practical impact.
Do not execute cloud/scheduler launchers against real infrastructure.

Core library code in `hydra/` is the primary runtime scope. First-party plugins
under `plugins/` are relevant but have separate dependencies and tests; the base
image does not claim to exercise all plugin backends. Website presentation,
release tooling, and third-party dependency internals are secondary to shipped
runtime paths. Distinguish dependency defects from Hydra integration defects.

## Reproduction and severity guidance

The checkout is at `/src`, with an editable installation, development dependencies,
Java for parser generation, and shells/expect for completion tests. Run
`python -m pytest -q` from `/src` with networking disabled. Focused entry points
include `tests/instantiate/`, `tests/test_logging_config.py`,
`tests/test_overrides_parser.py`, and `tests/defaults_list/`.
Standalone app and optional plugin environments are separate from this core run.

Provide a minimal deterministic local reproducer, affected revision and API,
attacker-controlled fields, required trusted setup, expected documented behavior,
and actual impact. Use temporary files and dummy secrets; no external targets.
Propose a regression test and a small fix preserving supported capabilities.
Treat unauthorized execution across an enforced policy as potentially high
severity; reserve critical for demonstrated realistic broad compromise.
Assess disclosure and writes by the privileges/data actually exposed. Assess DoS
by input size, work amplification, and exposure in a real consuming application;
ordinary invalid-input exceptions or large trusted workloads are not sufficient.
These are triage proposals, not a pre-existing project severity policy.

## Source baseline

Prepared against public commit `5fe65a1973d74a4c77d4c647d131532018478c62`.
Enrollment follows the default branch; re-read its documentation if it changes.
