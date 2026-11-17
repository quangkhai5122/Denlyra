# EMR: form field mapping, signing and clinical record lifecycle

**Research worksheet** — not a reproduced official form or certified interface. Retrieve the authoritative original Appendix XXVIII form, have a licensed dentist review every field and approve mappings.

## Form template registry design
```
FormTemplate(
  template_id, official_code, title, authority, source_url,
  source_sha256, issued_on, effective_from, effective_to,
  approved_by, approved_at, status, schema_version
)
FormField(
  template_id, field_code, label_vi, type, required_when,
  domain_path, validation_rule_id, privacy_class, provenance_source
)
FormInstance(
  template_id, patient_id, encounter_id, actor, created_at,
  data_snapshot_hash, review_state, signature_evidence_id
)
```

## Starter field-mapping worksheet (NOT an exhaustive 16/BV-01 form)
| Clinical concept to verify against original form | Proposed domain field | Data semantics and validation |
|---|---|---|
| Patient identity | `Patient.id`, identifiers and related persons | Internal ID distinct from official ID; manual identity review |
| Visit time | `Encounter.started_at` | Original event time vs record time distinct |
| Reason for visit | `ClinicalObservation.type=reason_for_visit` | Free text, source and author recorded |
| Illness history | `MedicalHistory` | Review and signing requirements vary by clinic |
| Allergies | `AllergyRecord` | `unknown` vs `no_known_allergies` vs positive distinct |
| Dental examination | `DentalFinding` | FDI tooth ref, surface and observation time |
| Diagnosis | `ClinicalAssessment` | Clinician controlled, no LLM inference |
| Proposed plan | `TreatmentPlanVersion` | Draft vs clinically approved version separate |
| Performed procedure | `ProcedureRecord` | Independent event, never inferred from charge |
| Signatures/confirmations | `SignatureEvidence` | Exact version, signer, approved method, verification results |
| Imaging | `ImagingStudy`, `MediaAsset` | Source device and patient linkage verified |
| Summary/export | `ClinicalDocument` | Exact approved form and snapshot version |

**Review checklist for licensed dentist:** copy original form field code; label; cardinality; conditional requirements; authorship; signature requirement; terminology code; negative/unknown semantics; report rendering; cross-field checks; example synthetic value. No coding agent may mark this complete alone.

## State machines and immutable artifact design
`draft → ready_to_authenticate → authenticated → addendum_created`; invalid states always fail closed. **The current code uses `draft → demo_locked` ONLY**, no real auth/identity/legal signature.

A production signed artifact envelope should record:
- canonical content bytes/hash and encoding/schema;
- exact approved form template ID/version and reference;
- author, signer, time source, signing method, sign evidence and verification status;
- parent encounter/patient/tenant/branch;
- related image/attachment hashes and manifest;
- immutable snapshot location, retention class, amended-from/version links;
- independent audit/event correlation.

The signer signs the exact canonical artifact **after verifying** it. A stored `is_signed=true` boolean is never sufficient. A future `signature_provider.verify()` adapter must be covered by mismatched signer, revoked credential, expired certificate, altered content and offline-provider negative tests. Signature legal validity must be reviewed by counsel.

## Legacy paper conversion
Legacy scan does not inherit a legal digital signature merely by being a PDF. Preserve original paper folder reference, scan operator, image hash, page count and reviewer. `unverified → pages_checked → identity_linked → verified_legacy_archive`, never `digitally_signed` by conversion. Patient identity collisions always human-approved. See `LEGACY_MIGRATION.md`.

## Clinical terminology
ISO 3950/FDI tooth notation is a proposed reference. Record permanent vs primary, surface schema, observed chronology, state of a restoration and source clinical record. The odontogram is a projection over immutable findings, not a single mutable per-tooth status. Do not invent clinical codes or procedures; clinic reviewer chooses localized terminology and coding framework.

## FHIR mapping
Target FHIR R4 `Patient`, `RelatedPerson`, `Practitioner`, `Organization`, `Appointment`, `Encounter`, `Condition`, `Procedure`, `CarePlan`, `DocumentReference`, `Composition`, `Provenance`, `AuditEvent`, `Consent`. R4 is chosen for interoperability baseline; verify profiles required by each external partner, and do not store all dental relational data as raw FHIR JSON. Signature validity remains jurisdiction-specific.

## Consent and patient communication
Treatment consent is different from data-processing consent, marketing permission and financial acceptance. Version each independently; guardian authority scoped; withdrawal may not invalidate legally retained clinical records. Portal must only publish clinician-approved summaries, never unreviewed LLM output.
