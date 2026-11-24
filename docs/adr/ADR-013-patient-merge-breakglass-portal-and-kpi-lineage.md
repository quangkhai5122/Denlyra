# ADR-013 — Reversible Patient Merge, Short-TTL Break-Glass, Scoped Patient Portal & Attributable KPI Lineage

- **Status:** Accepted (synthetic foundation implemented in `T015` and `T016`)
- **Date:** 2026-11-24
- **Depends on:** `ADR-007` (Identity/RBAC), `ADR-008` (Treatment DAG & Snapshots), `ADR-009` (Consent, Lab & Finance Ledger), `ADR-012` (Clinic Operations & Hash-Chained Audit)

## Context
1. Duplicate patient registrations inevitably occur in dental clinics (e.g., walk-in vs legacy paper import), yet `AGENTS.md` strictly forbids silent merging by phone/name or destructive overwriting of clinical/financial history (`PAT-006`).
2. Clinical emergencies occasionally require non-default chart visibility (`ORG-011`), which must be tightly time-boxed, read-only, justified, alerted via outbox/audit, and reviewed by an independent clinical leader.
3. Patients and verified guardians need portal visibility into appointments, care instructions, treatment progress, intake forms, and balances (`PORT-001`..`PORT-007`, `PORT-009`, `TRT-016`) without ever seeing internal draft notes, AI drafts, or unreviewed clinical tasks, and without mutating confirmed schedules directly.
4. Clinic owners and finance teams need a versioned fee schedule (`FIN-001`), dual-control discount approvals that never alter clinical plans (`FIN-014`), and an owner KPI suite where every metric carries exact denominator, exclusion, and record-ID lineage (`RPT-002`..`RPT-007`, `RPT-011`).

## Decision
1. **Non-Destructive Reversible Patient Merge (`patient_merge_request`):**
   - Require two distinct staff principals (`requester_staff_id != approver_staff_id`) to activate a merge.
   - Keep all historical `Encounter`, `Appointment`, `TreatmentPlan`, `LabCase`, `ConsentRecord`, `Charge`, `Payment`, and `ArchiveObject` rows bound to their original `patient_id` (`source_patient_id`), resolving canonical identity at read/command boundaries so merges are 100% lossless and reversible (`merged -> reversed`).
   - Reject new clinical/scheduling writes directly targeting a retired secondary patient (`409 Conflict`).
2. **Time-Boxed Read-Only Break-Glass (`break_glass_grant`):**
   - Cap TTL at 900 seconds (15 minutes), restrict scope to read-only chart inspection for a single `(clinic_id, patient_id)`, emit `AuditEvent` + `OutboxEvent` on activation and every read, and enforce independent post-hoc review (`reviewer_staff_id != requester_staff_id`).
3. **Publication-Gated Patient & Guardian Portal (`portal_*` tables):**
   - Issue distinct `HS256` tokens with `aud="patient_portal"` (never accepted by staff RBAC endpoints). Require verified guardian `ConsentRecord` before issuing `actor_kind="guardian"` grants.
   - Serve only explicit `portal_published_instruction` and `portal_published_plan_summary` records authored by `dentist` / `medical_director`, guaranteeing structural isolation from `ClinicalNote`, `NoteRevision`, and `AIDraftArtifact`.
   - Buffer reschedule requests (`portal_reschedule_request`) until staff validates chair/practitioner availability via `svc.reschedule_appointment`.
4. **Versioned Price Catalog, Discount Dual-Control & KPI Lineage (`service_price_catalog_item`, `estimate_price_snapshot`, `discount_approval_request`, `governance_analytics.py`):**
   - Treat catalog price updates as append-only version increments (`v1` `superseded` -> `v2` `active`) and freeze line unit prices in `estimate_price_snapshot`.
   - Require independent `clinic_owner` / `medical_director` approval for discounts exceeding `max_auto_discount_pct`, emitting a new numbered `EstimateVersion` without touching `TreatmentPlan` or `PlanTask`.
   - Compute `RPT-002`..`RPT-008` in integer VND and integer basis points (`0..10000` bp), returning full formula metadata and `source_record_ids` on every KPI (`RPT-011`).

## Consequences
- Schema advances cleanly via forward-only migration `0008_patient_merge_portal_and_kpi_lineage` (`56 -> 66` tables).
- Live patient portal deployment remains gated on external OIDC/OTP authentication, penetration testing (`SEC-G1`), and legal privacy notice sign-off (`NEEDS_CLINICAL_REVIEW.md`).
