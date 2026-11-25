# T025 — Versioned Terminology, Clinic-Reviewed Specialty Templates, PHI-Free Lab Billing, Labeled Overlays & Encrypted Report Exports
Priority P2 (`EMR` / `TRT` / `LAB` / `ODN` / `RPT`) · Owner: Clinical Charting, Lab Coordination & Owner Analytics · Depends T004, T007, T010, T016, T019, T020

**Status (2026-11-25):** Completed (versioned medical code sets & exact clinician-verified mappings without guessing, clinic-reviewed specialty plan templates, PHI-free lab vendor price list & invoice reconciliation, non-diagnostic labeled longitudinal imaging overlays, and scope-checked `DLY1`-encrypted PHI-free scheduled report exports verified in `test_terminology_templates_lab_reports.py`). See [ADR-018](../adr/ADR-018-terminology-specialty-templates-lab-billing-offline-sync-and-scheduling-ai.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Versioned Medical Code Sets & Exact Terminology Mapping (`EMR-016`):**
   - `terminology_code_entry` + `terminology_mapping_rule` store `(code_system, system_version, code)` and enforce `CheckConstraint("mapping_method = 'clinician_verified_exact'")` (`422` on guessed/fuzzy mapping); unmapped lookups abstain (`mapped=False`, `guessed_fallback_used=False`).
2. **Clinic-Reviewed Specialty Plan Templates (`TRT-015`):**
   - `specialty_plan_template` rejects generic/AI-generated unreviewed protocols (`422`), requires `dentist`/`medical_director` review (`403` for non-clinicians), and blocks instantiating patient plans from `draft_unreviewed` templates (`409`).
3. **PHI-Free Lab Price List & Invoice Reconciliation (`LAB-010`):**
   - `lab_vendor_price_item` + `lab_invoice_reconciliation` reconcile contracted unit + remake fees against vendor bills (`matched` vs `discrepancy_flagged`), reject patient PII in vendor references (`422`), and omit all patient identifiers from vendor statements (`CheckConstraint("NOT contains_phi")`).
4. **Labeled Non-Diagnostic Longitudinal Imaging Overlay (`ODN-009`):**
   - `longitudinal_imaging_overlay` binds same-patient baseline & follow-up `ArchiveObject`s with explicit `SYNTHETIC_VISUAL_COMPARISON_NOT_DIAGNOSTIC` provenance and blocks `claim_auto_diagnosis=True` (`409`, `CheckConstraint("NOT auto_diagnosis_generated")`).
5. **Multi-Branch Aggregates & Encrypted PHI-Free Scheduled Report Exports (`RPT-009`, `RPT-010`):**
   - `scheduled_report_export` enforces `OwnerBranchScopeGrant` on multi-branch exports (`403` without grant, zero patient chart pooling), blocks `include_phi=True` (`409`), restricts recipients to allowlisted clinic domains (`403`), and encrypts payloads using per-clinic `DLY1` Encrypt-then-MAC envelopes.

## Mandatory Negative Tests (Written Before Domain Code)
1. Non-clinician creating terminology mapping -> `403`; guessed mapping method -> `422`; unmapped lookup returns `mapped=False` (`EMR-016`); instantiating unreviewed specialty template -> `409` (`TRT-015`).
2. Lab invoice containing patient name/phone -> `422` and reconciled payload contains zero `patient_id`/PII while flagging overbilled variance (`LAB-010`); longitudinal overlay claiming auto-diagnosis or cross-patient object -> `409`/`422` (`ODN-009`).
3. Scheduled report export with `include_phi=True`, unallowlisted `@gmail.com` recipient, or unauthorized multi-branch key -> `409`/`403`; valid export produces `DLY1` ciphertext with zero patient names (`RPT-009`, `RPT-010`).
