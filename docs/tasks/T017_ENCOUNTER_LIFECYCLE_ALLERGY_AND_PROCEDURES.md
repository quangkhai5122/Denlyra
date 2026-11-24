# T017 — Tri-State Medical/Allergy Risk Review, Encounter Closure Gate & Clinician-Authored Procedure Evidence
Priority P0/P1 (`EMR` / `ODN` / `PAT`) · Owner: Clinical Safety & EMR Architecture · Depends T001, T003, T004, T005

**Status (2026-11-24):** Completed (tri-state medical/allergy risk review, encounter closure & missing-signature checklist gate, and clinician-authored dental diagnosis & FDI tooth procedure evidence verified in `test_encounter_lifecycle_and_procedures.py`). See [ADR-014](../adr/ADR-014-encounter-lifecycle-procedure-evidence-and-clinical-governance.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Tri-State Medical & Allergy Risk Review (`EMR-003`, `PAT-003`, `INV-022`):**
   - `patient_medical_risk_review` stores explicit revisioned states (`present`, `explicit_negative`, `unknown`, `not_applicable`, `unanswered`) with source provenance and actor.
   - Unanswered items remain `"unanswered"` — never coerced into `"explicit_negative"`. Any `"present"` or `"unknown"` risk activates `high_risk_banner_active=True`.
   - `"present"` drug allergy requires non-empty `drug_allergy_detail` (`422`).
2. **Encounter Closure State Machine & Missing-Signature Checklist (`EMR-009`, `EMR-018`):**
   - `GET /api/v1/encounters/{encounter_id}/closure-checklist` evaluates required clinical gates without fabricating locks or signatures, and `POST .../notify-missing-signatures` alerts the responsible practitioner via `OutboxEvent` + `AuditEvent`.
   - `POST /api/v1/encounters/{encounter_id}/close-demo` fails closed (`409`) if medical/allergy review is missing or `"unanswered"`, if no locked/signed note exists, if unlocked draft notes remain, or if any `ClinicalDocumentSnapshot` is still `ready_for_signature`.
   - Passing all gates transitions status to `"demo_closed_not_certified"` (never claiming certified legal EMR closure) and blocks direct post-closure draft edits/procedure writes (`409`).
3. **Clinician-Authored Dental Diagnosis & Performed Procedure Tooth Evidence (`EMR-010`, `EMR-011`, `ODN-005`):**
   - Strictly restricted to `dentist` and `medical_director` (`403` for `assistant`, `receptionist`, `finance`, `treatment_coordinator`); AI/LLM unreviewed authorship is rejected (`422`).
   - `performed_procedure_evidence` links explicit clinician-recorded performed procedures to validated 2-digit FDI tooth codes (`11..48`, `51..85`).
   - Recording a `Charge`/`Payment` or completing an administrative `PlanTask` NEVER populates `performed_procedure_evidence`.

## Mandatory Negative Tests (Written Before Domain Code)
1. Recording medical risk review with omitted/unanswered allergy keeps `drug_allergy_state == "unanswered"` (`!= "explicit_negative"`); attempting `close-demo` while allergy is unanswered or snapshot is unsigned -> `409`; `notify-missing-signatures` emits alert without signing.
2. Non-clinician (`assistant`/`finance`/`receptionist`) or `authoring_source="ai_unreviewed"` attempting to record dental diagnosis or performed procedure -> `403`/`422`.
3. Posting `Charge` + `Payment` + `PlanTask` `demo_completed` leaves `performed_procedures` empty (`0`); explicit dentist `POST /performed-procedures` on FDI tooth `36` records evidence, and post-closure write attempts fail closed (`409`).
