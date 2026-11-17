# T003 — Verified outpatient dental form mapping (clinical approval required)
Priority P0 · Owner: Clinical Domain + Medical Director · Blocked until clinic form evidence

**Status (2026-11-17):** Blocked — human clinical/legal evidence required. See `docs/PROJECT_STATE.md` for current ordering.

## Goal
Translate the authoritative current outpatient dental form (16/BV-01 and other applicable forms) into versioned normalized domain fields and rendering/export schema.

## Work
- Retrieve the official PDF, verify Circular 32/2023 Appendix XXVIII and later amendment applicability including Circular 25/2026.
- Clinic medical director maps each original field, cardinality, validation, category, owner, signature/confirmation and effective date.
- Build FormRegistry versioned schema and field map, synthetic golden fixtures, missing/unknown semantics and generated PDF/structured export prototype.
- Record source URL/hash/page and human approvals, not chatbot interpretation.

## Acceptance
100% of applicable fields in reviewed inventory mapped, signed-off sample patient form rendered and independently checked, historical template versions preserved; any missing legal approval blocks clinical use.
