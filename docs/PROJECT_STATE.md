# Denlyra durable agent handoff — 2026-11-18

## Current status
Research-grade **synthetic-only demonstrator**, version `0.1.0`.
- `R0` repository onboarding (`T000`) and `T001` synthetic authentication + deny-by-default RBAC/ABAC foundation (`ADR-007`) are verified.
- `T002` frozen Alembic migration chain (`0001_demo` -> `0002_hardening`), atomic multi-resource booking, `IntegrityError` -> `409` rollback, `idempotency_key`, SQLite overlap trigger, and 2-connection barrier concurrency test harness are implemented; final PostgreSQL exclusion verification awaits a live PostgreSQL instance (`DENLYRA_TEST_POSTGRES_URL`).
- `T003` quarantined synthetic `FormRegistry` and tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validation (`INV-022`) are implemented, with clinical activation blocked pending human review in [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md).
- **Not production, not approved EMR, not legally signed clinical records.**

Single source of current status: this file. Detailed dated evidence:
- [2026-11-18 T001/T002/T003 foundation hardening](sessions/2026-11-18_T001_T002_T003_FOUNDATION_HARDENING.md)
- [2026-11-17 T000 onboarding](sessions/2026-11-17_T000_ONBOARDING.md)
Mandatory opening/closing and Vietnamese report: [AGENT_WORKFLOW](engineering/AGENT_WORKFLOW.md).

## Implemented & demonstrated
- FastAPI localhost API, **23 domain/platform tables** and **48 OpenAPI HTTP operations**, plus static UI (`apps/demo-web/`) and optional Next.js prototype (`apps/clinic-web/`).
- **T001 Identity & RBAC/ABAC foundation (`ADR-007`):**
  - Local synthetic token issuer (`POST /api/v1/auth/token`, `HS256`) and server-side verification against live `Staff` membership (`active`, `role`, `clinic_id`, `branch_id`, `token_version`) and `revoked_token` (`jti`).
  - Deny-by-default RBAC/ABAC across all endpoints: receptionists cannot create encounters, lock clinical notes, review treatment plans, or allocate payments; finance staff are denied confidential clinical reads (`encounters`, `notes`, `findings`, `odontogram`); dentists cannot post financial allocations.
  - Immediate token invalidation upon staff deactivation (`POST /api/v1/staff/{id}/deactivate`) or session revocation (`POST /api/v1/auth/revoke`), preserving historical authored encounters.
  - Single-use clinic-scoped signed URL grants (`POST /api/v1/auth/signed-urls` -> `GET /api/v1/signed-download/{token}`) rejecting cross-clinic access, expiry, and reuse.
  - Fail-closed `503` when `DENLYRA_AUTH_PROVIDER_AVAILABLE=0`. Next.js proxy forwards `Authorization`, `Origin`, and `Sec-Fetch-Site` headers (`R-009` resolved).
- **T002 Scheduling & Migration Hardening:**
  - Frozen explicit DDL in `0001_demo_schema.py` (18 tables) + `0002_hardening.py` (5 new tables + columns + `schema_migration_meta`), tested from both empty DB and populated `0001_demo` fixture DB (`R-010` resolved).
  - Atomic booking of clinician + chair + optional `equipment_ids` (`kind="device"`), `idempotency_key` deduplication, `IntegrityError` -> `db.rollback()` -> `409 Conflict`, SQLite `BEFORE INSERT` overlap trigger, and 2-connection `threading.Barrier(2)` race test.
- **T003 Quarantined Clinical FormRegistry:**
  - Immutable `(official_code, schema_version)` registration in `quarantined_synthetic_draft` status (`NEG-16`), tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validation enforcing `INV-022`, and fail-closed `409` guards on template approval (`NEG-20`) and official EMR export (`docs/clinical/NEEDS_CLINICAL_REVIEW.md`).
- **Cross-agent pytest isolation:** `backend/tests/conftest.py` and `backend/pyproject.toml` isolate temporary directories inside `local_data/` and disable `.pytest_cache` contention across Windows agent sandboxes.

## Current truth vs future targets
| Category | Actual state | Target / next evidence |
|---|---|---|
| Identity | T001 synthetic token + RBAC/ABAC + revocation + signed URLs implemented | Live OIDC/MFA deployment and independent security review (`SEC-G1`) |
| Tenancy | Clinic-scoped FKs + verified token `clinic_id` check | ADR-003 proposed DB-per-clinic routing; not implemented |
| Scheduling | Atomic doctor+chair+device booking, `IntegrityError`->409, SQLite trigger + 2-connection race test | Run `test_live_postgresql_exclusion_constraint_and_race` on live PostgreSQL 16 (`T002`) |
| Forms & Notes | Quarantined `FormRegistry` (`INV-022`) + demo note revision/hash/addendum | Named dentist + legal counsel review (`NEEDS_CLINICAL_REVIEW.md`) + `T004` signature adapter |
| Treatment | Single-dependency tasks and version cloning | `T005` multi-dependency DAG, reassessment loops, cross-context contracts |
| Finance | Demo positive integer amounts/allocations | `T008` immutable ledger, idempotency/refunds and PostgreSQL row-lock concurrency |
| Frontend | Static default + buildable Next prototype (proxy headers fixed) | `T009` generated client, authorized role workspaces, browser/accessibility tests |
| DR / deployment | No backups or production infrastructure | `T010` archive/key restore and approved isolated deployment |

## Task / milestone ledger
| ID | Status | Evidence / starting condition |
|---|---|---|
| [T000](tasks/T000_REPOSITORY_ONBOARDING.md) | Completed | [2026-11-17 session](sessions/2026-11-17_T000_ONBOARDING.md); commits `d8d7c44` / `5437f43` |
| [T001](tasks/T001_HARDEN_IDENTITY.md) | Completed (synthetic foundation) | [ADR-007](adr/ADR-007-identity-and-authorization.md), `backend/src/denlyra/auth.py`, `backend/tests/test_identity_auth.py`; live OIDC & independent security review pending |
| [T002](tasks/T002_POSTGRES_BOOKING.md) | In progress — code & race harness complete; blocked on live PostgreSQL server | Explicit migrations `0001_demo`->`0002_hardening`, atomic equipment/idempotency/rollback, `test_scheduling_concurrency.py`; needs `DENLYRA_TEST_POSTGRES_URL` live run |
| [T003](tasks/T003_FORM_MAPPING.md) | Blocked on human clinical/legal sign-off (safe synthetic interface complete) | [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md), `FormRegistry` & `test_form_registry.py` implemented |
| [T004](tasks/T004_SIGNATURE_DOCUMENTS.md) | Blocked for real legal signing; ready for synthetic `SignatureProvider` double | Needs `SignatureProvider` fake double + negative tests (`NEG-03`, `NEG-14`) |
| [T005](tasks/T005_TREATMENT_E2E.md) | **Next / pending; ready to start** | `T001` complete; implement multi-dependency DAG, cycle check, reassessment events |
| [T006](tasks/T006_PAPER_IMPORT.md) | Pending | Depends on `T001`/`T003` + encrypted archive |
| [T007](tasks/T007_LAB_CONSENT.md) | Pending | Depends on `T001`/`T004` + consent/requisition contracts |
| [T008](tasks/T008_FINANCE_LEDGER.md) | Pending | Depends on `T001` + clinic billing policy |
| [T009](tasks/T009_REACT_FRONTEND.md) | Pending; prototype only | Depends on `T001` + stabilized OpenAPI |
| [T010](tasks/T010_BACKUP_RESTORE.md) | Pending; P0 before PHI | Depends on `T001`/`T004` + key/archive/retention design |

Full backlog: [ROADMAP](engineering/ROADMAP.md), [task packets](tasks/), [222-ID catalog](product/FUNCTION_CATALOG.md): **33 partial demo flags (`D`), 189 not implemented (`—`)**; 0 rows are certified production functionality.

## Validation evidence — last verified 2026-11-18
Windows, repository `.venv`, CPython 3.12.14; Node 24.11.1 / npm 11.6.2.

| Check | Observed result |
|---|---|
| `./.venv/Scripts/python.exe -m pytest backend/tests -q` | **40 passed, 1 skipped** (live PG skipped without `DENLYRA_TEST_POSTGRES_URL`); 1 Starlette/httpx deprecation warning |
| Backend & scripts Ruff / `compileall` / `node --check` | Passed (exit 0) |
| `python scripts/verify_artifact.py` | Passed; 222 unique catalog IDs, 20 mandatory files, disabled safety flags and Markdown links |
| `python scripts/smoke_baseline.py` | Passed; SQLite upgrade `0001_demo` -> `0002_hardening` (23 domain tables); CLI opt-in refusal and loopback HTTP startup (48 operations) |
| Alembic `upgrade head --sql` (cwd `backend`) | Passed; offline PostgreSQL SQL generated for `0001_demo` -> `0002_hardening` with `EXCLUDE USING gist` |
| Next `npm run typecheck` / `npm run build` | Passed on Windows, Next 15.5.29 / React 19.3.1 |
| `python scripts/update_manifest.py --check` | Passed |

## Open risk ledger / technical debt
| ID | Severity | Known truth and owner task |
|---|---|---|
| R-001 | High before PHI | T001 synthetic token + RBAC/ABAC + revocation implemented; live OIDC/MFA & independent security audit still required before PHI (`SEC-G1`) |
| R-002 | High | T002 atomic multi-resource booking, `IntegrityError`->409, and 2-connection race test pass on SQLite trigger; live PostgreSQL server verification still required (`T002`/`T008`) |
| R-003 | Critical before clinical use | Demo locks/audit mutable by DB actor; `SignatureProvider` fake double and DB append-only rules pending (`T004`/`T005`) |
| R-004 | Critical before clinical use | Quarantined `FormRegistry` implemented (`T003`); official form mapping and signature rules blocked on human sign-off (`docs/clinical/NEEDS_CLINICAL_REVIEW.md`) |
| R-005 | Critical before PHI | No encrypted archive, backup/key recovery, restore or incident implementation (`T010`) |
| R-006 | High | No real FHIR/DICOM, source migration or attachment identity validation (`T006`/interop) |
| R-007 | High | No consent/provider authorization for real payment, communications or clinical AI. Remain disabled |
| R-008 | Commercial blocker | Denlyra brand/trademark and software license undecided (`Owner/counsel`) |
| R-009 | Mitigated in local proxy | Next proxy now forwards `Authorization`, `Origin`, and `Sec-Fetch-Site`; full browser/E2E auth tests remain in `T009` |
| R-010 | Resolved in Alembic | `0001_demo` now uses frozen explicit DDL and `0002_hardening` upgrades cleanly with `schema_migration_meta`; live PostgreSQL rehearsal remains in `T002` |
| R-011 | Medium | DB timestamps are naive UTC, API appends Z; static calendar uses browser timezone rather than fixed clinic timezone (`T002`/`T009`) |
| R-012 | Medium | Missing pagination, generated DTO/client, outbox, and stricter money ledger reversals (`T005`/`T008`/`T009`) |
| R-013 | Low / platform debt | Cross-agent pytest temp/cache collision fixed in `conftest.py`/`pyproject.toml`; Starlette/httpx deprecation warning remains |

## Decisions locked so far
- `ADR-001`: synthetic modular-monolith direction
- `ADR-002`: separate clinical/finance authority and immutable-document principle
- `ADR-003`: **proposed** DB-per-clinic target
- `ADR-004`: draft-only optional AI
- `ADR-005`: site-specific release gates
- [ADR-006](adr/ADR-006-denlyra-onboarding.md): Denlyra naming and durable handoff
- [ADR-007](adr/ADR-007-identity-and-authorization.md): Identity, session verification, and deny-by-default RBAC/ABAC foundation

## Next tasks and human decisions
1. **P0 `T005` (`docs/tasks/T005_TREATMENT_E2E.md`)** — implement multi-dependency task DAG with cycle detection, stage transitions/reassessment events creating new task instances, and cross-context schedule/lab/finance contracts.
2. **P0 `T004` (`docs/tasks/T004_SIGNATURE_DOCUMENTS.md` synthetic slice)** — implement `SignatureProvider` interface with fake test double, canonical snapshot envelope, and negative tests (`NEG-03`, `NEG-14`) while keeping legal signing gated on `NEEDS_CLINICAL_REVIEW.md`.
3. **P0 `T002` live PostgreSQL verification & `M0`/`T003` human clinical review** — run `test_scheduling_concurrency.py` against a live PostgreSQL 16 instance when Docker/PostgreSQL is available, and obtain dentist/counsel sign-off for [NEEDS_CLINICAL_REVIEW.md](clinical/NEEDS_CLINICAL_REVIEW.md).

## Git and exact continuation
Next session begins with `git status --short --branch`, `git log -2 --oneline`, `AGENTS.md`, this file, [2026-11-18 session report](sessions/2026-11-18_T001_T002_T003_FOUNDATION_HARDENING.md), and `docs/tasks/T005_TREATMENT_E2E.md` (or `T004_SIGNATURE_DOCUMENTS.md`). Then run `./.venv/Scripts/python.exe -m pytest backend/tests -q` and scope negative tests before edits.
