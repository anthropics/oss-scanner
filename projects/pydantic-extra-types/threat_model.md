# Threat model: pydantic-extra-types

## What this project does and where untrusted input enters
pydantic-extra-types is a set of extra types for Pydantic: phone numbers, payment card numbers, colors,
coordinates, country, currency, language and script codes, IBAN, ISBN, ISIN, routing numbers, MAC addresses,
domains, DSNs, S3 paths, semantic versions, ULIDs, UUIDs, MongoDB object IDs, cron expressions, MIME types,
time zone names, epochs and Pendulum date-times. Each module in `pydantic_extra_types/` is one type or one
small family of types.

Applications use these types as fields of models that validate request data, so assume the value being
validated is attacker-controlled: any JSON input, and Python input made of native types (`str`, `bytes`,
`int`, `float`, `dict`, `list`, `tuple`). Everything the application defines is trusted: the models, the
type parameters and constraints, and the configuration. This is the same boundary as Pydantic's own threat
model (`SECURITY.md` in `pydantic/pydantic`).

## Components that matter most
1. **Hand-written parsers and regular expressions**: `color.py`, `coordinate.py`, `domain.py`, `dsn.py`,
   `s3.py`, `mac_address.py`, `semantic_version.py`, `mime_types.py`, `epoch.py`. Of interest:
   - **Denial of service**: a short string that makes validation take super-linear time (regular expression
     backtracking, repeated slicing or copying) or a number that is expensive to convert.
   - **Validation bypass**: a value accepted that the type documents as invalid, where an application would
     rely on the check. Examples: a domain or an S3 path with control characters, newlines or a trailing
     component the parser ignores; coordinates outside their bounds; a color that parses to out-of-range
     channels.
2. **Checksums and number formats**: `payment.py` (Luhn check, brand and length), `iban.py`, `isbn.py`,
   `isin.py`, `routing_number.py`. Of interest: numbers that pass with a wrong checksum, length or character
   set.
3. **Wrappers around other libraries**: `phone_numbers.py` (`phonenumbers`), `country.py`, `currency_code.py`,
   `language_code.py`, `script_code.py` (`pycountry`), `semver.py`, `ulid.py`, `uuid_types.py`, `cron.py`,
   `pendulum_dt.py`, `timezone_name.py`, `mongo_object_id.py`, `pandas.py`. Of interest: the wrapper accepting
   input that the wrapped library rejects, or passing input to it in an unsafe way.

## How to exercise it
- `tests/` is a pytest suite with one file per type. Run `pytest tests` from `/src`. Every extra is installed.
- PoCs should be a few lines: `TypeAdapter(TheType).validate_python(value)` or `validate_json(value)`, with
  a timing loop over growing input sizes for a denial-of-service claim.

## How we rate severity
- **Critical**: code execution or memory corruption from a validated value.
- **High**: validation time or memory that grows super-linearly with the input and is significant for an
  input a web application would commonly accept (seconds of CPU for a few kilobytes).
- **Medium**: a validation bypass that an application would plausibly rely on for a security decision
  (injection of control characters, a path or host that parses differently from how it is used).
- **Low**: other validation bypasses (a wrong checksum accepted, an out-of-range value), and crashes with an
  exception other than a validation error.

## Anything to leave alone
- Cost that grows linearly with the input: applications are expected to bound input size.
- Lax-mode coercions that the documentation describes.
- Serialization and JSON Schema generation, which work on data the application defines.
- Vulnerabilities in the wrapped libraries (`phonenumbers`, `pycountry`, `pendulum`, `semver`,
  `python-ulid`, `cron-converter`, `pymongo`, `pandas`) themselves, and validation in Pydantic itself.
