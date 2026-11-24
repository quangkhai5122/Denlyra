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

## Current position (2026-11-25)
R0 synthetic baseline verified by T000. Through 2026-11-25, twenty-four coded foundation slices (`T001`–`T024`) have synthetic domain, API, migration, frontend, and negative-test implementations:
- `T001` synthetic authentication, RBAC/ABAC deny-by-default, staff deactivation invalidation, token revocation, and single-use signed URL foundation completed (`ADR-007`).
- `T002` frozen Alembic migration chain (`0001_demo` -> `0012_telemetry_onboarding_incident_portal_and_hr`), atomic doctor+chair+equipment booking, `IntegrityError` -> `409` rollback, booking idempotency, 2-connection barrier race test harness, `scripts/verify_postgres_live.py`, and CI `postgres-concurrency-tests` implemented; live PostgreSQL run receipt remains gated on a running PostgreSQL 16 host or remote CI log review.
- `T003` safe synthetic `FormRegistry`, version immutability, and tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validation implemented with `docs/clinical/NEEDS_CLINICAL_REVIEW.md` blocking clinical activation until named dentist and legal counsel sign-off.
- `T004` synthetic `SignatureProvider` test double, canonical `ClinicalDocumentSnapshot` envelope, linked addenda, and `entered_in_error` negative/integrity suite completed (`ADR-008`); real legal signing remains blocked by `NEEDS_CLINICAL_REVIEW.md`.
- `T005` multi-dependency treatment DAG, cycle detection, cross-context schedule/lab/charge coordination links, transactional outbox, atomic appointment reschedule, append-only refunds, reassessment version loops, and evidence-aware timeline completed (`ADR-008`).
- `T006` synthetic legacy paper quarantine importer (`MigrationBatch`, `MigrationItem`, missing-page blocks, duplicate-candidate review queue, `legacy_scan` provenance, batch rollback) completed (`ADR-009`).
- `T007` purpose-separated `ConsentRecord`, lab delay alerts, delivery vs verification separation, remake lineage, and minimized-data `LabPartnerGrant` portal completed (`ADR-009`).
- `T008` versioned `EstimateVersion`, append-only `LedgerEntry`, idempotent charges/payments/allocations/refunds, concurrent allocation bounds, and daily `CashierReconciliation` completed (`ADR-009`).
- `T009` generated OpenAPI TypeScript client (`INT-001`), 5 role-based Next.js clinic workspaces, fixed `Asia/Ho_Chi_Minh` timezone formatting (`R-011`), accessible SVG FDI odontogram (`ODN-004`), and Node 24 contract/a11y tests completed (`ADR-010`).
- `T010` per-clinic envelope encryption, key rotation/revocation, retention/legal-hold deletion block (`DR-08`), signed cross-store `BackupManifest`, and isolated DR restore drill measuring `RTO`/`RPO` completed (`ADR-010`).
- `T011` append-only inventory lot & stock movement ledger (`INV-001`..`INV-010`, `INV-023`), DB immutability triggers, FEFO picking, and dual-control adjustments completed (`ADR-011`).
- `T012` clinic-scoped HL7 FHIR R4 `HTEST` + `Provenance` export/validator (`INT-002`/`INT-003`) and zero-egress draft-only AI span/timeline engine, prompt-injection firewall (`AI-010`), kill-switch (`AI-014`), and offline benchmark harness (`AI-009`) completed (`ADR-011`).
- `T013` clinician shift windows (`SCH-001`), chair/device maintenance downtime blocks (`SCH-015`/`HR-004`), confirmation state separation (`SCH-009`/`CRM-003`), identity-verified check-in + chair sanitation turnover gate (`PAT-009`/`SCH-010`/`HR-002`/`HR-003`), and consent-safe recall/follow-up queue (`CRM-004`/`005`/`010`) completed (`ADR-012`).
- `T014` per-clinic SHA-256 hash-chained `audit_event` journal + tamper verifier (`SEC-007`) and HMAC-signed clinic-scoped cursor pagination (`PAT-002`/`R-012`) completed (`ADR-012`).
- `T015` reversible dual-confirmed patient merge (`PAT-006`), <=15-minute read-only emergency break-glass with independent review (`ORG-011`), and clinician-published patient/guardian portal views (`PORT-001`..`007`, `PORT-009`, `TRT-016`) completed (`ADR-013`).
- `T016` versioned clinic service price catalog (`FIN-001`), dual-control discount override workflow (`FIN-014`), and attributable owner KPI dictionary & lineage (`RPT-002`, `RPT-004`..`007`, `RPT-011`) completed (`ADR-013`).
- `T017` tri-state medical/allergy risk review (`EMR-003`, `PAT-003`), encounter closure & missing-signature checklist gate (`EMR-009`, `EMR-018`), and clinician-authored dental diagnosis & FDI tooth performed procedure evidence (`EMR-010`, `EMR-011`, `ODN-005`) completed (`ADR-014`).
- `T018` clinical milestone checklists (`TRT-012`), lossless treatment pause/cancel/terminate governance (`TRT-014`), consent-safe schedule waiting list (`SCH-008`), reviewed installment schedules without auto-charge (`FIN-008`), and protected quality incident escalation queue (`HR-008`) completed (`ADR-014`).
- `T019` versioned odontogram legend (`ODN-006`), optimistic tooth restoration revisions & structured print/export (`ODN-007`, `ODN-008`, `ODN-010`), reviewed external referrals (`EMR-013`), document eligibility flags (`PAT-010`), and structured clinical archive export (`EMR-014`) completed (`ADR-015`).
- `T020` multi-branch aggregate view (`ORG-007`), auto-expiring temporary delegation (`ORG-009`), staff task escalations & handoffs (`HR-005`, `HR-006`), differentiated contact timeline & complaint recovery queue (`CRM-001`, `CRM-009`), and allowlisted read-only ops assistant (`AI-005`) completed (`ADR-015`).
- `T021` licensed facility metadata without display-name inference (`ORG-001`), procedure duration templates & non-mutating constraint slot optimizer (`SCH-011`, `SCH-012`), HMAC-traceable financial receipt exports (`FIN-013`), and timezone-correct attendance & overtime isolated from clinical authorship (`HR-001`, `HR-010`) completed (`ADR-016`).
- `T022` reviewed reminder templates & send-window/consent-gated communication drafts (`CRM-002`, `AI-006`), decoupled anonymous 1–5 patient satisfaction survey (`CRM-011`), and hash-verified incumbent software export adapter + parallel-run cutover guard (`INT-012`, `MIG-009`, `MIG-010`) completed (`ADR-016`).
- `T023` PHI-redacted structured telemetry (`OPS-005`), isolated per-clinic onboarding configuration (`OPS-010`), consent-gated support diagnostic bundles (`OPS-012`), forensic security incident & breach workflow (`SEC-012`), and exact-pinning SBOM supply-chain verifier (`SEC-013`) completed (`ADR-017`).
- `T024` retention-guarded patient subject access export (`PAT-011`), FIFO consent-safe cancellation slot recovery (`SCH-014`), malware-scanned quarantined portal uploads & human-triaged support messaging (`PORT-008`, `PORT-010`), and staff competency expiry guard + performed-vs-collected commission preview (`HR-007`, `HR-009`) completed (`ADR-017`).
No production milestone is complete; M0 human clinical/legal discovery, M1 live PostgreSQL receipt + external OIDC/KMS + independent `SEC-G1` review, and `T025` versioned clinical terminology & specialty plan templates, PHI-minimized lab invoicing, labeled imaging overlays, and encrypted de-identified report exports (`EMR-016`, `TRT-015`, `LAB-010`, `ODN-009`, `RPT-009`, `RPT-010`) are the next ordered priorities. See `docs/PROJECT_STATE.md`.

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
