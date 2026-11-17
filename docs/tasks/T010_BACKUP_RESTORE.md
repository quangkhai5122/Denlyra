# T010 — Encrypted record archive and disaster recovery
Priority P0 before PHI · Owner: Security/Operations · Depends T001, T004

**Status (2026-11-17):** Pending — implementation not started. See `docs/PROJECT_STATE.md` for current ordering.

## Work
Design object storage, key management, versioned signed document/archive manifest, DICOM backups and PostgreSQL PITR. Build automatic restore drill to isolated environment and verify all record/media/signature references. Document retention policy (legal review) and incident runbooks. Test missing/altered object, wrong key, stale backup, unavailable signature evidence, tenant cross-restore.

## Acceptance
Restored archive intact, no silent missing files, RPO/RTO measured against realistic outage tests, legal/security owner sign-off, no PHI use before success.
