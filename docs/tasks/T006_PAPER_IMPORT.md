# T006 — Legacy paper provenance and importer
Priority P1 · Owner: Integration/Clinical · Depends T003, T001, encrypted archive

**Status (2026-11-17):** Pending — implementation not started. See `docs/PROJECT_STATE.md` for current ordering.

## Work
Secure scan quarantine; page hashes/completeness, patient match review, separate legacy source and native digital records, optional OCR with human check; batch rollback/reconciliation and cutover SOP. Negative tests missing pages, wrong patient, duplicate names and damaged scan. No historical digital signature fabrication.

## Acceptance
Clinician/record owner signs off mapping, legal retention verified, source scans and manifest recoverable, batch import can be reconciled or safely rolled back, demo with fake documents only.
