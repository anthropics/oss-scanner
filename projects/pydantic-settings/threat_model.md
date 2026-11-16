# Threat model: pydantic-settings

## What this project does and where untrusted input enters
pydantic-settings loads application settings into Pydantic models. A `BaseSettings` class reads its fields
from several sources and merges them by priority: init arguments, environment variables, dotenv files,
secrets directories, command-line arguments, JSON, TOML, YAML and `pyproject.toml` files, and cloud secret
managers (AWS Secrets Manager and Systems Manager, Azure Key Vault, GCP Secret Manager).

Most of this input is operator-controlled and trusted: the settings classes, their configuration, the
process environment and the configuration files the application names. Input that can be untrusted is:
- Command-line arguments, when an application built with `CliApp` or `cli_parse_args` is started by a less
  trusted user or wrapper.
- The values of settings, when a deployment lets a less trusted party set some environment variables,
  secret files or secret-manager entries but not others.
- The content of a secrets directory mounted from elsewhere (file names, symlinks, sizes).

## Components that matter most
1. **Secrets directories**: `pydantic_settings/sources/providers/secrets.py`, `nested_secrets.py`. Of
   interest: a symlink or a file name that makes the source read a file outside the secrets directory, a
   `secrets_dir_max_size` limit that can be bypassed, and nested layouts that read more than they should.
2. **Environment and dotenv**: `sources/providers/env.py`, `dotenv.py`, `sources/base.py`, `sources/utils.py`.
   Of interest: a variable that sets a field it should not reach (prefix, nested delimiter, alias or case
   handling that lets one name shadow another), and complex values decoded in a way the documentation does
   not describe.
3. **Command-line parsing**: `sources/providers/cli.py`. Of interest: arguments that set a field
   through a name the documentation does not describe, that reach `eval`-like behaviour, or that make
   parsing take super-linear time.
4. **Source priority and merging**: `pydantic_settings/main.py`. Of interest: a lower-priority source that
   overrides a higher-priority one, against the documented order.
5. **Secret exposure**: every source. Of interest: secret values written to logs, warnings, `repr()` output
   or exception messages that the documentation says do not contain them.

Also in scope, but less important: the file sources (`json.py`, `toml.py`, `yaml.py`, `pyproject.py`) and the
cloud sources (`aws.py`, `azure.py`, `gcp.py`).

## How to exercise it
- `tests/` is a pytest suite. Run `pytest tests` from `/src`. Every extra is installed; the cloud sources
  are tested with mocks and need no network.
- PoCs should be a few lines: a `BaseSettings` subclass, an environment set with `monkeypatch.setenv` or a
  `tmp_path` directory, and one instantiation.

## How we rate severity
- **Critical**: code execution from a setting value, a file name or a command-line argument.
- **High**: a secrets directory source that reads a file outside its directory; a less trusted source that
  sets a field the documented rules keep out of its reach.
- **Medium**: secret values disclosed in logs, warnings or errors against the documentation; a small
  command-line or setting value that takes CPU or memory far out of proportion to its size.
- **Low**: crashes with a clean Python exception, and cost that grows linearly with the input.

## Anything to leave alone
- An attacker who controls the whole environment, the configuration files or the settings class: they
  already control the application.
- Validation itself, which belongs to Pydantic (`pydantic/pydantic` has its own threat model in
  `SECURITY.md`), and vulnerabilities in `python-dotenv`, `PyYAML` or the cloud SDKs themselves, unless
  pydantic-settings uses them in an unsafe way.
- Validation errors that include the invalid input: this is Pydantic's default, and `hide_input_in_errors`
  turns it off.
- `docs/`.
