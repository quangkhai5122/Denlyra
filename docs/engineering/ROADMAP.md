# Architecture-led product roadmap / coding backlog

**Roadmap is dependency-based rather than a delivery promise.** Develop within risk gates. Do NOT implement all 222 features at once. Use task packets, references and acceptance evidence.

| Stage | Focus | Deliverable | Exit gate |
|---|---|---|---|
| R0 | Synthetic foundation | Repo, demo UI, domain constraints and automated tests | Dev runs locally, no PHI, honest capabilities |
| M0 | Partner clinical & legal discovery | Clinic process maps, license scope, form inventory, signature analysis, legal matrix | Named dentist and counsel review, unresolved list |
| M1 | Secure platform core | OIDC MFA, tenant/branch authorization, migration, Postgres concurrency, encrypted archives, audit | Security integration suite, live Postgres transaction test |
| M2 | Patient + clinic operation | Identity, front desk schedule, staff shifts, accurate patient history import | 5 synthetic/approved workflows, clinic feedback |
| M3 | Clinical documentation | Odontogram, encounter, form schema and legally reviewed signature adapter | Complete 16/BV-01 field mapping and clinic/legal sign-off |
| M4 | Multi-stage treatment | Plan versions, task DAG, follow-ups, laboratory and financial associations | Full synthetic case E2E, clinician review |
| M5 | Finance and inventory | Estimates, ledger, deposits/refunds, inventory lots, cash reconciliation | Audit and financial consistency integration suite |
| M6 | Interoperability + migration | Paper source import, verified signed export, DICOM, FHIR mappings, payments/messaging | Cross-vendor sandbox and restore tests |
| M7 | AI research and assistive workflows | Dictation, extraction, retrieval, operations suggestions | Clinical evaluation and privacy/security review |
| M8 | Controlled clinical pilot | Approved production deployment, training, cutover, incident playbook | All launch gates signed by clinic and security/legal owners |
| M9 | Repeatable business deployment | Billing, onboarding wizard, support, license, clinic cohort metrics | Paid pilot retention and measured value |

## Current position (2026-11-17)
R0 synthetic baseline verified by T000; no production milestone is complete. M0 discovery
and M1 secure core are pending. Start T001 next; PostgreSQL/identity, clinical mapping and
release gates remain unsatisfied. See `docs/PROJECT_STATE.md` and its linked session evidence.
Archived foundation milestone numbers are historical and differ from this active roadmap.

## Next ten coded tasks
`T001` identity & authorization; `T002` PostgreSQL migration / booking race test; `T003` real clinical form mapping (blocked human); `T004` authenticated signature state machine (blocked human); `T005` treatment E2E with full dependency/rollback; `T006` audited source paper importer; `T007` lab and consent; `T008` financial ledger and refund; `T009` role-based React frontend; `T010` backup/archive/manifests and restore.

## Parallel agent constraints
- Foundation owner maintains schema/auth and cross-context invariants; no other agent edits DB migrations without coordination.
- Clinical owner builds form mapping **only after** legal/medical verification; test fixtures synthetic.
- Frontend owner can prototype screens against OpenAPI in parallel; no source-of-truth logic in UI.
- AI owner runs offline synthetic experiments, no AI write-to-EMR or external PHI.
- QA owner independently challenges tenant/role, note immutability, booking conflicts and finance.

## Exit criteria per milestone
User story complete end-to-end, source evidence, versioned API + migration, security/privacy review, negative tests including concurrency where applicable, runbook and recovery, measured performance, owner sign-off; no unresolved critical patient safety defect. Promote from `demo` to `clinical pilot` only with external approval.

## Recommended first weeks (not calendar commitment)
1. Run synthetic demo and tests; inspect schema and constraints.
2. Finish T001 and T002, independently review security and transactional scheduling.
3. In parallel run M0 partner interviews/form field mapping in **separate secure workspace**, keeping PHI out of code tools.
4. Create first React frontend role screens against stabilized OpenAPI.
5. Build patient/encounter clinical vertical slice only after medical director signoff.
