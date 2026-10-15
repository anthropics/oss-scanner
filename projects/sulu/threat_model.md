# Threat model: Sulu

## What this project does and where untrusted input enters
Sulu is an open-source CMS framework built on Symfony. Untrusted input enters through the public website
(request parameters, forms, uploaded files, rendered content), and through the admin API
(`/admin/api`, authenticated users with varying permissions: content editors are NOT trusted with server-side access).
Media uploads, rich-text/HTML content, URL and redirect handling, and the preview/search features are the main surfaces.

## Components that matter most / least
- Most: security/permission checks (webspace and entity permissions), authentication and password reset,
  media upload and processing (file type handling, image conversion), rich-text/HTML output, the admin REST API,
  route and redirect handling, import/export and the preview mechanism.
- Less: development-only tooling, test fixtures, docs and translations.
- Out of scope: third-party dependencies in `vendor/` (report upstream), issues requiring a malicious site administrator.

## How to exercise it
- Start the database with `sulu-db-start`, then run `php bin/runtests -i -a` (`-i` creates the schema).
  `-t MediaBundle` runs one bundle. All suites pass offline except one media test that fetches a URL.

## How you rate severity
- Unauthenticated RCE, SQL injection, authentication bypass: critical.
- Privilege escalation between admin users / permission bypass, stored XSS reachable by low-privileged editors against admins: high.
- Reflected XSS, open redirect, SSRF to internal hosts: medium.
- Denial of service needing authentication, information leaks of non-sensitive metadata: low.

## Anything to leave alone
- Findings that require the attacker to already be a system administrator with full admin rights.
