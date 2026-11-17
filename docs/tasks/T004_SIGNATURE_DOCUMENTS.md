# T004 — Authenticated clinical documents, legal signature adapter and addenda
Priority P0 · Owner: Clinical/Platform · Blocked by human legal+medical signature specification T003

**Status (2026-11-17):** Blocked — human clinical/legal evidence required. See `docs/PROJECT_STATE.md` for current ordering.

## Work
- Define identity proof, signer roles and forms requiring specific signature/confirmation, exact snapshot canonicalization and evidence.
- Build `SignatureProvider` interface with fake test double only; real provider requires contract and legal validation.
- Store content bytes hash, template/version, sign evidence, actor and timestamp, immutable archive manifest.
- Implement addendum and revoke/entered-in-error with required reason, without altering original.
- Test altered content/revoked signer/provider timeout/concurrent version/signature mismatch.

## Acceptance
All negative cases fail closed, no `authenticated` status without verified legal evidence, originals bit-for-bit retained, clinical+legal approvers sign off, restored artifacts validate.
