# Threat model

## What this project does and where untrusted input enters
- Solid is a client/server UI library (reactive primitives, JSX runtime, server-side rendering, hydration). Untrusted input enters mainly through data that applications render: strings placed into HTML or attributes during SSR (`packages/web`, `packages/html`, `packages/h`), values passed to spread/attribute/property setters, `innerHTML`-style APIs, and serialized hydration data.
- Bugs of interest: XSS via incorrect escaping in SSR or DOM rendering, prototype pollution in stores or spread/merge helpers, unsafe deserialization of hydration payloads, and unsafe handling of URLs or attributes (for example `javascript:` URLs).

## Components that matter most / least
- Most: `packages/web` (DOM and SSR rendering, hydration), `packages/solid` (core runtime, stores, control flow), `packages/signals`, `packages/html`, `packages/h`.
- Less: `packages/babel-plugin` and `packages/compiler` are build-time tools that process the developer's own source; only report issues that let untrusted source or data cause harmful output.
- Out of scope: `examples/`, `documentation/`, and test fixtures.

## How to exercise it
- Each package under `packages/` has its own tests (`pnpm run test`). The SSR and hydration tests in `packages/web` and `packages/solid` are good starting points for rendering untrusted strings.

## How you rate severity
- Escaping failures that allow script execution when applications render untrusted data in documented-safe ways are high+. Prototype pollution reachable from untrusted data through public APIs is high. Crashes or hangs on malformed input are medium.

## Anything to leave alone
- Application developers are responsible for not passing untrusted data to explicitly unsafe APIs (`innerHTML`, `eval`-like usage). Do not report these as library bugs.
