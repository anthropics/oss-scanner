# Threat model for Browser Agent Guide

## What this project does and where untrusted input enters
Browser Agent Guide is a Chrome extension (Manifest V3) that provides a deterministic side-panel agent and in-page annotation layer for web automation. It guides browser-operating AI agents using a closed verb registry (`clickAffordance`, `fillAffordance`, `markElement`, etc.) and structured outputs.

Untrusted input enters via:
1. **Host web pages**: Arbitrary DOM elements, mutated attributes, text nodes, and scripts running on third-party origins visited by the user.
2. **Extension message passing**: IPC between injected content scripts (`content/content-script.js`), background service worker (`background/service-worker.js`), and side-panel UI.
3. **External LLM responses**: JSON payloads and structured outputs returned from model API calls.
4. **Stored recipes and annotations**: Custom CSS/JS recipes and anchor selectors persisted in `chrome.storage.local`.

## Components that matter most / least
- **Critical scope**:
  - `content/content-script.js`: Injected into web pages; handles element anchoring and DOM clicks/fills. Must guard against DOM clobbering, prototype pollution from host page JavaScript, and untrusted event triggers.
  - `background/service-worker.js`: Dispatches API calls, manages authentication headers, and processes extension IPC messages. Must enforce sender validation so hostile pages cannot abuse privileged extension APIs.
  - `lib/storage.js`: Storage abstraction for API keys and site-scoped recipes. Must prevent leakage across origins.
  - `lib/recipe-merge.js` & `lib/workflow.js`: Parsing, sanitizing, and applying multi-step action recipes.
- **Out of scope**:
  - Pure cosmetic CSS in `sidepanel/`.
  - Scenarios assuming an attacker already possesses administrative control of the host operating system or raw file access to the user's Chrome profile directory.

## How to exercise it
- Syntax check: `npm run check:js`
- Unit test suite:
  ```bash
  node test/slug.test.mjs
  node test/recipe-merge.test.mjs
  node test/prompt.test.mjs
  node test/workflow-lib.test.mjs
  ```

## Severity rating
- **Critical**:
  - Host page escaping content script isolation to execute arbitrary code within the extension origin.
  - Unauthorized exfiltration of stored user LLM API keys.
  - Universal Cross-Site Scripting (UXSS) where an action injected on one origin can execute on an unrelated origin.
- **High**:
  - DOM-based XSS via unsanitized recipe injection or corrupted anchor selectors.
  - Bypass of the closed verb registry allowing execution of arbitrary JavaScript from agent chat.
- **Medium**:
  - Extension service worker crashes or infinite loops triggered by adversarial DOM structures.
- **Low**:
  - Minor visual distortion in side-panel overlays or transient selector desynchronization.

## Anything to leave alone
- Do not report issues that require physical access to an unlocked device.
- Do not report rate-limiting or quota exhaustion from third-party LLM providers.
