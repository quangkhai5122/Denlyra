# T021 — Licensed Facility Metadata, Procedure Duration Templates, Human-Approved Slot Optimizer, Traceable Financial Receipts & Attendance/Overtime
Priority P0/P1 (`ORG` / `SCH` / `FIN` / `HR`) · Owner: Organization Governance, Scheduling, Revenue & Operations · Depends T001, T002, T008, T013

**Status (2026-11-25):** Completed (versioned synthetic facility license profile & explicit scope evaluator, clinician-approved procedure duration templates with safe fallback, non-mutating constraint slot optimizer requiring explicit human acceptance, HMAC-traceable non-bank financial receipt exports, and `Asia/Ho_Chi_Minh` timezone-correct attendance/overtime separated from clinical authorship verified in `test_facility_optimizer_receipts_hr.py`). See [ADR-016](../adr/ADR-016-facility-licensing-optimizer-receipts-comms-and-cutover.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Licensed Facility Metadata Without Display-Name Inference (`ORG-001`):**
   - `facility_license_profile` versions `(clinic_id, version_number)` storing synthetic `license_number_demo` (`DEMO-*` / `SYN-*` prefix enforced -> `422` otherwise so real clinic license numbers are never committed), `license_type`, `permitted_scopes_json`, and `verification_status` (`unverified_synthetic` | `pending_counsel_review` | `verified_demo_only`).
   - `GET /api/v1/org/facility-profile/scope-check` evaluates explicit profile scope + `verified_demo_only` status and NEVER infers clinical/facility authorization from `Clinic.name` or `Staff.display_name`.
2. **Procedure Duration Templates & Human-Approved Slot Optimizer (`SCH-011`, `SCH-012`):**
   - `procedure_duration_template` requires clinician review (`plan.review`, `403` for non-clinicians); `GET /api/v1/scheduling/duration-estimate` returns template minutes or safe 30-minute fallback (`used_safe_fallback=True`, `staff_decides=True`).
   - `POST /api/v1/scheduling/optimizer/propose` runs deterministic constraint grid search avoiding active `ResourceBooking`, `ResourceDowntime`, and respecting `StaffShift` windows while guaranteeing `altered_confirmed_appointments=0`. Bookings occur ONLY when staff explicitly calls `POST /api/v1/scheduling/optimizer/proposals/{id}/accept`.
3. **Traceable Financial Receipts Without Fabricated Bank Proofs (`FIN-013`):**
   - `financial_receipt_export` binds exact `Payment`, `PaymentAllocation`, `Charge`, and `LedgerEntry` IDs with `payload_sha256` + `signature_hmac_sha256` and `synthetic_non_bank_receipt=True`; attempting `claim_verified_bank_settlement=True` fails closed (`409`), and non-finance clinical roles (`dentist`/`assistant`) are denied (`403`).
4. **Staff Attendance & Timezone-Correct Overtime Separated from Clinical Authorship (`HR-001`, `HR-010`):**
   - `staff_attendance_log` computes `local_date_hcm` strictly in `Asia/Ho_Chi_Minh` (`UTC+07:00`) across UTC midnight boundaries, calculates daily regular vs overtime minutes (`> 480` mins), and never grants clinical permissions (`403` preserved) or alters authored clinical encounters.

## Mandatory Negative Tests (Written Before Domain Code)
1. Clinic/staff display names containing `"Implant"` or `"Bệnh viện"` do NOT grant scope (`allowed_in_demo_scope=False`); unprefixed real-looking license number -> `422`; `receptionist` updating facility profile or approving duration template -> `403`.
2. `/scheduling/optimizer/propose` leaves all confirmed appointments untouched (`altered_confirmed_appointments=0`) and skips busy/downtime intervals; re-accepting an already booked optimizer proposal -> `409`.
3. `dentist` exporting financial receipt -> `403`; `claim_verified_bank_settlement=True` -> `409`; UTC rollover shift (`2026-12-01T18:00:00Z` -> `2026-12-02T04:00:00Z`) maps to `2026-12-02` in Ho Chi Minh City with `120` overtime minutes while `receptionist` still cannot open clinical encounters (`403`).
