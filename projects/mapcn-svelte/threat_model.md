# mapcn-svelte security scope

mapcn-svelte is a Svelte 5 port of MapCN with MapLibre GL map components, examples, reusable blocks, and a shadcn-svelte-compatible registry. The documentation application uses SvelteKit and a static adapter.

## Inputs and trust boundaries

- Inspect `src/lib/registry/blocks/map` and other map blocks for unsafe handling of GeoJSON, feature properties, labels, URLs, styles, map sources and event payloads.
- Marker popups and tooltips use DOM containers (`setDOMContent`); investigate whether attacker-controlled data can still reach HTML or script-executing URL sinks through project code or examples copied by consumers.
- Examine worker URL selection, external style/source loading and resource configuration. Consumer-selected remote URLs are an intended feature; establish an unexpected trust-boundary crossing before treating that choice as a vulnerability.
- Inspect registry generation and documentation/LLM source extraction for path traversal or disclosure of files outside the intended public source set. The copyable code and registry payloads are part of the distributed product.

## Build and offline investigation

The Dockerfile installs locked dependencies, runs `pnpm build` (registry plus static application), and runs the existing Vitest suite with `pnpm test`. Source, generated registry and static output remain under `/src`. Tests that fail are logged; rerun them to assess the failure.

Live map tiles, CARTO basemaps, GeoJSON CDNs, routing services and the default remote MapLibre worker cannot be fetched during the offline audit. Use local fixture GeoJSON and mocked resource loading. The installed `maplibre-gl` package contains worker assets for local investigation. Rendering a complete live basemap is not a prerequisite for testing parsing, source extraction or DOM handling. Do not test attacks against third-party services.

## Report expectations

Prioritize exploitable script execution from externally supplied feature data, unexpected local file disclosure, and malicious registry/source payloads. Provide a minimal component or local endpoint reproducer, identify the actual sink and required consumer configuration, and propose a focused regression test. Bugs limited to upstream MapLibre should be distinguished from this project's integration defects. Rendering glitches, expected permission prompts and explicitly trusted developer code are not vulnerabilities without an additional security boundary crossing.
