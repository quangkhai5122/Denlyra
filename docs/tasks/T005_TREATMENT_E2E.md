# T005 — Treatment Journey clinically reviewed vertical slice
Priority P0 · Owner: Treatment Domain + UX · Depends on secure identity, clinical content contract

**Status (2026-11-18):** Completed for synthetic domain/API slice (`ADR-008`, `backend/tests/test_treatment_journey_e2e.py`); independent clinician review of specialty workflow templates remains required before clinical use.

## Work
- Modeled plan version with typed `owner_role`, `due_at`, multi-dependency DAG (`plan_task_dependency`), DFS cycle detection (`422`), state transitions, and clinician reassessment events (`plan_reassessment` + `reassessed_from_task_id`, `PLAN-04`).
- Linked scheduling, lab, and finance via `treatment_coordination_link` and transactional `outbox_event` rather than foreign-table direct writes; enforced `requires_verified_lab` blocking completion when lab case is only `received` (`NEG-09`), atomic appointment reschedule preserving history (`SCH-005`), and append-only payment refunds (`FIN-006`, `OPS-03`).
- Implemented evidence-aware timeline (`GET /api/v1/treatment-plans/{id}/timeline`) displaying ownership, overdue flags, blocker reasons, reassessments, and status-separated financial summary (`implies_clinical_completion: False`).
- Added end-to-end synthetic orthodontic/prosthetic journey tests (`backend/tests/test_treatment_journey_e2e.py`) covering multi-dependency DAG, cycle rejection, reschedule, lab delay/verification gate, plan reassessment, and bounded refund.

## Acceptance
No payment or refund interpreted as performed; plan versions immutable; blocked tasks cannot complete; loop/reassessment recorded as new traced tasks in a new version; no clinical decision automated.
