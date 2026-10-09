# kumo-svelte security scope

kumo-svelte is a Svelte port of Cloudflare's Kumo UI library, with components built on Bits UI, a local CLI for installing blocks, a component registry, and a SvelteKit documentation application deployed to Cloudflare Workers.

## Inputs and trust boundaries

- Inspect `packages/kumo-svelte/src/lib` and `src/blocks` for handling of untrusted labels, links, rich content, HTML attributes and event data. Review HTML injection, script-executing URLs, and propagation of unsafe example patterns to consumers.
- Inspect `packages/kumo-svelte/src/command-line` for path traversal, symlink escapes, unintended overwrite and reads/writes outside configured destinations. The CLI reads local `kumo.json` and the packaged registry, transforms imports and writes block source files; report whether an exploit requires altering trusted project configuration or published package contents.
- Inspect `packages/kumo-svelte/src/routes` for documentation/source extraction, route parameter handling, generated API/registry payloads and accidental file disclosure.
- Review registry/code-generation tooling and distributed CLI output as well as runtime components. A vulnerability in upstream Bits UI or another dependency needs a reachable integration path and should be clearly attributed.

## Build and offline investigation

The Dockerfile installs locked dependencies and runs `pnpm build:package` (registry, checks, package, styles and CLI) followed by `pnpm build` (documentation). Outputs and source remain under `/src`; the CLI entry point is `packages/kumo-svelte/dist/command-line/cli.js`. Run `pnpm --filter kumo-svelte exec vitest run --maxWorkers=2` and `pnpm test:tools` for the existing component suite and tooling tests. The two-worker limit bounds memory and CPU use for offline analysis. Test failures are logged during construction; rerun tests before claiming they pass.

Use fixture data for examples that normally fetch remote resources. The existing unit suite uses Happy DOM; full browser visual-regression runs require separately installed browsers and are outside this image's default tests. Production Cloudflare credentials and deployment are not needed for the audit.

## Report expectations

Prioritize demonstrated arbitrary file writes or reads across intended CLI boundaries and script execution from externally supplied content. Supply a minimal local reproducer, exact affected entry point, attacker capabilities, and a regression test. Configuration selected knowingly by the developer, accessibility defects, styling issues and expected component behavior are not security findings without concrete security impact. Do not classify all local CLI execution as remote code execution.
