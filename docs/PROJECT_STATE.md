# Denlyra durable agent handoff — 2026-11-17

## Current status
Research-grade **synthetic-only demonstrator**, version `0.1.0`. R0 repository onboarding
and local baseline are verified; M0 partner discovery and M1 secure core are pending.
**Not production, not approved EMR, not legally signed clinical records.**

Single source of current status: this file. Detailed dated evidence:
[2026-11-17 T000 onboarding](sessions/2026-11-17_T000_ONBOARDING.md).
Mandatory opening/closing and Vietnamese report:
[AGENT_WORKFLOW](engineering/AGENT_WORKFLOW.md).

## Implemented & demonstrated
- FastAPI localhost API, 18 domain tables and 36 OpenAPI HTTP operations, plus static UI
  with fictional Clinic A/B selectors. Prototype code is still centralized in api/services/models,
  not yet separated into all target bounded-context modules.
- Patient UUID identity; shared fake phone does not merge patients; clinic-scoped references.
- Sequential appointment conflict checks for clinician/chair and cancellation history.
- FDI code/surface validation and append-only demo finding history.
- Draft note revisions, stale-revision rejection, `demo_locked` hash and linked addenda.
  This is service-level demo behavior, not DB-enforced immutable legal records.
- Draft/demo-reviewed plan versions; one optional prerequisite per task; cloned versions
  preserve old rows and reset new progress. No approved clinical plan or performed procedures.
- Lab state transitions and separate fictional charge/payment/allocation records.
- Explicit demo startup opt-in, launcher loopback validation, basic Host/Origin checks.
- Optional Next.js patients/plans prototype builds and typechecks; full role frontend pending.
- T000 renamed package/config/UI/docs to Denlyra, repaired Windows UTF-8 artifact checking
  and backend lint, aligned Alembic sample URL with Compose, added baseline constraints,
  npm lockfile/PostCSS patch, repeatable smoke/manifest tools and expanded CI definitions.

## Current truth vs future targets
| Category | Actual state | Target / next evidence |
|---|---|---|
| Identity | No authentication; `X-Demo-*` forgeable | T001 verified identity, deny-by-default roles/clinic membership |
| Tenancy | Shared demo DB and selected-clinic filters | ADR-003 proposed DB-per-clinic routing; not implemented or finally approved |
| Scheduling | SQLite sequential checks | T002 live PostgreSQL exclusion, concurrent transactions and 409 mapping |
| Notes | Demo revision/hash/addendum | T003/T004 reviewed forms, signer evidence, immutable archive |
| Treatment | Single-dependency administrative tasks | T005 multi-dependency journey, ownership, schedule/lab/consent contracts |
| Finance | Demo positive integer amounts/allocations | T008 immutable ledger, idempotency/refunds and concurrency |
| Frontend | Static default + small buildable Next prototype | T009 generated client, authorized role workspaces, browser/accessibility tests |
| Files / interop | No uploads, imaging, FHIR/DICOM | Reviewed encrypted archive and partner adapters |
| AI / external effects | No AI, messaging or real payment provider | Independent privacy/clinical/legal/provider gates |
| DR / deployment | No backups or production infrastructure | T010 archive/key restore and approved isolated deployment |

## Task / milestone ledger
| ID | Status | Evidence / starting condition |
|---|---|---|
| [T000](tasks/T000_REPOSITORY_ONBOARDING.md) | Completed — local baseline and handoff | Linked session; initial baseline commit `d8d7c44` pushed and remote SHA verified; latest documentation receipt via Git |
| [T001](tasks/T001_HARDEN_IDENTITY.md) | **Next / pending; not started** | Read packet, define identity ADR and permission matrix; negative tests before auth changes |
| [T002](tasks/T002_POSTGRES_BOOKING.md) | Pending | Isolated synthetic PostgreSQL server/driver; reviewed migration and race harness |
| T003 / T004 | Blocked for clinical implementation | Named dentist + counsel, official source/form/signer review; synthetic interfaces only |
| T005 | Pending | T001 and agreed clinical content contracts |
| T006 | Pending | T001/T003 + encrypted archive |
| T007 | Pending | T001/T004 + consent/requisition contracts |
| T008 | Pending | T001 + clinic billing policy |
| T009 | Pending; prototype only | T001 + stable OpenAPI; existing build is not acceptance |
| T010 | Pending; P0 before PHI | T001/T004 + key/archive/retention design |

No feature task is in progress after T000. No M0/M1 exit gate has passed. Full backlog:
[ROADMAP](engineering/ROADMAP.md), [task packets](tasks/),
[222-ID catalog](product/FUNCTION_CATALOG.md): **23 partial demo flags, 199 not implemented**;
no row is certified production functionality. The generator owns catalog status.

## Validation evidence — last verified 2026-11-17
Windows, repository `.venv`, CPython 3.12.14; Node 24.11.1 / npm 11.6.2.
Versions captured in `backend/constraints-baseline.txt` and frontend package-lock.json.
Exact commands/cwd and output are in the linked session report.

| Check | Observed result |
|---|---|
| `python -m pytest backend/tests -q` | 26 passed; 1 Starlette/httpx deprecation warning |
| Backend Ruff / compileall; static JS `node --check` | Passed |
| UTF-8 artifact guard | Passed; 222 unique catalog IDs, 20 mandatory files, disabled flags and Markdown links |
| `python scripts/smoke_baseline.py` | Passed; SQLite fresh upgrade to 0001_demo/18 tables; CLI opt-in refusal and real loopback HTTP startup; process stopped/temp DBs removed |
| Alembic `upgrade head --sql` (cwd backend) | PostgreSQL offline SQL generated with EXCLUDE; **not run on PostgreSQL** |
| Next `npm run typecheck` / `npm run build` | Passed on Windows, Next 15.5.29 / React 19.3.1 |
| `npm audit --audit-level=moderate` after PostCSS override | 0 reported vulnerabilities at check time; not a full security assurance |
| `python -m pip check` | Passed; Python vulnerability/license audit not run |
| Catalog regeneration / source manifest / diff review | See session evidence; manifest is refreshed before each commit |

CI definitions cover Windows/Ubuntu backend and Linux Next build/audit. A local pass or
workflow definition is not evidence of a remote CI pass; inspect actual runs after push.
No Docker/psql command was available. Live PostgreSQL/concurrency, existing-schema upgrade,
rollback/restore, browser E2E/accessibility, load, penetration/security and clinical/legal
acceptance are **not verified**.

## Open risk ledger / technical debt
| ID | Severity | Known truth and owner task |
|---|---|---|
| R-001 | Critical before PHI | No real auth, roles or revocation; selectors forgeable. T001 |
| R-002 | High | SQLite scheduling/finance races; PostgreSQL constraint/error mapping and concurrency untested. T002/T008 |
| R-003 | Critical before clinical use | Demo locks/audit mutable by DB actor; note lock-vs-update and plan version races lack transaction proof. T004/T005 |
| R-004 | Critical before clinical use | Official form mapping, signatures and clinic scope not human-approved. T003/T004/M0 |
| R-005 | Critical before PHI | No encrypted archive, backup/key recovery, restore or incident implementation. T010 |
| R-006 | High | No real FHIR/DICOM, source migration or attachment identity validation. T006/interop |
| R-007 | High | No consent/provider authorization for real payment, communications or clinical AI. Remain disabled |
| R-008 | Commercial blocker | Denlyra brand/trademark and software license undecided; rename is not clearance. Owner/counsel |
| R-009 | High before exposure | Next proxy drops browser Origin/Fetch-Metadata when forwarding; backend guards do not cover proxy input. Source-inspection finding; no exploit/browser test performed. T001/T009 |
| R-010 | Medium | Alembic 0001 imports mutable ORM metadata; no stable historical DDL/upgrade chain or safe destructive downgrade. T002 |
| R-011 | Medium | DB timestamps are naive UTC, API appends Z; static calendar uses browser timezone rather than fixed clinic timezone. T002/T009 |
| R-012 | Medium | Missing pagination, generated DTO/client, idempotency/outbox/read-access audit, stricter money input validation and DB-enforced append-only rules. Scope by owning task |
| R-013 | Low / platform debt | Starlette/httpx test-client deprecation; baseline constraints are a Windows capture, not a complete cross-platform dependency lock. Track in T001/T009/CI |

Source inspection is not an independent security audit. Existing regulatory references
and dates were inventoried, **not legally revalidated** in T000. No clinic approvals,
retention periods, legal signature methods, compliance claims or commercial claims were added.

## Decisions locked so far
ADR-001: synthetic modular-monolith direction; ADR-002: separate clinical/finance authority
and immutable-document principle (pending clinical/legal detail); ADR-003: **proposed**
DB-per-clinic target; ADR-004: draft-only optional AI; ADR-005: site-specific release gates;
[ADR-006](adr/ADR-006-denlyra-onboarding.md): Denlyra naming and durable handoff.
Archived research is context; active ADRs/domain invariant IDs/roadmap govern current work.
No schema/table/revision ID changed in T000; sample config names and Python imports changed.

## Next tasks and human decisions
1. **P0 T001** — start with identity provider options, local synthetic issuer/session contract,
   role/object permission matrix and failing negative tests. Keep clinical routes disabled
   unless permission coverage is demonstrated. Independent production auth review still required.
2. **P0 T002** — prepare isolated PostgreSQL, stable migration/error handling and two-connection
   booking tests (chair and clinician, adjacent slots, cancellation, rollback). Needs a test server.
3. **P0 M0 / T003 discovery** — owner identifies dentist/counsel and supplies approved structural
   form/license/signature requirements outside this synthetic repo; no PHI. Human work can
   proceed independently; no automatic multi-agent delegation or clinic communication.

Owner decisions: commercial license/brand; identity hosting/vendor requirements; PostgreSQL
integration environment; named dental/legal/security reviewers and clinic-specific forms.
No human confirmation is needed to resume authorized synthetic T001 preparation.

## Git and exact continuation
Initial branch `main`, no prior commits or tracked files; origin
`https://github.com/quangkhai5122/Denlyra.git` had no advertised refs at onboarding.
The owner authorized initial commit and normal push. No deployment is authorized.
Initial baseline commit **`d8d7c449f0c51c80162680beb7a38f4e43c17094`**, subject
`chore: establish Denlyra synthetic baseline [T000]`, was pushed successfully with
`git push -u origin main`; local/remote main SHA matched and worktree was clean.
This later documentation receipt records that observed outcome; it is committed separately.
Remote CI results have not been inspected. Current HEAD/push state remain authoritative in Git:
`git log -1 --format=fuller`, `git status --short --branch`,
`git ls-remote origin refs/heads/main`. Compare local/remote SHA for the latest receipt.

Next session begins with those commands and AGENTS/this file/latest report/T001/relevant
ADRs. Then run `.venv/Scripts/python.exe -m pytest backend/tests -q` on Windows and
scope T001 acceptance before edits. No running server is required; smoke checks stop
all child processes. Runtime/install caches, local databases and `.env.local` stay ignored.
