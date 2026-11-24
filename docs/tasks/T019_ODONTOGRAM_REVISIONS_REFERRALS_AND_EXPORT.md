# T019 — Optimistic Odontogram Restoration Revisions & Export, External Referrals, Eligibility Flags & Structured Clinical Export
Priority P1 (`ODN` / `EMR` / `PAT`) · Owner: Clinical Charting & Interoperability · Depends T004, T007, T010, T017

**Status (2026-11-24):** Completed (versioned odontogram legend, optimistic tooth restoration revisions & structured print/export, reviewed external referrals, non-destructive document eligibility evaluator, and structured clinical archive export verified in `test_odontogram_revisions_referrals_export.py`). See [ADR-015](../adr/ADR-015-odontogram-revisions-referrals-delegation-and-ops-assistant.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Clinician-Reviewed Odontogram Legend (`ODN-006`):**
   - `odontogram_legend_entry` versions `(clinic_id, code, version_number)` without silently remapping prior tooth restoration history (`legend_version_number` frozen at write time). Only `dentist`/`medical_director` may publish legend versions (`403` otherwise).
2. **Optimistic Tooth Restoration Revisions & Export (`ODN-007`, `ODN-008`, `ODN-010`):**
   - `odontogram_restoration_state` + `odontogram_restoration_revision` record documented source (`existing_external_reported` | `performed_in_clinic_demo`), date, evidence, and monotonic `revision_no`.
   - Updates require `expected_revision`; stale revision fails closed with `409 Conflict` instead of silent last-write-wins (`ODN-010`).
   - `GET /api/v1/patients/{id}/odontogram/export` reconciles findings, performed procedures, and restoration revision history with deterministic `export_sha256` (`ODN-008`).
3. **Reviewed External Referral Documents (`EMR-013`):**
   - `external_referral_document` ingests external referrals in `quarantined_unreviewed` status with origin facility metadata and `content_sha256`; only `dentist`/`medical_director` can transition to `clinician_reviewed`.
4. **Document Expiry & Eligibility Status (`PAT-010`):**
   - `GET /api/v1/patients/{id}/document-eligibility` flags missing, withdrawn, or stale consents and unanswered medical risk reviews while verifying that existing signed `ClinicalDocumentSnapshot` hashes remain 100% unaltered.
5. **Structured Clinical Export + Attachment Manifest (`EMR-014`):**
   - `GET /api/v1/clinical-documents/{snapshot_id}/structured-export` exports exact signed snapshot version, form metadata, and encrypted `ArchiveObject` attachment digests (`409` if snapshot is still `ready_for_signature`).

## Mandatory Negative Tests (Written Before Domain Code)
1. Concurrent odontogram restoration edit with stale `expected_revision` -> `409`; updating legend `v1 -> v2` preserves `legend_version_number=1` on historical revisions (`ODN-006`, `ODN-010`).
2. Non-clinician attempting external referral clinical review -> `403`; exporting unsigned `ready_for_signature` snapshot -> `409`.
3. Withdrawing/expiring consent flags `eligible_for_elective_procedure=False` in `document-eligibility` while `ClinicalDocumentSnapshot.canonical_sha256` stays bit-for-bit identical (`PAT-010`).
