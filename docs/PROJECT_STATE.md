# Denlyra durable agent handoff — 2026-11-18

## Current status
Research-grade **synthetic-only demonstrator**, version `0.1.0`.
- `R0` (`T000`), `T001` synthetic auth/RBAC (`ADR-007`), `T004`/`T005` synthetic signature envelope & multi-dependency treatment journey (`ADR-008`), and `T006`/`T007`/`T008` paper quarantine importer, consent taxonomy/scoped lab portal & idempotent revenue ledger (`ADR-009`) are implemented and verified locally.
- `T002` frozen Alembic migration chain (`0001_demo` -> `0004_lab_consent_finance_and_migration`), atomic multi-resource booking, SQLite triggers, 2-connection race harness, `scripts/verify_postgres_live.py`, and GitHub Actions `postgres-concurrency-tests` (`postgres:16`) are implemented; inspect the remote GitHub Actions run or run `verify_postgres_live.py` against a local PostgreSQL 16 server to close `T002`.
- `T003` quarantined synthetic `FormRegistry` (`INV-022`) and `T004` real legal signing remain gated on human clinical/legal sign-off in [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md).
- **Not production, not approved EMR, not legally signed clinical records.**

Single source of current status: this file. Detailed dated evidence:
- [2026-11-18 T006/T007/T008 lab, finance & paper quarantine](sessions/2026-11-18_T006_T007_T008_LAB_FINANCE_MIGRATION.md)
- [2026-11-18 T004/T005 treatment & signing slice](sessions/2026-11-18_T004_T005_TREATMENT_AND_SIGNING.md)
- [2026-11-18 T001/T002/T003 foundation hardening](sessions/2026-11-18_T001_T002_T003_FOUNDATION_HARDENING.md)
- [2026-11-17 T000 onboarding](sessions/2026-11-17_T000_ONBOARDING.md)
Mandatory opening/closing and Vietnamese report: [AGENT_WORKFLOW](engineering/AGENT_WORKFLOW.md).

## Implemented & demonstrated
- FastAPI localhost API, **36 domain/platform tables** and **78 OpenAPI HTTP operations**, plus static UI (`apps/demo-web/`) and optional Next.js prototype (`apps/clinic-web/`).
- **T001–T005:** Synthetic `HS256` token issuer + RBAC/ABAC + revocation + single-use signed URLs (`ADR-007`); frozen Alembic migrations (`0001_demo`..`0004_lab_consent_finance_and_migration`), atomic doctor+chair+device booking & 2-connection race tests; quarantined `FormRegistry` (`INV-022`); `FakeSyntheticSignatureProvider` + immutable `ClinicalDocumentSnapshot` + addenda/`entered_in_error`; multi-dependency DAG with DFS cycle detection, `treatment_coordination_link`, `outbox_event`, atomic reschedule, reassessment loops, and timeline (`ADR-008`).
- **T006 Paper Quarantine Importer (`ADR-009`):** `MigrationBatch`/`MigrationItem`, page-hash completeness checks (`NEG-10`/`DR-01`), duplicate patient candidate queue requiring explicit human resolution (`PAT-005`/`DR-02`), strict `legacy_scan` provenance rejecting digital signature claims (`DR-03`), batch reconciliation, and batch rollback (`MIG-008`).
- **T007 Consent Taxonomy & Scoped Lab Partner Portal (`ADR-009`):** Purpose-separated `ConsentRecord` (`treatment`, `data_processing`, `marketing`, `financial`) with guardian authority verification (`PAT-004`) and isolated marketing withdrawal (`SEC-07`); lab delay alerts (`lab_due_after_appointment`) without auto-rescheduling (`SCH-013`), delivery receipt vs clinical verification separation, remake lineage, and minimized-data `LabPartnerGrant` portal (`OPS-06`).
- **T008 Idempotent Revenue Ledger & Reconciliation (`ADR-009`):** Immutable `EstimateVersion` (`FIN-002`), append-only `LedgerEntry`, `idempotency_key` deduplication across charges/payments/allocations/refunds (`NEG-08`, `NEG-17`), DB allocation-bounds trigger + 2-connection allocation race verification, and daily `CashierReconciliation` by tender (`FIN-010`).

## Task / milestone ledger
| ID | Status | Evidence / starting condition |
|---|---|---|
| [T000](tasks/T000_REPOSITORY_ONBOARDING.md) | Completed | [2026-11-17 session](sessions/2026-11-17_T000_ONBOARDING.md) |
| [T001](tasks/T001_HARDEN_IDENTITY.md) | Completed (synthetic foundation) | [ADR-007](adr/ADR-007-identity-and-authorization.md), `test_identity_auth.py`; live OIDC & `SEC-G1` review pending |
| [T002](tasks/T002_POSTGRES_BOOKING.md) | In progress — code, `verify_postgres_live.py`, and CI job complete; awaiting live PG run receipt | Inspect GitHub Actions `postgres-concurrency-tests` or run `verify_postgres_live.py` with `DENLYRA_TEST_POSTGRES_URL` |
| [T003](tasks/T003_FORM_MAPPING.md) | Blocked on human clinical/legal sign-off (safe synthetic `FormRegistry` complete) | [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md), `test_form_registry.py` |
| [T004](tasks/T004_SIGNATURE_DOCUMENTS.md) | Synthetic adapter slice completed; real legal signing blocked on `NEEDS_CLINICAL_REVIEW.md` | [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md), `signing.py`, `test_signature_documents.py` |
| [T005](tasks/T005_TREATMENT_E2E.md) | Completed (synthetic domain/API slice) | [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md), `test_treatment_journey_e2e.py` |
| [T006](tasks/T006_PAPER_IMPORT.md) | Completed (synthetic quarantine slice) | [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md), `test_paper_import_quarantine.py`; physical archive/encryption (`T010`) pending |
| [T007](tasks/T007_LAB_CONSENT.md) | Completed (synthetic domain/API slice) | [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md), `test_lab_consent_portal.py` |
| [T008](tasks/T008_FINANCE_LEDGER.md) | Completed (synthetic domain/API slice) | [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md), `test_finance_ledger.py` |
| [T009](tasks/T009_REACT_FRONTEND.md) | **Next / pending; ready to start** | Generate typed OpenAPI TS client and build role-based Next.js workspaces (`R-011` timezone display) |
| [T010](tasks/T010_BACKUP_RESTORE.md) | **Next / pending; P0 before PHI** | Build encrypted object/archive manifest, key-rotation policy, and isolated DR restore verification (`NEG-13`, `DR-04`, `DR-05`) |

Full backlog: [ROADMAP](engineering/ROADMAP.md), [task packets](tasks/), [222-ID catalog](product/FUNCTION_CATALOG.md): **72 partial demo flags (`D`), 150 not implemented (`—`)**; 0 rows are certified production functionality.

## Validation evidence — last verified 2026-11-18
Windows, repository `.venv`, CPython 3.12.14; Node 24.11.1 / npm 11.6.2.

| Check | Observed result |
|---|---|
| `./.venv/Scripts/python.exe -m pytest backend/tests -q` | **48 passed, 1 skipped** (live PG skipped locally without `DENLYRA_TEST_POSTGRES_URL`) |
| Backend & scripts Ruff / `compileall` / `node --check` | Passed (exit 0) |
| `python scripts/verify_artifact.py` | Passed; 222 unique catalog IDs, 20 mandatory files, disabled safety flags and Markdown links |
| `python scripts/smoke_baseline.py` | Passed; SQLite upgrade `0001_demo` -> `0004_lab_consent_finance_and_migration` (36 domain tables; 78 HTTP operations) |
| Alembic `upgrade head --sql` (cwd `backend`) | Passed; offline PostgreSQL SQL generated through `0004_lab_consent_finance_and_migration` |
| Next `npm run typecheck` / `npm run build` | Passed on Windows, Next 15.5.29 / React 19.3.1 |
| `python scripts/update_manifest.py --check` | Passed |

## Open risk ledger / technical debt
| ID | Severity | Known truth and owner task |
|---|---|---|
| R-001 | High before PHI | T001 synthetic token + RBAC/ABAC implemented; live OIDC/MFA & independent security audit required before PHI (`SEC-G1`) |
| R-002 | High | T002/T008 concurrency harnesses & CI `postgres:16` job added; verify remote CI run or local PG server (`T002`/`T008`) |
| R-003 | High before clinical use | T004 canonical snapshot + `FakeSyntheticSignatureProvider` implemented; DB-level append-only roles and real legal signer remain pending (`T004`/`T010`) |
| R-004 | Critical before clinical use | Quarantined `FormRegistry` (`T003`) & synthetic signing (`T004`) gated on named dentist + counsel review (`NEEDS_CLINICAL_REVIEW.md`) |
| R-005 | Critical before PHI | No encrypted archive, backup/key recovery, restore or incident implementation (`T010`) |
| R-006 | High | T006 paper quarantine logic complete; physical scan storage encryption & real FHIR/DICOM pending (`T010`/interop) |
| R-007 | High | Consent taxonomy (`T007`) built; real payment/messaging/AI providers remain disabled until formal legal/vendor approval |
| R-008 | Commercial blocker | Denlyra brand/trademark and software license undecided (`Owner/counsel`) |
| R-009 | Mitigated in local proxy | Next proxy forwards `Authorization`, `Origin`, `Sec-Fetch-Site`; full browser/E2E auth tests remain in `T009` |
| R-010 | Resolved in Alembic | Frozen explicit DDL chain `0001_demo` -> `0004_lab_consent_finance_and_migration` |
| R-011 | Medium | DB timestamps naive UTC, API appends Z; static calendar uses browser timezone rather than fixed `Asia/Ho_Chi_Minh` (`T009`) |
| R-012 | Medium | Missing pagination and generated typed TS client (`T009`) |
| R-013 | Low / platform debt | Cross-agent pytest temp/cache fixed; Starlette/httpx deprecation warning remains |

## Decisions locked so far
- `ADR-001`..`ADR-005`: modular monolith, separate clinical/finance authority, proposed DB-per-clinic, draft-only AI, site-specific release gates
- [ADR-006](adr/ADR-006-denlyra-onboarding.md): Denlyra naming and durable handoff
- [ADR-007](adr/ADR-007-identity-and-authorization.md): Identity, session verification, and deny-by-default RBAC/ABAC foundation
- [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md): Multi-dependency Treatment Journey coordination and Synthetic Signature Envelope
- [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md): Purpose-separated Consent & Scoped Lab Portal, Idempotent Revenue Ledger, and Legacy Paper Quarantine Importer

## Next tasks and human decisions
1. **P0 before PHI — `T010` (`docs/tasks/T010_BACKUP_RESTORE.md`)** — encrypted archive manifest, key-rotation/escrow design, missing/corrupt object checks (`NEG-13`, `DR-04`, `DR-05`), and isolated DR restore drill.
2. **P1 — `T009` (`docs/tasks/T009_REACT_FRONTEND.md`)** — typed OpenAPI TS client generation, role-based Next.js workspaces, `Asia/Ho_Chi_Minh` timezone formatting (`R-011`), and Playwright E2E/accessibility suite.
3. **P0 external gates — `T002` & `M0`/`T003`/`T004`** — inspect CI `postgres-concurrency-tests` run (or run `verify_postgres_live.py` on local PG 16) and obtain dentist/counsel sign-off for [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md).

## Git and exact continuation
Next session begins with `git status --short --branch`, `git log -2 --oneline`, `AGENTS.md`, this file, [latest session report](sessions/2026-11-18_T006_T007_T008_LAB_FINANCE_MIGRATION.md), and `docs/tasks/T010_BACKUP_RESTORE.md` (or `T009_REACT_FRONTEND.md`). Then run `./.venv/Scripts/python.exe -m pytest backend/tests -q` and write negative tests first before edits.
