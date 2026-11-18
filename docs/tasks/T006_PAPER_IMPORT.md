# T006 — Legacy paper provenance and importer
Priority P1 · Owner: Integration/Clinical · Depends T003, T001, encrypted archive

**Status (2026-11-18):** Completed for synthetic quarantine/provenance slice (`ADR-009`, `backend/tests/test_paper_import_quarantine.py`); physical clinic paper archive retention rules and encrypted object storage (`T010`) remain required before real patient folders are scanned.

## Work
- Implemented `MigrationBatch` and `MigrationItem` quarantine pipeline (`POST /api/v1/migrations/paper-batches`, `POST /api/v1/migrations/paper-batches/{id}/items`).
- Enforced page completeness and legibility verification: missing pages (e.g. page 3 of 5) or illegible scans are quarantined (`incomplete_missing_pages` / `illegible_quarantined`) and blocked from verification (`409`, `NEG-10`, `DR-01`).
- Implemented duplicate patient candidate detection (`needs_human_identity_review`, `PAT-005`, `DR-02`) requiring explicit human resolution (`link_existing_patient` or `create_distinct_patient`) and never auto-merging by name or phone.
- Preserved `provenance_source="legacy_scan"` and `digital_signature_status="not_digitally_signed_legacy_paper"`, rejecting any attempt to claim digital signature on a legacy paper scan (`409`, `INV-019`, `DR-03`, `MIG-007`).
- Added batch reconciliation report (`GET /api/v1/migrations/paper-batches/{id}/reconciliation`) and safe batch rollback (`POST /api/v1/migrations/paper-batches/{id}/rollback`, `MIG-008`).

## Acceptance
All negative tests (missing pages, duplicate names/phones, digital signature forgery, batch rollback) pass with synthetic data.
