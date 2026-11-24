# T022 — Reviewed Reminder Templates, Consent-Gated Communication Drafts, Anonymized Satisfaction & Cutover Readiness
Priority P1 (`CRM` / `AI` / `INT` / `MIG`) · Owner: Patient Communications, Safe AI & Legacy Cutover · Depends T006, T007, T012, T013, T020

**Status (2026-11-25):** Completed (reviewed reminder templates with Ho Chi Minh City send-window & consent gates, draft-only communication generator with urgent clinical triage & injection firewall, decoupled anonymous 1–5 patient satisfaction survey with PII rejection & replay guard, and hash-verified incumbent software quarantine + parallel-run cutover guard verified in `test_comms_satisfaction_cutover.py`). See [ADR-016](../adr/ADR-016-facility-licensing-optimizer-receipts-comms-and-cutover.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Reviewed Reminder Templates & Consent-Gated Communication Drafts (`CRM-002`, `AI-006`):**
   - `reminder_template_version` versions clinic-reviewed wording and `Asia/Ho_Chi_Minh` send windows (`window_start_hour_hcm..window_end_hour_hcm`; `403` for unauthorized staff).
   - `communication_draft_record` enforces AI kill-switch (`503`), prompt-injection firewall (`409`), send-window bounds (`409`), marketing/data-processing `ConsentRecord` checks (`409`), urgent clinical symptom escalation (`escalation_required=True`), and DB `CheckConstraint("auto_sent = 0")`.
2. **Anonymized & Non-Manipulative Patient Satisfaction Survey (`CRM-011`):**
   - Decouples `satisfaction_token_receipt` (`token_sha256` replay guard -> `409`) from `patient_satisfaction_response` (zero `patient_id`, `appointment_id`, or `token_sha256` columns), accepts the full symmetric `1..5` scale without hiding `1`-star ratings, and rejects phone/email/CCCD PII in free-text comments (`422`).
3. **Incumbent Software Export Adapter & Parallel-Run Cutover Guard (`INT-012`, `MIG-009`, `MIG-010`):**
   - `incumbent_export_package` requires confirmed export rights (`409` if unconfirmed), verifies canonical `declared_sha256 == computed_sha256` (`409` on mismatch), forbids relabeling legacy records as Denlyra-signed (`422`), blocks duplicate package ingestion (`409`), and mandates independent reviewer sign-off (`approver != uploader` -> `409`) before cutover.
   - `migration_cutover_plan` blocks `cutover_locked_legacy` unless the package is reviewer-approved, `legacy_write_freeze_confirmed=True`, and parallel-run patient/VND totals reconcile (`409` otherwise).

## Mandatory Negative Tests (Written Before Domain Code)
1. Communication draft outside approved Ho Chi Minh City send hours, without `marketing` consent, or containing prompt injection -> `409`; `receptionist` publishing reminder template -> `403`.
2. Satisfaction survey comment containing phone number or 12-digit ID -> `422`; replaying single-use survey token -> `409`; `1`-star rating preserved honestly in summary with `contains_patient_identifiers=False`.
3. Incumbent export with `export_license_confirmed=False` or tampered `declared_sha256` -> `409`; self-approving uploader -> `409`; cutover with `legacy_write_freeze_confirmed=False` or mismatched reconciliation totals -> `409`.
