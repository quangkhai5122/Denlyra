# Denlyra durable agent handoff — 2026-11-24

## Current status
Research-grade **synthetic-only demonstrator**, version `0.1.0`.
- Sixteen foundational engineering packets (`T000`–`T016`) now have verified synthetic domain, API, migration, frontend, and negative-test implementations (`ADR-006`..`ADR-013`).
- `T002` frozen Alembic migration chain (`0001_demo` -> `0008_patient_merge_portal_and_kpi_lineage`), atomic multi-resource booking, SQLite triggers, 2-connection race harness, `scripts/verify_postgres_live.py`, and GitHub Actions `postgres-concurrency-tests` (`postgres:16`) are implemented; inspect the remote GitHub Actions run or run `verify_postgres_live.py` against a local PostgreSQL 16 server to record the live PG receipt.
- `T003` quarantined synthetic `FormRegistry` (`INV-022`), `T004` real legal e-signing, and `T010` statutory retention schedules remain gated on human clinical/legal sign-off in [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md) and [RETENTION_AND_DR_POLICY.md](operations/RETENTION_AND_DR_POLICY.md).
- **Not production, not approved EMR, not legally signed clinical records.**

Single source of current status: this file. Detailed dated evidence:
- [2026-11-24 T015/T016 patient merge, break-glass, portal & KPI lineage](sessions/2026-11-24_T015_T016_MERGE_PORTAL_KPI_LINEAGE.md)
- [2026-11-24 T013/T014 clinic operations, hash-chained audit & cursor pagination](sessions/2026-11-24_T013_T014_OPERATIONS_AUDIT_PAGINATION.md)
- [2026-11-24 T011/T012 inventory ledger, FHIR R4 & offline AI safety harness](sessions/2026-11-24_T011_T012_INVENTORY_FHIR_AI.md)
- [2026-11-24 T009/T010 encrypted archive, DR drill & role workspaces](sessions/2026-11-24_T009_T010_ARCHIVE_DR_AND_FRONTEND.md)
- [2026-11-18 T006/T007/T008 lab, finance & paper quarantine](sessions/2026-11-18_T006_T007_T008_LAB_FINANCE_MIGRATION.md)
- [2026-11-18 T004/T005 treatment & signing slice](sessions/2026-11-18_T004_T005_TREATMENT_AND_SIGNING.md)
- [2026-11-18 T001/T002/T003 foundation hardening](sessions/2026-11-18_T001_T002_T003_FOUNDATION_HARDENING.md)
- [2026-11-17 T000 onboarding](sessions/2026-11-17_T000_ONBOARDING.md)
Mandatory opening/closing and Vietnamese report: [AGENT_WORKFLOW](engineering/AGENT_WORKFLOW.md).

## Implemented & demonstrated
- FastAPI localhost API, **66 domain/platform tables** and **163 OpenAPI HTTP operations** (`138` paths), plus zero-dependency static UI (`apps/demo-web/`) and role-based Next.js 15.5.29 workspaces (`apps/clinic-web/`).
- **T001–T005 (`ADR-007`, `ADR-008`):** Synthetic `HS256` token issuer + RBAC/ABAC + revocation + single-use signed URLs; frozen Alembic migrations (`0001_demo`..`0008_patient_merge_portal_and_kpi_lineage`), atomic doctor+chair+device booking & 2-connection race tests; quarantined `FormRegistry` (`INV-022`); `FakeSyntheticSignatureProvider` + immutable `ClinicalDocumentSnapshot` + addenda/`entered_in_error`; multi-dependency DAG with DFS cycle detection, `treatment_coordination_link`, `outbox_event`, atomic reschedule, reassessment loops, and timeline.
- **T006–T008 (`ADR-009`):** Paper quarantine importer (`MigrationBatch`/`MigrationItem`, missing-page block, duplicate-patient queue, `legacy_scan` provenance, rollback); purpose-separated `ConsentRecord`, lab delay alerts, delivery vs verification separation, remake lineage, and minimized `LabPartnerGrant` portal; immutable `EstimateVersion`, append-only `LedgerEntry`, idempotent charges/payments/allocations/refunds, allocation-bounds trigger, and daily `CashierReconciliation`.
- **T009–T010 (`ADR-010`):** Generated OpenAPI TypeScript client (`scripts/generate_openapi_ts.py`), 5 role workspaces (`receptionist`, `dentist`, `treatment_coordinator`, `finance`, `clinic_owner`) with in-memory Bearer tokens, pessimistic `409 Conflict` alerts, fixed `Asia/Ho_Chi_Minh` (`+07:00`) timezone formatting (`R-011`), accessible SVG FDI odontogram (`11–48` & `51–85`, `ODN-004`); per-clinic wrapped DEKs, `DLY1` Encrypt-then-MAC `ArchiveObject` storage, key rotation/revocation, `409` retention/legal-hold deletion block (`DR-08`), signed `BackupManifest`, and isolated DR restore drill (`RestoreDrillRun` + `scripts/run_dr_restore_drill.py`).
- **T011–T012 (`ADR-011`):** Append-only inventory lot & stock movement ledger (`INV-001`..`INV-010`, `INV-023` `reservation != consumption`, FEFO picking, expired/quarantined blocks, DB immutability triggers, and dual-control adjustments `INV-010`); clinic-scoped HL7 FHIR R4 `HTEST` + `Provenance` export/validator (`INT-002`/`INT-003`) and zero-egress draft-only AI span/timeline engine, prompt-injection firewall (`AI-010`), feature kill-switch (`AI-014`), and 8-case offline benchmark harness (`scripts/run_ai_eval_harness.py`).
- **T013–T014 (`ADR-012`):** Clinician shift windows (`SCH-001`), chair/device maintenance downtime blocks + DB trigger (`SCH-015`/`HR-004`), confirmation state separation (`SCH-009`/`CRM-003`), identity-verified check-in + chair sanitation turnover gate (`PAT-009`/`SCH-010`/`HR-002`/`HR-003`), and consent-safe recall/follow-up queue (`CRM-004`/`005`/`010`); per-clinic SHA-256 hash-chained `audit_event` journal + tamper verifier (`SEC-007`) and HMAC-signed clinic-scoped cursor pagination (`PAT-002`, `R-012`).
- **T015–T016 (`ADR-013`):** Reversible dual-confirmed patient merge preserving `source_patient_id` (`PAT-006`), `<=15`-minute read-only emergency break-glass with mandatory independent review (`ORG-011`), and verified-guardian gated `patient_portal` read/reschedule/intake views excluding internal draft notes (`PORT-001`..`007`, `PORT-009`, `TRT-016`); append-only versioned clinic service price catalog + locked `EstimatePriceSnapshot` (`FIN-001`), dual-control discount override workflow without clinical plan edits (`FIN-014`), and attributable owner KPI dictionary & lineage (`RPT-002`, `RPT-004`..`007`, `RPT-011`).

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
| [T011](tasks/T011_INVENTORY_LEDGER.md) | Completed (synthetic append-only inventory lot ledger, FEFO & dual control) | [ADR-011](adr/ADR-011-inventory-ledger-fhir-r4-and-ai-safety-harness.md), `inventory.py`, `test_inventory_ledger.py` |
| [T012](tasks/T012_FHIR_AND_AI_HARNESS.md) | Completed (synthetic FHIR R4 `HTEST` export & zero-egress AI safety/injection harness) | [ADR-011](adr/ADR-011-inventory-ledger-fhir-r4-and-ai-safety-harness.md), `fhir_interop.py`, `ai_harness.py`, `test_fhir_and_ai_harness.py` |
| [T013](tasks/T013_OPERATIONS_CHECKIN_AND_RECALL.md) | Completed (synthetic shifts, downtime, check-in, chair turnover & consent-safe recall) | [ADR-012](adr/ADR-012-clinic-operations-tamper-evident-audit-and-pagination.md), `operations.py`, `test_operations_checkin_recall.py` |
| [T014](tasks/T014_TAMPER_EVIDENT_AUDIT_AND_PAGINATION.md) | Completed (hash-chained tamper-evident audit journal & signed cursor pagination) | [ADR-012](adr/ADR-012-clinic-operations-tamper-evident-audit-and-pagination.md), `audit_chain.py`, `test_audit_chain_and_pagination.py` |
| [T015](tasks/T015_PATIENT_MERGE_BREAKGLASS_AND_PORTAL.md) | Completed (reversible dual-confirmed merge, short-TTL break-glass & scoped patient portal) | [ADR-013](adr/ADR-013-patient-merge-breakglass-portal-and-kpi-lineage.md), `patient_portal.py`, `test_patient_merge_breakglass_portal.py` |
| [T016](tasks/T016_PRICE_CATALOG_AND_KPI_LINEAGE.md) | Completed (versioned price catalog, discount dual-control & attributable KPI lineage) | [ADR-013](adr/ADR-013-patient-merge-breakglass-portal-and-kpi-lineage.md), `governance_analytics.py`, `test_price_catalog_and_kpi_lineage.py` |

Full backlog: [ROADMAP](engineering/ROADMAP.md), [task packets](tasks/), [222-ID catalog](product/FUNCTION_CATALOG.md): **138 partial demo flags (`D`), 84 not implemented (`—`)**; 0 rows are certified production functionality.

## Validation evidence — last verified 2026-11-24
Windows, repository `.venv`, CPython 3.12.14; Node 24.11.1 / npm 11.6.2.

| Check | Observed result |
|---|---|
| `./.venv/Scripts/python.exe -m pytest backend/tests -q` | **69 passed, 1 skipped** (live PG skipped locally without `DENLYRA_TEST_POSTGRES_URL`) |
| `python scripts/verify_audit_chain.py` | Passed; verified per-clinic SHA-256 `prev_hash -> entry_hash` chain |
| `python scripts/run_dr_restore_drill.py` | Passed; isolated restore verified 2 encrypted objects (`v1`+`v2`) + 1 sealed snapshot, `rpo_lag_ms=0` |
| `python scripts/run_ai_eval_harness.py` | Passed; 8/8 cases (`extraction=100%`, `injection_blocked=100%`) |
| `python scripts/generate_openapi_ts.py --check` | Passed; `generated-api.ts` matches 138 FastAPI paths / 163 operations |
| Backend & scripts Ruff / `compileall` / `node --check` | Passed (exit 0) |
| `python scripts/verify_artifact.py` | Passed; 222 unique catalog IDs (138 `D`), 20 mandatory files, disabled safety flags and Markdown links |
| `python scripts/smoke_baseline.py` | Passed; SQLite upgrade `0001_demo` -> `0008_patient_merge_portal_and_kpi_lineage` (66 domain tables; 163 HTTP operations) |
| Alembic `upgrade head --sql` (cwd `backend`) | Passed; offline PostgreSQL SQL generated through `0008_patient_merge_portal_and_kpi_lineage` |
| Next `npm test` / `npm run typecheck` / `npm run build` | Passed on Windows (4/4 contract & a11y tests, Next 15.5.29 / React 19.3.1, 0 npm audit issues) |
| `python scripts/update_manifest.py --check` | Passed |

## Open risk ledger / technical debt
| ID | Severity | Known truth and owner task |
|---|---|---|
| R-001 | High before PHI | T001/T015 synthetic token, RBAC/ABAC, break-glass & portal scoping implemented; live OIDC/MFA & independent security audit required before PHI (`SEC-G1`) |
| R-002 | High | T002/T008 concurrency harnesses & CI `postgres:16` job added; verify remote CI run or local PG server (`T002`/`T008`) |
| R-003 | High before clinical use | T004 canonical snapshot + `FakeSyntheticSignatureProvider` implemented; DB-level append-only roles and real legal signer remain pending (`T004`) |
| R-004 | Critical before clinical use | Quarantined `FormRegistry` (`T003`), synthetic signing (`T004`), and statutory retention (`T010`) gated on named dentist + counsel review (`NEEDS_CLINICAL_REVIEW.md`) |
| R-005 | Mitigated in synthetic foundation | `T010` envelope encryption + DR drill & `T014` hash-chained audit journal implemented; external Cloud KMS/HSM & WORM cloud sink required before real PHI |
| R-006 | Mitigated for FHIR R4 | `T012` FHIR R4 `HTEST` + `Provenance` export/validator implemented; real Orthanc DICOMweb/OHIF server remains pending (`INT-004`) |
| R-007 | High | Consent taxonomy (`T007`) & offline AI firewall (`T012`) built; real payment/messaging/external LLM providers remain disabled until formal legal/vendor approval |
| R-008 | Commercial blocker | Denlyra brand/trademark and software license undecided (`Owner/counsel`) |
| R-009 | Mitigated in Next.js workspaces | `T009` uses in-memory Bearer sessions + loopback `Host`/`Origin` proxy check + Node contract tests; provisioned Playwright live-OIDC browser E2E pending (`SEC-G1`) |
| R-010 | Resolved in Alembic | Frozen explicit DDL chain `0001_demo` -> `0008_patient_merge_portal_and_kpi_lineage` |
| R-011 | Resolved in `clinic-web` | `apps/clinic-web` enforces fixed `Asia/Ho_Chi_Minh` (`+07:00`) via `timezone.ts` |
| R-012 | Resolved | Both generated OpenAPI TS client (`T009`) and signed clinic-scoped cursor pagination (`T014`) implemented and verified |
| R-013 | Low / platform debt | Windows sandbox NTFS junction (`WinError 448`) fixed in `conftest.py`; Starlette/httpx deprecation warning remains |

## Decisions locked so far
- `ADR-001`..`ADR-005`: modular monolith, separate clinical/finance authority, proposed DB-per-clinic, draft-only AI, site-specific release gates
- [ADR-006](adr/ADR-006-denlyra-onboarding.md): Denlyra naming and durable handoff
- [ADR-007](adr/ADR-007-identity-and-authorization.md): Identity, session verification, and deny-by-default RBAC/ABAC foundation
- [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md): Multi-dependency Treatment Journey coordination and Synthetic Signature Envelope
- [ADR-009](adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md): Purpose-separated Consent & Scoped Lab Portal, Idempotent Revenue Ledger, and Legacy Paper Quarantine Importer
- [ADR-010](adr/ADR-010-encrypted-archive-dr-and-role-workspaces.md): Encrypted Record Archive, Isolated DR Restore Drill, and Role-Based React Workspaces
- [ADR-011](adr/ADR-011-inventory-ledger-fhir-r4-and-ai-safety-harness.md): Append-Only Inventory Lot Ledger, Honest FHIR R4 Export, and Offline Draft-Only AI Safety Harness
- [ADR-012](adr/ADR-012-clinic-operations-tamper-evident-audit-and-pagination.md): Clinic Operations Queue/Shift/Recall Governance, Hash-Chained Tamper-Evident Audit Journal, and Signed Cursor Pagination
- [ADR-013](adr/ADR-013-patient-merge-breakglass-portal-and-kpi-lineage.md): Reversible Patient Merge, Short-TTL Break-Glass, Scoped Patient Portal & Attributable KPI Lineage

## Next tasks and human decisions
1. **P0/P1 clinical safety & encounter lifecycle (`EMR-003`, `EMR-009`, `EMR-010`, `EMR-011`, `EMR-018`, `ODN-005`) — `T017` Structured Medical/Allergy Risk Review, Encounter Closure State Machine & Clinician-Authored Procedure Evidence** — prominent tri-state allergy/risk review (`INV-022`), encounter closure gate blocking incomplete reviews/signatures (`EMR-009`/`EMR-018`), and explicit clinician-authored dental diagnosis/performed procedure evidence tied to FDI teeth (`ODN-005`, never inferred from planned tasks or payments).
2. **P1 treatment & operational continuity (`TRT-012`, `TRT-014`, `SCH-008`, `FIN-008`, `HR-008`) — `T018` Clinical Milestone Checklists, Treatment Pause/Terminate Governance, Consent-Safe Waiting List & Protected Quality Incident Queue** — enforce milestone criteria/override justifications, preserve clinical/financial history on treatment pause/termination, manage privacy-safe schedule waiting list & reviewed installment plans (no auto-charge), and track protected quality incidents.
3. **P0 external gates — `T002` & `M0`/`T003`/`T004`/`T010`** — inspect GitHub Actions `postgres-concurrency-tests` receipt (or run `verify_postgres_live.py` on PostgreSQL 16) and obtain dentist/counsel sign-off on [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md) & [RETENTION_AND_DR_POLICY.md](operations/RETENTION_AND_DR_POLICY.md).

## Git and exact continuation
Next session begins with `git status --short --branch`, `git log -2 --oneline`, `AGENTS.md`, this file, and [latest session report](sessions/2026-11-24_T015_T016_MERGE_PORTAL_KPI_LINEAGE.md). Run `./.venv/Scripts/python.exe -m pytest backend/tests -q`, author task packet `docs/tasks/T017_ENCOUNTER_LIFECYCLE_ALLERGY_AND_PROCEDURES.md` and negative tests first before editing domain code.
