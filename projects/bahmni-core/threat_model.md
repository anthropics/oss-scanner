# Threat model

## What this project does and where untrusted input enters

- `bahmni-core` is the backend of Bahmni, an open-source hospital management system and EMR. It is a set of
  OpenMRS modules (`.omod`) loaded into an OpenMRS server (platform 2.6.x); it is not a standalone service.
- It stores and serves clinical data: patients, visits, encounters, observations, orders (drug, lab, radiology),
  diagnoses, notes, forms, patient documents and images, and the configuration the Bahmni UI renders.
  Confidentiality and integrity of this data matter.
- Untrusted input enters through the REST controllers in
  `bahmnicore-omod/src/main/java/org/bahmni/module/bahmnicore/web/`, mounted under
  `/rest/v1/bahmnicore/...` and `/rest/v2/...`, and through the admin import/export controllers. Request bodies,
  path variables (UUIDs), query parameters (`offset`, `limit`, `sortBy`, search keys and values, time ranges),
  uploaded CSV files and base64 document payloads all come from authenticated but possibly low-privileged or
  malicious users.
- Some endpoints are unusually sensitive and deserve attention:
  - `SqlSearchController` (`/rest/v1/bahmnicore/sql`) runs SQL that is stored in an OpenMRS global property,
    substituting request parameters as `?` placeholders. The SQL text is trusted configuration, but the
    parameters, the query name, and the `globalproperty` sub-endpoint that returns any global property value are
    all caller-controlled.
  - `BahmniConfigController` reads and writes the per-app configuration the UI renders, with no explicit
    privilege check in the controller.
  - `VisitDocumentController` and `PatientDocumentServiceImpl` accept base64 documents, build file paths from
    patient and encounter data, decode images and generate video thumbnails.
  - `AdminImportController` accepts multipart CSV uploads for patients, encounters and form-to-encounter import.
  - `TemplateRenderController` forwards a request body to an external template service, passing the caller's
    session and authorization headers through.
  - `EmailCommunicationController` sends mail whose content comes from the request body.
  - The ELIS/ERP atom feed clients (`openmrs-elis-atomfeed-client-omod`) and `BahmniOdooClient` make outbound
    HTTP calls and parse the responses.
- We assume the surrounding OpenMRS web services layer authenticates the caller before a controller runs, that
  OpenMRS global properties, the database and the file system are controlled by the administrator and are
  trusted, and that outbound service URLs are operator configuration.

## Components that matter most / least

- Most important: the REST controllers under `bahmnicore-omod/.../web/v1_0/controller/` and `web/v2_0/`, the
  privilege checks inside them, and the DAOs that build HQL or SQL in `bahmnicore-api/.../dao/impl/`,
  `bahmni-mapping/.../dao/impl/`, `obs-relation/.../dao/impl/` and `admin/.../config/dao/impl/`.
- Important: `bahmnicore-api/.../service/impl/*` (business logic, including `PatientDocumentServiceImpl` file
  handling), `bahmnicore-api/.../util/SqlQueryHelper.java`, the CSV import/export code in
  `admin/.../csv/` and `bahmnicore-omod/.../web/v1_0/controller/AdminImportController.java`, the atom feed
  clients, and `bahmnicore-omod/.../web/v1_0/client/`.
- Less important: `bahmnicore-omod/.../web/contract/*` and `web/model/*` (plain data holders), `bahmnicore-ui`
  (UI mapping code), `jss-old-data` and `vagrant-deploy` (migration and deployment helpers, not deployed in a
  running server).
- Out of scope: third-party dependencies (OpenMRS core, webservices.rest, Spring, Hibernate, jcodec and so on).
  Report issues in them only if this project uses them in an unsafe way.

## How you rate severity

- Authorization bypass that exposes patient data to a user without the right privilege, or lets a user create or
  change clinical records (orders, observations, encounters, documents) without the matching privilege: high,
  and critical if it allows tampering with medication orders or records in a way that could harm a patient.
- SQL or HQL injection reachable by an authenticated user: high, and critical if it reads or modifies data
  outside the caller's authorization.
- Path traversal or arbitrary file write/read through document upload, download or delete: high, and critical if
  it reaches files outside the configured document directory.
- Disclosure of secrets through the `globalproperty` endpoint or config endpoints (database credentials, mail
  passwords, API keys held in global properties): high.
- Server-side request forgery, credential forwarding, or session leakage through the template service proxy:
  high.
- Insecure deserialization, XXE, or unsafe image/video parsing reachable through request data: high.
- Stored XSS in configuration or clinical text that the UI renders: medium to high, depending on whether it
  reaches another user's session.
- Unbounded `limit` or `offset`, oversized uploads, or similar resource exhaustion by an authenticated user: low.
- Verbose error messages that echo exception text back to the client: low, unless they leak secrets or patient
  data.
- Findings that require administrator access, a modified database, or a modified server configuration: low.

## Anything to leave alone

- Do not report problems that exist only in test code, in commented-out code, or in `jss-old-data` and
  `vagrant-deploy` scripts.
- Do not report outdated dependency versions on their own. Report a vulnerable dependency only with a concrete,
  reachable path from this project's code.
- Do not report that the modules rely on OpenMRS for authentication, session handling and CSRF protection, or
  that the SQL in `SqlSearchController` is administrator-supplied configuration. Report only how caller-controlled
  values reach it.
- Do not report missing rate limiting, version disclosure, or the absence of security headers on their own.

## Reports and patches

- Describe a reproducer as a concrete request to the affected endpoint: the HTTP method and path, the parameters
  or body, the privileges the caller needs, and the code path that follows. Running tests is not expected.
- Proposed patches should be minimal, follow the existing code style, and stay within the affected module.
