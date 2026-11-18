# T004 — Authenticated clinical documents, legal signature adapter and addenda
Priority P0 · Owner: Clinical/Platform · Blocked by human legal+medical signature specification T003

**Status (2026-11-18):** Synthetic adapter slice completed (`ADR-008`, `backend/src/denlyra/signing.py`, `backend/tests/test_signature_documents.py`). **Real legal `authenticated` signing remains blocked pending human clinical/legal sign-off in `docs/clinical/NEEDS_CLINICAL_REVIEW.md`.**

## Work
- Defined `SignatureProvider` protocol and `FakeSyntheticSignatureProvider` test double (`backend/src/denlyra/signing.py`); `mode="legal_authenticated"` fails closed (`409`).
- Built `ClinicalDocumentSnapshot` storing canonical JSON bytes, `canonical_sha256`, `manifest_sha256`, signer staff ID, synthetic provider receipt, and creation timestamp (`0003_treatment_and_signing.py`).
- Implemented linked `addenda` (`POST /api/v1/clinical-documents/{id}/addenda`) and `entered_in_error` (`POST /api/v1/clinical-documents/{id}/enter-in-error`) requiring non-empty reason while preserving original canonical bytes bit-for-bit.
- Verified negative cases in `test_signature_documents.py`: altered content/digest mismatch (`NEG-03` -> `409`), deactivated/non-clinician signer (`NEG-15` -> `401`/`403`), provider timeout (`NEG-14` -> `503` unsealed), concurrent note revision (`409`), and signature receipt mismatch (`409`).

## Acceptance
All synthetic negative cases fail closed, no `authenticated` status is granted without verified legal evidence, originals are retained bit-for-bit, and synthetic receipt verification passes. Final clinical+legal sign-off (`CLIN-G2`) remains gated by `NEEDS_CLINICAL_REVIEW.md`.
