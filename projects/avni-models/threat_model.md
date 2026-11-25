# Threat model

The scanner reads this file before it starts. It covers avni-models (published to npm as `openchs-models`).

## What this project does and where untrusted input enters

Avni is an open-source platform that NGOs and governments use for field work in health, nutrition, water, education
and social welfare. Field workers collect data on an offline-first Android app that syncs with a central server. The
server stores personal and health data about the people those organisations serve, and one deployment holds many
organisations (tenants). Reading or changing another organisation's data is the most serious class of finding in
every Avni component.

avni-models is the shared JavaScript domain model of Avni: the entity classes, the Realm schema and its migrations,
and the helpers that parse, validate and merge entity data. It is a library with no network code of its own. It runs
inside the Android app (avni-client), the web app (avni-webapp) and the server-side rules service (rules-server), so
a flaw here is reachable in all three.

Untrusted input reaches it through its callers:

- **Entities received from the server during sync** or read from a restored database: JSON for forms, concepts,
  observations, subjects and settings, written by other users of the organisation.
- **Form configuration authored by organisation administrators**: key-values, validation formats (regular
  expressions), date and duration strings, uuids and names.
- **Values typed by field users or read from uploaded CSV files**, which are matched against that configuration.
- **Rule code**, which receives these model objects and calls their methods.

## Components that matter most / least

### Highest priority

1. Parsing and merging of untrusted JSON (`fromResource` methods, `MergeUtil`, key-value handling): prototype
   pollution, type confusion, and unbounded recursion.
2. Regular expressions and formats taken from configuration (`application/Format.js`) and applied to user input:
   catastrophic backtracking, since rules-server runs them in a process shared by every organisation.
3. Realm schema migrations and queries that interpolate values (`Schema.js`, the `framework/` Realm proxies).
4. Anything that evaluates strings as code.

### Lower priority and out of scope

- Out of scope: `test/`, `scripts/`, `dist/`, documentation and CI configuration.

## How to exercise it

- `/src` is the checkout; the image ran `yarn install`, `yarn build`, `yarn validate:schemas` and `yarn test-ci`
  on Node 20.
- Run the tests with `yarn test` (Jest). A proof of concept is a Jest test under `test/` that passes hostile data to
  a public method of a model class.

## How you rate severity

A finding is rated by what it lets an attacker do in a consuming application, so say which one.

- **High**: data from one user or organisation causing code execution, or reading or changing another user's data,
  in the Android app, the web app or rules-server.
- **Medium**: input that stalls or crashes rules-server (shared by every organisation) or corrupts a field user's
  local database.
- **Low**: a crash limited to the user who supplied the input; hardening gaps with no demonstrated outcome.

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
