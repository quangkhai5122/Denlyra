# Data architecture: schema, migrations and PostgreSQL constraints

## Executable demo model
`backend/src/denlyra/models.py` holds 50 SQLAlchemy tables (18 R0 core domain tables, 5 T001/T002/T003 hardening tables, 6 T004/T005 tables, 7 T006/T007/T008 tables, 4 T010 archive/DR tables, and 10 T011/T012 inventory & AI tables: `inventory_supplier`, `inventory_sku`, `purchase_order`, `inventory_lot`, `stock_movement`, `stock_reservation`, `stock_adjustment_request`, `ai_model_registry`, `ai_draft_artifact`, and `ai_evaluation_run`). Demo bootstrap calls `Base.metadata.create_all` **only with explicit `DENLYRA_DEMO_MODE=1`** and installs SQLite `BEFORE INSERT`/`UPDATE`/`DELETE` triggers for booking overlap, payment allocation bounds, and `stock_movement` append-only immutability + lot balance bounds. Tables are NOT clinically approved EMR schema. `0001_demo_schema.py` through `0006_inventory_fhir_and_ai_harness.py` form the forward-only upgrade chain. Live PostgreSQL concurrency is wired in `scripts/verify_postgres_live.py` and `.github/workflows/ci.yml` (`postgres-concurrency-tests`).

## Core constraints and indexes
- Opaque immutable UUID PKs, parent clinic ownership, composite FKs where possible.
- Appointments: aware client timestamps converted to UTC; positive interval; active booking range overlap excluded in production PostgreSQL.
- Notes: revisions append-only by convention, `expected_revision` optimistic check; production should enforce append-only through DB policy/permissions and protected archive.
- Treatment: `(plan_id, version_number)` unique, dependencies refer only to same plan version; prevent cycles (starter one-edge-to-existing-task implicitly prevents cycles).
- Finance: integer VND positive amounts, charge/payment same patient & clinic, allocation <= unallocated amounts, idempotency and provider receipt verification future.
- Lab: state machine in application service; production should enforce allowed transitions and role review.

## Proposed future additional tables
`organization`, `licensed_facility`, `branch`, `credential`, `patient_identifier`, `guardian`, `clinical_observation`, `dental_finding`, `tooth_surface`, `clinical_assessment`, `procedure_event`, `clinical_form_template`, `clinical_document_snapshot`, `signature_evidence`, `consent`, `plan_milestone`, `task_instance`, `lab_partner`, `lab_file_manifest`, `inventory_lot`, `stock_movement`, `estimate_version`, `invoice_reference`, `refund`, `communication_job`, `outbox`, `inbox_idempotency`, `tenant_key`, `restore_manifest`, `legal_rule_version`, `regulatory_review`.

## No single generic status
Separate: appointment state, encounter state, note authentication, plan approved version, task progress, lab state, payment/billing state and patient communication state. Do not have one `patient.status` controlling these.

## Migration policy
1. Schema tracked in Alembic revisions with forward-only discipline for signed record changes.
2. Before production migration, snapshot DB and media references, test dry-run on restored copy, document compatibility and rollback/forward-fix.
3. No data deletion/field rename without clinical record retention and legacy export analysis.
4. Release migration after review; keep old signed bytes/forms readable bit-for-bit or with independently verifiable original snapshots.
5. Run PostgreSQL integration suite on live test PostgreSQL with 2 simultaneous transactions attempting same chair; exactly 1 must commit.
6. Check composite clinic FK integrity, role permissions and all read/export paths; no cross-tenant joins by omission of clinic scope.

## Partitioning/tenancy
Initially prefer one logical database per clinic plus central control plane without PHI, if deployment cost and provider constraints allow. `Organization`, legally licensed `Clinic`, and operational `Branch` may differ; clinic-specific data sharing requires authorization and legal evaluation. Redis/queue/outbox and object-store prefixes alone are not a security boundary; verify scoped identities and encryption keys.

## Performance and indexing
Potential indexes on clinic+appointment start, patient normalized search tokens (sensitive), plan task status/due, encounter patient/date, document provenance, lab due/status and payment client. No new index until measured query plans; avoid PHI in caches and third-party telemetry.

## Soft delete and retention
Clinical records must not be destroyed on ordinary user delete. Use distinct `entered_in_error`, supersession and retention governance; account closure requires legal archive/export. Avoid universally hard-coded retention periods.
