# Current deliverable versus future target — no marketing confusion

## Executed in starter
- Synthetic demo UI: overview, clinics, patients, appointments, encounter draft, note version/demolock, plan/task version, FDI tooth-code event reference, lab status, finance charges/payment, audit event.
- Python backend FastAPI+SQLAlchemy. Demo SQLite automatically bootstrapped; clinic scoping on API reads; basic Host/Origin protections.
- Typed schemas and constrained positive integer money; note revision history; task prerequisites; basic cross-tenant reference reject.
- Reference PostgreSQL Alembic migration with resource EXCLUDE; offline PostgreSQL SQL generation and disposable SQLite upgrade passed. Live PostgreSQL, upgrade compatibility and concurrency remain unverified; Docker Compose was not run.
- Negative automated tests, legal and domain reference docs, 222-ID feature catalog.

## Designed only — not implemented
- Real login, role authorizations, multi-clinic user identities, production clinic database routing.
- EMR 16/BV-01 compliance, full tooth chart, clinical decision recording, legally valid e-signature and certified clinic archive.
- Real encounter workflow, treatment consent, document forms, lab partner portal, inventory, refunds, invoicing, real payments.
- Files, DICOM, imaging, FHIR interoperability, patient portal, external Zalo/SMS, authorized e-health integration.
- Secure encryption, object manifests, backups/recovery, operations observability, incident response.
- AI transcription, clinical drafts, retrieval, evaluation or predictive algorithms.
- Full role-based React/Next.js frontend. A small optional patients/plans prototype exists in `apps/clinic-web`; typecheck/build passed on Windows 2026-11-17. The default UI remains static HTML/CSS/JS; browser E2E, authorization and accessibility remain unverified.

## Known limitations and technical debt
Demo authorization is header spoofable; no encryption; audit not tamper-resistant; SQLite scheduling and finance are not concurrency-safe; no schema version upgrades tested; no rate-limiting or robust CSP testing; no production security monitoring; no real QA with a licensed dentist. Keep demo restricted to localhost and fake records.

## Verification records
Run and record exact command output, date, commit and environment in `docs/PROJECT_STATE.md`. Never claim compliance based on a passing unit test. See `TEST_STRATEGY.md`.
