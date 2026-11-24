# T016 — Versioned Service Price Catalog, Discount Dual-Control & Attributable KPI Lineage Dictionary
Priority P1 (`FIN` / `RPT`) · Owner: Revenue Governance & Clinic Analytics · Depends T005, T007, T008, T011, T013

**Status (2026-11-24):** Completed (versioned clinic service price catalog, immutable estimate price snapshots, dual-control discount override workflow without treatment mutation, and attributable KPI dictionary/lineage verified in `test_price_catalog_and_kpi_lineage.py`). See [ADR-013](../adr/ADR-013-patient-merge-breakglass-portal-and-kpi-lineage.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Versioned Clinic Service Price Catalog (`FIN-001`):**
   - `service_price_catalog_item` stores integer `unit_price_vnd > 0` under `(clinic_id, service_code, version_number)`.
   - Publishing an updated price increments `version_number` and transitions the prior active row to `superseded` — never mutating historical catalog rows or retroactively changing `estimate_price_snapshot` / `estimate_version` amounts already quoted or accepted.
2. **Discount & Override Dual-Control Workflow (`FIN-014`):**
   - Discounts within `max_auto_discount_pct` create a traced `auto_approved_within_policy` record and a new numbered `EstimateVersion`.
   - Discounts exceeding policy threshold enter `pending_owner_approval` and require approval by an authorized `clinic_owner` or `medical_director` distinct from the requester (`approver_staff_id != requester_staff_id`, else `409 Conflict`).
   - Approved discounts emit a new financial `EstimateVersion` (`version_number + 1`) with immutable explanation while leaving `TreatmentPlan` versions and `PlanTask` clinical items completely unchanged ("no hidden treatment change").
3. **Attributable Owner KPI Report & Metric Lineage Dictionary (`RPT-002`, `RPT-004`, `RPT-005`, `RPT-006`, `RPT-007`, `RPT-011`):**
   - `RPT-002` (Chair utilization): strictly distinguishes `scheduled_chair_minutes` from actual `utilized_chair_minutes` (appointments transitioned through `in_chair`/`completed` check-in queue) and `maintenance_downtime_minutes`.
   - `RPT-004` (Retention & follow-up): documents denominator (`RecallFollowupItem` due items excluding withdrawn-consent opt-outs) and numerator (`closed` items with `closure_evidence`).
   - `RPT-005` (Treatment plan pipeline): separates `draft`, `clinician_reviewed`, `estimate_accepted`, `in_progress`, and `all_tasks_completed_admin` counts.
   - `RPT-006` (Billing vs collection): separates accrual `billed_charges_vnd`, `gross_collected_cash_vnd`, `refunded_vnd`, `net_collected_cash_vnd`, `allocated_to_charges_vnd`, `unallocated_deposit_liability_vnd`, and `outstanding_receivable_vnd` (never equating billed charges with collected cash).
   - `RPT-007` (Lab turnaround exceptions): counts actual overdue unreceived cases, `received` cases awaiting clinical verification (`LAB-009`), `verified` cases, and remakes.
   - `RPT-011` (Metric dictionary & lineage): every KPI includes `formula_expression`, `numerator_definition`, `denominator_definition`, `exclusions_definition`, `source_tables`, `source_record_ids`, `refreshed_at`, and `review_owner_role`.

## Mandatory Negative Tests (Written Before Domain Code)
1. Updating `service_price_catalog_item` price creates `v2` (`superseded` on `v1`) and leaves previously created `EstimateVersion` + `EstimatePriceSnapshot` integer VND amounts completely unchanged (`FIN-001`).
2. Requesting an above-threshold discount enters `pending_owner_approval` without altering estimates; self-approval by requester -> `409`; unauthorized role (`finance`/`receptionist`) attempting owner override approval -> `403`; independent `clinic_owner` approval creates `EstimateVersion` `v2` while leaving clinical `TreatmentPlan` / `PlanTask` unchanged (`FIN-014`).
3. Booking an appointment without seating (`in_chair`) increases `scheduled_chair_minutes` while `utilized_chair_minutes` remains `0` (`RPT-002`); posting a `Charge` without `Payment` increases `billed_charges_vnd` while `net_collected_cash_vnd` remains `0` (`RPT-006`); every KPI exposes complete formula + `source_record_ids` lineage (`RPT-011`).
