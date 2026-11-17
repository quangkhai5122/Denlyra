# T005 — Treatment Journey clinically reviewed vertical slice
Priority P0 · Owner: Treatment Domain + UX · Depends on secure identity, clinical content contract

**Status (2026-11-17):** Pending — implementation not started. See `docs/PROJECT_STATE.md` for current ordering.

## Work
- Model plan snapshot/version with typed phases and multiple task dependencies, cycle detection, state transitions and reassessment events.
- Link scheduling, lab and finance through requests/events not foreign-table writes.
- Implement timeline of real/proposed/status-separated work and task ownership, due and evidence.
- Add end-to-end synthetic orthodontic/prosthetic journey tests including reschedule, lab delay, plan change and refund, with independent clinician review of workflow templates.

## Acceptance
No payment interpreted as performed; plan versions immutable; blocked tasks cannot complete; loop/reassessment recorded as new tasks; no clinical decision automated.
