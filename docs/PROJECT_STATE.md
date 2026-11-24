# Denlyra durable agent handoff — 2026-11-24

## Current status
Research-grade **synthetic-only demonstrator**, version `0.1.0`.
- All ten foundational engineering packets (`T000`–`T010`) now have verified synthetic domain, API, migration, frontend, and negative-test implementations (`ADR-006`..`ADR-010`).
- `T002` frozen Alembic migration chain (`0001_demo` -> `0005_archive_and_dr`), atomic multi-resource booking, SQLite triggers, 2-connection race harness, `scripts/verify_postgres_live.py`, and GitHub Actions `postgres-concurrency-tests` (`postgres:16`) are implemented; inspect the remote GitHub Actions run or run `verify_postgres_live.py` against a local PostgreSQL 16 server to record the live PG receipt.
- `T003` quarantined synthetic `FormRegistry` (`INV-022`), `T004` real legal e-signing, and `T010` statutory retention schedules remain gated on human clinical/legal sign-off in [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md) and [RETENTION_AND_DR_POLICY.md](operations/RETENTION_AND_DR_POLICY.md).
- **Not production, not approved EMR, not legally signed clinical records.**

Single source of current status: this file. Detailed dated evidence:
- [2026-11-24 T009/T010 encrypted archive, DR drill & role workspaces](sessions/2026-11-24_T009_T010_ARCHIVE_DR_AND_FRONTEND.md)
- [2026-11-18 T006/T007/T008 lab, finance & paper quarantine](sessions/2026-11-18_T006_T007_T008_LAB_FINANCE_MIGRATION.md)
- [2026-11-18 T004/T005 treatment & signing slice](sessions/2026-11-18_T004_T005_TREATMENT_AND_SIGNING.md)
- [2026-11-18 T001/T002/T003 foundation hardening](sessions/2026-11-18_T001_T002_T003_FOUNDATION_HARDENING.md)
- [2026-11-17 T000 onboarding](sessions/2026-11-17_T000_ONBOARDING.md)
Mandatory opening/closing and Vietnamese report: [AGENT_WORKFLOW](engineering/AGENT_WORKFLOW.md).

## Implemented & demonstrated
- FastAPI localhost API, **40 domain/platform tables** and **93 OpenAPI HTTP operations** (`79` paths), plus zero-dependency static UI (`apps/demo-web/`) and role-based Next.js 15.5.29 workspaces (`apps/clinic-web/`).
- **T001–T005 (`ADR-007`, `ADR-008`):** Synthetic `HS256` token issuer + RBAC/ABAC + revocation + single-use signed URLs; frozen Alembic migrations (`0001_demo`..`0005_archive_and_dr`), atomic doctor+chair+device booking & 2-connection race tests; quarantined `FormRegistry` (`INV-022`); `FakeSyntheticSignatureProvider` + immutable `ClinicalDocumentSnapshot` + addenda/`entered_in_error`; multi-dependency DAG with DFS cycle detection, `treatment_coordination_link`, `outbox_event`, atomic reschedule, reassessment loops, and timeline.
- **T006–T008 (`ADR-009`):** Paper quarantine importer (`MigrationBatch`/`MigrationItem`, missing-page block, duplicate-patient queue, `legacy_scan` provenance, rollback); purpose-separated `ConsentRecord`, lab delay alerts, delivery vs verification separation, remake lineage, and minimized `LabPartnerGrant` portal; immutable `EstimateVersion`, append-only `LedgerEntry`, idempotent charges/payments/allocations/refunds, allocation-bounds trigger, and daily `CashierReconciliation`.
- **T010 Encrypted Record Archive & Isolated DR Restore Drill (`ADR-010`):** Per-clinic wrapped DEKs (`TenantEncryptionKey`), `DLY1` Encrypt-then-MAC `ArchiveObject` storage (`clinical_attachment`, `dicom_study_stub`, `legacy_paper_scan`, `signed_snapshot_export`), key rotation (`v1 -> v2` `retired_decrypt_only`) & revocation, `409` retention/legal-hold deletion block (`INV-018`/`DR-08`), signed cross-store `BackupManifest`, and automated isolated SQLite + object + signature restore drill (`RestoreDrillRun` + `scripts/run_dr_restore_drill.py`) measuring `rto_ms` & `rpo_lag_ms` (`INV-024`, `NEG-13`, `DR-04`, `DR-05`).
- **T009 Role-Based React/Next.js Workspaces (`ADR-010`):** Generated OpenAPI TypeScript client (`scripts/generate_openapi_ts.py` -> `generated-api.ts`, `INT-001`), 5 role workspaces (`receptionist`, `dentist`, `treatment_coordinator`, `finance`, `clinic_owner`) with in-memory Bearer tokens, pessimistic `409 Conflict` alerts, fixed `Asia/Ho_Chi_Minh` (`+07:00`) timezone formatting (`R-011`), accessible SVG FDI odontogram (`11–48` & `51–85`, `ODN-004`), and Node 24 contract/a11y test suite.

## Task / milestone ledger
| ID | Status | Evidence / starting condition |
|---|---|---|
| [T000](tasks/T000_REPOSITORY_ONBOARDING.md) | Completed | [2026-11-17 session](sessions/2026-11-17_T000_ONBOARDING.md) |
| [T001](tasks/T001_HARDEN_IDENTITY.md) | Completed (synthetic foundation) | [ADR-007](adr/ADR-007-identity-and-authorization.md), `test_identity_auth.py`; live OIDC & `SEC-G1` review pending |
| [T002](tasks/T002_POSTGRES_BOOKING.md) | In progress — code, `verify_postgres_live.py`, and CI job complete; awaiting live PG run receipt | Inspect GitHub Actions `postgres-concurrency-tests` or run `verify_postgres_live.py` with `DENLYRA_TEST_POSTGRES_URL` |
| [T003](tasks/T003_FORM_MAPPING.md) | Blocked on human clinical/legal sign-off (safe synthetic `FormRegistry` complete) | [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md), `test_form_registry.py` |
| [T004](tasks/T004_SIGNATURE_DOCUMENTS.md) | Synthetic adapter slice completed; real legal signing blocked on `NEEDS_CLINICAL_REVIEW.md` | [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md), `signing.py`, `test_signature_documents.py` |
| [T005](tasks/T005_TREATMENT_E2E.md) | Completed (synthetic domain/API slice) | [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md), `test_treatment_journey_e2e.py` |
| [T006](tasks/T006_PAPER_IMPORT.md) | Completed (synthetic quarantine slice) | [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md), `test_paper_import_quarantine.py` |
| [T007](tasks/T007_LAB_CONSENT.md) | Completed (synthetic domain/API slice) | [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md), `test_lab_consent_portal.py` |
| [T008](tasks/T008_FINANCE_LEDGER.md) | Completed (synthetic domain/API slice) | [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md), `test_finance_ledger.py` |
| [T009](tasks/T009_REACT_FRONTEND.md) | Completed (synthetic role workspaces & generated OpenAPI TS client) | [ADR-010](adr/ADR-010-encrypted-archive-dr-and-role-workspaces.md), `generate_openapi_ts.py`, `frontend_contracts_and_a11y.test.mjs` |
| [T010](tasks/T010_BACKUP_RESTORE.md) | Completed (synthetic encrypted archive & isolated DR drill; external KMS & legal retention gated) | [ADR-010](adr/ADR-010-encrypted-archive-dr-and-role-workspaces.md), [RETENTION_AND_DR_POLICY.md](operations/RETENTION_AND_DR_POLICY.md), `test_backup_restore_dr.py` |

Full backlog: [ROADMAP](engineering/ROADMAP.md), [task packets](tasks/), [222-ID catalog](product/FUNCTION_CATALOG.md): **83 partial demo flags (`D`), 139 not implemented (`—`)**; 0 rows are certified production functionality.

## Validation evidence — last verified 2026-11-24
Windows, repository `.venv`, CPython 3.12.14; Node 24.11.1 / npm 11.6.2.

| Check | Observed result |
|---|---|
| `./.venv/Scripts/python.exe -m pytest backend/tests -q` | **53 passed, 1 skipped** (live PG skipped locally without `DENLYRA_TEST_POSTGRES_URL`) |
| `python scripts/run_dr_restore_drill.py` | Passed; isolated restore verified 2 encrypted objects (`v1`+`v2`) + 1 sealed snapshot, `rpo_lag_ms=0` |
| `python scripts/generate_openapi_ts.py --check` | Passed; `generated-api.ts` matches 79 FastAPI paths / 93 operations |
| Backend & scripts Ruff / `compileall` / `node --check` | Passed (exit 0) |
| `python scripts/verify_artifact.py` | Passed; 222 unique catalog IDs (83 `D`), 20 mandatory files, disabled safety flags and Markdown links |
| `python scripts/smoke_baseline.py` | Passed; SQLite upgrade `0001_demo` -> `0005_archive_and_dr` (40 domain tables; 93 HTTP operations) |
| Alembic `upgrade head --sql` (cwd `backend`) | Passed; offline PostgreSQL SQL generated through `0005_archive_and_dr` |
| Next `npm test` / `npm run typecheck` / `npm run build` | Passed on Windows (4/4 contract & a11y tests, Next 15.5.29 / React 19.3.1, 0 npm audit issues) |
| `python scripts/update_manifest.py --check` | Passed |

## Open risk ledger / technical debt
| ID | Severity | Known truth and owner task |
|---|---|---|
| R-001 | High before PHI | T001 synthetic token + RBAC/ABAC implemented; live OIDC/MFA & independent security audit required before PHI (`SEC-G1`) |
| R-002 | High | T002/T008 concurrency harnesses & CI `postgres:16` job added; verify remote CI run or local PG server (`T002`/`T008`) |
| R-003 | High before clinical use | T004 canonical snapshot + `FakeSyntheticSignatureProvider` implemented; DB-level append-only roles and real legal signer remain pending (`T004`) |
| R-004 | Critical before clinical use | Quarantined `FormRegistry` (`T003`), synthetic signing (`T004`), and statutory retention (`T010`) gated on named dentist + counsel review (`NEEDS_CLINICAL_REVIEW.md`) |
| R-005 | Mitigated in synthetic foundation | `T010` envelope encryption, key rotation, retention hold, and isolated DR drill implemented; external Cloud KMS/HSM & WORM cloud storage required before real PHI |
| R-006 | Medium | T006 paper quarantine + T010 encrypted blob archive complete; real Orthanc DICOM/FHIR R4 adapters remain pending (`M6`) |
| R-007 | High | Consent taxonomy (`T007`) built; real payment/messaging/AI providers remain disabled until formal legal/vendor approval |
| R-008 | Commercial blocker | Denlyra brand/trademark and software license undecided (`Owner/counsel`) |
| R-009 | Mitigated in Next.js workspaces | `T009` uses in-memory Bearer sessions + `DELETE` proxy forwarding + Node contract tests; provisioned Playwright live-OIDC browser E2E pending (`SEC-G1`) |
| R-010 | Resolved in Alembic | Frozen explicit DDL chain `0001_demo` -> `0005_archive_and_dr` |
| R-011 | Resolved in `clinic-web` | `apps/clinic-web` enforces fixed `Asia/Ho_Chi_Minh` (`+07:00`) via `timezone.ts`; legacy `apps/demo-web` static view remains demo-only |
| R-012 | Resolved for TS client | `scripts/generate_openapi_ts.py` (`--check` in CI) keeps `generated-api.ts` synchronized; cursor pagination remains backlog debt |
| R-013 | Low / platform debt | Windows sandbox NTFS junction (`WinError 448`) fixed in `conftest.py`; Starlette/httpx deprecation warning remains |

## Decisions locked so far
- `ADR-001`..`ADR-005`: modular monolith, separate clinical/finance authority, proposed DB-per-clinic, draft-only AI, site-specific release gates
- [ADR-006](adr/ADR-006-denlyra-onboarding.md): Denlyra naming and durable handoff
- [ADR-007](adr/ADR-007-identity-and-authorization.md): Identity, session verification, and deny-by-default RBAC/ABAC foundation
- [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md): Multi-dependency Treatment Journey coordination and Synthetic Signature Envelope
- [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md): Purpose-separated Consent & Scoped Lab Portal, Idempotent Revenue Ledger, and Legacy Paper Quarantine Importer
- [ADR-010](adr/ADR-010-encrypted-archive-dr-and-role-workspaces.md): Encrypted Record Archive, Isolated DR Restore Drill, and Role-Based React Workspaces

## Next tasks and human decisions
1. **P1 domain slice (`M5`) — `T011` Append-Only Inventory Lot & Stock Movement Ledger (`INV-001`..`INV-010`, `INV-023`)** — SKU/lot expiry tracking, append-only stock movement ledger, reservation != consumption invariant, and procedure-linked consumption.
2. **P1 interoperability & AI safety (`M6`/`M7`) — `T012` FHIR R4 Read/Export Profiles & Offline AI Draft-Only Evaluation Harness (`INT-002`, `AI-009`, `AI-010`)** — clinic-scoped FHIR Patient/Appointment/Encounter export validation and prompt-injection/abstention harness with zero direct EMR writes.
3. **P0 external gates — `T002` & `M0`/`T003`/`T004`/`T010`** — inspect GitHub Actions `postgres-concurrency-tests` receipt (or run `verify_postgres_live.py` on PostgreSQL 16) and obtain dentist/counsel sign-off on [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md) & [RETENTION_AND_DR_POLICY.md](operations/RETENTION_AND_DR_POLICY.md).

## Git and exact continuation
Next session begins with `git status --short --branch`, `git log -2 --oneline`, `AGENTS.md`, this file, and [latest session report](sessions/2026-11-24_T009_T010_ARCHIVE_DR_AND_FRONTEND.md). Run `./.venv/Scripts/python.exe -m pytest backend/tests -q`, author task packet `docs/tasks/T011_INVENTORY_LEDGER.md` and negative tests first before editing domain code.
