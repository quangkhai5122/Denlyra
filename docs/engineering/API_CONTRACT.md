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
| POST `/api/v1/consents` | `consent.write` | `ConsentCreate` | Records purpose-separated consent (`treatment`/`data_processing`/`marketing`/`financial`); checks guardian authority (`T007`) |
| GET `/api/v1/patients/{id}/consents` | `consent.read` | list of consents | Returns distinct purpose consent records |
| POST `/api/v1/consents/{id}/withdraw` | `consent.write` | `ConsentWithdrawRequest` | Withdraws single consent purpose without affecting clinical records (`SEC-07`) |
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
| GET/POST `/api/v1/lab-cases` | `lab.read`/`write` | `LabCaseCreate` | Create/list simulated lab cases with specs, `due_on`, and file manifest |
| GET `/api/v1/lab-cases/{id}/alerts` | `lab.read` | alert summary | Alerts when `due_on > linked_appointment.start_at` (`SCH-013`) without auto-rescheduling |
| POST `/api/v1/lab-cases/{id}/partner-grants` | `lab.write` | `LabPartnerGrantCreate` | Mints case-scoped revocable partner token (`OPS-06`) |
| GET `/api/v1/lab-portal/cases/{token}` | Partner grant | minimized specs | Partner view excluding patient PII (`403` on expired/cross-clinic) |
| POST `/api/v1/lab-portal/cases/{token}/milestones` | Partner grant | `LabPartnerMilestoneUpdate` | Partner updates `accepted`/`in_progress`/`ready`; blocks `verified` (`403`) |
| POST `/api/v1/lab-cases/{id}/receive` | `lab.write` | `LabReceiveRequest` | Records delivery receipt condition (`received`, distinct from `verified`) |
| POST `/api/v1/lab-cases/{id}/remakes` | `lab.write` | `LabRemakeCreate` | Creates linked child remake version preserving original (`LAB-007`) |
| POST `/api/v1/lab-cases/{id}/state` | `lab.write` | next_status | Validated lab lifecycle transition |
| POST `/api/v1/finance/estimates` | `finance.write` | `EstimateCreate` | Immutable versioned treatment estimate (`FIN-002`) |
| POST `/api/v1/finance/estimates/{id}/accept` | `finance.write` | `EstimateAcceptRequest` | Marks patient estimate acceptance and supersedes older accepted estimate |
| GET/POST `/api/v1/finance/charges` | `finance.read`/`write` | `ChargeCreate` (idempotent) | Demo charge + append-only `LedgerEntry`; no real invoice |
| GET/POST `/api/v1/finance/payments` | `finance.read`/`write` | `PaymentCreate` (idempotent) | Demo payment (`cash`/`bank_transfer`/`card`) + `LedgerEntry`; deduplicates webhooks (`NEG-08`) |
| POST `/api/v1/finance/allocations` | `finance.allocate` | `AllocationCreate` (idempotent) | `finance`/`clinic_owner` only; DB-guarded bounds + `LedgerEntry` |
| POST `/api/v1/finance/payments/{id}/refunds` | `finance.refund` | `RefundCreate` (idempotent) | Append-only bounded refund reversal (`FIN-006`, `OPS-03`) + `LedgerEntry` |
| GET `/api/v1/patients/{id}/revenue-account` | `finance.read` | ledger summary | Billed/collected/refunded/allocated/outstanding + ledger trail (`implies_clinical_completion: False`) |
| POST `/api/v1/finance/reconciliations` | `finance.allocate` | `CashierReconciliationCreate` | Daily cashier close comparing counted vs ledger net by tender (`FIN-010`) |
| POST `/api/v1/migrations/paper-batches` | `migration.write` | `PaperBatchCreate` | Opens quarantined legacy paper import batch (`T006`) |
| POST `/api/v1/migrations/paper-batches/{id}/items` | `migration.write` | `PaperItemCreate` | Checks page hashes/completeness (`NEG-10`) and flags duplicate patient candidates (`DR-02`) |
| POST `/api/v1/migrations/paper-items/{id}/verify-link` | `migration.write` | `PaperItemVerifyLinkRequest` | Human resolution preserving `legacy_scan` provenance (`409` on incomplete or forged digital sig) |
| GET `/api/v1/migrations/paper-batches/{id}/reconciliation` | `migration.read` | batch counts | Batch reconciliation report (`MIG-008`) |
| POST `/api/v1/migrations/paper-batches/{id}/rollback` | `migration.write` | `PaperBatchRollbackRequest` | Rolls back batch item links while preserving native patients |
| GET/POST `/api/v1/clinical-forms/templates` | `clinical_form.read`/`write` | `FormTemplateCreate` | Register immutable quarantined synthetic template version (`T003`) |
| POST `/api/v1/clinical-forms/templates/{id}/approve` | `clinical_form.write` | 409 blocked | Fails closed until external clinical/legal review (`NEEDS_CLINICAL_REVIEW.md`) |
| POST `/api/v1/clinical-forms/validate-preview` | `clinical_form.read` | `FormValidatePreviewRequest` | Tri-state (`present`/`explicit_negative`/`unknown`/`missing`) validation preview |
| POST `/api/v1/clinical-forms/official-export` | `clinical_form.write` | 409 blocked | Fails closed until clinical/legal approval |
| GET `/api/v1/encounters/{id}/snapshots` | `clinical_doc.read` | list of snapshots | Lists encounter document snapshots and addenda; read audited (`T009`) |
| GET `/api/v1/finance/estimates` | `finance.read` | list of estimates | Lists clinic versioned treatment estimates (`T009`) |
| GET `/api/v1/finance/reconciliations` | `finance.read` | list of reconciliations | Lists daily cashier reconciliation records (`T009`) |
| GET `/api/v1/archive/keys` | `archive.read` | key metadata | Lists per-clinic key versions and fingerprints (excludes wrapped DEK) (`T010`) |
| POST `/api/v1/archive/keys/rotate` | `archive.key_manage` | new active key | Retires active key to `retired_decrypt_only` and issues `v+1` (`T010`) |
| POST `/api/v1/archive/keys/{id}/revoke` | `archive.key_manage` | revoked key | Marks tenant key `revoked`; blocks future decrypt/restore (`T010`) |
| GET/POST `/api/v1/archive/objects` | `archive.read`/`write` | `ArchiveObjectCreate` | Stores/lists envelope-encrypted clinical/DICOM/scan blobs (`DLY1` Encrypt-then-MAC) (`T010`) |
| GET `/api/v1/archive/objects/{id}/verify` | `archive.read` | integrity report | Unwraps DEK, verifies tag and plaintext/ciphertext SHA-256; read audited (`T010`) |
| POST `/api/v1/archive/objects/{id}/legal-hold` | `archive.key_manage` | `ArchiveLegalHoldRequest` | Places explicit audited `legal_hold` on archive object (`T010`) |
| DELETE `/api/v1/archive/objects/{id}` | `archive.key_manage` | 409 blocked | Fails closed (`409`) under active retention or legal hold (`INV-018` / `DR-08`) |
| GET/POST `/api/v1/archive/backups` | `archive.read`/`restore` | `BackupCreateRequest` | Creates/lists signed cross-store backup manifest + encrypted object bundle (`T010`) |
| POST `/api/v1/archive/backups/{id}/restore-drill` | `archive.restore` | `RestoreDrillRequest` | Restores to isolated SQLite DB, verifies objects/keys/signatures, measures `rto_ms` & `rpo_lag_ms` (`DR-04`, `DR-05`, `NEG-13`) |
| GET `/api/v1/archive/restore-drills` | `archive.read` | drill history | Lists passed/failed isolated DR restore drill runs (`T010`) |
| GET `/api/v1/dashboard` | `dashboard.read` | basic counts | No clinical or financial inference |
| GET `/api/v1/audit-events` | `audit.read` | demo history | Includes mutation and sensitive clinical read/denial events |

## HTTP and semantics
- 201 creation, 200 query/action, 401 unauthenticated/expired/revoked token, 403 unauthorized role/cross-origin/reused signed URL, 404 unknown/wrong-clinic scope, 409 immutable/conflict/precondition/clinical gate block, 422 validation error, 503 identity provider unavailable.
- IDs opaque UUID strings; never use phone as an identifier. All amounts integer VND, not float.
- Dates with timezone offset; stored UTC. UI displays clinic timezone.
