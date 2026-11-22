# OmegaConf threat model

## Purpose and downstream importance

OmegaConf provides hierarchical Python configuration with YAML loading/saving,
merging, typed/structured containers, interpolation, and registered resolvers.
Hydra directly depends on OmegaConf, so parsing and interpolation behavior also
affects configurable applications and machine-learning workflows using Hydra.
No current download count or criticality score is asserted here.

## Inputs and trust boundaries

Inputs include YAML strings/files, dictionaries/lists, dot-list updates, key paths,
interpolation expressions, and structured-config values. Some applications accept
these from less-trusted sources. OmegaConf is a library, not a network endpoint:
state how an attacker reaches the API in the proposed deployment.

YAML loading should not grant arbitrary Python object construction or execution.
Review the actual loader and its supported compatibility tags rather than assuming
all Python-looking YAML tags are either safe or forbidden. YAML alias expansion
has explicit limits; see `website/docs/reference/yaml-alias-limits.md`. The current
default caps expanded nodes at 10,000 and also rejects over-100-fold expansion
above 1,000 nodes. Recursive aliases are rejected even when the expansion limit
is disabled. Caller/environment opt-outs and higher limits are trusted choices;
a reproducer should preserve defaults unless testing a specific supported limit.
These protections are not a universal memory or CPU quota for all inputs.

Interpolation can read other configuration values and call registered resolvers.
Resolvers are Python code registered by the application and can have side effects.
The built-in `oc.env` intentionally reads process environment variables, and
`oc.create` constructs configuration from data. `oc.coerce` supports imported
type/enum paths; the documentation explicitly warns that imports can execute
module top-level code and require trusted configs. See
`website/docs/reference/built-in-resolvers.md` and
`website/docs/guides/custom-resolvers.md`. OmegaConf does not promise that arbitrary
resolver expressions are a sandbox or that environment access is secret-isolated.
Identify an actual boundary violation rather than reporting these documented
capabilities alone as execution or disclosure bugs.

Installed modules, registered resolver implementations, structured-config classes,
and arbitrary live Python objects allowed explicitly by the caller are trusted.
Pickle deserialization requires trusted data; see
`website/docs/guides/load-and-save.md`. Do not classify malicious pickle execution
or a deliberately dangerous user resolver as an OmegaConf vulnerability by itself.
Read-only and struct flags govern config mutations, not isolation from Python code
already executing in the same process. OmegaConf is not a filesystem sandbox.

## Review priorities and scope

Prioritize YAML construction and alias/merge expansion limits, parser and
interpolation evaluation, recursion/cycle handling, key-path traversal, merge
semantics, structured validation, and resolver dispatch/cache behavior in
`omegaconf/`. The vendored ANTLR runtime participates in the shipped parser;
distinguish upstream runtime defects from integration errors. Check that invalid
input fails predictably without unintended execution or excessive amplification.

Developer debugger integration in `subprojects/` has separate dependencies and is
not exercised by the core image. Website presentation and release/developer
automation are secondary to runtime library entry points. Do not invoke publishing
or external infrastructure. Downstream application misuse and vulnerabilities in
unrelated third-party libraries require separate attribution.

## Reproduction and severity guidance

The checkout is at `/src`, installed editable with development dependencies and
Java for generating the parser from the bundled ANTLR jar. Run
`python -m pytest -q` from `/src` with networking disabled. Tests in `tests/`,
including `tests/interpolation/`, provide configurations and regression examples.

Provide an offline minimal reproducer with affected revision/API, exact input,
attacker control, resolver registrations and nondefault flags, observed result,
and realistic downstream impact. Use temporary files and dummy environment data.
Include a focused regression test and preserve supported configuration semantics.
Unexpected execution from ordinary data-only loading is potentially high severity;
reserve critical for demonstrated realistic broad compromise. Assess unintended
disclosure or mutation by the actual protected data and boundary. Rank DoS by
input size, amplification, and reachable deployment, not merely the ability to
trigger an exception. These are proposed triage guidelines, not an established
project severity policy.

## Source baseline

Prepared against public commit `329fc49498c9f782643a7a0f7b02f6c5678cd06d`.
Enrollment follows the default branch; re-read its documentation if it changes.
