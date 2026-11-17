# Interoperability strategy: FHIR, DICOM, government systems, vendors

## Design principle
**Domain-first, adapters-second.** Dental charts, booking resource overlap, billing rules and clinical versioning belong in a normalized relational model. FHIR R4 resources provide structured exchange adapters. Exact Vietnam Implementation Guides must be discovered and verified with clinical partner/government system; generic FHIR payload does NOT imply regulatory compliance.

## Initial FHIR mappings
Patient→Patient; Staff→Practitioner/PractitionerRole; Clinic/Branch→Organization/Location; Appointment→Appointment; Encounter→Encounter; ClinicalAssessment→Condition; ProcedureRecord→Procedure; Plan→CarePlan; ClinicalDocument→DocumentReference/Composition; Consent→Consent; author/sign evidence→Provenance; access audit→AuditEvent. Version, identifiers, clinical terminology and consent profiles require site-approved mapping. FHIR reference: https://hl7.org/fhir/R4/ .

## DICOM adapter
Orthanc for gateway/archive and OHIF for viewer when devices support DICOM/DICOMweb. Always verify patient+study ID before ingestion, import with quarantine on ambiguity, manifest SHA256/size, role-scoped viewer access and original file retention. Images can be large, require separate backup and confidentiality measures. Never infer disease by image processing without medical-device regulatory validation.

## External adapters
- Zalo OA/ZNS and SMS: official API, permission, templates, delivery evidence, opt-out and cost approval.
- E-invoice/accounting: only actual contracted provider APIs; do not invent tax endpoints.
- Lab: limited case-specific share, provider identity, signed URL expiry, no full chart access.
- Payment: signed and idempotent webhook, separate settle/receipt/allocate/reconcile states.
- E-sign: actual legal identity/signature validation with fail-closed status, no fake `signed=true`.
- Health information exchange: permissions, standards, exact government endpoint, test/certification where required.

## Test matrix
For each adapter: fake sandbox and malicious data; schema change, 400/401/403/409/429/500; duplicate events, out-of-order events, timeout, retries, cancellation, stale token, PHI isolation, localization and logging. Do not assume any provider exposes integration simply because it is advertised as 'connected'.
