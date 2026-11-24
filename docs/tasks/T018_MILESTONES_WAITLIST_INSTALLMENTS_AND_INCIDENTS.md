# T018 — Clinical Milestone Checklists, Treatment Pause/Terminate, Consent-Safe Waitlist, Installments & Quality Incidents
Priority P1 (`TRT` / `SCH` / `FIN` / `HR`) · Owner: Treatment Continuity & Operations Governance · Depends T002, T005, T007, T008, T013

**Status (2026-11-24):** Completed (clinical milestone checklists, lossless treatment pause/terminate lifecycle, consent-safe schedule waiting list, reviewed installment schedule without auto-charge, and protected quality incident queue verified in `test_milestones_waitlist_installments_incidents.py`). See [ADR-014](../adr/ADR-014-encounter-lifecycle-procedure-evidence-and-clinical-governance.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Clinical Milestone Checklist (`TRT-012`):**
   - `plan_milestone_checklist` attaches clinician-defined criteria to a `PlanTask`. Completing the task while any milestone is `pending` fails closed (`409`).
   - Evaluating a milestone with `all_criteria_met=False` requires a documented `clinician_override_reason` (`409` if missing).
2. **Treatment Pause / Cancel / Terminate Governance (`TRT-014`):**
   - Append-only `treatment_plan_lifecycle_event` transitions a plan to `paused`, `cancelled`, `terminated`, or `active` (resumed) with mandatory clinical explanation while preserving 100% of historical tasks, encounters, charges, and payments.
   - Adding or completing tasks on a `paused`/`cancelled`/`terminated` plan fails closed (`409`).
3. **Consent-Safe Schedule Waiting List (`SCH-008`):**
   - `schedule_waitlist_entry` blocks outreach preparation (`409`) unless active `"granted"` `treatment` consent exists, and never books a slot without explicit staff confirmation through `svc.schedule`.
4. **Reviewed Installment Schedule without Auto-Charge (`FIN-008`):**
   - `installment_schedule` requires an active `"granted"` `financial` `ConsentRecord` (`409` otherwise), enforces tranche sum equality with `EstimateVersion.amount_vnd` (`422`), enforces `auto_charge_enabled=False` in DB constraint, and never fabricates `Charge` or `Payment` rows when created or reminded.
5. **Protected Quality Incident Queue (`HR-008`):**
   - Any staff member can submit `quality_incident_report`, whereas listing/inspecting incidents is restricted to `clinic_owner` and `medical_director` (`403` for other roles). AI clinical diagnosis/root-cause attribution is rejected (`422`), and `high`/`critical` incidents auto-escalate via `OutboxEvent`.

## Mandatory Negative Tests (Written Before Domain Code)
1. Completing `PlanTask` with `pending` milestone -> `409`; overriding unmet milestone without reason -> `409`; pausing/terminating plan blocks task completion (`409`) while preserving all prior `Charge`/`Payment`/`PlanTask` rows.
2. Preparing waitlist outreach without active `treatment` consent -> `409`; creating installment schedule without `financial` consent -> `409` or mismatched tranche sum -> `422`, and neither creates automatic `Charge` rows.
3. Filing `high` severity quality incident by `assistant` succeeds (`201` + escalated), `assistant`/`receptionist` reading incident queue -> `403`, and `clinic_owner` reading queue -> `200`.
