# T013 — Clinician Shifts, Resource Downtime, Check-In Queue, Chair Turnover & Consent-Safe Recall
Priority P1 (`M2` / `CRM` / `HR`) · Owner: Clinic Operations · Depends T001, T002, T007

**Status (2026-11-24):** Completed (synthetic clinician shift windows, chair/device maintenance downtime blocks + DB trigger, confirmation state separation, identity-verified check-in + chair sanitation turnover gate, and consent-safe recall/follow-up queue verified in `test_operations_checkin_recall.py`). See [ADR-012](../adr/ADR-012-clinic-operations-tamper-evident-audit-and-pagination.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Approved Clinician Shifts (`SCH-001`, `ORG-008`):**
   - When a practitioner has active `staff_shift` windows defined in a clinic, booking or rescheduling an appointment outside an approved `[start_at, end_at)` shift window fails closed with `409 Conflict` unless an explicit audited `override_shift_reason` is supplied.
2. **Resource Downtime & Equipment Maintenance Blocks (`SCH-015`, `HR-004`):**
   - Active `resource_downtime` windows on any chair or equipment (`device`) block overlapping appointment bookings and reschedules with `409 Conflict` (enforced both in `svc.schedule` and via SQLite `BEFORE INSERT ON resource_booking` trigger `tr_no_booking_during_downtime`).
3. **Confirmation State Separation (`SCH-009`, `CRM-003`):**
   - `appointment_confirmation` separates transport states (`sent`, `delivered`) from explicit patient intent (`patient_confirmed`, `declined`). Recording `sent` or `delivered` NEVER marks an appointment `patient_confirmed`.
4. **Identity-Verified Check-In & Chair Turnover Gate (`PAT-009`, `SCH-010`, `HR-002`, `HR-003`, `RPT-003`):**
   - `checkin_queue_item` requires `identity_verified=True` and explicit `verification_method` at check-in (`422`/`409` otherwise).
   - Transitioning a checked-in patient to `in_chair` is blocked with `409 Conflict` if an open `chair_turnover_checklist` (`surface_disinfected`, `sterile_kit_verified`, `waterline_flushed`, `assistant_prep_ready`) for that appointment/chair has not been completed (`sanitized_ready`).
5. **Consent-Safe Recall & Coordinator Follow-Up Queue (`CRM-004`, `CRM-005`, `CRM-010`):**
   - `clinical_recall` items require `clinician_approved=True` (`409` if unapproved).
   - `marketing_outreach` items require an active `"granted"` `ConsentRecord` with `purpose="marketing"` for that patient; missing or withdrawn marketing consent blocks creation with `409 Conflict` while leaving `clinical_recall` unaffected (`SEC-07`).

## Mandatory Negative Tests (Written Before Domain Code)
1. Booking appointment outside practitioner's defined shift without override -> `409`; inside shift (or with audited override) -> `201`.
2. Booking or rescheduling onto a chair/device during an active `resource_downtime` maintenance window -> `409`.
3. Recording reminder `sent` or `delivered` does NOT set `confirmation_status == "patient_confirmed"`.
4. Check-in with `identity_verified=False` -> `422`/`409`; seating patient (`in_chair`) while `chair_turnover_checklist` is still `pending` -> `409`; completing sanitation + assistant prep checklist unblocks `in_chair` (`200`).
5. Creating `clinical_recall` without clinician approval -> `409`; creating `marketing_outreach` without active `marketing` consent (or after marketing consent withdrawal) -> `409`, while `clinical_recall` succeeds (`201`).
