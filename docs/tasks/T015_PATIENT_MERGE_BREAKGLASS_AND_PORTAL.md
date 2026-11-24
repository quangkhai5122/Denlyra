# T015 — Reversible Dual-Confirmed Patient Merge, Break-Glass Access & Clinician-Published Patient Portal
Priority P1 (`PAT` / `ORG` / `PORT` / `TRT`) · Owner: Identity, Privacy & Patient Experience · Depends T001, T005, T007, T008, T013, T014

**Status (2026-11-24):** Completed (synthetic dual-confirmed reversible patient merge, short-TTL audited break-glass flow with independent after-action review, and scoped patient/guardian portal views verified in `test_patient_merge_breakglass_portal.py`). See [ADR-013](../adr/ADR-013-patient-merge-breakglass-portal-and-kpi-lineage.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Reversible Dual-Confirmed Patient Merge (`PAT-006`):**
   - Never silently merge patients by phone number or display name (`AGENTS.md`, `INV-002`).
   - `patient_merge_request` requires two distinct authorized staff members (`approver_staff_id != requester_staff_id`); self-confirmation fails closed with `409 Conflict`.
   - Merging `secondary_patient_id` into `primary_patient_id` preserves 100% of original clinical, appointment, lab, consent, and financial rows under their original `source_patient_id` — zero destructive FK rewriting.
   - Unified view `GET /api/v1/patients/{patient_id}/unified-summary` resolves retired secondary IDs to `canonical_patient_id` and returns every encounter, appointment, plan, charge, and payment tagged with `source_patient_id`.
   - New appointments or encounters targeting an actively merged `secondary_patient_id` fail closed with `409 Conflict` directing callers to `canonical_patient_id`.
   - Reversing a merge (`POST /api/v1/patients/merges/{merge_id}/reverse`) requires an explicit `reversal_reason` and cleanly decouples the two records with zero history loss.
2. **Short-TTL Emergency Break-Glass Flow (`ORG-011`):**
   - `break_glass_grant` requires a documented clinical emergency purpose (`>= 15` chars) and enforces a hard maximum duration (`1 <= ttl_seconds <= 900`, i.e. at most 15 minutes).
   - Grants read-only emergency chart visibility (`encounter.read`, `note.read`, `clinical_doc.read`, `odontogram.read`) for a single `(clinic_id, patient_id)` — never clinical signing, deletion, financial refunds, or key management.
   - Emits immediate `AuditEvent` (`auth.break_glass_activated`) and `OutboxEvent` (`BreakGlassActivated`), logs every chart read (`auth.break_glass_chart_accessed`), fails closed (`403`) on expiry/revocation/cross-clinic access, and requires independent after-action review (`reviewer_staff_id != requester_staff_id` -> `409` on self-review).
3. **Clinician-Published Patient & Guardian Portal (`PORT-001`..`PORT-007`, `PORT-009`, `TRT-016`):**
   - Scoped `HS256` portal token (`aud="patient_portal"`) bound to `(clinic_id, patient_id, actor_kind)`. Guardian portal issuance (`actor_kind="guardian"`) fails closed (`403`) unless an active `ConsentRecord` exists with `signer_relationship="guardian"` and `guardian_authority_verified=True`.
   - Portal overview/endpoints expose ONLY confirmed appointments (`PORT-002`), clinician-published care instructions (`PORT-004`), clinician-published lay treatment summaries (`PORT-005`, `TRT-016`), and patient-scoped integer VND balance/ledger (`PORT-007`). Raw `ClinicalNote`, `NoteRevision`, `AIDraftArtifact`, and internal `PlanTask` draft data are NEVER returned.
   - Portal reschedule requests (`PORT-003`) queue `pending_staff_validation` without altering confirmed bookings until staff validates availability and commits via atomic reschedule (`SCH-005`).
   - Portal intake submissions (`PORT-006`) record `provenance="patient_portal_intake"` and `legal_consent_granted=False`.

## Mandatory Negative Tests (Written Before Domain Code)
1. Patient merge self-confirmation by same staff member -> `409`; booking new appointment/encounter on merged secondary patient -> `409`; reversing merge restores independent histories with all `source_patient_id` intact.
2. Break-glass request with `ttl_seconds > 900` or blank/short reason -> `422`; expired or revoked break-glass grant -> `403`; requester attempting after-action self-review -> `409`.
3. Guardian portal token request without verified guardian `ConsentRecord` -> `403`; cross-patient / staff-endpoint misuse of portal token -> `401`/`403`.
4. Creating internal draft `ClinicalNote`, `AIDraftArtifact`, and unreviewed `PlanTask` while publishing only approved lay summary -> portal payload contains published lay summary and ZERO internal draft text.
5. Submitting portal reschedule request leaves appointment time unchanged until staff validates; submitting portal intake form enforces `provenance="patient_portal_intake"` and `legal_consent_granted=False`.
