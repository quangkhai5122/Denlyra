# Denlyra Foundation · AI-Agent-Ready Starter Repository

> **PROJECT CODENAME:** Denlyra is the repository and development name. Commercial brand/trademark clearance remains pending. No affiliation with third-party dental software vendors is implied.
>
> **MEDICAL SAFETY:** Synthetic demo ONLY. This is NOT a certified electronic medical record (EMR), not healthcare-ready, not legally signed clinical documentation, not production secure, and not authorized for real patient data, prescriptions, diagnosis, or clinical decision-making.

**Verified 2026-11-17** · Vietnamese dentistry market · modular monolith target · Python FastAPI/SQLAlchemy/PostgreSQL · static HTML/CSS/JS demo · optional Next.js prototype (typecheck/build verified; role workspaces pending).

## What you receive
- A functioning **localhost-only** demonstrator (`apps/demo-web/` + `backend/`), with clinics, synthetic patients, resource-checked appointments, draft notes & immutable demo-lock, FDI reference odontogram, versioned treatment tasks, laboratory state machine, and toy receivables/payment allocations.
- Source-specified domain invariants and negative tests. The demo is designed to fail closed for clinical signatures, real payment, medical advice, AI sending PHI, and public exposure.
- Target PostgreSQL schema and demonstration Alembic migration, including **PostgreSQL exclusion constraint** for atomic resource booking overlap prevention. PostgreSQL integration/concurrency is NOT tested in this authoring environment.
- Comprehensive functional catalog, PRD, UI/UX specifications, clinical/legal forms worksheet, FHIR/DICOM strategy, AI experiments, architecture ADRs, deployment and security, QA gates, AI Agent instructions, tasks, handoff state, partner-clinic interview forms.
- Previous Architecture Foundation research from the earlier study under `archive/foundation/` and an updated clinic discovery checklist.

## Start immediately (Windows PowerShell)
From the repository root:
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -c backend/constraints-baseline.txt -e ".\backend[dev]"
$env:DENLYRA_DEMO_MODE = "1"
$env:DENLYRA_DATABASE_URL = "sqlite+pysqlite:///./local_data/denlyra-demo.db"
python -m denlyra
```
Visit **http://127.0.0.1:8766/** and API docs **http://127.0.0.1:8766/api/docs**. Demo schema and fictional clinic staff are created automatically. If `py -3.11` isn't available, use an installed Python 3.11+ interpreter. On macOS/Linux, create a `.venv`, `source .venv/bin/activate`, install, then `DENLYRA_DEMO_MODE=1 python -m denlyra`.

### Run tests
```bash
python -m pytest backend/tests -q
# inside backend/ or with PYTHONPATH=backend/src; after editable installation either works
python -m compileall -q backend/src
python -m ruff check backend/src backend/tests
node --check apps/demo-web/app.js
python scripts/verify_artifact.py
python scripts/smoke_baseline.py
python scripts/update_manifest.py --check
```

### Demo script (2 minutes)
1. Create fictional "Bệnh nhân Demo A".
2. Schedule an appointment with synthetic dentist and chair. Try a conflicting slot, expect HTTP 409.
3. Create encounter and draft note; lock the draft and try rewriting, expect HTTP 409. **Demo lock is NOT legal signature**.
4. Create a plan and tasks, demo-review, complete them, start a new version. No clinical procedures are authorized or recorded.
5. Create a lab case and move through accepted → in_progress → ready → received → verified.
6. Record fictional charge/payment in separate ledgers. Payment does NOT complete a clinical encounter.
7. View audit events (demo-only, not tamper-proof), and switch to a second fake clinic to test scoping.

## What is not done
No real identity/authentication, permission enforcement, consent, official clinical records, EMR templates, signature provider, encryption at rest, production audit immutability, licensed payments, official invoices, prescription generation, document upload, imaging, clinical AI, production backups or validated migrations. Current demo actor/clinic request headers are **not authenticating anyone**. Do NOT deploy publicly; do NOT import identifiable patient data. See `docs/engineering/IMPLEMENTATION_STATUS.md`.

SQLite demo checks overlaps sequentially, **not atomically under concurrency**. PostgreSQL exclusion DDL is supplied as a design baseline and must be tested on running PostgreSQL before claiming collision safety. In production, replace demo schema bootstrap with reviewed migration pipeline, authorization, encrypted storage and signed EMR adapter.

## Read in this order (for human developer or Agent)
1. `AGENTS.md` — mandatory guardrails.
2. `docs/PROJECT_STATE.md` — exact current status and unresolved risks.
3. `docs/product/PRD.md`, `docs/product/FUNCTION_CATALOG.md` — product scope and full feature catalog.
4. `docs/clinical/REGULATORY_MATRIX.md`, `docs/clinical/EMR_AND_FORMS.md` — evidence, site-specific compliance worksheet.
5. `docs/architecture/SYSTEM.md`, `docs/architecture/DOMAIN_MODEL.md`, `docs/architecture/DATABASE.md` — architecture.
6. `docs/engineering/API_CONTRACT.md`, `docs/engineering/FRONTEND_UX.md`, `docs/engineering/TEST_STRATEGY.md` — execution contracts.
7. `docs/security/THREAT_MODEL.md`, `docs/operations/DEPLOYMENT.md` — hardening gates.
8. `docs/engineering/ROADMAP.md`, `docs/tasks/`, `docs/engineering/AGENT_WORKFLOW.md` — implementation sequence.

## Documentation index
| Area | Documents |
|---|---|
| Product | `PRD.md`, `FUNCTION_CATALOG.md`, `USER_JOURNEYS.md`, `COMPETITIVE_STRATEGY.md` |
| Clinical | `REGULATORY_MATRIX.md`, `EMR_AND_FORMS.md`, `CLINIC_DISCOVERY_PREVIOUS.md`, `LEGACY_MIGRATION.md` |
| Architecture | `SYSTEM.md`, `DOMAIN_MODEL.md`, `DATABASE.md`, `EVENTS_AND_WORKFLOWS.md`, `INTEROPERABILITY.md` |
| Engineering | `API_CONTRACT.md`, `FRONTEND_UX.md`, `ROADMAP.md`, `TEST_STRATEGY.md`, `AGENT_WORKFLOW.md`, `IMPLEMENTATION_STATUS.md` |
| AI | `AI_ARCHITECTURE.md`, `EVALUATION_PLAN.md` |
| Operations & security | `DEPLOYMENT.md`, `RUNBOOKS.md`, `THREAT_MODEL.md`, `PRIVACY_AND_RELEASE_GATES.md` |
| Customer research | `CLINIC_INTERVIEW.md`, `PILOT_SCORECARD.md`, `VALIDATION_PLAN.md` |
| Decisions & tasks | `docs/adr/`, `docs/tasks/` |

## Status summary
`RUNNABLE`: synthetic demo domain slice, no Node or GPU needed. `DESIGNED`: full practice system, FHIR/DICOM, AI, professional EMR, cloud deployment. `BLOCKED`: any real patient data, legal EMR signing and regulated clinical features until qualified approval. This distinction is enforced in docs and starter capability flags.

## Suggested durable workflow
Use `docs/PROJECT_STATE.md` as the status entry point and `docs/engineering/AGENT_WORKFLOW.md` for mandatory opening/closing steps. The onboarding audit and evidence are in `docs/sessions/2026-11-17_T000_ONBOARDING.md`; new sessions select the next task from the state document. Commit completed, reviewed changes and push when owner authorization and remote state permit; never force-push or include unrelated changes.
