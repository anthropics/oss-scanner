# React Native threat model

## What this project does and where untrusted input enters

React Native builds native iOS and Android apps with React. This repository holds the JS runtime and components (`packages/react-native/Libraries`), the C++ core shared by both platforms (`packages/react-native/ReactCommon`: JSI, Fabric renderer, TurboModules, Yoga, the modern JS inspector), the Android (`ReactAndroid`) and iOS (`React`) native layers, and Node tooling used during development: the dev server middleware (`packages/dev-middleware`), the CLI plugin (`packages/community-cli-plugin`), codegen (`packages/react-native-codegen`) and debugger front/back ends.

The app developer, their JS bundle, and their native code are trusted. Untrusted input reaches React Native through:

- **The dev server (development only).** `packages/dev-middleware` and `packages/community-cli-plugin` serve HTTP and WebSocket endpoints (`/open-debugger`, `/json`, `/json/list`, `/inspector/device`, `/inspector/debug`, the CLI's message socket and middlewares). The server may be bound to a LAN interface, so other machines on the network, and web pages in the developer's browser (via cross-origin requests or DNS rebinding), are untrusted callers.
- **Deep links and intents** handled by `Linking` and the native intent/URL plumbing: any other app or web page can send them.
- **Network data** fetched by the app (`fetch`/`XMLHttpRequest`, `WebSocket`, `Image` sources, blob/file URIs) and handed to native code.
- **Data crossing the JS/native bridge** (TurboModule arguments, Fabric props, `MapBuffer`): JS is trusted, but values often originate from network data, so native code must not trust lengths, types or indices it receives.
- **Images, fonts and other media** decoded by native code from app-supplied or network URIs.

## Components that matter most / least

Most important:
- `packages/dev-middleware/src/` (`createDevMiddleware.js`, `middleware/openDebuggerMiddleware.js`, `inspector-proxy/`, `utils/DefaultToolLauncher.js`, `utils/getDevToolsFrontendUrl.js`): anything that lets a remote or cross-origin caller launch a process, open an arbitrary URL or file, reach a device's debugger session, or read source/runtime state.
- `packages/community-cli-plugin/src/dev-server/` and `commands/`: middleware loading, key handlers, asset saving during `bundle` (path traversal when writing assets).
- `packages/react-native/ReactCommon/` C++: memory safety in JSI value conversion, `react/renderer` (props parsing, `MapBuffer`, attributed strings / text layout), `jsinspector-modern` (CDP message handling from the debugger), `cxxreact`, `yoga`.
- `packages/react-native/ReactAndroid/` and `packages/react-native/React/`: native modules that parse untrusted input (networking, WebSocket, blob, image loading, `Linking`/intent handling, file/URI access, exported Android components).

Less important or out of scope:
- `packages/rn-tester`, `packages/new-app-screen`, `packages/react-native-test-library`, `private/`, `scripts/`, CI config, `__docs__`, `flow-typed`.
- `packages/eslint-*`, `packages/react-native-babel-*`, `packages/metro-config`, `packages/typescript-config`: run on developer-controlled input.
- `packages/react-native-codegen`: parses the developer's own spec files at build time; only issues reachable from a third-party library's specs matter (e.g. code injection into generated native code).
- Metro, Hermes and the React reconciler live in other repositories; report them only where React Native uses them unsafely.

## Security model

- The dev server is a development tool, but it must not give remote or cross-origin callers code execution, arbitrary file read/write, or arbitrary process/URL launch on the developer's machine. It may assume callers on `localhost` that pass its origin/host checks are the developer.
- Debugger access (CDP over the inspector proxy) is equivalent to code execution in the app; reaching it without being the developer is the vulnerability.
- Production apps do not include the dev server or the inspector. Issues that only reproduce in debug builds of an app are dev-tooling issues, not app issues.
- JS in the app bundle is trusted. A JS-to-native memory corruption bug matters when the triggering values plausibly come from untrusted data (network responses, deep links, user text), not from deliberately malformed native calls only the app author could write.

## How to exercise it

From `/src`:

```sh
yarn jest packages/dev-middleware          # inspector proxy and middleware tests
yarn jest packages/community-cli-plugin
yarn jest <path-or-pattern>                # any other JS tests
```

`packages/dev-middleware/src/__tests__/` contains harnesses that start a real dev server with `createDevMiddleware` and connect fake devices and debuggers over WebSocket; this is the easiest way to write a reproducer for dev-server issues. Built Node packages are in `packages/*/dist` after `yarn build`. Android and iOS native code is not built in this image; native findings need a source-level argument or a small standalone C++ test against `ReactCommon`.

## How we rate severity

- **Critical**: unauthenticated remote code execution on the developer's machine via the dev server from the network or from a web page the developer visits; memory corruption in shipped native code with a demonstrated path to code execution from network data or a deep link.
- **High**: arbitrary file read/write or process/URL launch through the dev server; reaching a device's debugger session from a non-developer origin; native memory corruption reachable from untrusted data without a full exploit; a deep link or intent that bypasses app-level checks React Native is responsible for.
- **Medium**: information disclosure from the dev server (source, paths, device list) to a non-developer caller; native crashes (DoS) from untrusted network data or deep links in release builds.
- **Low**: dev-server DoS; crashes reachable only from app-authored JS; issues needing a non-default configuration.

Not security issues: anything that requires control of the app's JS bundle or native code; behavior of debug builds that is documented as development-only; the dev server being reachable from the developer's own machine.

## Anything to leave alone

- Do not report test fixtures, `rn-tester`, or CI scripts.
