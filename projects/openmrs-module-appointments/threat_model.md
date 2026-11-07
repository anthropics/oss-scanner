# Threat model

## What this project does and where untrusted input enters
- An OpenMRS module (`.omod`, platform 2.8.x) for appointment scheduling: appointments, recurring appointments,
  appointment services and their attributes, specialities, providers, and teleconsultation links. It runs inside an
  OpenMRS server and handles patient-linked scheduling data.
- Untrusted input arrives at the Spring MVC controllers in `omod/src/main/java/org/openmrs/module/appointments/web/controller/`,
  under `/ws/rest/v1/appointment`, `/appointmentService`, `/appointment-services`, `/appointmentSearch`,
  `/speciality`, `/adhocTeleconsultation` and `/appointment-service-attribute-types`. Inputs are JSON bodies,
  path variables (UUIDs) and query parameters (dates, search terms, status filters).
- The OpenMRS web layer is assumed to authenticate the caller. Authorization is enforced by privilege checks in the
  controllers and services.

## Components that matter most / least
- Most: controllers and their privilege checks, `api/.../service/impl`, the DAOs and search queries, and the
  `atom-feed` module that publishes events.
- Less: model and contract classes, and tests.
- Out of scope: OpenMRS core, webservices.rest, Spring and Hibernate, except where this module uses them unsafely.

## How to exercise it
- `./mvnw -B -ntp test` runs the unit tests in `api`, `atom-feed` and `omod`. There is no running OpenMRS server in the
  sandbox.

## How you rate severity
- Authorization bypass that exposes appointment or patient data, or lets a user create, change or cancel appointments
  without the matching privilege: high.
- SQL or HQL injection through search filters: high, critical if it reads or writes data beyond the caller's rights.
- Access to another provider's, service's or patient's appointments through a guessable identifier (IDOR): medium to high.
- SSRF, XXE, insecure deserialization or path traversal reachable from request data: high.
- Resource exhaustion by an authenticated user (unbounded recurrence or date ranges): low to medium.
- Findings that require administrator access or a modified database: low.

## Anything to leave alone
- Test-only and commented-out code, and outdated dependency versions without a reachable path.

## Reports and patches
- A failing JUnit test is the most useful reproducer. Keep patches minimal and keep `./mvnw -B -ntp test` passing.
