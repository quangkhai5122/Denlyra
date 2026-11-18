# ADR-009 — Purpose-separated Consent & Scoped Lab Portal (`T007`), Idempotent Revenue Ledger (`T008`), and Legacy Paper Quarantine Importer (`T006`)

Date: 2026-11-18 · Status: Accepted for synthetic foundation · Owners: Domain Architect + Clinical/Finance/Legal Reviewers (pending)

## Context & evidence
With `T001`–`T005` established, three P1 domain slices are required to complete the core operational and migration architecture before frontend workspace expansion (`T009`) and disaster-recovery archive drills (`T010`):
1. **Lab coordination & Consent taxonomy (`T007`):** The starter `LabCase` lacked technical specifications, due-date conflict alerts against scheduled appointments, remake lineage, and a case-scoped partner portal token (`LAB-003..009`, `OPS-06`). Patient consents (`treatment`, `data_processing`, `marketing`, `financial`) and pediatric guardian verification (`PAT-004`, `INV-024`, `SEC-07`) were not yet modeled.
2. **Financial ledger & reconciliation (`T008`):** `Charge`, `Payment`, `PaymentAllocation`, and `PaymentRefund` lacked `idempotency_key` deduplication (`NEG-08`, `NEG-17`), an explicit append-only `LedgerEntry` journal, versioned treatment estimates (`FIN-002`), and daily cashier reconciliation by tender type (`FIN-010`).
3. **Legacy paper quarantine importer (`T006`):** Paper-first clinics require a staged quarantine pipeline (`MigrationBatch`, `MigrationItem`) that verifies page completeness (`NEG-10`, `DR-01`), flags duplicate patient candidates for human resolution without auto-merging (`PAT-005`, `DR-02`), preserves `source="legacy_scan"` without forging digital signatures (`INV-019`, `DR-03`), and supports safe batch rollback (`MIG-008`).

## Decision
1. **Purpose-separated Consent & Scoped Lab Partner Portal (`T007`):**
   - Add `consent_record` scoped by `(clinic_id, patient_id, purpose)` where `purpose` is one of `treatment`, `data_processing`, `marketing`, `financial`. Guardian signatures (`signer_relationship="guardian"`) require `guardian_authority_verified=True` (`422` otherwise). Withdrawing `marketing` consent never mutates or invalidates `treatment` or `data_processing` consents or clinical records (`SEC-07`).
   - Extend `lab_case` with `specification_demo`, `file_manifest_json`, `parent_lab_case_id`, `revision_number`, delivery receipt metadata, and dentist verification tracking.
   - Add `lab_partner_grant` issuing time-bounded, revocable, single-case tokens. The partner portal endpoint (`/api/v1/lab-portal/cases/{grant_token}`) exposes only minimal case specifications and file manifests (zero patient PII or clinical chart data, `OPS-06`) and forbids transitioning a case to `verified` (`403`).
   - Expose lab due-date delay alerts (`lab_due_after_appointment`) whenever `lab_case.due_on > linked_appointment.start_at` and `status != "verified"`, without auto-rescheduling appointments (`SCH-013`).
2. **Idempotent Revenue Ledger, Versioned Estimates & Cashier Reconciliation (`T008`):**
   - Add `estimate_version` with immutable `(plan_id, version_number)` and explicit patient acceptance state (`FIN-002`).
   - Add `idempotency_key` to `charge`, `payment` (with `payment_method` in `cash | bank_transfer | card`), `payment_allocation`, and `payment_refund`. Duplicate requests with matching parameters return the original record idempotently (`NEG-08`, `NEG-17`); conflicting parameters return `409`.
   - Record every financial event in append-only `ledger_entry`. Add SQLite/DB transaction serialization for concurrent allocations and `cashier_reconciliation` comparing counted cash/transfer/card against ledger net collections (`FIN-010`).
3. **Quarantined Paper Migration Pipeline (`T006`):**
   - Add `migration_batch` and `migration_item`. Missing or illegible pages mark the item `incomplete_missing_pages` and block verification (`409`, `DR-01`).
   - Matching patient names or phones populate `candidate_patient_ids_json` and set `match_status="needs_human_identity_review"`, blocking finalization until explicit human resolution (`link_existing_patient` or `create_distinct_patient`, `DR-02`).
   - Verified items create/link records with `provenance_source="legacy_scan"` and `digital_signature_status="not_digitally_signed_legacy_paper"`; any attempt to claim digital signature on a legacy scan is rejected (`409`, `DR-03`). Batch rollback (`POST /api/v1/migrations/paper-batches/{id}/rollback`) safely reverses unconfirmed batch items with full audit trail.

## Consequences
- Migration `0004_lab_consent_finance_and_migration.py` upgrades `0003_treatment_and_signing` cleanly to 36 tables.
- All external payment gateways, tax e-invoices, and clinical consent wordings remain synthetic-only until site-specific legal/financial sign-off.
