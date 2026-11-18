# Current deliverable versus future target — no marketing confusion

## Executed in starter
- Synthetic demo UI: overview, clinics, patients, appointments, encounter draft, note version/demolock, plan/task version, FDI tooth-code event reference, lab status, finance charges/payment, audit event.
- Python backend FastAPI+SQLAlchemy (23 tables, 48 OpenAPI operations). Demo SQLite automatically bootstrapped; clinic scoping on API reads; basic Host/Origin protections.
- T001 synthetic token issuer (`HS256`), deny-by-default RBAC/ABAC policy engine, staff deactivation token invalidation, JTI revocation, one-time clinic-scoped signed URLs, and sensitive clinical read/denial audit trail (`ADR-007`).
- T002 explicit frozen Alembic migration chain (`0001_demo` -> `0002_hardening`), atomic multi-resource (doctor + chair + equipment) booking, `IntegrityError` -> `409` rollback, idempotency keys, SQLite `BEFORE INSERT` overlap trigger, and 2-connection barrier concurrency test harness. Live PostgreSQL server execution remains unverified until a PostgreSQL instance is provisioned.
- T003 quarantined synthetic `FormRegistry` with immutable `(official_code, schema_version)`, tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validation (`INV-022`), and fail-closed `409` blocks on self-approval and official EMR export (`docs/clinical/NEEDS_CLINICAL_REVIEW.md`).
- Negative automated tests (40 passed, 1 skipped live-Postgres check), legal and domain reference docs, 222-ID feature catalog (33 partial demo flags).

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
