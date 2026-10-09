# wxcn security scope

wxcn provides weather, tide, and moon components for Svelte, React, and Vue, shared data utilities, a component registry, and an Astro application deployed to Cloudflare Workers.

## Inputs and trust boundaries

- Inspect `packages/core/src` and `apps/web/src/lib/server` for parsing and validation of coordinates, dates, time zones, station identifiers, upstream URLs and API responses. Treat NWS/NOAA response bodies as external input; a URL obtained from an API response should not automatically be trusted for server-side requests.
- Inspect `apps/web/src/pages/api/{forecast,tides,locations}.ts` and their helpers for SSRF, parameter abuse, bounded requests, error disclosure and cache behavior. These public GET endpoints have no authentication barrier.
- Inspect all framework components and generated registry content for unsafe HTML/URL handling of externally supplied labels, links and forecast data, including rendering in SSR contexts.
- Inspect `tooling/registry`, documentation generation and consumer tooling for path containment and unintended file writes. Developer-provided project configuration is generally trusted, but crossing a documented destination boundary should be reported.

## Build and offline investigation

The Dockerfile installs the locked dependencies and builds the documentation/Worker application plus React and Vue previews. Source and output remain under `/src`. Run `pnpm test`, `pnpm test:react` and `pnpm test:vue` for the existing unit and SSR checks. Test failures are logged during image construction and must be investigated; an image build alone is not proof of passing tests.

Live NWS/NOAA services are unavailable during the audit. Use fixture responses and mocked fetches to exercise upstream-data handling. Do not send attack traffic to third-party services. Browser screenshots and production deployment are not required to analyze these boundaries.

## Report expectations

Prioritize demonstrated server-side request abuse, attacker-controlled script execution, unauthorized file access and cross-user data disclosure. Show the input, affected entry point, trust boundary crossed, and impact using a minimal local reproducer and regression test. Ordinary inaccurate forecasts, expected upstream failures, stylistic issues and accessibility defects are not security findings unless a concrete security impact is demonstrated. Report dependency issues with a reachable project-specific exploit path where possible.
