# Current deliverable versus future target — no marketing confusion

## Executed in starter
- Synthetic demo UI: overview, clinics, patients, appointments, encounter draft, note version/demolock, plan/task version, FDI tooth-code event reference, lab status, finance charges/payment, audit event.
- Python backend FastAPI+SQLAlchemy (50 tables, 115 OpenAPI operations). Demo SQLite automatically bootstrapped; clinic scoping on API reads; basic Host/Origin protections.
- T001 synthetic token issuer (`HS256`), deny-by-default RBAC/ABAC policy engine, staff deactivation token invalidation, JTI revocation, one-time clinic-scoped signed URLs, and sensitive clinical read/denial audit trail (`ADR-007`).
- T002 explicit frozen Alembic migration chain (`0001_demo` -> `0002_hardening` -> `0003_treatment_and_signing` -> `0004_lab_consent_finance_and_migration`), atomic multi-resource (doctor + chair + equipment) booking, `IntegrityError` -> `409` rollback, idempotency keys, SQLite overlap trigger, 2-connection barrier concurrency test harness, `scripts/verify_postgres_live.py`, and CI `postgres-concurrency-tests` job. Local live PostgreSQL server execution remains unverified on hosts without Docker/PostgreSQL.
- T003 quarantined synthetic `FormRegistry` with immutable `(official_code, schema_version)`, tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validation (`INV-022`), and fail-closed `409` blocks on self-approval and official EMR export (`docs/clinical/NEEDS_CLINICAL_REVIEW.md`).
- T004 synthetic `SignatureProvider` + `FakeSyntheticSignatureProvider` test double, canonical `ClinicalDocumentSnapshot` envelope (`canonical_sha256` + `manifest_sha256`), linked addenda, and `entered_in_error` preserving original bytes bit-for-bit (`ADR-008`); legal `authenticated` signing remains blocked (`409`).
- T005 multi-dependency treatment DAG with DFS cycle detection, cross-context coordination links (`appointment`, `lab_case` with `requires_verified_lab`, `charge`), transactional `outbox_event`, atomic appointment reschedule (`SCH-005`), bounded append-only payment refunds (`FIN-006`), clinician reassessment loops (`PLAN-04`), and status-separated timeline (`ADR-008`).
- T006 synthetic legacy paper quarantine importer (`MigrationBatch`, `MigrationItem`), page completeness blocks (`NEG-10`, `DR-01`), duplicate patient candidate queue (`PAT-005`, `DR-02`), `legacy_scan` provenance enforcement (`DR-03`), batch reconciliation, and batch rollback (`ADR-009`).
- T007 purpose-separated `ConsentRecord` (`treatment`, `data_processing`, `marketing`, `financial`) with guardian authority check and isolated marketing withdrawal (`SEC-07`), lab delay alerts (`SCH-013`), delivery vs verification separation (`LAB-006`/`LAB-009`), remake lineage, and minimized-data scoped `LabPartnerGrant` portal (`ADR-009`).
- T008 versioned `EstimateVersion` (`FIN-002`), append-only `LedgerEntry` journal, `idempotency_key` deduplication across charges/payments/allocations/refunds (`NEG-08`, `NEG-17`), DB allocation bounds trigger + concurrent barrier test, and daily `CashierReconciliation` (`FIN-010`, `ADR-009`).
- T009 generated OpenAPI TypeScript client (`scripts/generate_openapi_ts.py` -> `apps/clinic-web/src/lib/generated-api.ts`, `INT-001`), 5 role-based Next.js 15.5.29 workspaces (`receptionist`, `dentist`, `treatment_coordinator`, `finance`, `clinic_owner`) using in-memory `HS256` Bearer sessions, pessimistic `409` conflict handling, fixed `Asia/Ho_Chi_Minh` timezone formatting (`R-011`), keyboard/touch accessible SVG FDI odontogram (`ODN-004`), and Node 24 contract/accessibility tests (`ADR-010`).
- T010 per-clinic envelope encryption (`TenantEncryptionKey` wrapped DEK + `DLY1` Encrypt-then-MAC `ArchiveObject`), key rotation (`v1` -> `v2` `retired_decrypt_only`) and revocation, retention/legal-hold deletion block (`409`, `DR-08`), signed cross-store `BackupManifest`, and automated isolated DR restore drill (`RestoreDrillRun` + `scripts/run_dr_restore_drill.py`) measuring `RTO`/`RPO` (`ADR-010`).
- T011 append-only inventory lot & stock movement ledger (`InventorySupplier`, `InventorySku`, `PurchaseOrder`, `InventoryLot`, `StockMovement`, `StockReservation`, `StockAdjustmentRequest`), DB `no_update`/`no_delete`/bounds triggers, reservation != consumption (`INV-023`), FEFO picking, expired/quarantined lot blocks, and dual-control adjustment approval (`INV-010`, `ADR-011`).
- T012 clinic-scoped HL7 FHIR R4 `Bundle` exporter & validator (`HTEST` tag + honest `Provenance`, `INT-002`/`INT-003`) and zero-egress draft-only AI span/timeline engine, prompt-injection/exfiltration firewall (`AI-010`), feature kill-switch (`AI-014`), and 8-case offline benchmark harness (`run_ai_eval_harness.py`, `ADR-011`).
- Negative automated tests (59 passed, 1 skipped live-Postgres check in backend; 4 passed in `apps/clinic-web`), legal and domain reference docs, 222-ID feature catalog (103 partial demo flags).

## Designed only — not implemented
- Real OIDC/MFA login, multi-clinic production user identities, production clinic database routing, external Cloud KMS/HSM key custody.
- EMR 16/BV-01 compliance, clinical decision recording, legally valid e-signature and certified clinic archive.
- Official e-invoicing (`FIN-009`), real payment webhooks (`INT-008`), Zalo OA/SMS/email provider adapters (`CRM-006`..`CRM-008`), patient portal (`PORT-*`).
- Real Orthanc DICOM/OHIF server (`INT-004`), government health exchange (`INT-010`), external speech/LLM model providers (`AI-001`).
- Provisioned Playwright multi-browser E2E against live OIDC/MFA (`SEC-G1`).

## Known limitations and technical debt
Demo authorization is header spoofable; no encryption; audit not tamper-resistant; SQLite scheduling and finance are not concurrency-safe; no schema version upgrades tested; no rate-limiting or robust CSP testing; no production security monitoring; no real QA with a licensed dentist. Keep demo restricted to localhost and fake records.

## Verification records
Run and record exact command output, date, commit and environment in `docs/PROJECT_STATE.md`. Never claim compliance based on a passing unit test. See `TEST_STRATEGY.md`.
