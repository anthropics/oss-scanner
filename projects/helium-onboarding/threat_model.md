# Helium onboarding threat model

## What this repository is

The first-run setup page of the Helium browser, shown at `helium://setup`. It is a Svelte app (`src/`) built with
Vite and bundled into the browser as a WebUI resource (`BUILD.gn`, `helium_onboarding_strings.grdp`). It walks the
user through importing data from other browsers, choosing a search engine and password manager, setting Helium as
the default browser, and opting in to Helium services. It talks to the browser process through `chrome.send` and
WebUI message handlers (`src/lib/cr/`, `src/lib/browser/`); the browser side of those handlers is in Helium's
`patches/helium/core/onboarding-page.patch` (github.com/imputnet/helium, enrolled separately).
`src/lib/chrome-send-polyfill.ts` is a fake browser for `pnpm dev` and is not shipped.

In the scanner image, `/src` is this repository with dependencies installed and the page built into `/src/dist`.
`pnpm dev` serves it locally with the polyfill.

## Scope

The page runs with WebUI privileges: it can change preferences, the default search engine, and what gets imported,
so script execution in it is equivalent to those capabilities. Look for ways untrusted data reaches the DOM or is
treated as markup or a URL, where it can come from:

- data read from other browsers' profiles during import (profile names, search engine names and URLs, extension
  names), which websites the user visited in those browsers can influence, such as search engines added from a
  site;
- anything fetched from the network or from Helium services;
- the URL of the page itself (query string, fragment).

Also in scope: the page sending the browser a choice the user did not make (for example enabling services, importing
data, or setting a search engine without consent), and anything in the build that lets a third party change what is
bundled into the browser.

## Out of scope

As in Chromium's threat model: physically-local attacks and compromised machines (anything that needs the attacker
to run code as the user or write to the profile directory), enterprise policy, and script the user runs themselves
in DevTools. Bugs in the browser-side handlers belong to the `helium` enrollment, and `chrome-send-polyfill.ts` only
runs in development.

## How you would like reports

Name the component or file and line, and the data path from the untrusted source to the sink. Say when a finding was
only confirmed by reading code.
