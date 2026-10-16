<!-- Threat model for the Cipansor IMS enrolment. The scanner reads this before it starts. -->

# Threat model — Cipansor IMS (`cipansor/cipansor`)

## 1. What the system is

Cipansor is the information management system of **Yayasan Pesantren Cipansor**, a
boarding-school foundation in Tasikmalaya, West Java. It runs four schools (TK
Qur'an, SD IT, SMP IT, SMA Qur'an + tahfidz), their admissions, attendance, report
cards, tahfidz records, finance, staff HR and payroll, and electronic
correspondence with a digital signature.

One pnpm + Turborepo monorepo, two deployed hosts:

| Workspace | Stack | Runtime role |
|---|---|---|
| `apps/api` | Express 5, Prisma 7 (PostgreSQL), Redis, JWT, Zod, helmet, express-rate-limit | **the trust boundary** |
| `apps/web` | Next.js 16 App Router, React 19, React Query | untrusted client; also renders the public site |
| `packages/shared` | TypeScript + Zod | request/response contracts shared by both |

Deployed on the foundation's own Azure infrastructure at two hosts:
`cipansor.or.id` (public landing + verification pages) and
`portal.cipansor.or.id` (everything behind a login). Production and staging are
deployed from CI (`.github/workflows/deploy-{staging,production}.yml`). This is a
single-organization deployment — there is no multi-tenant SaaS instance to scan as
a running service; the risk lives in the code.

Scale, from the repository itself: ~595k lines of TypeScript across 2,215 files;
`apps/api` has 95 modules, 430 test files and 114 `app.use` mounts; `apps/web` has
437 pages and 132 Playwright specs. The Prisma schema is 11,012 lines: **306
models, 163 enums, 51 migrations**.

## 2. Where untrusted input enters

Every HTTP request to `apps/api` is untrusted: JSON bodies, query strings, path
parameters, headers, multipart uploads, and the session-free routes below. The web
client is itself an untrusted caller as far as the API is concerned.

**Unauthenticated endpoints (the reason to scan this code).** All are mounted
*before* `authenticate`, all rate-limited, none needs a session. Sources:
`apps/api/src/modules/{admissions,esign,certificates}/*.routes.ts`.

| Method + path | Attacker-controlled input | Notes |
|---|---|---|
| `GET /api/v1/admissions/public/intakes` | query | public SPMB page |
| `POST /api/v1/admissions/public/registrants` | JSON body | Turnstile-gated, 10 req/min/IP |
| `POST /api/v1/admissions/public/registrants/:id/documents` | **multipart file upload** | own limiter; Zod-validated |
| `GET /api/v1/admissions/public/track` | query | applicant status |
| `POST /api/v1/admissions/public/parse-document` | **base64 file payload** | capped at 2 MB; base64-decode + regex, no real OCR (see below) |
| `POST /api/v1/esign/verify-pdf` | **uploaded PDF** | Turnstile-gated; Ed25519 verification |
| `GET /api/v1/esign/public/key-status` | query (fingerprint) | signing-key state |
| `GET /api/v1/certificates/verify/:code` | path param | public certificate check |
| `GET /api/v1/certificates/public/:code/download` | path param | public file download |

Three things make the public surface worth a careful read:

- **Uploads.** `multer` memory storage at four sites (`esign.routes.ts`,
  `hr.routes.ts` punch photo, `permits.routes.ts` doctor note, `units.routes.ts`
  accreditation PDF). The identity-document path accepts a KTP image/PDF up to
  `MAX_IDENTITY_DOCUMENT_BYTES` with a `fileFilter`. Memory storage means a size or
  type check that is wrong is a memory-exhaustion or content-sniffing bug; a
  `fileFilter` that trusts the client-supplied MIME type is a content-type bypass.
- **File bytes and signatures.** `POST /esign/verify-pdf` computes
  `sha256(uploadedBuffer)`, looks the hash up in the DB, and verifies an
  **Ed25519** signature over that hash (`modules/esign/esign.service.ts`,
  `utils/esign.ts`, `ESIGN_ALGORITHM = 'Ed25519'`). It **does not run a PDF
  parser** - it reads the raw bytes - but it is anonymous, consumes an
  attacker-controlled file, and drives a cryptographic verification plus a
  revocation lookup (`matchRevokedCopy`). Bugs here are a forged-signature or DoS
  class, not a parser class; read it that way.
- **`parse-document` is deliberately *not* an OCR/PDF parser.** Per the code's own
  contract (`modules/admissions/document-ocr.service.ts`), it base64-decodes the
  payload, checks for PNG/JPEG/PDF magic bytes and, when the content is *not*
  binary, regex-scans the decoded text for a 16-digit NIK/KK and compares it to the
  applicant's input; every real binary document is passed to a human for manual
  verification. The request is capped at 2 MB by `parseDocumentSchema` and shares
  the strict registrant limiter. The interesting surface is the base64 decode, the
  magic-byte sniff and the regex - not deep document parsing. `pdf-lib` in this
  project *generates* PDFs (letters, certificates, raport); it is not on an
  attacker-input path.

**Authenticated but still attacker-controlled.** Everything behind
`authenticate`/`authorize`: attendance selfie uploads, permit documents, finance
and payroll records, grades and report cards, plus a chatbot and WhatsApp/email
notification paths that build outbound requests from stored data.

## 3. Components to spend effort on

Ranked, most important first:

1. **`modules/auth` + `middleware/auth.ts`.** Login, TOTP 2FA (`otplib`: TOTP plus
   stored recovery codes), JWT issue/verify (`lib/jwt.ts`), password change, and
   the authorization middleware (`authenticate`, `authorize(RoleCode…)`,
   `hasPermission`, `sameUnit`, `isAdmin`, `isSuperAdmin`). This module also holds
   the **privilege-escalation guards** (e.g. a unit admin must not be able to mint
   governance roles); a hole here is the worst case for a school system.
2. **`modules/esign`.** The public `verify-pdf` path, identity-document upload and
   key activation, Ed25519 signing and revocation — the highest-value target
   because it is reachable *and* anonymous.
3. **`modules/admissions`** public routes: registrant creation, document upload,
   `parse-document`.
4. **Upload handling everywhere** (`multer` configs; `utils/attendance-photo-store.ts`
   writes to `private/attendance`, deliberately *not* the statically-served
   `public/uploads`; `utils/esign.ts` file handling). Path traversal, a type filter
   that trusts the client, or a write into a served directory is the worst case.
5. **Outbound-URL builders** — the SSRF/open-redirect surface. `modules/calendar/
   holiday-sync.service.ts` fetches an **admin-configurable** `sourceUrl`
   (`redirect: 'error'`, https-only check), `modules/admissions/admissions.service.ts`
   validates a document URL as `http(s)://`, `modules/notifications/*` posts to
   WhatsApp/Gmail endpoints, and `modules/chatbot/providers/openai-compatible.ts`
   posts to a configurable `baseUrl`.
6. **Authorization in aggregate/report queries** — dashboards, report cards,
   finance summaries. Data is scoped by role and unit; a missing scope is a
   cross-unit leak.
7. **Raw SQL.** `$queryRaw`/`$executeRaw` appear in `hr`, `assessment`, `tahfidz`,
   `correspondence` and `performance-management` (e.g. advisory locks, aggregate
   reports). Prisma parameterizes tagged templates, but any string-built fragment
   is a real injection.
8. **Scheduled jobs** (`src/jobs/`, 35 files) and `eventBus` side effects.

## 4. Data at risk

The API holds minors' personal data and staff records: student and guardian
identities, uploaded **KTP** identity documents and attendance selfies, clinic/UKS
records, grades and tahfidz progress, SPP/SPMB payments and payroll, and
Ed25519-signed official letters. Any unauthenticated read, cross-unit read, or
write outside the intended scope is a serious incident for real children. This is
the "sensitive data" half of the inclusion criteria and it is not in doubt.

## 5. Out of scope for this audit

- `apps/web/public/icons/**` and static assets; bundled `node_modules`; generated
  `dist/`.
- Test fixtures under any `tests/`/`e2e/` directory, and synthetic demo/presentation
  seed data (`prisma/seeds/`, `seed-presentasi.ts`) — not real people.
- Missing security headers / TLS in `next.config.ts` or `nginx.conf` unless the
  configuration actively defeats a control; those are set in the deployment layer.

## 6. How severity maps to this project

- AuthN bypass, privilege escalation across roles/units, or any unauthenticated or
  cross-tenant read of another person's records: **critical**.
- SQLi, SSRF, path traversal, arbitrary file read/write, or stored/reflected XSS
  reachable from an HTTP endpoint: **high**, **critical** if unauthenticated or
  leading to code execution.
- An authorization gap needing a valid session (a role reaching data its role
  should not): **high**.
- DoS / unbounded resource use / a missing rate limit with no demonstrated
  amplification: **medium**.
- Disclosure of data the caller may already see (verbose errors, version banners):
  **low**.
- The legacy `UserRole` enum and the `src/services/*` / `lib/api-client.ts`
  re-exports are being removed; a finding that exists only because of them is low
  priority — report the `RoleCode` equivalent instead.

## 7. How to build and exercise it

- **Build (what this Dockerfile does):** install deps from the lockfile, build
  `@cipansor/shared`, `prisma generate`, then `tsc` the API. The API unit suite
  (`pnpm --filter api test`, vitest) runs as a fatal build step.
- **Unit suite:** Prisma is mocked, so it needs no database and covers services,
  controllers, RBAC guards and the repository's own guard scripts.
- **A full end-to-end run** needs PostgreSQL and Redis. Point `DATABASE_URL` at any
  reachable Postgres, `pnpm --filter api db:push`, then `pnpm --filter api dev` and
  issue requests against `http://localhost:3001`. `GET /health` answers without a
  database. The Dockerfile stops at a green build rather than starting the servers.
- **Web:** `pnpm --filter web build`; Playwright specs live in `apps/web/e2e/`
  (they need the full stack and are not run in this image).
