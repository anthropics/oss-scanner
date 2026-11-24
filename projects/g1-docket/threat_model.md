# Threat Model: G1-Docket

## What this project does and where untrusted input enters
G1-Docket is a cryptographic data attestation framework for AI gateways and LLM control planes. It issues and validates signed, expiring DSSE (Dead Simple Signing Envelope) provenance records over data chunks at rest and in transit before the data is ingested by models.

Untrusted input enters via:
1. Raw data payloads submitted for pre-validation and cryptographic attestation.
2. HTTP/REST API endpoints and webhook ingestion handlers.
3. Serialized attestation envelopes (JSON/DSSE) received from untrusted clients.
4. Merkle chunk trees and vector RAG chunk inputs.

## Components that matter most / least
* Critical / In-Scope:
  - DSSE cryptographic signature verification algorithms (ECDSA / Ed25519).
  - Envelope expiration, replay validation, and provenance claim integrity.
  - Token and key parsers in the attestation engine.
  - Serialization / deserialization routines and input validation parsers.
* Lower Priority / Out of Scope:
  - Sample CLI wrappers in examples/ and test runners in pc_demo_folder/.
  - Demo scripts designed strictly for local demonstration.

## How you rate severity
* Critical: Any cryptographic verification bypass, unauthorized attestation forgery, secret key extraction, or Remote Code Execution (RCE) in pre-validation parsers.
* High: Premature envelope validation, replay attack vulnerability, or parser crashes/DoS in gateway hot-paths.
* Medium: Bounded Denial of Service (DoS) requiring extreme resource consumption, or information disclosure of non-sensitive metadata.
* Low / Informational: Style discrepancies or non-exploitable memory usage in benchmark utilities.
