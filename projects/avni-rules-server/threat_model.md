# Threat model

The scanner reads this file before it starts. It covers Avni's rules-server.

## What this project does and where untrusted input enters

Avni is an open-source platform that NGOs and governments use for field work in health, nutrition, water, education
and social welfare. Field workers collect data on an offline-first Android app that syncs with a central server. The
server stores personal and health data about the people those organisations serve, and one deployment holds many
organisations (tenants). Reading or changing another organisation's data is the most serious class of finding in
every Avni component.

rules-server (Node.js, Express) runs the JavaScript rules that organisation administrators write in Avni's form
designer: form element visibility, validation, decision, visit-schedule, eligibility, summary and messaging rules.
avni-server calls it over HTTP on the same host when a rule has to run on the server side (web data entry, bulk
upload, messaging). One process serves every organisation. While a rule runs, the service may call back into
avni-server with the caller's token.

Untrusted input reaches it through:

- **The HTTP API** (`routes/index.js`): request bodies carry rule source code, entities, form definitions and the
  caller's `AUTH-TOKEN`, `ORGANISATION-UUID` and user name headers. The service is meant to be reachable only from
  avni-server; treat a request from anywhere else as hostile.
- **Rule source code** written by an organisation administrator. Running it is the product, but a rule must not be
  able to affect another organisation, read the service's credentials or environment, reach the host, or stall the
  service for everyone.
- **Data from avni-server** fetched during rule execution (entities, legacy rule bundles) and CSV rows from bulk
  upload, including text that is matched against administrator-authored regular expressions.

### Trust model

- avni-server is the only intended caller. Organisation administrators are trusted only inside their own
  organisation; an organisation can be created by self-signup. Field users and CSV uploaders are less trusted than
  administrators. Avni's operators and the environment are trusted.

## Components that matter most / least

### Highest priority

1. How rule code is evaluated (`src/services/RuleEvalService.js`, `RuleService.js`, `evalRule.js`): what a rule can
   reach (process, filesystem, network, environment, module state shared with other organisations).
2. Authentication of callers and how the caller's identity is carried through a request (`rulesController.js`,
   `AuthService.js`, `api.js`), including state shared between concurrent requests.
3. Caches keyed by organisation and how they are filled and cleared.
4. Building observations from uploaded rows (`src/observationBuilder/`).
5. What is written to logs.

### Lower priority and out of scope

- Out of scope: `test/`, `deploy/`, the root `Dockerfile`, CI configuration.

## How to exercise it

- `/src` is the checkout; the image ran `npm install` and `npm test` on Node 10, the version the service runs on.
- Run the tests with `npm test` (Jest). Start the service with `node app.js`; it listens on port 3000.
  avni-server and the identity provider are not available in the image, so stub the HTTP calls or use the request
  shapes in `test/`.
- A proof of concept is a request body (or a rule string) and what it reaches, shown with a Jest test or a `curl`
  command against the local service.

## How you rate severity

- **Critical**: code execution on the host or reading the service's credentials by someone who is not an
  organisation administrator; any path by which one organisation's rule or request reads or changes another
  organisation's data, rules or tokens.
- **High**: an organisation administrator's rule reading the environment, the filesystem or other requests' tokens;
  a request running with another caller's identity.
- **Medium**: one organisation or one uploaded file stalling or crashing the service for all; tokens or personal
  data in logs.
- **Low**: information disclosure without personal data or secrets; hardening gaps with no demonstrated outcome.

## Anything to leave alone

- Development defaults that deployments replace (default passwords, keys and URLs in configuration templates and
  Makefiles). Do report a default that is used where no setting exists to replace it.
- Vulnerabilities in third-party dependencies unless this project's code reaches them in an exploitable way.
- Missing rate limiting and missing security headers, unless they combine into one of the outcomes above.

### Reports and patches

- One report per root cause, listing every affected endpoint, file or class.
- State who the attacker is (unauthenticated, field user, organisation administrator) and whether the effect crosses
  organisations.
- Include a reproducer (a test beside the existing ones, or the exact requests) and a minimal patch with a
  regression test.
