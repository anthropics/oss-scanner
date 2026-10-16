# Threat model

Omi is a wearable and desktop AI assistant that records conversations and screen
context, then stores transcripts, memories, and related user data. Cross-user
data exposure and authentication bypass are the highest-impact failures.

## What this project does and where untrusted input enters

Scan **`backend/`** of https://github.com/BasedHardware/omi (Python 3.11 FastAPI).
It is the internet-facing API for consumer devices: REST and WebSocket endpoints
accept audio streams, transcripts, screen frames, user data, OAuth, app/plugin
webhooks, and payment events.

Adversarial inputs (treat as untrusted):

- Any HTTP or WebSocket request, authenticated or not (including `/v4/listen`
  and `/v4/web/listen` audio streaming).
- Uploaded audio and files (sync, speech profiles, imports, screen frames).
- Data from third-party Omi apps, plugins, webhooks, OAuth callbacks, calendars,
  MCP/developer API keys, and Stripe/PayPal payment webhooks.
- Redirect URIs, URLs, and hostnames supplied by clients or third-party apps
  (SSRF, open redirects, webhook callbacks).

## Components that matter most / least

**In scope (highest priority):** `backend/` authn/authz across users' data;
IDOR between users' conversations, memories, people, action items, and files;
WebSocket/audio streaming (`routers/transcribe.py`, `routers/listen/`);
file/audio upload parsing; webhooks and third-party app integrations
(`routers/apps.py`, `routers/integration*.py`, `routers/oauth.py`); SSRF
(including desktop proxy / outbound fetch helpers); injection (command, SQL,
template, header, prompt-injection that yields data exfil or auth bypass);
secrets handling; payment/subscription endpoints (`routers/payment.py`, Stripe).

**Still in scope, lower priority:** rate limiting, DoS, info leaks that do not
expose another user's data, CSRF on cookie-less Bearer APIs, open redirects
that do not leak tokens.

**Out of scope:**

- Flutter mobile app, desktop app binaries/UI, and web frontends.
- Firmware under `omi/` (nRF5340 Zephyr) and hardware design files.
- Docs, examples, and plugins that are not deployed with the backend.
- Issues that require already-compromised Google Cloud / Firebase credentials
  (stolen service-account JSON, admin ADC, or project-owner tokens).
- Pure availability / cost-exhaustion without a security boundary break.

## How to exercise it

Working directory for the backend is `/src/backend`. Interpreter and deps are
in `/opt/venv` (`PATH` already includes it).

```
cd /src/backend
ENCRYPTION_SECRET="omi_ZwB2ZNqB2HHpMK6wStk7sTpavJiPTFg7gXUHnc4tFABPU6pZ2c2DKgehtfgi4RZv" \
OPENAI_API_KEY="test-openai-key-not-real" \
python -m pytest -q -m "not integration and not slow" tests/unit/test_ws_auth_handshake.py
```

`bash test.sh` is the project's unit runner (defaults to `not integration and
not slow`). Many files must run in isolated processes because of `sys.modules`
stub pollution; a verified single-process list is
`tests/.single_process_safe_subset`. Tests marked `integration` need Redis,
Firebase, or vendor API keys — skip them offline. Do not expect live GCP,
Stripe, Deepgram, or Pinecone.

Entry points: `backend/main.py` (FastAPI `app`), routers under
`backend/routers/`, auth helpers in `backend/utils/other/endpoints.py`.

## How you rate severity

- **Critical:** cross-user data access (conversations, memories, audio, screen
  context, profiles); authentication/authorization bypass; remote code execution.
- **High:** privilege escalation; SSRF that can reach cloud metadata or
  internal services; secret/credential exposure (API keys, tokens, ENCRYPTION_SECRET
  material that decrypts user data).
- **Medium:** injection or SSRF without demonstrated cross-user impact or
  internal-network reach; stored XSS on authenticated JSON APIs that is not
  reachable to other users' browsers; payment integrity issues that do not
  leak data (e.g. skipping a paywall for the attacker's own account).
- **Low:** DoS, missing rate limits, verbose errors, theoretical issues without
  a realistic trigger.

Post-auth bugs that let user A read user B's data are **critical**, not medium.
"Works only if Firebase Admin is already compromised" is out of scope.

## Reports and patches

One report per root cause. Include a **minimal PoC** (request, payload, or
unit-test-sized snippet) and a **suggested patch**. Prefer the smallest change
in `backend/` that closes the bug. Do not file duplicates that share a fix.

## Anything to leave alone

Do not report missing production secrets, absent `google-credentials.json`, or
tests that skip without cloud credentials. Do not treat the dummy
`ENCRYPTION_SECRET` in `backend/test.sh` as a leaked production key.
