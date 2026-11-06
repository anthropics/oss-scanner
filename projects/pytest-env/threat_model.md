# Threat model

The reporting policy is `.github/SECURITY.md`. Use GitHub private vulnerability reporting or the Tidelift contact
described there, not a public issue.

## What pytest-env does and where untrusted input enters

pytest-env is a pytest plugin that reads environment assignments from pytest configuration and optional dotenv files,
then changes `os.environ` before test collection. INI entries support replacement, `D:` skip-if-set, `R:` raw values and
`U:` removal. TOML provides the same operations as fields. Values may format against the existing environment.
`--envfile` selects or extends configured dotenv files, and `--pytest-env-verbose` prints every action in the pytest
header.

Pytest configuration is code-adjacent and trusted in the standard workflow. The same checkout can load `conftest.py` and
plugins with arbitrary process privileges, so a repository choosing `PATH`, `PYTHONPATH`, a dotenv path or a formatted
secret has not escaped a sandbox. A service that treats pytest configuration as inert data must establish and document
that separate boundary.

The plugin still owns parsing and precedence. Inputs to test include:

- `env` entries from INI files and `[pytest_env]` entries from `pytest.toml`, `.pytest.toml` or `pyproject.toml`;
- flag combinations, empty and Unicode names, duplicate assignments, braces, missing format keys, long values and
  removals;
- dotenv filenames, contents, quoting, interpolation, encoding and duplicate keys;
- pytest's configuration path, root path, parent directories and `--rootdir`;
- process-environment values read during formatting or protected by skip-if-set;
- values printed when the user enables verbose reporting.

## Components to prioritize

All installed behavior is in `src/pytest_env/plugin.py`. Follow `pytest_load_initial_conftests` through TOML discovery,
dotenv loading and inline entry application. TOML, INI and CLI precedence must match the documentation.
`env_files_skip_if_set` takes its baseline before pytest-env applies any dotenv file; `skip_if_set` entries observe the
environment at their point in the ordered stream. A report should identify the violated guarantee rather than assume a
different precedence.

Review `_find_toml_config` and `_load_env_files` for root selection and parent traversal. The user trusts an explicit
CLI path and a configuration-selected dotenv path in an ordinary pytest run, but path confusion can matter when a caller
has constrained configuration to one project root.

Formatting uses `entry.value.format(**os.environ)`. Test missing keys, braces and error messages, but remember that a
configured field can request any existing environment key by design. Verbose mode prints names and values by design;
exposing a value under `--pytest-env-verbose` is not a secret leak unless the report shows a separate promise to redact
it.

`python-dotenv` and pytest configuration discovery are dependencies. Attribute a finding to pytest-env when its path
choice, merge order or diagnostics create the impact.

## How to exercise the image

The checkout is at `/src`, installed in `/opt/venv` with its test group. Run `python -m pytest tests`. Most tests use
`pytester` to launch an isolated pytest process.

Build a temporary project with one configuration file, controlled parent directories and placeholder secrets. Assert on
the child process environment and header output. Cover INI and TOML as distinct cases because their syntax and defaults
differ. Restore the parent environment after each test.

## Severity

- High: a documented caller that treats pytest configuration as non-executable data suffers code execution or reads an
  unrelated credential file through pytest-env. Name the caller and the containment guarantee; a normal pytest checkout
  has no such boundary.
- Medium: pytest-env selects configuration or a dotenv file outside a caller-enforced root, changes a variable despite
  the applicable skip-if-set rule, or includes an existing secret in an error path that did not request verbose value
  output.
- Low: a crash, incorrect assignment or unexpected precedence confined to the test process, with no privilege or
  confidentiality boundary.

## Reports and exclusions

Include the pytest-env commit, pytest command, configuration format and path, root path, initial environment, dotenv
files and final environment. State whether the user enabled verbose mode and which configuration source pytest selected.

Do not report:

- arbitrary behavior from tests, `conftest.py` or another plugin;
- a repository assigning or removing a dangerous variable by design;
- documented lookup of an environment key during formatting;
- values printed because the user selected `--pytest-env-verbose`;
- a defect in pytest or python-dotenv that reproduces without pytest-env.
