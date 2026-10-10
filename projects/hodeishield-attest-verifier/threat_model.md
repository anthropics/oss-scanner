# Threat model

Everything here is taken from the repository's own public documents: README.md, SECURITY.md, CHANGELOG.md, the header of `scripts/attest/verify-attestation.sh`, and `docs/security/` (attest-verification.md, key-anchor.md, keys.md, reason-codes.md, json-output.md).

## What this project does and where untrusted input enters
The project is one bash script, `scripts/attest/verify-attestation.sh` (v1.4.0), that a third party runs to check a signed posture attestation offline. It uses OpenSSL (3.5 or later, for ML-DSA-65 / FIPS 204), an embedded `python3` program (standard library only) that re-derives the canonical signed bytes, and `jq` for status lists. `curl` is used only when a status list is given as a URL; `cosign` (3.1.3 or later) only for the optional `--anchor-file`.

The verifier exists so that a reader does not have to trust the issuer's word. Its whole value is that it says "verified" only when it should. The reader is the victim: a wrong "verified" makes them rely on a document they should not.

Untrusted input, all of it, whatever the file says about itself:
- The attestation document: the compact JWS (attached or detached, `--jws`), the claims JSON (`--attestation`, `--claims`), every header and claim member, labels and strings inside the posture. Duplicate members, extra members the signature does not cover, odd Unicode, control characters, huge numbers and strange timestamps are all in play.
- The key set (`--jwks`, `--pub-b64url`), including `kid`, `pub` and `hs_retired_at`.
- The status list and its key set (`--status`, `--status-keys`), including `seq`, `nextUpdate`, and the keys and subjects it lists. They may be files or `http(s)://` URLs.
- The key statement and Sigstore bundle (`--anchor-file`, `--anchor-bundle`) and whatever `cosign` prints about them.
- Network responses when a URL is given (a man in the middle, a server that answers oddly, redirects, slow or endless bodies).
- The working directory and the files in it, the environment variables (including `PATH`, `PYTHON*`, `OPENSSL_*`, locale variables, and any variable whose name the script also uses as a shell variable), and the terminal that shows the output.
- The command line arguments, including values copied from a document or a web page (`--expect-slug`, `--expect-nonce`, `--expect-kid`, `--expect-issuer`, `--now`, `--min-seq`).

## Components that matter most / least
Most important: the code that decides the verdict and the exit code.
- Parsing of the JWS and of the protected header (closed set `alg`, `kid`, `typ`; no `crit`; the header is used exactly as received, never re-serialised).
- The canonical encoders (the envelope `hodei-shield.attest.attestation.v1` and the nested posture `hodei-shield.attest.posture.v1`) and the check that every member of the document is covered by the signature (`unsigned_member`).
- Public key handling: `kid` recomputed from the key bytes, key length, the ML-DSA-65 SPKI wrapping, key selection by `kid`, `hs_retired_at` and the `retired_key` rule.
- The OpenSSL signature call and the handling of its result.
- Freshness: `generatedAt`, `expiresAt`, the one-hour ceiling, clock skew, `--max-age-seconds`, `--now`, and the `EXPIRED` verdict.
- Binding checks: `--expect-slug`, `--expect-issuer`, `--expect-nonce`, `--expect-kid`.
- Status lists (`--status-list`): signature, issuer, freshness (`nextUpdate`), `seq` and `--min-seq` (rollback), self-revoking lists, subject and key rules, and the 0 / 1 / 2 / 3 split.
- The anchor (`--anchor-file`): the fixed Sigstore identity and issuer, the bundle shape (v0.3 only), the second cosign call with the identity read from the certificate, the repository ID check, the release tag compared with the script's own version (anti-rollback), and the statement's membership logic.
- Output: the text mode, and `--json` (schema `hodeishield.verifier.result.v1`, see docs/security/json-output.md). The reason codes in docs/security/reason-codes.md are a public interface.

Least important: `tests/` (they are the project's own acceptance tests and published vectors, with TEST-ONLY keys), `container/` (the image build), `.github/` workflows, and the documentation text. Bugs in them matter only if they let a broken verifier pass the suite or ship a different script than the one released.

## Where to look first
Places in `scripts/attest/verify-attestation.sh` where two readers of the same bytes or an error path could disagree:
- `header_field` (sed, C locale, first match) reads `alg`/`kid`/`typ`, while python enforces the member set, and the sed-read `kid` selects the key.
- `epoch_of` (GNU `date -d`, then python, then BSD fallbacks) versus the strict instant/compare code in `RETIRED_PY`: age, expiry and staleness use the first; skew, TTL, validity, retirement and `notBefore` use the second.
- The `claims_field` / `list_field` sentinels and NUL byte handling.
- The `DOCX_PY` split (the attestation wrapper) and `DUPKEY_PY` (duplicate members).
- The status list re-serialised by `jq '.statusList'` before `CANON_STATUS_PY`.
- Fail-open shapes: `[ ... ] 2>/dev/null` used as a condition, and `|| true`.
- Under `set -e`, a failing tool's own status showing up instead of 2.
- The `fetch_or_read` URL case patterns.
- `anchor_repository_id_ok` and the certificate SAN parse.
- Rule K (derived versus header `kid`) and Rule B (the subject hash, `notBefore`, truncation, and `--check-*` adding to rather than replacing the document's own values).
- The `on_exit` / `json_emit` exit-code path.

## How it is meant to be used (the promises)
The exit code is the contract. Do not report a deviation from it as low severity.

Posture mode (the default):
- `0` verified: the signature holds and every requested check passed.
- `1` check failed: do not rely on the document. A genuine but expired document is also `1`; its last line says `EXPIRED`. A document made at or after its key's retirement is `1` (`retired_key`).
- `2` could not check: missing or unsuitable tool (for example LibreSSL or OpenSSL older than 3.5), unreadable input, unknown key, malformed input to the tool itself, usage errors. This says nothing about the document and must never be a "verified".

`--status-list` mode: `0` good, `1` revoked (or the document failed), `2` could not check, `3` unknown.
- "Unknown is not good." A list that was obtained but does not verify, is stale, was rolled back (`--min-seq`), names its own signer, or comes after its key's retirement is `3`. Exit `3` must never be reported as `0`, and must stay distinct from `1` and `2`. A caller who tests `$? -ne 0` is the caller's mistake; a verifier that merges two codes is the bug.
- The same rule holds for everything else: anything the verifier cannot decide is `2` or `3`, never `0`.

Other promises:
- Nothing a document, status list or bundle contains can make the verifier use a key outside the key set given for it (`--jwks`/`--pub-b64url` for documents, `--status-keys` for lists, never the other), accept an `iss` other than `--expect-issuer` when given, or accept a Sigstore identity other than the fixed one. The Sigstore identity for the anchor is fixed in the script, and no option or environment variable changes it.
- A value from a document, key set or status list never reaches the terminal as a control character. Check lines and messages show every byte outside printable ASCII as `\xHH`. The Attested content block (verified runs only) shows non-printable characters as `?` and prints other text as UTF-8. `--json` output is printable ASCII on one line (`--help` and `--version` excepted).
- The verdict does not depend on the locale, on `PYTHON*` variables, on files in the working directory, or on an exported variable that shares a name with a script variable (the script sets every global it reads before reading it, and runs every python3 as `python3 -I -X utf8`).
- Verification is offline; the script contacts the network only for status-list URLs (and `cosign` may refresh its Sigstore trust root for `--anchor-file`).

## Trust roots
What a reader is told to trust, and what is not trusted:
- The attestation signing key, ML-DSA-65, named by its `kid` (`BASE64URL(SHA-256("hodei-shield.attest.kid.v1" || pub)[0..16])`). The verifier recomputes the `kid` from the key bytes, so a label is never trusted. The reader may pin it (`--expect-kid`). The reader fetches the key set from the issuer's web host over HTTPS and passes it as a file, so for that one binding (key to issuer) the reader trusts the Web PKI and DNS. This is stated in the docs as a known limit, not a bug.
- The optional anchor: a key statement (`keys-statement.json`) published with each release from v1.4.0 and signed keyless with Sigstore by this repository's `release.yml` at a `vN.N.N` tag (GitHub Actions OIDC). `--anchor-file` requires cosign 3.1.3 or later, a Sigstore bundle v0.3, the fixed identity, this repository's numeric ID, and a release tag not older than the script. It lists the keys by `kid` and role. It is a second channel, not a root of trust of the issuer.
- The status list is signed with a separate key set (`--status-keys`), and a status `kid` is resolved only against it, never `--jwks`. The `typ` values keep one kind of document from verifying as the other. The script does not check that the two sets are disjoint; `--anchor-file` checks each key's role.
- The signature proves integrity and origin, and the timestamps as signed. It does not prove the claims are true, that the key belongs to the issuer (beyond the above), that a document was ever meant to exist, or that one document is not revoked (there is no per-document revocation; per-key and per-subject revocation exist through the status list). These are documented limits in docs/security/attest-verification.md section 6, so they are not findings.
- The document's own `iss`, `kid`, `slug` and `nonce` are never trusted: the reader says what is expected, and the verifier compares.

## Attacker model
The attacker may fully control any of:
- the attestation document, the JWS, the claims, the key set, the status list and the key statement, as bytes (valid or malformed, from the real issuer or forged);
- the network responses when a URL is used (on-path attacker; a hostile server); the verifier warns on cleartext `http://` for `--status` (loopback included) and refuses it for `--status-keys` unless the host is `localhost`, `127.0.0.1` or `[::1]`; redirects are not followed;
- the files in the directory the verifier runs in, and file names and paths passed to it;
- the environment variables of the process (an exported variable with the same name as one of the script's shell variables, `PYTHON*`, `LANG`/`LC_*`, `TZ`, `NO_COLOR`);
- the terminal that displays the output (escape sequences, newlines and control characters smuggled through a document so that output lines look like a verdict).

The attacker can replay any genuine document within its validity window, can serve an older genuine status list or an older genuine key statement, and can ask the reader to run the tool with arguments taken from the document.

The attacker does not hold the issuer's private keys (see out of scope) and cannot edit the script or the tools the user runs it with.

## In-scope bug classes
Report these. Give a command line, the input files and the exact output and exit code.
- **Accepting something that should fail.** Exit `0` (or "good") for a document, key set, status list, key statement or bundle that is invalid, tampered, unsigned in part, signed by another key, for another issuer, slug, nonce or kid, expired, not yet valid, or signed by a retired or revoked key. This includes an extra or duplicate member the signature does not cover, a header with extra members or `crit`, a payload segment that differs from what was signed, a key whose `kid` is not derived from its bytes, and a signature OpenSSL did not actually verify.
- **Wrong exit code.** Any case where the exit code does not match the contract above: `1` reported as `0`; `2` ("could not check") or `3` ("unknown") reported as `0`; `1` and `2` or `3` swapped or merged; a tool failure (missing `jq`, `curl` or `cosign`, an `openssl` that cannot do ML-DSA, an interrupted read) that ends in `0`; an error swallowed by `set -e` / pipe / subshell behaviour of bash so that a failed check is skipped.
- **Parser differentials** between the components that read the same bytes: bash, `jq`, the embedded `python3`, and `openssl`. Examples: a document that one component reads as one thing and another as something else (duplicate members, numbers, Unicode, whitespace, base64url padding, member order, `null` and missing values, integers beyond the range bash can compare); a value that passes one check and is then used differently by the next; the signature verifying over bytes other than the ones whose content is then shown or checked.
- **Output or terminal injection.** Any document, key set, status list, bundle or cosign output that makes the text output or the `--json` output contain a raw control character or escape sequence, a forged `PASS` / `VERIFIED` line, a forged verdict, or invalid JSON.
- **Anti-rollback bypass.** A stale or older status list accepted despite `--min-seq`, `nextUpdate` or `seq` rules; an older release's key statement accepted by a newer verifier; a status list or key statement that avoids the `retired_key` rule.
- **Local-environment influence.** Anything in the working directory or the environment variables (including variables that happen to share the name of a script variable, `PYTHON*`, `LANG`/`LC_*`, `TZ`) that changes a verdict, an exit code, the trusted identity, or the files the script reads, writes or runs; unsafe temporary file handling; files in the working directory that get imported or executed; command or argument injection through a value taken from a document into `openssl`, `python3`, `jq`, `curl` or `cosign`.
- **Anchor bypass.** A statement or bundle accepted for the wrong identity, wrong repository, wrong issuer, a non-v0.3 bundle that reaches cosign, a second cosign call that can be satisfied differently from the first, or a release tag read from something cosign did not verify.
- **Network handling:** a cleartext `--status-keys` URL accepted for a host that is not loopback; `http` used for `--status` without the warning; a redirect or URL form that changes which host is trusted; information leaked from the document to a request the user did not ask for.
- **Release integrity:** logic in `.github/workflows/release.yml`, `container/` or `SHA256SUMS` handling that could ship or sign a script other than the tagged one.
- Logic errors in the test vectors (`tests/vectors/v1`) that make a broken verifier pass, since the vectors are published for other implementations.

## Out of scope
- The issuer's back end, signing process, web host, CDN and anything that produces attestations. Only the verifier is in scope.
- A forged document or status list that verifies against a key set the attacker also supplied, when the reader pinned nothing (`--expect-kid`, `--anchor-file`): this is the Web PKI limit of docs/security/attest-verification.md §6 item 2. A structural flaw is still in scope (a `kid` not derived from its bytes, a duplicate `kid`, a retired key accepted).
- Variables and files that configure or select the tools themselves (`PATH`, `BASH_ENV`/`ENV`, `LD_*`, `OPENSSL_CONF`/`OPENSSL_MODULES`, `SSL_CERT_*`, `CURL_*` and `~/.curlrc`, cosign's `SIGSTORE_*`/`TUF_ROOT`/`~/.sigstore`): controlling them is controlling the tools. Making the script ignore them is hardening (Low).
- Compromise of the issuer's signing keys, and the way those keys are stored. The docs state that the attestation key is held in software, not in an HSM; a validly signed false document from a compromised key is outside what any verifier can detect. The answer to a key compromise is the status list, which is a documented path.
- Whether the claims inside a genuine, correctly signed document are true, and the issuer's scoring.
- A malicious local root or user who can edit the script, the installed tools (`openssl`, `python3`, `jq`, `cosign`, `curl`), or the files in the verifier's own repository checkout.
- A reader who treats a nonzero exit as one outcome, or who ignores a documented limit (for example, not passing `--expect-issuer`, `--expect-slug` or `--expect-nonce`, not pinning a key, not using `--min-seq`).
- Denial of service by very large or very slow inputs (memory, time, endless network bodies), unless it ends in a wrong verdict or a wrong exit code, for example a timeout or out-of-memory that makes the script exit `0`.
- Bugs in OpenSSL, python3, jq, curl, cosign, Sigstore itself, GitHub Actions, or bash. Report a flaw in how the script uses them; a flaw only in the tool is not this project's.
- The weakness already published in docs/security/attest-verification.md section 9 (the issuer's TypeScript ML-DSA library is not externally audited). The verifier uses OpenSSL, a different implementation.
- Documentation wording, style, and the CI workflows, unless they let a wrong script be released.
- Only the latest release is supported. A finding that exists only in an older release and is already fixed is not a finding.
- Limits of the anchor stated in docs/security/key-anchor.md: it accepts any `v*` tag that `release.yml` builds, drafts included; anyone who can push a `v*` tag, or a compromised release pipeline, can have a statement signed; an old verifier can be served a statement as old as itself.

## How to exercise it
- The script is `scripts/attest/verify-attestation.sh`. Run it directly with `bash`; `--help` lists the options. The container build is in `container/Dockerfile`.
- `tests/run.sh` mints its own documents with a throwaway ML-DSA-65 key (`tests/lib/mint.py`) and asserts both the exit code and the reason line. Use its helpers as a model for a reproducer. Run it as `VERIFIER_SKIP_MUTANTS=1 bash tests/run.sh`; it also runs `tests/vectors.sh` (text and `--json`).
- `tests/vectors/v1/` holds published documents with TEST-ONLY keys, a fixed `--now`, and the expected exit code and reason for each.
- `--json` gives the reason code that decided the exit (docs/security/reason-codes.md). Use `--now` to fix the clock.
- `cosign` is not installed in the scan image, so `--anchor-file` against real Sigstore bundles cannot be run there. The anchor logic is tested with a cosign stand-in in `tests/run.sh`.
- Do not run `tests/mutants.sh` (do not build a copy of the verifier with its signature check disabled), `tests/live.sh` or `tests/keys-drift.sh` (they read the issuer's live endpoints), or `tests/container.sh` / `tests/image-smoke.sh` (Docker). Keep reproducers to the script as released.
- There is no network at scan time. Use local files for every input.

## How you rate severity
SECURITY.md sets no scale; §10 of docs/security/attest-verification.md says a verification failure you can reproduce is a security report. The scale below follows the exit-code contract above.
- **Critical:** the verifier exits `0` (verified, or status "good") for input that must fail, and an attacker who controls only the document, status list, bundle or network can cause it, or who also controls the key set (`--jwks`, `--status-keys`) while the reader pinned it with `--expect-kid` or `--anchor-file`. Examples: a forged or tampered document accepted; a revoked key or subject reported good; a key not derived from its bytes accepted; the anchor satisfied by the wrong identity; the signature check skipped. Also a wrong `0` from an environment variable or a file in the working directory.
- **High:** a wrong verdict that needs a precondition the docs consider reasonable, such as a stale status list or key statement accepted (rollback) or a retired key accepted; a `2` or `3` ("could not check", "unknown") turned into `0`; a `1`, `2` or `3` turned into `0` by any other route; parser differentials that can change what is signed versus what is shown; command or argument injection through document values; a terminal injection that can forge a `VERIFIED` line.
- **Medium:** a wrong non-zero exit code (`1`, `2` and `3` swapped or merged, or a valid document rejected); terminal or JSON injection that cannot forge a verdict; a wrong reason code or a wrong reason line for the right exit code; information leaks from the working directory.
- **Low:** misleading messages, diagnostics that name a temporary path, documentation that contradicts the script, hardening without a demonstrated wrong verdict.
- **Not a finding:** items under "Out of scope", and anything that needs control of the installed tools or their configuration (see Out of scope).
- A reproducer with the exact command, input files and output raises the rating; a theory without one is capped at medium. Name the exit code you got and the one the contract requires.
- Please propose patches as small diffs to `scripts/attest/verify-attestation.sh`, plus a case for `tests/run.sh` that fails before the fix and passes after.

## Anything to leave alone
- The documented limits of what a `VERIFIED` result proves (docs/security/attest-verification.md section 6): claims may be wrong, the key binding rests on the Web PKI unless pinned or anchored, no per-document revocation, software key custody.
- Embedded test keys and fixtures under `tests/` and the demonstration organisation `talmaren-payments`: they are test data, not secrets.
- Intentionally strict rejections (for example, any extra header member, any extra signed-document member, any bundle that is not v0.3) are the design.
- The `shellcheck` directives in the script, each of which is documented in place.
- Paths in the script such as `app/src/lib/attest/...` and `docs/architecture/specs/...` point to the issuer's private repository; they are provenance, not missing files.
- Style or portability remarks on bash that do not change a verdict (the script requires bash 4 or later and OpenSSL 3.5 or later).
