# ADR-014 — Encounter Closure Gate, Clinician Procedure Evidence, Treatment Lifecycle & Protected Incident Governance

- **Status:** Accepted (synthetic foundation implemented in `T017` and `T018`)
- **Date:** 2026-11-24
- **Depends on:** `ADR-007` (Identity/RBAC), `ADR-008` (Treatment DAG & Snapshots), `ADR-009` (Consent & Finance Ledger), `ADR-012` (Clinic Operations & Audit Chain)

## Context
1. Dental encounters require explicit medical/allergy risk verification (`EMR-003`, `INV-022`), explicit clinician-recorded dental diagnoses and FDI tooth procedures (`EMR-010`, `EMR-011`, `ODN-005`), and a strict closure checklist (`EMR-009`, `EMR-018`) that blocks premature encounter completion without fabricating signatures or inferring performed care from billing.
2. Multi-stage treatment journeys require clinical milestone gates (`TRT-012`), lossless pause/termination handling (`TRT-014`), consent-gated schedule waitlists (`SCH-008`), non-auto-charging installment schedules (`FIN-008`), and protected quality incident escalation (`HR-008`).

## Decision
1. **Append-Only Tri-State Medical Risk & Encounter Closure Gate (`clinical_lifecycle.py`):**
   - Persist numbered `patient_medical_risk_review` revisions where unanswered items remain `"unanswered"` and `"present"`/`"unknown"` states raise `high_risk_banner_active=True`.
   - Require answered allergy/bleeding states, at least one locked/signed note, zero unlocked draft notes, and zero `ready_for_signature` snapshots before transitioning an `Encounter` to `"demo_closed_not_certified"`.
   - Restrict `encounter_diagnosis_demo` and `performed_procedure_evidence` writes to `dentist`/`medical_director`, reject unreviewed AI authorship, and freeze closed encounters against direct mutation.
2. **Milestone Checklists, Plan Lifecycle, Waitlist, Installments & Quality Incidents (`continuity_governance.py`):**
   - Enforce `plan_milestone_checklist` evaluation (`passed` or `overridden_with_reason`) and active `treatment_plan_lifecycle_event` status inside `svc.complete_task_demo` and `svc.add_task`.
   - Gate `schedule_waitlist_entry` outreach on active `treatment` consent and require explicit staff slot confirmation via `svc.schedule`.
   - Gate `installment_schedule` on active `financial` consent, enforce `CheckConstraint("auto_charge_enabled = 0")`, and validate exact integer VND tranche sums against `EstimateVersion.amount_vnd`.
   - Allow broad staff reporting into `quality_incident_report` while restricting read access to `clinic_owner` and `medical_director` and auto-escalating `high`/`critical` events via `OutboxEvent`.

## Consequences
- Schema advances cleanly via forward-only migration `0009_encounter_lifecycle_and_clinical_governance` (`66 -> 78` tables).
- Clinical templates, diagnostic code sets (`EMR-016`), and legal e-signing remain gated on human dentist and legal counsel review in `docs/clinical/NEEDS_CLINICAL_REVIEW.md`.
