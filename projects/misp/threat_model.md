# MISP threat model

MISP is an open source threat intelligence and information sharing platform.
It stores, correlates, imports, exports and shares events, attributes, objects,
attachments and other intelligence between users, organisations and instances.

## Security policy and reporting

The authoritative policy is https://www.misp-project.org/security/.
Report vulnerabilities privately to CIRCL at info@circl.lu. The enrollment
includes the public encryption key published on that page, fingerprint
`CA57 2205 C002 4E06 BA70 BE89 EAAD CFFC 22BD 4CD5`.
Include reproduction steps, affected versions, impact and how the reporter
wishes to be acknowledged. MISP's maintainers assign CVE/GCVE identifiers.

The policy explicitly values reports of even minor bugs suspected of having
security impact. Do not exclude a finding solely because it requires an
authenticated user or has limited impact. Explain the privileges, configuration
and deployment assumptions needed to reproduce it; do not infer a severity
threshold or a disclosure deadline that the policy does not state.

## Untrusted input and important boundaries

- Web and REST requests, authentication keys, sessions and authentication plugins.
- Events, attributes, objects, proposals, tags and analyst data created by users
  with different roles and organisation memberships.
- Data received from synchronisation peers, feeds and imports, including JSON,
  XML, STIX, CSV, archives, attachments and malware samples.
- URLs and remote content used by enrichment, feeds, synchronisation, exports
  and configurable integrations.
- Inputs passed between PHP, Python conversion tools, background workers and
  external commands.

Prioritise authentication and authorisation, organisation isolation, sharing
groups and distribution restrictions, access to unpublished or restricted data,
API key scope, session handling, injection, unsafe deserialisation, file handling,
path traversal, server-side request forgery and browser script execution.
Consider both a malicious low-privilege local user and a malicious remote peer.
Distinguish intended administrative configuration from an escalation across a
privilege or trust boundary. Attribute dependency findings to their responsible
component and show whether MISP exposes the vulnerable behaviour.

## Audit environment and checks

The Dockerfile builds the supplied MISP 2.5 checkout at `/src`, initialises its
recorded submodules, installs PHP and Python dependencies and creates a local
MariaDB test database using MISP's CI fixtures. This is a disposable test
instance; its database credentials and generated administrator credentials must
never be used for a real deployment. Email delivery and background jobs are
disabled. No external services or production credentials are required.

From the offline shell opened by `tools/check misp`, run:

```sh
cd /src
sudo -u www-data app/Vendor/bin/phpunit --do-not-cache-result app/Test/
python -m pytest -q tests/test_misp_framing.py tests/test_stix2misp_wrapper.py
misp-start
curl --fail http://localhost/users/login
```

`misp-start` restarts MariaDB, Redis and Apache inside the container; their
processes do not persist from the image build. The checkout, dependencies and
database files do persist. PHPUnit covers the tests in `app/Test/`; the two
Python suites exercise the STIX conversion wrappers. The upstream CI workflow
in `.github/workflows/main.yml` documents additional integration suites, some
of which require extra fixtures, LDAP, background workers or network access.
Do not treat those additional suites as having run merely because the image
built. Use local fixtures and instances for reproductions, never live MISP
deployments or external systems.
