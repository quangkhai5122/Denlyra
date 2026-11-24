# T024 — Retention-Aware Subject Access Export, Cancellation Slot Recovery, Quarantined Portal Uploads/Support & HR Competency/Commission Separation
Priority P2 (`PAT` / `SCH` / `PORT` / `HR`) · Owner: Patient Rights, Portal Safety, Scheduling & Clinical HR · Depends T007, T010, T015, T017, T018, T020

**Status (2026-11-25):** Completed (authority-verified & retention-guarded patient subject access workflow, FIFO consent-safe cancellation slot recovery without clinical urgency inference, malware/active-content-scanned quarantined portal uploads, human-triaged portal support messaging blocking autonomous medical advice, expired staff competency procedure guard, and performed-vs-collected commission preview verified in `test_portal_access_recovery_hr.py`). See [ADR-017](../adr/ADR-017-redacted-telemetry-onboarding-incident-portal-quarantine-and-hr-competency.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Patient Data Export & Access Request Workflow (`PAT-011`):**
   - `patient_access_request` verifies requester authority (`403` for unverified requester or unverified guardian), blocks `erasure_request` when clinical encounters/signed snapshots/retained archive objects exist (`409`), and excludes internal-only staff/complaint notes from `structured_access_export`.
2. **Consent-Safe Cancellation Slot Recovery (`SCH-014`):**
   - `cancellation_recovery_suggestion` requires a `cancelled` appointment (`409` if still `confirmed`), excludes waitlist patients lacking active `treatment` consent or having withdrawn `data_processing` consent, rejects `claim_clinical_urgency_ranking=True` (`409`), and ranks strictly by FIFO arrival (`CheckConstraint("NOT clinical_priority_inferred")`).
3. **Quarantined Portal File Upload & Human-Triaged Support Messaging (`PORT-008`, `PORT-010`):**
   - `portal_quarantined_upload` enforces allowlisted MIME/extensions (`pdf`/`jpeg`/`png`), size bounds, and EICAR/PE/ELF/script/PDF-JS scanning (`422` on threat), holding clean uploads in `quarantined_pending_review` until clinician review.
   - `portal_support_message` flags urgent symptom keywords (`urgent_human_triage` + `OutboxEvent`), enforces `CheckConstraint("NOT autonomous_medical_advice_sent")`, and blocks non-human/AI replies (`422`).
4. **Staff Competency Expiry Guard & Performed-vs-Collected Commission Support (`HR-007`, `HR-009`):**
   - `staff_competency_record` blocks restricted procedure assignment and `record_performed_procedure_evidence` (`409`) when a governed competency is expired, revoked, or missing.
   - `GET /api/v1/hr/commission-preview` strictly separates `PerformedProcedureEvidence` counts from `PaymentAllocation` cash collections (`performed_equated_to_collected=False`).

## Mandatory Negative Tests (Written Before Domain Code)
1. Unverified guardian subject access request -> `403`; clinical record erasure request under retention -> `409`; valid export omits `internal_staff_only` contact logs (`PAT-011`).
2. Cancellation recovery on non-cancelled appointment or with `claim_clinical_urgency_ranking=True` -> `409`; waitlist patient without consent excluded (`SCH-014`); portal upload with EICAR/executable/script payload -> `422`, and AI autonomous reply on support thread -> `422` (`PORT-008`, `PORT-010`).
3. Dentist with expired `IMP-SURG-L2` competency blocked from recording restricted performed procedure -> `409` (`HR-009`); unperformed paid charge yields `0` performed procedures while unpaid performed procedure yields `0` collected VND (`HR-007`).
