# Threat model

## What this project does and where untrusted input enters

Stirling-PDF is a self-hosted web app and REST API for editing, converting and securing PDFs.
Users upload files and the server processes them with PDFBox, JPDFium and external tools
(qpdf, Ghostscript, LibreOffice, Tesseract, unpaper). Untrusted input enters through:

- Uploaded files of any type: PDF, Office, images, HTML, Markdown, EML, CBZ/CBR and ZIP. Assume
  every byte is hostile.
- API parameters: page ranges, file names, colours, fonts, URLs and JSON pipeline definitions.
- URLs the server fetches: URL to PDF, HTML and Markdown conversion, remote images and fonts.
- Login, OAuth2 and SAML callbacks, JWTs and API keys when security is enabled.

## Components that matter most / least

- Most: `app/core` (controllers, conversions, external process calls), `app/common` (file
  handling, temp files, `CustomPDFDocumentFactory`, `ProcessExecutor`, sanitizers) and
  `app/proprietary` (auth, users, teams, API keys, SSO, audit, policies, stored files).
- Lower but in scope: the `frontend/` React app (XSS) and the `engine/` Python AI service.
- Out of scope: `testing/`, `devTools/`, `docs/`, `scripts/`, `buildSrc/` and `app/saas`.

## How to exercise it

- Build with `./gradlew --offline $SPDF_GRADLE_FLAGS :stirling-pdf:bootJar`. The jar is in
  `app/core/build/libs/`.
- Run `stirling-pdf-start`. It starts the app the way the release image does (`/scripts/init.sh`
  with unoserver and the LibreOffice sandbox) on port 8080. The log is `/var/log/stirling-pdf.log`.
- Login is on by default, so API calls need a session or an `X-API-KEY`. Set
  `SECURITY_ENABLELOGIN=false` before starting to call the tools without auth, and
  `SYSTEM_ENABLEURLTOPDF=true` to turn on `url-to-pdf`.
- Run tests with `./gradlew --offline $SPDF_GRADLE_FLAGS :<module>:test --tests <class>`, where
  the modules are `common`, `stirling-pdf` and `proprietary`.
- `/v1/api-docs` lists every endpoint. Most take a multipart `fileInput`.

## How you rate severity

- Critical: unauthenticated remote code execution, command injection into the external tool
  calls, and authentication bypass or account takeover.
- High: SSRF that reaches internal hosts or cloud metadata, reading or writing files outside the
  request's temp directory, one user reaching another user's files, jobs or stored data,
  privilege escalation to admin, and XXE that reads local files.
- Medium: denial of service from a single crafted file (decompression, zip or pixel bombs,
  unbounded loops, out of memory), stored XSS, and leaks of server paths or configuration.
- Low: anything that needs admin access or control of `settings.yml`.

## Anything to leave alone

- With `security.enableLogin=false` the admin chose to run without auth, so unauthenticated access
  in that mode is by design.
- Admins and `settings.yml` / `custom_settings.yml` are trusted.
- `url-to-pdf` is off by default (`system.enableUrlToPDF`) and documented as internal only. SSRF
  through it is low unless it gets past the URL checks; SSRF anywhere else is high.
- Bugs inside LibreOffice, Ghostscript or Tesseract themselves, unless our invocation exposes them.
- High but proportional resource use from a large upload is not a finding.
