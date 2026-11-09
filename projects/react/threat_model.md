# React threat model

## What this project does and where untrusted input enters

React is a library for building user interfaces. This repository contains the core (`react`), the reconciler, renderers (`react-dom`, `react-native-renderer`, `react-art`, test renderers), server rendering (Fizz: `react-dom/server`, `react-dom/static`), React Server Components (Flight: `react-server`, `react-client`, `react-server-dom-{webpack,turbopack,parcel,esm,unbundled}`), DevTools, Fast Refresh and the scheduler.

The application developer is trusted: their components, their bundler configuration, and the server functions they choose to expose. Untrusted input reaches React through:

- **Values rendered as children or props** that came from end users (text, attribute values, `href`/`src`/`action`/`formAction` URLs, `style` objects, keys). React must escape them so they cannot become markup or script.
- **HTTP requests to a Server Components / Server Functions endpoint.** `decodeReply`, `decodeReplyFromBusboy`, `decodeReplyFromAsyncIterable`, `decodeAction` and `decodeFormState` parse attacker-controlled request bodies (FormData, multipart, streams). Anyone on the network can send these.
- **Flight payloads read by the client** (`createFromFetch`, `createFromReadableStream`, `createFromNodeStream`). These normally come from the app's own server; treat them as trusted unless a bug lets attacker data be written into the stream.
- **Server-rendered HTML hydrated by the client**, including attribute values and text that an attacker placed in the database.
- **DevTools**: the backend runs inside the inspected page and talks to the extension/standalone frontend over a message bridge. A malicious page is untrusted relative to the extension.

## Components that matter most / least

Most important:
- `packages/react-server/src/ReactFlightReplyServer.js`, `packages/react-server-dom-*/src/server/` and `packages/react-client/src/ReactFlightReplyClient.js`: decoding Server Function arguments. Prototype pollution, access to properties outside the module manifest, reaching `constructor`/`__proto__`/`then`, resolving server references the app did not export, and unbounded resource use while parsing are all in scope.
- `packages/react-server/src/ReactFlightActionServer.js` (`decodeAction`, `decodeFormState`) and the manifest lookups in `packages/react-server-dom-*/src/client/ReactFlightClientConfigBundler*.js` (`resolveServerReference`, `preloadModule`, `requireModule`, which the server also uses to load server functions): anything that loads a module or export the manifest does not list.
- `packages/react-dom-bindings/src/server/` (Fizz HTML output): text and attribute escaping, `<script>`/`<style>` content escaping, bootstrap scripts, inline runtime instructions, nonce handling, `<title>`, `<meta>`, resource hints (`preload`, `preinit`), and Flight data embedded in HTML.
- `packages/react-dom-bindings/src/client/` and `packages/react-dom-bindings/src/shared/`: attribute/property setting, `sanitizeURL` (blocking `javascript:` URLs), `dangerouslySetInnerHTML` handling, hydration of text and attributes.
- `packages/react-server/src/ReactFlightServer.js` and `ReactFizzServer.js`: serialization of values into the stream, taint APIs (`experimental_taintObjectReference`, `experimental_taintUniqueValue`), error message/digest handling (server error details must not leak to clients in production builds).

Less important or out of scope:
- `compiler/`: a Babel plugin run by developers on their own code at build time. Out of scope for this enrolment.
- `fixtures/`, `scripts/`, build tooling, `packages/*/npm/` shims, test utilities (`internal-test-utils`, `jest-react`), `react-noop-renderer`.
- `packages/eslint-plugin-react-hooks`, `react-refresh`, `react-is`, `use-sync-external-store`: run on developer-controlled input.
- Third-party dependencies, unless React uses them unsafely.

## Security model

- `dangerouslySetInnerHTML`, `suppressHydrationWarning`, raw `<script>` children the developer writes, and any value the developer passes into a `<script>`/`<style>` body on purpose are explicit opt-ins. XSS that requires them is not a React bug. XSS from an ordinary string prop or child **is**.
- React blocks `javascript:` URLs in URL attributes (`href`, `src`, `action`, `formAction`, `xlink:href`, etc.). A bypass of that check in a supported browser is in scope.
- A Server Functions endpoint is reachable by any unauthenticated network client. The app's server functions are trusted code, but React's decoding of their arguments is not allowed to run code, load modules, or reach objects beyond what the decoded types (primitives, plain objects/arrays, Date, BigInt, Map, Set, FormData, Blob, typed arrays, streams, iterables, promises, temporary references, server references in the manifest) describe.
- Authorization of server functions is the app's job. A server function being callable is not a React bug unless React let the caller reach one the manifest does not expose.
- Development builds print more detail by design. Information disclosure counts only in production builds.

## How to exercise it

From `/src`:

```sh
yarn test <path-or-pattern>                                  # Jest, source, experimental channel
yarn test -r=stable <pattern>                                # stable channel
yarn test --prod <pattern>                                   # production mode
```

Good starting points for reproducers:
- `packages/react-server-dom-webpack/src/__tests__/ReactFlightDOMReply-test.js`, `ReactFlightDOMReplyNode-test.js`, `ReactFlightDOMForm-test.js`: build a malicious FormData/multipart body and call `decodeReply`/`decodeAction` with a test manifest.
- `packages/react-dom/src/__tests__/ReactDOMServerIntegration*-test.js`, `ReactDOMFizzServer-test.js`, `ReactDOMServerIntegrationUntrustedURL-test.js`: render untrusted strings and check the HTML.
- Built Node bundles are in `build/node_modules/*` (dev and prod, experimental channel). A plain Node script that `require`s `build/node_modules/react-server-dom-webpack/server.node` with `--conditions react-server` and serves an HTTP endpoint is the closest to a real deployment.

## How we rate severity

- **Critical**: remote code execution or arbitrary module loading on the server from an unauthenticated request to a Server Functions endpoint; prototype pollution on the server reachable from an unauthenticated request with a demonstrated path to RCE or auth bypass.
- **High**: XSS in default usage (a plain string child or prop, no `dangerouslySetInnerHTML`) from server rendering, hydration, or client rendering; a `javascript:` URL filter bypass; reaching a server function or module export not in the manifest; prototype pollution without a demonstrated exploit; leaking tainted values or server-only data to the client.
- **Medium**: denial of service on the server from a single small unauthenticated request (CPU or memory blow-up, hang, or crash of the process); server error messages or stack traces reaching the client in production builds; DevTools extension compromise from a malicious page.
- **Low**: client-side DoS (a crafted value freezing or crashing the tab), issues needing a non-default configuration or an unusual browser, info leaks in development builds only.

Not security issues: XSS that needs `dangerouslySetInnerHTML` or other explicit opt-in; missing authorization inside an app's server function; issues that need control of the app's code, bundler, or manifest; self-XSS; dev-only warnings.

## Anything to leave alone

- Do not report the `compiler/` directory.
- Do not report that development builds expose component stacks, source locations, or error messages.
