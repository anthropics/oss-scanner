# Threat model

## Project and security goals

Frontaliere Ticino is a production web application for cross-border workers. It
includes a browser application, Firebase Authentication, Firestore and Storage
rules, serverless functions, newsletter integrations, and paid assisted-job-
application flows.

The scanner build uses the compact repository
`valerielinc-ops/frontaliere-si-o-no-oss-scanner` as its Git entry point because
the production repository's Git history is too large for the scanner's clone
window. Its Dockerfile fetches the pinned production commit
`51d4352e369d784ad8d0805400c6dc9df09e3d64` with a shallow Git fetch and runs
that source tree's own build. The code under review is therefore the production
site commit, not a separate implementation.

Protect account data, uploaded CVs and application documents, consent and
payment state, privileged credentials, and the integrity of information shown
to users. A compromise could expose personal data, alter paid services, or
publish misleading content.

## Untrusted input and trust boundaries

Treat all browser requests, query parameters, form fields, and user-controlled
profile data as untrusted. Uploaded CVs and documents are untrusted files.
External job listings, article feeds, public datasets, and content fetched by
build or crawler code are also untrusted.

Authentication and authorization cross boundaries between the browser, Firebase
Auth, Firestore, Storage, serverless functions, and external payment or email
providers. Webhook payloads and provider responses must be treated as untrusted
until authenticated and validated.

## Components in scope

Prioritize the frontend and its build plugins, Firebase Authentication and
security rules, Firestore and Storage access, serverless functions, and CI or
deployment code that handles credentials or publishes application artifacts.
Assess a finding when it has a concrete security effect in this project; do not
report an upstream dependency issue without a project-specific path to impact.

Do not probe production services, user accounts, payment providers, job sites,
or other third-party systems. Use local fixtures and the prepared build only.

## Severity guidance

- Critical: unauthenticated remote code execution, broad exposure of private
  CVs or account data, or compromise that permits widespread production
  credential theft.
- High: broken authorization exposing or modifying another user's data,
  bypassing payment or consent checks, privileged account takeover, or
  persistent script injection that can access sensitive user sessions.
- Medium: a reproducible security issue with limited scope, including
  user-specific data exposure or persistent injection requiring meaningful
  user interaction.
- Low: defense-in-depth weaknesses without a demonstrated security boundary
  bypass.

Prefer a concise reproducer, the affected trust boundary, an impact assessment,
and a focused patch with a regression test.
