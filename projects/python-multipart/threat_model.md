# Threat model: python-multipart

## What this project does and where untrusted input enters
python-multipart is a streaming parser for `multipart/form-data`, `application/x-www-form-urlencoded` and
`application/octet-stream` request bodies. Web frameworks (Starlette, FastAPI and others) feed it raw bytes
straight from clients, along with the `Content-Type` header.

Assume the request body and every header passed to the parser (`Content-Type`, `Content-Disposition`,
`Content-Transfer-Encoding`, boundaries) are attacker-controlled. The calling framework and its configuration
are trusted.

## Components that matter most
1. **Parsers**: `python_multipart/multipart.py` - `MultipartParser`, `QuerystringParser`, `OctetStreamParser`,
   `FormParser`, `parse_options_header`. Of interest: parsing that diverges from the RFCs in a way a
   framework would trust, boundary confusion, state machine errors, and callbacks invoked with wrong data.
2. **Decoders**: `python_multipart/decoders.py` (base64 and quoted-printable).
3. **File handling**: `File` in `multipart.py`. Of interest: writing outside the configured upload
   directory, file names that are not sanitised, temporary files that are not cleaned up.

Denial of service is the main concern: input that makes the parser take super-linear CPU time, buffer
without bound, or ignore its size limits.

## How to exercise it
- `tests/` is a pytest suite. Run `pytest tests` from `/src`.
- `fuzz/` contains atheris harnesses and seed corpora for each parser; `fuzz/helpers.py` shows how to drive
  them. The parsers can be called directly with bytes, so PoCs can be a few lines.

## How we rate severity
- **Critical**: code execution, or writing files outside the upload directory.
- **High**: a single request under a typical body size limit that consumes CPU or memory far out of
  proportion to its size (e.g. ReDoS, quadratic parsing, unbounded buffering).
- **Medium**: parser differentials with a demonstrated security impact on a framework that uses the parser
  as documented; temporary file leaks.
- **Low**: crashes with a clean Python exception, and linear-cost DoS.

## Anything to leave alone
- `multipart/` is a deprecated compatibility shim that re-exports `python_multipart`.
- Frameworks that misuse the parser, or set no size limits of their own.
- `docs/`.
