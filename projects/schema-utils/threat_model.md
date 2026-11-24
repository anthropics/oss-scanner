# Threat model

This follows webpack's published threat model,
<https://github.com/webpack/security-wg/blob/main/docs/threat-model.md>.

## What this project does and where untrusted input enters

schema-utils validates an options object against a JSON Schema and, when the object does not match,
throws a `ValidationError` with a human-readable message. webpack validates its own configuration with it,
and almost every webpack loader and plugin (and webpack-dev-server, webpack-dev-middleware and others) calls
`validate(schema, options, configuration)` on the options it is given. It runs at build time, with the
developer's privileges. It is built on `ajv`, `ajv-formats` and `ajv-keywords`, with its own keywords
(`absolutePath`, `undefinedAsNull`, `formatMinimum`/`formatMaximum` and friends) and its own error
formatter. It can also precompile a schema into a standalone check module (`precompile()`,
`schema-utils precompile` in `bin/schema-utils.js`).

**Under webpack's threat model, every input schema-utils handles is trusted:**
- schemas, which the calling package's author writes;
- the `configuration` argument;
- the options being validated, which come from configuration, CLI flags, environment variables or inline
  loader options in the project's sources.

webpack trusts all of these. schema-utils takes no network input. So there is no known path for an attacker
to reach it, and a finding that needs control of any of these inputs is not a vulnerability.

Bugs are still worth reporting as robustness issues, as long as a real configuration could contain the
value:
- a crash, hang or super-linear slowdown on an options value;
- a precompiled check that accepts a value the full validation rejects;
- `undefinedAsNull` writing somewhere it should not.

These are not security vulnerabilities under webpack's model; they are rated Low and handled as normal
bugs.

## Components that matter most / least

- Most:
  - `src/validate.js` (validation entry point, error filtering);
  - `src/precompile.js` and `src/runtime.js` (generated check modules);
  - `src/keywords/` and `src/util/formats.js`;
  - `src/ValidationError.js` (message rendering).
- In scope: all of `src/`, `bin/schema-utils.js` with `src/cli.js`, and `declarations/` (generated types).
- Out of scope: `test/`, `.github/`, `.changeset/`, `.husky/` and the lint/format/build configuration
  files.
- Out of scope: other webpack-org repositories and schema-utils' dependencies (`ajv`, `ajv-formats`,
  `ajv-keywords`). A schema of a caller that is too permissive is that caller's bug.

## How to exercise it

- The image has the repository at `/src` with dependencies installed and `dist/` built, so
  `require("/src")` gives the public API (`validate`, `ValidationError`, `precompile`, ...) and
  `node /src/bin/schema-utils.js precompile [--check] [--minify] <schema.json>` writes
  `<schema>.check.js` next to the schema.
- A reproducer is a small Node.js script: a schema, an options value, a call to `validate`, and the
  thrown message or the mutated options printed. For precompiled checks, call `precompile(schema)`, load the
  module, and compare its verdict with `validate` without a check; `test/helpers/precompiled.js` shows how.
- `test/index.test.js`, `test/precompile.test.js`, `test/formats.test.js` and `test/large-errors.test.js`
  are good templates. `npm run test:only` runs the Jest suite (all of it passes offline, about 15 s). Avoid
  plain `npm test`, which runs the linters first, and `npm run security`, which needs the network.

## How you rate severity

- **Critical, High, Medium:** none expected, since no untrusted input reaches this package. A report at these
  levels must show a path by which network data reaches `validate` through webpack's dev tooling, with
  default or documented options.
- **Low:** robustness bugs that are not security vulnerabilities under webpack's model:
  - crashes, hangs, super-linear time (including ReDoS in schema-utils' own regular expressions and format
    comparators) or memory exhaustion from an options value;
  - a precompiled check disagreeing with full validation;
  - `absolutePath` misclassifying a path;
  - `undefinedAsNull` writing outside the options object.
- Not a vulnerability:
  - anything that needs control of the schema, the `configuration` argument, configuration files, CLI flags,
    environment variables, the project's sources or `node_modules`;
  - code that ajv generates from a schema;
  - `SKIP_VALIDATION` or `disableValidation()` turning validation off (by design);
  - option values quoted in error messages;
  - a message that is merely unhelpful or wrong;
  - Node.js or OS bugs.

## Anything to leave alone

- Dependency CVEs in `ajv`, `ajv-formats` or `ajv-keywords`. Report those upstream.
- Test fixtures under `test/fixtures/` contain deliberately broken schemas.
- Over-permissive or wrong schemas in packages that use schema-utils. Those belong to that package.

## How reports should look

Give a Node.js script run with `node` in `/src` that calls `require("/src")` with a minimal schema and
value and prints the result. For precompiled checks, include the schema, the generated module and both
verdicts. Label it as a robustness bug unless you can show a path from untrusted network input. A proposed
patch against `src/` is welcome, ideally with a test in `test/index.test.js` or `test/precompile.test.js`.
Plain text or Markdown.
