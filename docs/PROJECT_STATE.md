# Denlyra durable agent handoff — 2026-11-18

## Current status
Research-grade **synthetic-only demonstrator**, version `0.1.0`.
- `R0` repository onboarding (`T000`), `T001` synthetic authentication + deny-by-default RBAC/ABAC (`ADR-007`), `T005` multi-dependency Treatment Journey + cross-context coordination (`ADR-008`), and `T004` synthetic `SignatureProvider` snapshot/addendum/entered-in-error slice (`ADR-008`) are verified locally.
- `T002` frozen Alembic migration chain (`0001_demo` -> `0002_hardening` -> `0003_treatment_and_signing`), atomic multi-resource booking, `IntegrityError` -> `409` rollback, `idempotency_key`, SQLite overlap trigger, 2-connection barrier test harness, `scripts/verify_postgres_live.py`, and GitHub Actions `postgres-concurrency-tests` job (`postgres:16`) are implemented; inspect the remote GitHub Actions run or execute `verify_postgres_live.py` against a local PostgreSQL 16 instance to close `T002`.
- `T003` quarantined synthetic `FormRegistry` (`INV-022`) and `T004` legal signing remain gated on human clinical/legal approval in [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md).
- **Not production, not approved EMR, not legally signed clinical records.**

Single source of current status: this file. Detailed dated evidence:
- [2026-11-18 T004/T005 treatment & signing slice](sessions/2026-11-18_T004_T005_TREATMENT_AND_SIGNING.md)
- [2026-11-18 T001/T002/T003 foundation hardening](sessions/2026-11-18_T001_T002_T003_FOUNDATION_HARDENING.md)
- [2026-11-17 T000 onboarding](sessions/2026-11-17_T000_ONBOARDING.md)
Mandatory opening/closing and Vietnamese report: [AGENT_WORKFLOW](engineering/AGENT_WORKFLOW.md).

## Implemented & demonstrated
- FastAPI localhost API, **29 domain/platform tables** and **60 OpenAPI HTTP operations**, plus static UI (`apps/demo-web/`) and optional Next.js prototype (`apps/clinic-web/`).
- **T001 Identity & RBAC/ABAC foundation (`ADR-007`):**
  - Local synthetic token issuer (`HS256`), live `Staff` active/role/`token_version` and `revoked_token` (`jti`) checks, deny-by-default RBAC/ABAC across all 60 operations, immediate staff deactivation invalidation, one-time clinic-scoped signed URLs, sensitive clinical read/denial auditing, fail-closed `503` on provider outage, and Next.js proxy header forwarding (`R-009` resolved).
- **T002 Scheduling, Migration Chain & PostgreSQL CI Verifier:**
  - Frozen explicit DDL across `0001_demo` (18 tables) -> `0002_hardening` (23 tables) -> `0003_treatment_and_signing` (29 tables) (`R-010` resolved).
  - Atomic doctor + chair + `equipment_ids` booking, `idempotency_key`, `IntegrityError` -> `409` rollback, atomic reschedule (`SCH-005`), SQLite `BEFORE INSERT` overlap trigger, 2-connection `threading.Barrier(2)` race test, `scripts/verify_postgres_live.py`, and CI `postgres-concurrency-tests`.
- **T003 Quarantined Clinical FormRegistry:**
  - Immutable `(official_code, schema_version)` registration (`NEG-16`), tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validation (`INV-022`), and fail-closed `409` guards on self-approval (`NEG-20`) and official EMR export (`NEEDS_CLINICAL_REVIEW.md`).
- **T004 Synthetic `SignatureProvider` & Canonical Document Snapshots (`ADR-008`):**
  - `FakeSyntheticSignatureProvider` test double (`backend/src/denlyra/signing.py`) + `ClinicalDocumentSnapshot` (`canonical_json`, `canonical_sha256`, `manifest_sha256`).
  - Verified fail-closed behavior on altered digest (`NEG-03`), provider timeout (`NEG-14` -> `503`), signature mismatch (`409`), stale note revision (`409`), deactivated/unauthorized signer (`401`/`403`), and `mode="legal_authenticated"` (`409`). Supports linked `addenda` and `entered_in_error` with mandatory reason preserving original bytes bit-for-bit.
- **T005 Multi-dependency Treatment Journey & Cross-Context Coordination (`ADR-008`):**
  - `plan_task_dependency` multi-edge DAG with DFS cycle rejection (`422`), `owner_role`, `due_at`, clinician reassessment version loops (`plan_reassessment` + `reassessed_from_task_id`, `PLAN-04`).
  - `treatment_coordination_link` + transactional `outbox_event` linking tasks to `appointment`, `lab_case` (`requires_verified_lab` blocking unverified lab cases per `NEG-09`), and `charge`, plus bounded append-only `payment_refund` (`FIN-006`, `OPS-03`) and status-separated timeline (`GET /api/v1/treatment-plans/{id}/timeline`).

## Task / milestone ledger
| ID | Status | Evidence / starting condition |
|---|---|---|
| [T000](tasks/T000_REPOSITORY_ONBOARDING.md) | Completed | [2026-11-17 session](sessions/2026-11-17_T000_ONBOARDING.md) |
| [T001](tasks/T001_HARDEN_IDENTITY.md) | Completed (synthetic foundation) | [ADR-007](adr/ADR-007-identity-and-authorization.md), `test_identity_auth.py`; live OIDC & `SEC-G1` review pending |
| [T002](tasks/T002_POSTGRES_BOOKING.md) | In progress — code, `verify_postgres_live.py`, and CI job complete; awaiting live PG run receipt | Inspect GitHub Actions `postgres-concurrency-tests` or run `verify_postgres_live.py` with `DENLYRA_TEST_POSTGRES_URL` |
| [T003](tasks/T003_FORM_MAPPING.md) | Blocked on human clinical/legal sign-off (safe synthetic `FormRegistry` complete) | [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md), `test_form_registry.py` |
| [T004](tasks/T004_SIGNATURE_DOCUMENTS.md) | Synthetic adapter slice completed; real legal signing blocked on `NEEDS_CLINICAL_REVIEW.md` | [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md), `signing.py`, `test_signature_documents.py` |
| [T005](tasks/T005_TREATMENT_E2E.md) | Completed (synthetic domain/API slice) | [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md), `test_treatment_journey_e2e.py`; clinician template review pending |
| [T006](tasks/T006_PAPER_IMPORT.md) | Pending (synthetic quarantine importer ready to start) | Build batch/page-hash quarantine, duplicate-patient review queue, `legacy_scan` provenance |
| [T007](tasks/T007_LAB_CONSENT.md) | **Next / pending; ready to start** | Implement purpose-separated `ConsentRecord`, scoped lab partner token/portal, due-date delay alerts |
| [T008](tasks/T008_FINANCE_LEDGER.md) | **Next / pending; ready to start** | Implement versioned estimates, idempotent payment/refund ledger, cashier daily reconciliation |
| [T009](tasks/T009_REACT_FRONTEND.md) | Pending; prototype only | Generate typed OpenAPI client and build role-based Next.js workspaces |
| [T010](tasks/T010_BACKUP_RESTORE.md) | Pending; P0 before PHI | Archive/media/signature manifest + isolated restore drill |

Full backlog: [ROADMAP](engineering/ROADMAP.md), [task packets](tasks/), [222-ID catalog](product/FUNCTION_CATALOG.md): **47 partial demo flags (`D`), 175 not implemented (`—`)**; 0 rows are certified production functionality.

## Validation evidence — last verified 2026-11-18
Windows, repository `.venv`, CPython 3.12.14; Node 24.11.1 / npm 11.6.2.

| Check | Observed result |
|---|---|
| `./.venv/Scripts/python.exe -m pytest backend/tests -q` | **43 passed, 1 skipped** (live PG skipped locally without `DENLYRA_TEST_POSTGRES_URL`) |
| Backend & scripts Ruff / `compileall` / `node --check` | Passed (exit 0) |
| `python scripts/verify_artifact.py` | Passed; 222 unique catalog IDs, 20 mandatory files, disabled safety flags and Markdown links |
| `python scripts/smoke_baseline.py` | Passed; SQLite upgrade `0001_demo` -> `0002_hardening` -> `0003_treatment_and_signing` (29 domain tables; 60 HTTP operations) |
| Alembic `upgrade head --sql` (cwd `backend`) | Passed; offline PostgreSQL SQL generated for `0001_demo` -> `0003_treatment_and_signing` |
| Next `npm run typecheck` / `npm run build` | Passed on Windows, Next 15.5.29 / React 19.3.1 |
| `python scripts/update_manifest.py --check` | Passed |

## Open risk ledger / technical debt
| ID | Severity | Known truth and owner task |
|---|---|---|
| R-001 | High before PHI | T001 synthetic token + RBAC/ABAC implemented; live OIDC/MFA & independent security audit required before PHI (`SEC-G1`) |
| R-002 | High | T002 concurrency harness + `verify_postgres_live.py` + CI `postgres:16` job added; verify remote CI run or local PG server (`T002`/`T008`) |
| R-003 | High before clinical use | T004 canonical snapshot + `FakeSyntheticSignatureProvider` implemented; DB-level append-only roles and real legal signer remain pending (`T004`/`T010`) |
| R-004 | Critical before clinical use | Quarantined `FormRegistry` (`T003`) & synthetic signing (`T004`) gated on named dentist + counsel review (`NEEDS_CLINICAL_REVIEW.md`) |
| R-005 | Critical before PHI | No encrypted archive, backup/key recovery, restore or incident implementation (`T010`) |
| R-006 | High | No real FHIR/DICOM, paper quarantine importer, or attachment identity validation (`T006`/interop) |
| R-007 | High | No consent/provider authorization for real payment, communications or clinical AI (`T007`, remain disabled) |
| R-008 | Commercial blocker | Denlyra brand/trademark and software license undecided (`Owner/counsel`) |
| R-009 | Mitigated in local proxy | Next proxy forwards `Authorization`, `Origin`, `Sec-Fetch-Site`; full browser/E2E auth tests remain in `T009` |
| R-010 | Resolved in Alembic | Frozen explicit DDL chain `0001_demo` -> `0002_hardening` -> `0003_treatment_and_signing` |
| R-011 | Medium | DB timestamps naive UTC, API appends Z; static calendar uses browser timezone rather than fixed clinic timezone (`T009`) |
| R-012 | Medium | Missing pagination, generated TS client, estimate versions, and cashier reconciliation (`T008`/`T009`) |
| R-013 | Low / platform debt | Cross-agent pytest temp/cache fixed; Starlette/httpx deprecation warning remains |

## Decisions locked so far
- `ADR-001`..`ADR-005`: modular monolith, separate clinical/finance authority, proposed DB-per-clinic, draft-only AI, site-specific release gates
- [ADR-006](adr/ADR-006-denlyra-onboarding.md): Denlyra naming and durable handoff
- [ADR-007](adr/ADR-007-identity-and-authorization.md): Identity, session verification, and deny-by-default RBAC/ABAC foundation
- [ADR-008](adr/ADR-008-treatment-journey-and-signature-envelope.md): Multi-dependency Treatment Journey coordination and Synthetic Signature Envelope

## Next tasks and human decisions
1. **P1 `T007` (`docs/tasks/T007_LAB_CONSENT.md`)** — purpose-separated `ConsentRecord` (`treatment`, `data_processing`, `marketing`, `financial`), approved lab requisition specs, due-date delay alerts, and case-scoped revocable lab partner access.
2. **P1 `T008` (`docs/tasks/T008_FINANCE_LEDGER.md`)** — versioned treatment estimates, idempotent payment/allocation/refund ledger, daily cashier reconciliation, and billed/collected/refunded/planned reporting.
3. **P1 `T006` (`docs/tasks/T006_PAPER_IMPORT.md` synthetic quarantine slice)** — batch/page-hash ingestion quarantine, missing-page block (`DR-01`), duplicate-patient review queue (`PAT-005`), and `legacy_scan` provenance preservation (`DR-03`).

## Git and exact continuation
Next session begins with `git status --short --branch`, `git log -2 --oneline`, `AGENTS.md`, this file, [latest session report](sessions/2026-11-18_T004_T005_TREATMENT_AND_SIGNING.md), and `docs/tasks/T007_LAB_CONSENT.md`. Then run `./.venv/Scripts/python.exe -m pytest backend/tests -q` and write negative tests first before edits.
