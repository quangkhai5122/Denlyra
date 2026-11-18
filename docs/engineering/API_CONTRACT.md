# HTTP/API Contract v0.1 — synthetic demonstration vs production target

## Demo status, endpoint scope and safety
Base URL: `http://127.0.0.1:8766`, OpenAPI at `/api/docs`. **Start only after explicitly setting DENLYRA_DEMO_MODE=1.** Every request is synthetic.
- When `DENLYRA_REQUIRE_AUTH=1` (`Settings.require_auth=True`), all `/api/v1/*` endpoints require a verified `Authorization: Bearer <token>` minted by the local synthetic issuer (`POST /api/v1/auth/token`) and enforce deny-by-default RBAC/ABAC (`ADR-007`); `X-Demo-*` headers alone are rejected with `401`.
- When `DENLYRA_REQUIRE_AUTH=0` (default R0 demo mode), unauthenticated requests fall back to synthetic demo selectors for local UI exploration, while any request carrying `Authorization: Bearer <token>` still undergoes full cryptographic, membership, and role verification.

| Method + route | Permission | Body / output | What actually happens |
|---|---|---|---|
| GET `/health` | Public | status, demo flags | technical availability, not medical compliance |
| GET `/api/v1/capabilities` | Public | disabled feature flags | `production_auth`, `clinical_e_signature`, `emr_certified` all `False`; `synthetic_auth_foundation` `True` |
| POST `/api/v1/auth/token` | Public (demo) | `TokenIssueRequest` | Mints signed synthetic staff bearer token (`HS256`) |
| POST `/api/v1/auth/revoke` | Authenticated | revocation receipt | Revokes current token `jti` immediately |
| POST `/api/v1/auth/signed-urls` | `signed_url.create` | `SignedUrlCreateRequest` | Mints single-use clinic-scoped download URL |
| GET `/api/v1/signed-download/{token}` | `signed_url.consume` | grant payload | Consumes single-use signed URL; rejects reuse/expiry/cross-clinic (`403`) |
| POST `/api/v1/staff` | `staff.manage` | `StaffCreateRequest` | Registers synthetic staff in clinic/branch |
| POST `/api/v1/staff/{id}/deactivate` | `staff.manage` | `Staff` | Deactivates staff & increments `token_version`, invalidating active tokens |
| POST `/api/v1/resources` | `resource.manage` | `ResourceCreateRequest` | Registers synthetic chair or equipment (`device`) |
| GET `/api/v1/demo/context` | `context.read` | clinic IDs, dentists, chairs | synthetic seed context |
| GET/POST `/api/v1/patients` | `patient.read`/`write` | `PatientCreate` / synthetic patient | Clinic-scoped prototype registry |
| GET `/api/v1/patients/{id}` | `patient.read` | patient | 404 if missing in clinic |
| GET/POST `/api/v1/appointments` | `appointment.read`/`write` | aware RFC3339 datetime, doctor/chair/equipment, optional `idempotency_key` | Atomic multi-resource booking + DB overlap catch (`409`) |
| POST `/api/v1/appointments/{id}/cancel` | `appointment.write` | appointment | Cancel state/history, release active reservations |
| POST `/api/v1/appointments/{id}/reschedule` | `appointment.write` | `AppointmentReschedule` | Atomic release + rebook preserving `rescheduled_from_id` + outbox (`SCH-005`) |
| GET/POST `/api/v1/encounters` | `encounter.read`/`create` | patient and practitioner | Creates/lists synthetic encounter; read audited; `finance` denied (`403`) |
| GET/POST `/api/v1/encounters/{id}/findings` | `finding.read`/`write` | FDI tooth code, surface, demo text | Append-only mock dental event; read audited |
| GET `/api/v1/patients/{id}/odontogram` | `odontogram.read` | patient | Return sourced FDI finding history; read audited |
| GET/POST `/api/v1/encounters/{id}/notes` | `note.read`/`write` | note draft and revisions | Confidential clinical note; `finance`/`receptionist` denied (`403`) |
| PUT `/api/v1/notes/{id}` | `note.write` | content + expected_revision | Optimistic check, new revision (`dentist`/`medical_director` only) |
| POST `/api/v1/notes/{id}/demo-lock` | `note.lock` | digest and status | **NOT e-signature**; clinician role required (`403` for receptionist) |
| POST `/api/v1/clinical-documents/snapshots` | `clinical_doc.write` | `DocumentSnapshotCreate` | Prepares canonical JSON + SHA256 snapshot envelope (`T004`) |
| GET `/api/v1/clinical-documents/{id}` | `clinical_doc.read` | snapshot envelope | Returns snapshot metadata and canonical digest; read audited |
| POST `/api/v1/clinical-documents/{id}/sign-synthetic` | `clinical_doc.sign` | `DocumentSyntheticSignRequest` | Seals with `FakeSyntheticSignatureProvider` (`synthetic_signed_NOT_legal`); blocks `legal_authenticated` (`409`) |
| GET `/api/v1/clinical-documents/{id}/verify` | `clinical_doc.read` | verification result | Verifies canonical SHA256 and synthetic receipt integrity |
| POST `/api/v1/clinical-documents/{id}/addenda` | `clinical_doc.write` | `DocumentAddendumCreate` | Creates linked addendum preserving original snapshot bytes bit-for-bit |
| POST `/api/v1/clinical-documents/{id}/enter-in-error` | `clinical_doc.write` | `DocumentEnterInErrorRequest` | Marks `entered_in_error` with mandatory reason without mutating bytes |
| GET/POST `/api/v1/treatment-plans` | `plan.read`/`write` | patient, title | Plan with draft version |
| GET `/api/v1/treatment-plans/{id}` | `plan.read` | current version and tasks | Snapshot of current plan |
| GET `/api/v1/treatment-plans/{id}/timeline` | `plan.read` | status-separated timeline | Owner, overdue, `blocked_reasons`, links, reassessments, financial summary (`T005`) |
| POST `/api/v1/treatment-plans/{id}/tasks` | `plan.write` | `TaskCreate` (`depends_on_task_ids`) | Multi-dependency DAG task with DFS cycle check (`422`) |
| POST `/api/v1/treatment-tasks/{id}/dependencies` | `plan.write` | `TaskDependenciesUpdate` | Adds DAG prerequisites on draft version with cycle detection |
| POST `/api/v1/treatment-tasks/{id}/links` | `plan.write` | `TaskCoordinationLinkCreate` | Links task to `appointment`, `lab_case` (`requires_verified_lab`), or `charge` |
| POST `/api/v1/treatment-plans/{id}/demo-review` | `plan.review` | version state | **NOT clinical approval**; clinician role required |
| POST `/api/v1/treatment-plans/{id}/versions` | `plan.write` | new version state | Clone tasks and DAG links to fresh draft |
| POST `/api/v1/treatment-plans/{id}/reassessments` | `plan.reassess` | `PlanReassessmentCreate` | Preserves completed history + spawns traced follow-up task in new version (`PLAN-04`) |
| POST `/api/v1/treatment-tasks/{id}/demo-complete` | `plan.complete_task` | task state | Checks all DAG prerequisites and `requires_verified_lab` (`NEG-09`) |
| GET/POST `/api/v1/lab-cases` | `lab.read`/`write` | patient, title | Create/list simulated lab cases |
| POST `/api/v1/lab-cases/{id}/state` | `lab.write` | next_status | Validated lab lifecycle transition |
| GET/POST `/api/v1/finance/charges` | `finance.read`/`write` | positive integer VND | Demo charge; no real invoice |
| GET/POST `/api/v1/finance/payments` | `finance.read`/`write` | positive integer VND | Demo payment; no gateway/receipt |
| POST `/api/v1/finance/allocations` | `finance.allocate` | charge/payment/positive VND | `finance`/`clinic_owner` only; reject over-allocation and cross-patient |
| POST `/api/v1/finance/payments/{id}/refunds` | `finance.refund` | `RefundCreate` | Append-only bounded refund reversal (`FIN-006`, `OPS-03`); preserves original payment |
| GET/POST `/api/v1/clinical-forms/templates` | `clinical_form.read`/`write` | `FormTemplateCreate` | Register immutable quarantined synthetic template version (`T003`) |
| POST `/api/v1/clinical-forms/templates/{id}/approve` | `clinical_form.write` | 409 blocked | Fails closed until external clinical/legal review (`NEEDS_CLINICAL_REVIEW.md`) |
| POST `/api/v1/clinical-forms/validate-preview` | `clinical_form.read` | `FormValidatePreviewRequest` | Tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validation preview |
| POST `/api/v1/clinical-forms/official-export` | `clinical_form.write` | 409 blocked | Fails closed until clinical/legal approval |
| GET `/api/v1/dashboard` | `dashboard.read` | basic counts | No clinical or financial inference |
| GET `/api/v1/audit-events` | `audit.read` | demo history | Includes mutation and sensitive clinical read/denial events |

## HTTP and semantics
- 201 creation, 200 query/action, 401 unauthenticated/expired/revoked token, 403 unauthorized role/cross-origin/reused signed URL, 404 unknown/wrong-clinic scope, 409 immutable/conflict/precondition/clinical gate block, 422 validation error, 503 identity provider unavailable.
- IDs opaque UUID strings; never use phone as an identifier. All amounts integer VND, not float.
- Dates with timezone offset; stored UTC. UI displays clinic timezone.
