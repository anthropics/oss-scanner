# Threat model

## Project and security goals

This repository contains the article corpus, content-generation code, shared
rendering engine, and API builder for frontaliereticino.ch. It publishes JSON,
RSS, and sitemap data that the production site consumes over HTTP. Protect the
integrity of the publishing pipeline, keep generated output safe for browsers
and feed readers, and prevent unauthorized publication or leakage of
credentials.

The production reach is first-party rather than a broad third-party library
ecosystem: a dated GA4 snapshot for the consuming site (2026-03-04, previous
30 days) recorded 2,178 users, 2,566 sessions, 12,571 page views, and 73.2%
engaged sessions. The public manifest contains 3,870 frontaliere articles,
2,100 Swiss articles, 10 RSS feeds, and the sitemap/ticker surfaces. These
figures describe the live consumer and published surface; they are not a claim
of independent downstream projects or critical infrastructure.

## Untrusted input and trust boundaries

Treat article text, translations, editorial metadata, images, RSS/XML/HTML from
external sources, and fetched public datasets as untrusted. Data moves through
generator scripts and validation gates into the public API. GitHub Actions and
publication credentials form a separate trust boundary between source changes
and production publication.

## Components in scope

Prioritize the generators and fetchers, content and output validation,
scripts/build-api.mjs, engine/, host/, publication workflows, and any code that
reads secrets or writes the public API. Assess script injection, unsafe parsing,
path traversal, unsafe HTML/XML output, credential exposure, and unauthorized
or unintended publication when the project code provides a concrete path to
impact.

The main site is a separate repository and consumes this project over HTTP.
Do not report issues in that separate codebase unless this repository has a
specific vulnerability that reaches it through the published API. Do not probe
external source sites, production APIs, CDN accounts, or other third-party
systems.

## Severity guidance

- Critical: compromise of publication credentials or the CI publisher that
  enables broad unauthorized releases, or a remotely reachable path to execute
  attacker-controlled code in the publishing environment.
- High: persistent script injection or content manipulation that affects site
  visitors, or unauthorized changes to production API output.
- Medium: reproducible parser, path, or resource-exhaustion issues with a
  limited but meaningful effect on the build or published data.
- Low: hardening gaps without a demonstrated security boundary bypass.

Prefer a focused reproducer, the input-to-output path, and a patch with a
regression test. Do not treat factual, editorial, or SEO defects as security
findings without a concrete security impact.
