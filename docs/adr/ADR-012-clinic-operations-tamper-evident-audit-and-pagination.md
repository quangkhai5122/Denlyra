# ADR-012 — Clinic Operations Queue/Shift/Recall Governance (`T013`), Hash-Chained Tamper-Evident Audit Journal, and Signed Cursor Pagination (`T014`)

- **Status:** Accepted (synthetic research foundation; external WORM log shipping and live messaging providers remain gated)
- **Date:** 2026-11-24
- **Tasks:** [T013](../tasks/T013_OPERATIONS_CHECKIN_AND_RECALL.md), [T014](../tasks/T014_TAMPER_EVIDENT_AUDIT_AND_PAGINATION.md)
- **Related invariants & risks:** `INV-001`, `INV-003`, `INV-017`, `SEC-007`, `PAT-002`, `PAT-009`, `SCH-001`, `SCH-009`, `SCH-010`, `SCH-015`, `CRM-003`..`CRM-005`, `CRM-010`, `HR-002`..`HR-004`, `R-012`

## Context

1. **Daily clinic operations (`T013`):** Scheduling previously enforced overlap constraints (`T002`) without modeling clinician working shifts (`SCH-001`), chair/device maintenance downtime (`SCH-015` / `HR-004`), transport-vs-intent appointment confirmation (`SCH-009`), identity-verified waiting-room check-in (`PAT-009` / `SCH-010`), chair sanitation/prep turnover (`HR-002` / `HR-003`), or consent-safe patient recall/follow-up queues (`CRM-004` / `CRM-005` / `CRM-010`).
2. **Audit tamper evidence & query pagination (`T014`):** `audit_event` previously lacked cryptographic hash chaining (`SEC-007`) and DB-level update/delete blocks, while collection endpoints lacked opaque cursor pagination (`PAT-002`, `R-012`).

## Decisions

### 1. Shift, Maintenance Downtime, Turnover & Consent-Safe Recall (`T013`)
- Add 6 tables in migration `0007_operations_audit_chain_and_pagination.py`: `staff_shift`, `resource_downtime`, `appointment_confirmation`, `checkin_queue_item`, `chair_turnover_checklist`, and `recall_followup_item` (**56 tables total**).
- Enforce `resource_downtime` both in `svc.schedule` / `svc.reschedule_appointment` and via SQLite trigger `tr_no_booking_during_downtime` on `resource_booking`.
- Enforce `staff_shift` containment whenever a practitioner has active shifts configured in the clinic unless an explicit audited `override_shift_reason` is recorded.
- Gate `checkin_queue_item` seating (`in_chair`) on completion (`sanitized_ready`) of any open `chair_turnover_checklist` for that appointment/chair, and gate `marketing_outreach` recall items on an active granted `marketing` `ConsentRecord`.

### 2. Per-Clinic Hash-Chained Audit Journal (`T014` / `SEC-007`)
- Extend `audit_event` with `chain_seq`, `prev_hash`, and `entry_hash`, automatically populated via a SQLAlchemy `Session` `before_flush` listener so every `AuditEvent` across `auth.py`, `services.py`, `archive_dr.py`, `inventory.py`, `ai_harness.py`, and `operations.py` is seamlessly chained per `clinic_id`.
- Install `tr_audit_event_no_update` and `tr_audit_event_no_delete` triggers for preventive protection, and expose `GET /api/v1/audit-events/verify-chain` (plus CLI `scripts/verify_audit_chain.py`) for detective verification against out-of-band storage tampering.

### 3. HMAC-Signed Clinic-Scoped Cursor Pagination (`T014` / `PAT-002` / `R-012`)
- Introduce `pagination.py` minting and verifying HMAC-SHA256-authenticated opaque cursors bound to `(clinic_id, resource_kind, sort_key, last_id)` so tampered cursors (`422`) and cross-clinic cursor replays (`403`) fail closed while preserving existing unpaginated demo routes.

## Consequences
- Resolves `R-012` completely (both typed OpenAPI TS client and cursor pagination implemented) and advances `SEC-007` to cryptographic hash-chained tamper detection; production deployment before real PHI still requires shipping periodic head hashes to an external WORM log sink.
