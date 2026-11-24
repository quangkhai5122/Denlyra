# ADR-016: Licensed Facility Scope, Non-Mutating Slot Optimizer, Traceable Receipts, Consent-Gated Comms, De-Identified Surveys & Parallel-Run Cutover

- **Status:** Accepted (synthetic research demonstrator)
- **Date:** 2026-11-25
- **Related tasks:** `T021` (`ORG-001`, `SCH-011`, `SCH-012`, `FIN-013`, `HR-001`, `HR-010`), `T022` (`CRM-002`, `CRM-011`, `AI-006`, `INT-012`, `MIG-009`, `MIG-010`)
- **Builds on:** `ADR-007` (RBAC), `ADR-009` (ledger & migration quarantine), `ADR-011` (offline AI firewall), `ADR-012` (operations & shifts), `ADR-015` (delegation & ops assistant)

## Context
Remaining P0/P1 single-clinic operational requirements span licensed facility metadata (`ORG-001`), procedure duration estimates and constraint-based slot optimization (`SCH-011`, `SCH-012`), traceable payment receipt exports (`FIN-013`), staff attendance and overtime (`HR-001`, `HR-010`), reviewed reminder templates and communication drafting (`CRM-002`, `AI-006`), confidential patient satisfaction surveys (`CRM-011`), and incumbent dental software migration cutover (`INT-012`, `MIG-009`, `MIG-010`). Each workflow carries domain-crossing hazards if permissions, confirmed bookings, bank proofs, clinical authorship, patient anonymity, or parallel-run write freezes are inferred rather than explicitly enforced.

## Decisions
1. **Explicit Facility License Profile (`ORG-001`):**
   - `facility_license_profile` versions clinic license type, synthetic `DEMO-*`/`SYN-*` license code, permitted scopes, and verification status. Scope checks evaluate this table exclusively and never inspect `Clinic.name` or `Staff.display_name`.
2. **Clinician-Reviewed Duration Templates & Proposal-Only Slot Optimizer (`SCH-011`, `SCH-012`):**
   - `procedure_duration_template` provides clinician-reviewed durations with a deterministic 30-minute fallback when unconfigured.
   - `schedule_optimizer_proposal` searches 15-minute candidate intervals against active `ResourceBooking`, `ResourceDowntime`, and `StaffShift` constraints without touching confirmed appointments; booking occurs only via explicit human `accept` calling `services.create_appointment`.
3. **Traceable Non-Bank Financial Receipt Exports (`FIN-013`):**
   - `financial_receipt_export` snapshots `Payment`, `PaymentAllocation`, `Charge`, and `LedgerEntry` lineage with canonical `SHA-256` and clinic `HMAC-SHA256`, enforces `synthetic_non_bank_receipt=True`, and rejects any request claiming verified bank settlement (`409`).
4. **Timezone-Correct Attendance & Overtime Isolated from Clinical Authority (`HR-001`, `HR-010`):**
   - `staff_attendance_log` normalizes shifts into `Asia/Ho_Chi_Minh` (`UTC+07:00`) local dates before computing `>480`-minute daily overtime and has zero coupling to `ROLE_PERMISSIONS` or `Encounter` authorship.
5. **Reviewed Send-Window & Consent-Gated Drafts + Decoupled Anonymous Surveys (`CRM-002`, `AI-006`, `CRM-011`):**
   - `communication_draft_record` binds to `reminder_template_version`, blocks out-of-window hours, missing marketing/data-processing consents, and prompt injections (`409`), flags urgent clinical symptoms for clinician escalation, and enforces `CheckConstraint("auto_sent = 0")`.
   - Satisfaction responses (`patient_satisfaction_response`) omit all patient/visit/token foreign keys; one-time replay prevention lives in a separate `satisfaction_token_receipt` table while free-text PII patterns fail validation (`422`).
6. **Hash-Verified Incumbent Export Quarantine & Parallel-Run Cutover Guard (`INT-012`, `MIG-009`, `MIG-010`):**
   - `incumbent_export_package` verifies export rights, canonical `SHA-256` digest, legacy signature non-forgery, duplicate-import rejection, and two-person reviewer sign-off before `migration_cutover_plan` allows `cutover_locked_legacy` with confirmed legacy write freeze and reconciled patient/VND totals.

## Consequences
- Migration `0011_facility_optimizer_receipts_comms_and_cutover` adds 11 normalized tables (total **97 domain tables**), preserving forward-only upgrades across SQLite and PostgreSQL 16.
- Real bank payment webhooks (`INT-008`), official tax e-invoices (`FIN-009`/`INT-009`), live Zalo/SMS gateways (`CRM-006`/`007`), and legal clinical/EMR sign-off remain explicitly gated.
