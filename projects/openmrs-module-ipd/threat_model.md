# Threat model

## What this project does and where untrusted input enters
- `openmrs-module-ipd` is the backend of Bahmni's Inpatient Department (IPD) care and monitoring features. It is an
  OpenMRS module (an `.omod`) that is loaded into an OpenMRS server (platform 2.8.x); it is not a standalone service.
- It handles clinical data about admitted patients: ward and bed assignments, care teams, medication schedules, and
  medication administration records, notes and acknowledgements. Confidentiality and integrity of this data matter.
- Untrusted input enters through the HTTP REST controllers in `omod/src/main/java/org/openmrs/module/ipd/web/controller/`,
  under `/ws/rest/v1/ipd/...` and `/ws/rest/v1/ipdVisit/{visitUuid}/...`. Request bodies, path variables (UUIDs) and
  query parameters (`offset`, `limit`, `sortBy`, search keys and values, time ranges) all come from authenticated
  but possibly low-privileged or malicious users.
- We assume the surrounding OpenMRS web services layer authenticates the caller before a controller runs, and that
  OpenMRS global properties and the database are controlled by the administrator and are trusted.

## Components that matter most / least
- Most important: `omod/.../web/controller/*` (the attack surface), the privilege checks inside them, and the
  Hibernate DAOs in `api/src/main/java/org/openmrs/module/ipd/api/dao/impl/` (which build HQL, some of it dynamically).
- Important: `api/.../service/impl/*` and `omod/.../web/factory/*` and `web/mapper/*`, which turn request contracts into
  persisted entities, and `api/.../events/*` and `api/.../scheduler/*`, which hold event handlers and scheduled tasks.
- Less important: `omod/.../web/contract/*` and `web/model/*` (plain data holders), and `src/test/**` (tests).
- Out of scope: third-party dependencies (OpenMRS core, webservices.rest, FHIR2, Spring, Hibernate and so on). Report
  issues in them only if this module uses them in an unsafe way.

## How to exercise it
- `./mvnw -B -ntp test` runs the unit tests in `api` and `omod`. The project is built and installed into `~/.m2`
  already, and a full OpenMRS server is not available in the sandbox, so controllers and DAOs are best exercised
  through unit tests with mocked `Context`, services and Hibernate sessions, or by reading the code.

## How you rate severity
- Authorization bypass that exposes patient data to a user without the right privilege, or lets a user create or change
  medication tasks or medication administration records without the matching privilege (for example, any of
  `Edit Medication Tasks`, `Edit Medication Administration`, `Edit adhoc medication tasks`, `Approve Amend Note`):
  high, and critical if it allows tampering with medication records in a way that could harm a patient.
- Missing privilege check on a read endpoint that returns patient-identifying or clinical data: medium to high,
  depending on how much data is exposed.
- SQL or HQL injection reachable by an authenticated user: high, and critical if it reads or modifies data outside the
  caller's authorization.
- Insecure deserialization, XXE, SSRF or path traversal reachable through request data: high.
- Unbounded `limit` or `offset`, or similar resource exhaustion by an authenticated user: low.
- Verbose error messages that echo exception text back to the client: low, unless they leak secrets or patient data.
- Findings that require administrator access, a modified database, or a modified server configuration: low.

## Anything to leave alone
- Do not report problems that exist only in test code or in commented-out code.
- Do not report outdated dependency versions on their own. Report a vulnerable dependency only with a concrete, reachable
  path from this module's code.
- Do not report that the module relies on OpenMRS for authentication and session handling.

## Reports and patches
- A reproducer as a failing JUnit test in the existing `api` or `omod` test layout is the most useful form.
- Proposed patches should be minimal, follow the existing code style, and keep `./mvnw -B -ntp test` passing.
