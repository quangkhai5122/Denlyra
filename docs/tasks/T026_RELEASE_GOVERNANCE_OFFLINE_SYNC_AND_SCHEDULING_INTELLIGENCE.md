# T026 — Canary Release/Rollback Approvals, Multi-Branch Operator Scopes, Conflict-Safe Offline Sync & Timeout-Safe Scheduling Intelligence
Priority P1/P2 (`OPS` / `AI`) · Owner: Platform Reliability, Offline Continuity & Operational AI · Depends T002, T010, T012, T020, T021

**Status (2026-11-25):** Completed (two-person canary release/migration compatibility & rollback gate, multi-branch operator assignments preserving clinical chart isolation, conflict-safe offline sync rejecting `last-write-wins` on signed records & bookings, demographic-fair calibrated no-show risk with safe fallback, and timeout-safe discrete CP-SAT scheduling proposals verified in `test_release_sync_and_scheduling_ai.py`). See [ADR-018](../adr/ADR-018-terminology-specialty-templates-lab-billing-offline-sync-and-scheduling-ai.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Canary Release, Migration Compatibility & Rollback Approvals (`OPS-009`):**
   - `release_change_approval` rejects backward-incompatible migrations (`409`), enforces two-person approval (`proposer != approver` -> `409`), and blocks `promoted_100pct` without an approved canary stage (`409`).
2. **Multi-Branch Operator Management Preserving Clinical Scopes (`OPS-011`):**
   - `multibranch_operator_assignment` grants cross-branch operational KPI visibility while enforcing `CheckConstraint("NOT grants_clinical_chart_access")` (`409` if requested) and keeping cross-clinic patient/encounter reads blocked (`404`/`403`).
3. **Offline Continuity Policy & Conflict-Safe Sync (`OPS-013`):**
   - `offline_sync_mutation` rejects `last_write_wins` (`422`), blocks offline mutations against `demo_locked` notes or `ClinicalDocumentSnapshot`s (`409`), and quarantines/rejects stale `base_version` draft edits or overlapping booking syncs (`409`).
4. **Calibrated Fair No-Show Risk & Timeout-Safe CP-SAT Optimization (`AI-007`, `AI-008`):**
   - `noshow_risk_assessment` blocks protected demographic features (`409`), never auto-cancels or overbooks appointments (`CheckConstraint("NOT auto_cancelled_or_overbooked")`), and falls back cleanly (`fallback_neutral`) when AI is disabled or unavailable.
   - `cpsat_optimization_run` solves multi-appointment discrete constraint assignments with `CheckConstraint("existing_bookings_mutated_count = 0")`; solver timeout (`simulate_solver_timeout=True` or `solver_budget_ms=0`) aborts cleanly leaving all confirmed bookings untouched.

## Mandatory Negative Tests (Written Before Domain Code)
1. Backward-incompatible release or self-approved canary promotion -> `409` (`OPS-009`); multi-branch operator requesting clinical chart access -> `409`, and direct cross-clinic patient chart read still fails `404` (`OPS-011`).
2. Offline sync with `resolution_strategy="last_write_wins"`, targeting a locked/signed clinical record, or carrying a stale `base_version` / overlapping slot -> `422`/`409` (`OPS-013`).
3. No-show risk with `include_demographic_features=True` -> `409`, and model-unavailable fallback preserves `Appointment.status="confirmed"` (`AI-007`); CP-SAT solver timeout returns `timeout_aborted_zero_changes` with `existing_bookings_mutated_count=0` (`AI-008`).
