# Threat model: GuideChimp

## What this project does and where untrusted input enters

GuideChimp is a client-side JavaScript library (ES module and UMD bundle, built with Vite and Sass) for product
tours and user onboarding in web pages. A host page defines **tour steps**, each with a title, description,
target element, position and options, and GuideChimp draws an overlay, highlights the element and shows a
tooltip with navigation, progress and optional extras. Steps can be defined in JavaScript objects or in HTML
`data-guidechimp-*` attributes. The library runs entirely in the visitor's browser; it has no server component.
Optional plugins live in `plugins/` (beacons, blurred overlay, lazy loading, Vue Router integration).

Untrusted input reaches the code through:

- **Step content**: `title`, `description` and button labels. The library renders **HTML** here on purpose
  (the README states HTML can be used in tooltip text), through its templates in `src/templates` and
  `innerHTML`.
- **`data-guidechimp-*` attributes** and the **DOM** the host page already contains. If the host page lets
  users author markup (comments, profiles, CMS fields), an attacker can place attributes that GuideChimp then
  reads as steps.
- **Selectors, URLs and options** passed in step definitions: target selectors (`querySelector`), `data-` URLs,
  custom classes, `position` and other options.
- **Remote tour definitions**, where a host page loads steps from a server response (`fetch`/JSON) and passes
  them in.
- **The host page's custom event handlers and templates**, which the library calls.

## Trust model

- **The host page's developer is trusted.** Step objects, templates and options written by the developer are
  trusted input, including HTML in `description`. HTML in developer-written step content is **not** a finding.
- **Content that originates from end users or third parties is untrusted.** When the host passes such content
  into a step (a user's display name in a title, a stored comment in a description, a tour fetched from an
  untrusted origin), GuideChimp's job is to not make things worse: it must not turn text that is meant as text
  into executable markup, and it must not evaluate strings as code.
- **The library must be safe by default in the parts that are not documented as HTML.** For example text-only
  fields, button labels, progress text, attribute values and class names should be inserted as text or
  validated, not parsed as HTML.
- **No server and no stored secrets.** Impact is client-side: script execution in the host page's origin,
  content spoofing, data exfiltration from the page, denial of service of the page.

## Components that matter most / least

Most important:

1. `src/GuideChimp.js`: every place a value reaches `innerHTML`, `insertAdjacentHTML`, `outerHTML`, `setAttribute`
   (`href`, `src`, `on*`), `document.write`, `eval`/`Function`, or a selector. Notably the button, title and
   description creation (`createDescriptionEl`, the tooltip and navigation code) and step data parsing.
2. `src/templates/*`: the template functions (`description`, `customButtons`, `next`, `notification`, ...) return
   HTML strings that `GuideChimp.js` inserts. Check which of their inputs are escaped and which are
   concatenated raw, and any path where a user-influenced string becomes part of a *template* a host can
   override, or is evaluated as code.
3. Parsing of `data-guidechimp-*` attributes into step objects, including JSON-valued options and
   `data-` values used as URLs or selectors.
4. `src/utils/*`: DOM helpers, element lookup, scrolling and positioning code; prototype pollution through
   merging of user-supplied option objects (the library uses lodash `merge`, which has had prototype-pollution
   advisories: check which lodash version is resolved and whether untrusted JSON reaches it).
5. `plugins/*`: the beacons, lazy-loading and Vue Router plugins, which handle more external input
   (route data, remote loading).

Less important: `demo/`, `docs/`, `build/` (tooling), styles in `src/assets`.

Out of scope: lodash and other dependencies themselves (report how GuideChimp uses them), browser bugs, and
issues that require the host developer to write malicious code themselves.

## How to exercise it

The image is built with `npm ci` and `npm run build` (output in `/src/dist`); the checkout is at `/src`. There
is no network. Tests run with Vitest and happy-dom (`npm run test`, tests under `test/`).

- A reproducer is a Vitest test, or a small Node script using `happy-dom`/`jsdom`, that builds a page, starts a
  tour with a crafted step or `data-guidechimp-*` attribute, and asserts that a script, an event handler
  attribute or an unexpected element is created or executed (`document.querySelector('img[onerror]')`, a global
  flag set by the payload, and so on). Include the exact step definition and the HTML of the host page.
- Headless browser tests are not available offline unless Chromium is installed in the image; happy-dom is the
  supported route.

## How you rate severity

- **Critical**: DOM-based XSS that fires with step content or an attribute the library documents as *text* or
  that a host would reasonably fill from untrusted data, with no developer error needed; code execution through
  template evaluation of an untrusted string; prototype pollution that leads to code execution in the page.
- **High**: XSS through `data-guidechimp-*` attributes that a page lets untrusted users inject (the attribute is
  the *only* thing the attacker needs to control); script or `javascript:` URL injection through a link/URL
  option; prototype pollution without a demonstrated gadget but with reachable global effect.
- **Medium**: a way to spoof or overlay page content outside the step's own tooltip (clickjacking-style
  overlay), selector injection that makes the library act on an element outside the intended scope,
  denial of service of the page from a crafted step definition (infinite loops, catastrophic regex), loading of
  a remote resource from an untrusted value without validation.
- **Low**: hardening gaps with no demonstrated impact, accessibility or privacy issues without a security
  consequence.
- Memory-safety does not apply (JavaScript). Impact is limited to the page: rate by what an attacker gets in the
  host page's origin. A claim without a working reproducer is at most Medium.

## Anything to leave alone

- HTML or script in the `description` (or any field the README documents as HTML) written by the page's
  developer. That is the documented feature.
- A host page that deliberately passes unsanitised user input into HTML fields: sanitising it is the host's
  duty, unless the library's documentation says it does so.
- `demo/`, `docs/`, `build/` (including `cdn.clear.cache.js`) and `privacy-policy.md`.
- Dependency CVEs with no reachable path from the library's own code, and bundler/tooling advisories that affect
  only the build.
- Browser-specific quirks that need an already-compromised page.

## Reports and patches

One finding per report, with file and line, the trust boundary crossed, and a Vitest or Node reproducer that
runs without network access. A minimal patch in the existing style is preferred, with a test in `test/`, and it
must keep documented HTML fields working (escape or validate the undocumented ones; do not silently sanitise the
documented HTML in `description`).
