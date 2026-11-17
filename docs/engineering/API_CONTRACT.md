# HTTP/API Contract v0.1 — synthetic demonstration vs production target

## Demo status, endpoint scope and safety
Base URL: `http://127.0.0.1:8766`, OpenAPI at `/api/docs`. **Start only after explicitly setting DENLYRA_DEMO_MODE=1.** Every request is synthetic. `X-Demo-Clinic` and `X-Demo-Actor` are **untrusted demo selectors**, not authentication. User can select Clinic A/B in UI; there is NO clinical tenant security or role enforcement.

| Method + route | Body / output | What actually happens |
|---|---|---|
| GET `/health` | status, demo flags | technical availability, not medical compliance |
| GET `/api/v1/capabilities` | disabled feature flags | signed EMR/auth/live payment/AI all disabled |
| GET `/api/v1/demo/context` | clinic IDs, dentists, chairs | synthetic seed, NO auth |
| GET/POST `/api/v1/patients` | `PatientCreate` / synthetic patient | Clinic-scoped prototype registry |
| GET `/api/v1/patients/{id}` | patient | 404 if missing in selected demo clinic |
| GET/POST `/api/v1/appointments` | aware RFC3339 datetime, doctor/chair/patient | Sequential overlap check + ResourceBooking rows |
| POST `/api/v1/appointments/{id}/cancel` | appointment | Cancel state/history, release active reservations |
| GET/POST `/api/v1/encounters` | patient and practitioner | Creates synthetic encounter |
| GET/POST `/api/v1/encounters/{id}/findings` | FDI tooth code, surface, demo text | Append-only mock dental event |
| GET `/api/v1/patients/{id}/odontogram` | patient | Return sourced FDI finding history |
| GET/POST `/api/v1/encounters/{id}/notes` | note draft and revisions | Not legal EMR note |
| PUT `/api/v1/notes/{id}` | content + expected_revision | Optimistic check, new revision |
| POST `/api/v1/notes/{id}/demo-lock` | digest and status | **NOT e-signature**; prevent further demo editing |
| GET/POST `/api/v1/treatment-plans` | patient, title | Plan with draft version |
| GET `/api/v1/treatment-plans/{id}` | current version and tasks | Snapshot of current plan |
| POST `/api/v1/treatment-plans/{id}/tasks` | title, phase, optional existing dependency ID | Same-version prerequisite, acyclic by construction |
| POST `/api/v1/treatment-plans/{id}/demo-review` | version state | **NOT clinical approval** |
| POST `/api/v1/treatment-plans/{id}/versions` | new version state | Clone tasks and dependency links to fresh draft |
| POST `/api/v1/treatment-tasks/{id}/demo-complete` | task state | Administrative simulation only |
| GET/POST `/api/v1/lab-cases` | patient, title | Create/list simulated lab cases |
| POST `/api/v1/lab-cases/{id}/state` | next_status | Validated lab lifecycle transition |
| GET/POST `/api/v1/finance/charges` | positive integer VND | Demo charge; no real invoice |
| GET/POST `/api/v1/finance/payments` | positive integer VND | Demo payment; no gateway/receipt |
| POST `/api/v1/finance/allocations` | charge/payment/positive VND | Reject over-allocation and cross-patient |
| GET `/api/v1/dashboard` | basic counts | No clinical or financial inference |
| GET `/api/v1/audit-events` | demo history | Not tamper-evident production log |

## Example booking
```json
{
  "patient_id": "<synthetic_uuid>",
  "practitioner_id": "<demo_staff_uuid>",
  "chair_id": "<demo_chair_uuid>",
  "start_at": "2026-12-01T09:00:00+07:00",
  "end_at": "2026-12-01T10:00:00+07:00",
  "reason_demo": "Khám mô phỏng"
}
```
Positive: 201 with stored UTC interval. Negative: 409 time conflict, 404 wrong-clinic IDs, 422 invalid interval/naive timestamp. Constraint tested sequentially in SQLite; **PostgreSQL concurrent exclusion not yet verified**.

## Example draft note
`POST /api/v1/encounters/{id}/notes` `{ "content":"Bản nháp mô phỏng" }` → 201 draft. `PUT /api/v1/notes/{note_id}` `{ "content":"Bản mới mô phỏng", "expected_revision":1 }` → 200. `POST .../demo-lock` → `demo_locked` + content hash. Subsequent PUT → 409. Addendum is a new note with `parent_note_id` in the encounter notes endpoint. This is NOT an approved EMR signature flow.

## HTTP and semantics
- 201 creation, 200 query/action, 404 unknown/wrong-clinic scope, 409 immutable/conflict/precondition, 422 validation error, 403 cross-origin demonstration guard.
- IDs opaque UUID strings; never use phone as an identifier. All amounts integer VND, not float.
- Dates with timezone offset; stored UTC. UI displays clinic timezone.
- No production authentication, pagination, signed audit or idempotency keys in starter. Implement before PHI.
- Do not return full SQLAlchemy objects including internal secure fields once production models are introduced; use explicit DTO serializers.

## Target API conventions (future)
`/api/v1/clinics`, `/patients/{id}/history`, `/clinical/encounters`, `/clinical/documents/{id}/authenticate`, `/odontogram/findings`, `/treatments/{id}/plan-versions`, `/schedules/slots`, `/inventory/lots`, `/finance/refunds`, `/lab/orders`, `/portal`, `/interop/fhir`, `/interop/dicom`, `/audit`, `/ai/drafts`. New endpoints require OIDC session, RBAC+ABAC, tenant resolution from server-side claims, authorization at object and action level, version concurrency guards, idempotency token for external effects and complete OpenAPI contracts. Never copy demo paths to production without a security migration.

## API contract versioning
Preserve `/api/v1` for compatible additions; breaking schema needs versioned contract and migration, with generated typed frontend client. Add request/response schemas, error codes, roles and feature gates per endpoint. All state-changing actions audited at domain layer; avoid arbitrary generic PATCH of signed clinical fields.
