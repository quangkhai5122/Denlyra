# ADR-010 — Encrypted Record Archive, Isolated DR Restore Drill, and Role-Based React Workspaces

- **Status:** Accepted (synthetic research foundation; production KMS/HSM, live OIDC, and Circular 33/2025/TT-BYT retention sign-off remain gated)
- **Date:** 2026-11-24
- **Tasks:** [T010](../tasks/T010_BACKUP_RESTORE.md), [T009](../tasks/T009_REACT_FRONTEND.md)
- **Related invariants & risks:** `INV-001`, `INV-006`, `INV-018`, `INV-023`, `INV-024`, `NEG-02`, `NEG-13`, `DR-04`, `DR-05`, `DR-08`, `R-005`, `R-006`, `R-009`, `R-011`, `R-012`

## Context

1. **Encrypted archive & disaster recovery (`T010`, P0 before PHI):** Clinical attachments, DICOM imaging studies, quarantined paper scans (`T006`), and sealed `ClinicalDocumentSnapshot` artifacts (`T004`) cannot rely solely on database backups. If an object store checkpoint lags behind PostgreSQL PITR (`DR-05`), if an encrypted object is missing (`NEG-13`) or tampered with, if a tenant key is lost/revoked, or if signature receipts cannot be verified after restore (`DR-04`), clinical integrity (`INV-024`) fails silently unless tested by an automated isolated restore drill. Furthermore, retention and legal-hold rules (`INV-018`, `DR-08`) must block physical deletion while exact retention durations under Circular 33/2025/TT-BYT await legal sign-off.
2. **Role-based clinic workspaces & typed contract (`T009`, P1):** `apps/clinic-web` previously contained only a 50-line unauthenticated prototype with hand-written types, no role workspaces, no chair/provider resource lanes, no interactive accessible FDI odontogram, and browser-dependent timezone rendering (`R-011`, `R-012`).

## Decisions

### 1. Per-Clinic Envelope Encryption & Key Rotation (`T010`)
- Introduce `tenant_encryption_key` with per-clinic versioned Data Encryption Keys (`DEK`s). Raw `DEK`s are never persisted in database tables or backup manifests; they are wrapped under a clinic-and-version-derived Key Encryption Key (`KEK`) from `DENLYRA_ARCHIVE_MASTER_SECRET` (production target: external Cloud KMS / HSM).
- Encrypt every `archive_object` (`clinical_attachment`, `dicom_study_stub`, `legacy_paper_scan`, `signed_snapshot_export`) using authenticated Encrypt-then-MAC (`DLY1` envelope: 16-byte random nonce, counter-mode SHA-256 stream, and independent constant-time `HMAC-SHA256` authentication tag bound to `clinic_id`, `patient_id`, `object_id`, and `key_version` as AAD).
- Key rotation (`v1` -> `v2`) transitions `v1` to `retired_decrypt_only` so historical objects remain verifiable without re-encrypting immutable clinical evidence in place, while new writes use `v2`. Explicit key revocation (`revoked`) fails closed on read and restore.

### 2. Retention / Legal Hold Block & Isolated Cross-Store DR Drill (`T010`)
- All `archive_object` rows carry `retention_class`, conservative provisional `retention_until`, and `legal_hold`. `DELETE /api/v1/archive/objects/{id}` refuses physical deletion with `409 Conflict` (`DR-08`) and emits `archive.deletion_blocked_retention`.
- `backup_manifest` seals a signed JSON manifest (`manifest_sha256` + `manifest_hmac`) binding `db_checkpoint_at`, `object_store_checkpoint_at`, sealed `clinical_document_snapshot` digests/signature flags, and `archive_object` plaintext/ciphertext SHA-256 digests.
- `restore_drill_run` (`POST /api/v1/archive/backups/{id}/restore-drill` and `scripts/run_dr_restore_drill.py`) restores into an **isolated disposable SQLite database and scratch directory**, verifying:
  1. Tenant scope (`target_clinic_id == backup.clinic_id`; cross-tenant restore rejected with `403`).
  2. Manifest HMAC/SHA-256 integrity.
  3. Cross-store checkpoint freshness (`object_store_checkpoint_at >= max(archive_object.created_at)`, rejecting stale object backups per `DR-05`).
  4. Presence (`NEG-13`), ciphertext digest, key availability/unwrapping, and authenticated decryption + plaintext SHA-256 of every archived object.
  5. Presence and cryptographic verification of `SignatureReceipt` on every sealed `ClinicalDocumentSnapshot` (`DR-04`).
  6. Measured `rto_ms` and `rpo_lag_ms` persisted in `restore_drill_run`.

### 3. Generated OpenAPI TypeScript Client & Role-Based Next.js Workspaces (`T009`)
- Add `scripts/generate_openapi_ts.py` (`--check` enforced in CI) generating `apps/clinic-web/src/lib/generated-api.ts` directly from FastAPI's OpenAPI schema (`INT-001`), exposing path/schema types and `DenlyraApiClient` returning explicit `{ ok, status, data, error }` results so `409 Conflict` booking/revision collisions are surfaced pessimistically without optimistic false success.
- Authenticate role sessions (`receptionist`, `dentist`, `treatment_coordinator`, `finance`, `clinic_owner`) via server-minted `HS256` Bearer tokens (`/api/demo/auth/token` -> `Authorization: Bearer <token>`) held strictly in React memory (`useState`), never `localStorage` or unverified actor headers.
- Format and construct all clinic schedule timestamps in fixed `Asia/Ho_Chi_Minh` (`UTC+07:00`) via `apps/clinic-web/src/lib/timezone.ts` (`R-011`).
- Build an accessible interactive SVG FDI odontogram (`apps/clinic-web/src/components/OdontogramSvg.tsx`) supporting permanent (`11–48`) and primary (`51–85`) dentition with keyboard (`Tab`, `Enter`, `Space`), `aria-pressed`, and Vietnamese tooth/surface labels.

## Consequences

- **Positive:** Closes `R-005` (synthetic foundation), `R-011` (Next.js clinic-web timezone), and `R-012` (typed OpenAPI client); adds migration `0005_archive_and_dr` (40 tables total) and automated DR restore drill + frontend contract/a11y tests without introducing unpinned third-party packages.
- **Remaining production gates:** External Cloud KMS/HSM key escrow, live PostgreSQL WAL/pgBackRest PITR against cloud object storage, Playwright headless browser suite in provisioned browser CI, live OIDC/MFA (`SEC-G1`), and human clinical/legal sign-off ([NEEDS_CLINICAL_REVIEW.md](../clinical/NEEDS_CLINICAL_REVIEW.md)) remain mandatory before any real PHI.
