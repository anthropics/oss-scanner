# react-admin threat model

## What this project does and where untrusted input enters

react-admin is a frontend framework (React, TypeScript, Material UI) for building single-page admin and B2B applications on top of REST or GraphQL APIs. It runs entirely in the browser; it has no server component of its own.

The application developer is trusted: their code, configuration, and the `dataProvider`, `authProvider` and `i18nProvider` they write or choose. Untrusted input reaches react-admin through:

- **API responses** returned by the dataProvider (record fields, list results, error payloads). Records can contain data entered by other, less privileged users of the same back-end, so any field value must be treated as attacker-controlled.
- **The URL**: route parameters, record ids, and query string values (`filter`, `sort`, `order`, `page`, `perPage`, `displayedFilters`), which an attacker can craft and send as a link to an authenticated admin user.
- **User input in forms** (inputs, rich text editor, file and image uploads, CSV import/export).
- **Browser storage** (`localStorage` via the store, `ra-data-local-storage`, `ra-data-local-forage`), which may contain values written by another origin context or an older version.

## Components that matter most / least

Most important:
- `packages/ra-core`: routing, controllers (list/edit/create/show), URL parameter parsing, authentication and access-control logic (`useAuthenticated`, `useCanAccess`, `Authenticated`, `CanAccess`, redirects after login/logout), the store, and i18n interpolation.
- `packages/ra-ui-materialui`: components that render record data, especially `RichTextField`, `UrlField`, `EmailField`, `FileField`, `ImageField`, `ReferenceField` links, and anything using `dangerouslySetInnerHTML` or building `href`/`src` attributes.
- `packages/ra-input-rich-text`: HTML produced and consumed by the rich text editor.
- `packages/ra-data-*`: data provider adapters that build HTTP requests from parameters (URL construction, query string encoding, GraphQL query building). Injection of unintended parameters or paths is in scope.
- `packages/ra-i18n-*`: interpolation of translation strings with record values.

Less important or out of scope:
- `examples/`: demo applications, not production code. Only report issues there if they reveal a flaw in a package.
- `docs/`, `docs_headless/`, `cypress/`, `scripts/`, build tooling.
- `packages/create-react-admin`: a project scaffolding CLI run by a developer on their own machine; only report issues reachable with untrusted input (e.g. a template or name argument leading to unexpected file writes).
- Vulnerabilities in third-party dependencies (React, MUI, react-router, TanStack Query, react-hook-form), unless react-admin uses them in an unsafe way.

## Security model

- react-admin is a client-side framework: **authorization must be enforced by the back-end API**. UI-level access control (hiding buttons, menu items or pages via `canAccess`) is a convenience, not a security boundary. Bypassing a UI access check is only in scope if it leads to the client sending a request the application developer explicitly configured it not to send, or to rendering data the client already received for a different, unauthorized purpose.
- The `authProvider` and `dataProvider` are trusted application code. Bugs in a provider written by the developer are out of scope; bugs in the providers shipped in this repository are in scope.
- Rendering record data must never lead to script execution unless the developer explicitly opted into raw HTML. `RichTextField` sanitizes HTML with DOMPurify by default; a sanitization bypass is in scope.

## How to exercise it

From `/src`:

```sh
yarn test-unit                       # all Jest unit tests
yarn test-unit packages/ra-core      # tests for one package
```

Each component has a `*.stories.tsx` file next to it, and most `*.spec.tsx` tests render these stories with Testing Library. Writing a new spec that renders a story with malicious data (from `ra-data-fakerest` or a mocked dataProvider) is the easiest way to build a reproducer. Built packages are in `packages/*/dist`. The avatar/favicon tests in `examples/crm/src/providers/commons/` fetch remote URLs and fail offline; ignore them.

## How we rate severity

- **Critical**: script execution (XSS) in the admin app triggered by data an unauthenticated attacker can inject, with no developer opt-in to raw HTML; or leaking the auth token or credentials to a third-party origin.
- **High**: stored XSS from data entered by a low-privilege authenticated user; open redirect after login/logout to an attacker-controlled origin; a crafted URL that makes the data provider send a request to an unintended endpoint or with unintended parameters (e.g. path traversal in resource names or ids).
- **Medium**: reflected XSS or HTML injection requiring a crafted link and user interaction; sanitization bypasses requiring a non-default but documented configuration; prototype pollution from URL or API data without a demonstrated exploit.
- **Low**: client-side denial of service (a crafted URL or record crashing the page or freezing the tab), information disclosure limited to data the current user can already read.

Not security issues: missing back-end authorization, UI elements visible to users lacking permissions when the API rejects their requests, self-XSS, issues requiring control of the application's own code or providers.

## How we'd like reports and patches

A minimal reproducer as a Jest spec or a story, the affected component or hook, the attacker's position (unauthenticated, authenticated user, crafted link), and a patch with a regression test. Patches should preserve backward compatibility of public APIs where possible.
