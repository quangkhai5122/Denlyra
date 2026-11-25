# ADR-018: Authoritative Terminology, Specialty Templates, PHI-Free Lab Billing, Encrypted Report Exports, Safe Offline Sync & Timeout-Safe Scheduling AI

- **Status:** Accepted (synthetic research demonstrator)
- **Date:** 2026-11-25
- **Related tasks:** `T025` (`EMR-016`, `TRT-015`, `LAB-010`, `ODN-009`, `RPT-009`, `RPT-010`), `T026` (`OPS-009`, `OPS-011`, `OPS-013`, `AI-007`, `AI-008`)
- **Builds on:** `ADR-008` (plans & snapshots), `ADR-010` (`DLY1` envelope encryption), `ADR-011` (AI firewall), `ADR-015` (multi-branch grants), `ADR-016` (slot optimizer), `ADR-017` (redacted governance)

## Context
Completing the remaining local clinical, analytical, continuity, and assistive scheduling capabilities requires strict boundaries against five failure modes: (1) fuzzy/guessed medical code mappings or unreviewed internet treatment protocols entering charts, (2) patient PII leaking into lab vendor invoices or scheduled report emails, (3) unlabeled or diagnostic claims on comparative dental imagery, (4) offline sync overwriting locked clinical documents or double-booking chairs via `last-write-wins`, and (5) scheduling AI discriminating on demographics, auto-cancelling patients, or corrupting schedules on solver timeout.

## Decisions
1. **Exact Versioned Terminology & Clinic-Reviewed Specialty Templates (`EMR-016`, `TRT-015`):**
   - `terminology_mapping_rule` enforces `mapping_method = 'clinician_verified_exact'` at schema and DB levels; unmapped codes abstain rather than guessing.
   - `specialty_plan_template` requires explicit `dentist`/`medical_director` review before instantiating draft `TreatmentPlan` graphs.
2. **PHI-Minimized Lab Invoicing, Non-Diagnostic Overlays & `DLY1`-Encrypted Reports (`LAB-010`, `ODN-009`, `RPT-009`, `RPT-010`):**
   - `lab_invoice_reconciliation` compares contracted fee schedules + remake surcharges against vendor bills while excluding all patient identifiers (`CheckConstraint("NOT contains_phi")`).
   - `longitudinal_imaging_overlay` requires same-patient `ArchiveObject` pairs, mandatory alignment labels, and `CheckConstraint("NOT auto_diagnosis_generated")`.
   - `scheduled_report_export` verifies `OwnerBranchScopeGrant` for multi-branch aggregates, allowlists recipient domains, forbids `include_phi=True`, and encrypts report JSON with per-clinic `DLY1` Encrypt-then-MAC keys.
3. **Two-Person Canary Approvals, Scoped Multi-Branch Operators & Conflict-Safe Offline Sync (`OPS-009`, `OPS-011`, `OPS-013`):**
   - `release_change_approval` requires backward-compatible schema confirmation, documented backup/forward-fix plans, and distinct proposer/approver staff IDs before canary promotion.
   - `multibranch_operator_assignment` shares aggregate operational metrics across authorized branches while enforcing `CheckConstraint("NOT grants_clinical_chart_access")`.
   - `offline_sync_mutation` forbids `last_write_wins`, rejects locked/signed clinical targets (`409`), and enforces optimistic `base_version` and active `ResourceBooking` conflict checks.
4. **Fair Calibrated No-Show Risk & Timeout-Safe CP-SAT Solver (`AI-007`, `AI-008`):**
   - `noshow_risk_assessment` uses only operational attendance history (`CheckConstraint("NOT uses_protected_demographics")`), never auto-cancels bookings, and degrades to `fallback_neutral` when AI is disabled.
   - `cpsat_optimization_run` runs bounded backtracking constraint satisfaction (`CheckConstraint("existing_bookings_mutated_count = 0")`), aborting cleanly with zero mutations if its millisecond budget expires.

## Consequences
- Migration `0013_terminology_templates_lab_reports_sync_and_ai` adds 12 normalized tables (total **121 domain tables**), raising synthetic catalog coverage to **198/222 (`D`)**.
- All remaining 24 `—` catalog entries correspond strictly to external third-party/cloud contracts (live OIDC SSO, tax e-invoices, insurers, Zalo/SMS/Email gateways, Orthanc DICOM, speech/radiology AI, cloud IaC, load testing) or formal legal/clinical sign-off gates (`M0`/`SEC-G1`).
