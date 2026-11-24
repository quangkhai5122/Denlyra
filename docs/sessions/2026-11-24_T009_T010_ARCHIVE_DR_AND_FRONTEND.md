# Session Report — 2026-11-24 (`T010` Encrypted Archive & DR Drill + `T009` Role-Based React Workspaces)

- **Tasks:** [T010](../tasks/T010_BACKUP_RESTORE.md) (`P0` before PHI), [T009](../tasks/T009_REACT_FRONTEND.md) (`P1`)
- **Architecture Decision:** [ADR-010](../adr/ADR-010-encrypted-archive-dr-and-role-workspaces.md), [RETENTION_AND_DR_POLICY.md](../operations/RETENTION_AND_DR_POLICY.md)
- **Canonical State Index:** [PROJECT_STATE.md](../PROJECT_STATE.md)

## 1. Objective & Scope
1. Implement `T010` per-clinic envelope encryption, key rotation/revocation, retention/legal-hold physical deletion block (`INV-018`/`DR-08`), signed cross-store backup manifests, and isolated DR restore drill (`INV-024`, `NEG-13`, `DR-04`, `DR-05`) with negative-first tests (`backend/tests/test_backup_restore_dr.py`).
2. Implement `T009` OpenAPI-generated TypeScript client (`scripts/generate_openapi_ts.py` -> `apps/clinic-web/src/lib/generated-api.ts`, `INT-001`), 5 role-based Next.js 15.5.29 workspaces with in-memory Bearer sessions, pessimistic `409 Conflict` handling, fixed `Asia/Ho_Chi_Minh` timezone formatting (`R-011`), accessible SVG FDI odontogram (`ODN-004`), and Node 24 contract/accessibility tests.
3. Fix Windows sandbox NTFS junction traversal (`[WinError 448]`) in `backend/tests/conftest.py` using junction-free `tmp_path` allocation.

## 2. Key Artifacts Delivered
- **Backend & Migrations (`40` tables, `93` OpenAPI operations):**
  - `backend/src/denlyra/archive_dr.py`: `DLY1` Encrypt-then-MAC (`HMAC-SHA256` KEK/DEK wrapping + stream encryption + `hmac.compare_digest` tag verification), key rotation (`v1 -> v2` `retired_decrypt_only`) & revocation, `409` retention/legal-hold deletion guard, `create_backup_snapshot`, and `run_isolated_restore_drill` restoring into an isolated SQLite DB and measuring `rto_ms` & `rpo_lag_ms`.
  - `backend/alembic/versions/0005_archive_and_dr.py`: adds `tenant_encryption_key`, `archive_object`, `backup_manifest`, and `restore_drill_run`.
  - `scripts/run_dr_restore_drill.py`: standalone disposable CLI DR restore drill verifier.
  - `backend/tests/test_backup_restore_dr.py`: 5 comprehensive test suites covering key rotation, legal-hold deletion block, clean DR drill, bit-flipped ciphertext, missing blob (`NEG-13`), wrong master key, revoked key, stale object-store checkpoint (`DR-05`), tampered signature evidence (`DR-04`), and cross-tenant restore (`403`/`404`).
- **Frontend & Contract Generation (`apps/clinic-web`):**
  - `scripts/generate_openapi_ts.py` & `apps/clinic-web/src/lib/generated-api.ts`: auto-generated TypeScript interfaces + pessimistic `DenlyraApiClient` (`--check` enforced in CI).
  - `apps/clinic-web/src/lib/timezone.ts`: fixed `Asia/Ho_Chi_Minh` (`UTC+07:00`) formatting and integer-only VND guard (`INV-019`).
  - `apps/clinic-web/src/components/OdontogramSvg.tsx`: keyboard/touch accessible SVG FDI chart (`11–48` permanent & `51–85` primary).
  - `apps/clinic-web/src/app/page.tsx`, `globals.css`, `api/demo/[...path]/route.ts`: 5 role workspaces (`receptionist`, `dentist`, `treatment_coordinator`, `finance`, `clinic_owner`) + `DELETE` proxy forwarding.
  - `apps/clinic-web/tests/frontend_contracts_and_a11y.test.mjs`: 4 automated contract, timezone, integer VND, and accessibility/security tests (`npm test`).

## 3. Verification Summary
- `pytest backend/tests -q`: **53 passed, 1 skipped** (live PostgreSQL skipped locally without `DENLYRA_TEST_POSTGRES_URL`).
- `python scripts/run_dr_restore_drill.py`: **PASS** (`status=passed objects=2 snapshots=1 rpo_lag_ms=0`).
- `python scripts/generate_openapi_ts.py --check`: **PASS** (79 paths / 93 operations).
- `python scripts/smoke_baseline.py`: **PASS** (`40` domain tables at head `0005_archive_and_dr`; `93` OpenAPI operations).
- `apps/clinic-web`: `npm test` (**4 pass, 0 fail**), `npm run typecheck` (**PASS**), `npm run build` (**PASS**, Next.js 15.5.29).
- `python scripts/verify_artifact.py` & `python scripts/update_manifest.py --check`: **PASS** (`83/222` `D` flags).

## 4. Remaining External Gates
- Live PostgreSQL 16 concurrency receipt (`T002` — inspect GitHub Actions `postgres-concurrency-tests` or run `scripts/verify_postgres_live.py` with `DENLYRA_TEST_POSTGRES_URL`).
- Named dentist & legal counsel sign-off on [NEEDS_CLINICAL_REVIEW.md](../clinical/NEEDS_CLINICAL_REVIEW.md) (`T003`, `T004`, `T010` Circular 33/2025/TT-BYT retention).
- Live OIDC/MFA + external Cloud KMS/HSM + independent `SEC-G1` security review before any real PHI.
