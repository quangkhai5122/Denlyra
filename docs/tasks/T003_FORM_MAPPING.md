# T003 — Verified outpatient dental form mapping (clinical approval required)
Priority P0 · Owner: Clinical Domain + Medical Director · Blocked until clinic form evidence

**Status (2026-11-18):** Blocked on human clinical/legal sign-off — safe synthetic `FormRegistry` interface, versioned template/field schema, tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validator, and fail-closed approval/export guards implemented (`backend/tests/test_form_registry.py`); review packet created at `docs/clinical/NEEDS_CLINICAL_REVIEW.md`.

## Goal
Translate the authoritative current outpatient dental form (`16/BV-01` and other applicable forms) into versioned normalized domain fields and rendering/export schema.

## Work
- Created `docs/clinical/NEEDS_CLINICAL_REVIEW.md` detailing exact source verification and field-by-field sign-off needed from Clinic Medical Director and Legal Counsel.
- Built `FormTemplateVersion` and `FormFieldMap` tables and `FormRegistry` service (`register_form_template`, `list_form_templates`, `validate_form_preview`, `approve_form_template_blocked`, `export_official_form_blocked`).
- Enforced immutable `(official_code, schema_version)` registration (`NEG-16`), `INV-022` tri-state semantics (missing/unanswered allergy is never coerced to negative), and fail-closed `409 Conflict` on self-approval (`NEG-20`) or official EMR export.

## Acceptance
100% of applicable fields in reviewed inventory mapped, signed-off sample patient form rendered and independently checked, historical template versions preserved; any missing legal approval blocks clinical use. Remains blocked for clinical activation until `docs/clinical/NEEDS_CLINICAL_REVIEW.md` is signed off by named human reviewers.
