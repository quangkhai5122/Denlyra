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
| GET/POST `/api/v1/inventory/suppliers` | `inventory.read`/`write` | `SupplierCreate` | Clinic-scoped supplier registry with duplicate tax_code guard (`INV-002`) |
| GET/POST `/api/v1/inventory/skus` | `inventory.read`/`write` | `SkuCreate` | Clinic-scoped material SKU catalog + stock summary (`INV-001`) |
| GET `/api/v1/inventory/skus/{id}/stock` | `inventory.read` | SKU + lot balances | Physical vs active reserved vs available stock derived from movements (`INV-005`) |
| GET `/api/v1/inventory/skus/{id}/fefo-picks` | `inventory.read` | FEFO pick list | Earliest-expiry picks skipping expired & quarantined lots (`INV-009`) |
| POST `/api/v1/inventory/purchase-orders` | `inventory.write` | `PurchaseOrderCreate` | Opens clinic purchase order (`INV-003`) |
| POST `/api/v1/inventory/purchase-orders/{id}/receive` | `inventory.write` | `PurchaseOrderReceiveRequest` | Separates ordered/delivered/inspected_accepted qty; creates `InventoryLot` + `receipt_accepted` movement |
| POST `/api/v1/inventory/reservations` | `inventory.write` | `StockReservationCreate` | Holds allocatable stock without deducting physical balance (`INV-006`, `INV-023`) |
| POST `/api/v1/inventory/reservations/{id}/release` | `inventory.write` | `StockReservationReleaseRequest` | Releases active reservation without fabricating receipt |
| POST `/api/v1/inventory/consumptions` | `inventory.consume` | `StockConsumptionCreate` | Clinician/assistant encounter-linked consumption; blocks expired/quarantined lots (`INV-004`, `INV-007`) |
| POST `/api/v1/inventory/adjustments` | `inventory.adjust_request` | `StockAdjustmentCreate` | Opens dual-control stock adjustment request (`INV-010`) |
| POST `/api/v1/inventory/adjustments/{id}/approve` | `inventory.adjust_approve` | `StockAdjustmentApproveRequest` | Distinct `clinic_owner`/`medical_director` approves (`409` on self-approval); appends movement |
| GET `/api/v1/inventory/alerts` | `inventory.read` | alert summary | Low-stock SKUs, expired/near-expiry lots, and shrinkage movements (`INV-008`, `RPT-008`) |
| GET `/api/v1/interop/fhir/r4/patients/{id}/bundle` | `interop.fhir_read` | FHIR R4 Bundle | Exports clinic-scoped `Patient`/`Practitioner`/`Appointment`/`Encounter`/`DocumentReference`/`Provenance` tagged `HTEST` (`INT-002`, `INT-003`) |
| POST `/api/v1/interop/fhir/r4/validate-bundle` | `interop.fhir_read` | `FhirBundleValidateRequest` | Validates `HTEST`, clinic scope, and blocks forged legal signature claims (`409`) |
| GET `/api/v1/ai/models` | `ai.draft` | local model registry | Lists registered zero-egress local extractors (`AI-011`) |
| POST `/api/v1/ai/drafts/dictation-extract` | `ai.draft` | `AIDictationExtractRequest` | Span extraction + tri-state allergy abstention (`INV-022`); `409` on prompt injection (`AI-010`); `503` when disabled (`AI-014`) |
| POST `/api/v1/ai/drafts/timeline-summary` | `ai.draft` | `AITimelineSummaryRequest` | Source-linked longitudinal summary without inferred diagnosis (`AI-004`) |
| POST `/api/v1/ai/drafts/{id}/accept-into-note-draft` | `ai.accept_clinical` | `AIDraftAcceptRequest` | Clinician-only acceptance creating `draft` `ClinicalNote` (never locked/signed) (`AI-003`) |
| GET/POST `/api/v1/ai/evaluations` & `/run` | `ai.evaluate` | benchmark results | Runs/lists offline extraction & prompt-injection benchmark (`AI-009`, `AI-010`) |
| GET `/api/v1/patients/page` | `patient.read` | paginated patients | Clinic-scoped `q` search + HMAC-signed opaque cursor (`PAT-002`, `R-012`) |
| GET `/api/v1/appointments/page` | `appointment.read` | paginated appointments | Clinic-scoped HMAC-signed cursor pagination (`R-012`) |
| GET/POST `/api/v1/appointments/{id}/confirmations` | `appointment.read`/`write` | `AppointmentConfirmationCreate` | Separates `sent`/`delivered` from `patient_confirmed`/`declined` (`SCH-009`, `CRM-003`) |
| GET/POST `/api/v1/operations/shifts` | `operations.read`/`shift_manage` | `StaffShiftCreate` | Approved clinician working shift windows (`SCH-001`, `ORG-008`) |
| GET/POST `/api/v1/operations/downtimes` & `/{id}/resolve` | `operations.read`/`downtime_manage` | `ResourceDowntimeCreate` | Chair/device maintenance blocks enforced in service + DB trigger (`SCH-015`, `HR-004`) |
| GET/POST `/api/v1/operations/turnovers` & `/{id}/complete` | `operations.read`/`turnover` | `ChairTurnoverCreate` / `Complete` | Chair sanitation + assistant prep checklist (`HR-002`, `HR-003`) |
| GET/POST `/api/v1/operations/checkins` & `/{id}/status` | `operations.read`/`checkin` | `CheckinCreate` / `CheckinStatusUpdate` | Identity-verified check-in (`PAT-009`) + turnover-gated `in_chair` (`SCH-010`) |
| GET/POST `/api/v1/operations/recalls` & `/{id}/close` | `operations.read`/`recall` | `RecallCreate` / `RecallCloseRequest` | Clinician-approved recalls (`CRM-005`) & consent-safe marketing outreach (`CRM-010`) |
| GET `/api/v1/audit-events/page` | `audit.read` | paginated audit events | HMAC-signed cursor pagination over `chain_seq` (`R-012`) |
| GET `/api/v1/audit-events/verify-chain` | `audit.read` | chain verification | Recomputes genesis-to-head SHA-256 `prev_hash -> entry_hash` (`409` on tamper, `SEC-007`) |
| GET/POST `/api/v1/patients/merges`, `/{id}/confirm`, `/{id}/reverse` | `patient.merge_request`/`merge_approve` | `PatientMergeCreate` / `Confirm` / `Reverse` | Reversible dual-confirmed patient merge (`409` on self-confirm or retired secondary booking, `PAT-006`) |
| GET `/api/v1/patients/{id}/unified-summary` | `patient.read` | unified patient summary | Resolves merged secondary to canonical ID while preserving `source_patient_id` on every record (`PAT-006`) |
| GET/POST `/api/v1/auth/break-glass`, `/{id}/patient-chart`, `/{id}/revoke`, `/{id}/review` | `auth.break_glass`/`staff.manage` | `BreakGlassCreateRequest` / `Review` | <=15 min read-only emergency chart grant + mandatory independent review (`409` on self-review, `ORG-011`) |
| POST `/api/v1/portal/grants`, `/instructions`, `/plan-summaries`, `/reschedule-requests/{id}/approve` | `portal.manage`/`publish`/`appointment.write` | `PortalGrantCreate` / `Publish` | Verified-guardian gated `aud="patient_portal"` token + clinician-only portal publication (`PORT-001`..`009`) |
| GET/POST `/api/v1/patient-portal/overview`, `/appointments/{id}/confirm`, `/reschedule-requests`, `/intake-forms` | `patient_portal` Bearer | portal views & intake | Exposes only published instructions/lay summaries & balance; zero draft note leakage (`PORT-002`..`007`, `TRT-016`) |
| GET/POST `/api/v1/finance/price-catalog`, `/estimates/from-catalog`, `/estimates/{id}/lines` | `finance.read`/`catalog_manage`/`write` | `PriceCatalogCreate` / `EstimateFromCatalogCreate` | Append-only versioned fee schedule + locked line prices (`FIN-001`) |
| GET/POST `/api/v1/finance/discount-requests`, `/estimates/{id}/discounts`, `/discount-requests/{id}/decide` | `finance.write`/`discount_approve` | `DiscountRequestCreate` / `Decision` | Dual-control discount approval spawning new `EstimateVersion` without clinical plan changes (`FIN-014`) |
| GET `/api/v1/reports/dictionary` & `/api/v1/reports/kpi-lineage` | `dashboard.read` | KPI dictionary & lineage | Chair scheduled vs utilized (`RPT-002`), recall opt-out exclusions (`RPT-004`), accrual vs cash (`RPT-006`), lab exceptions (`RPT-007`), and `source_record_ids` (`RPT-011`) |
| GET/POST `/api/v1/patients/{id}/medical-risk-reviews` | `encounter.read`/`medical_risk.write` | `MedicalRiskReviewCreate` | Append-only tri-state allergy/bleeding/cardio/pregnancy review (`unanswered != explicit_negative`, `EMR-003`, `PAT-003`, `INV-022`) |
| GET/POST `/api/v1/encounters/{id}/closure-checklist`, `/notify-missing-signatures`, `/close-demo` | `encounter.read`/`encounter.close` | readiness checklist | Blocks closure on unanswered allergy, unlocked drafts, or unsigned snapshots (`EMR-009`, `EMR-018`) |
| GET/POST `/api/v1/encounters/{id}/diagnoses` & `/performed-procedures` | `diagnosis.write`/`procedure.record_performed` | `EncounterDiagnosisCreate` / `PerformedProcedureCreate` | Clinician-only FDI tooth diagnosis/procedure evidence (`422` on AI authorship; never inferred from payment, `EMR-010`, `EMR-011`, `ODN-005`) |
| POST `/api/v1/treatment-tasks/{id}/milestones` & `/api/v1/treatment-milestones/{id}/evaluate` | `plan.review` | `MilestoneChecklistCreate` / `Evaluate` | Blocks task completion while pending; requires override reason when unmet (`TRT-012`) |
| GET/POST `/api/v1/treatment-plans/{id}/lifecycle` | `plan.read`/`plan.review` | `PlanLifecycleTransitionCreate` | Lossless `pause`/`resume`/`cancel`/`terminate` governance (`TRT-014`) |
| GET/POST `/api/v1/operations/waitlist`, `/{id}/prepare-outreach`, `/{id}/confirm-booking` | `appointment.read`/`write` | `WaitlistCreate` / `AppointmentCreate` | Consent-gated waitlist outreach + explicit staff slot booking (`SCH-008`) |
| GET/POST `/api/v1/finance/installments` & `/{id}/tranches/{tid}/log-reminder` | `finance.read`/`write` | `InstallmentScheduleCreate` | Requires active `financial` consent; `auto_charge_enabled=False` enforced (`FIN-008`) |
| GET/POST `/api/v1/operations/incidents` | `quality.report_read`/`report_create` | `QualityIncidentCreate` | Protected quality incident queue (`403` read for non-leadership; `422` on AI diagnosis, `HR-008`) |
| GET/POST `/api/v1/odontogram/legend`, PUT `/api/v1/patients/{id}/odontogram/restorations/{tooth}`, GET `/export` | `odontogram.read`/`write` | `OdontogramLegendCreate` / `RestorationUpsert` | Versioned legend (`ODN-006`), optimistic restoration revisions (`409` stale, `ODN-007`/`010`), and hashed export (`ODN-008`) |
| GET/POST `/api/v1/patients/{id}/referrals` & `/api/v1/referrals/{id}/review` | `referral.intake`/`review` | `ExternalReferralCreate` / `Review` | Quarantined external referral intake + clinician review (`EMR-013`) |
| GET `/api/v1/patients/{id}/document-eligibility` & `/api/v1/clinical-documents/{id}/structured-export` | `patient.read`/`clinical_doc.read` | eligibility / archive package | Non-destructive consent/allergy flags (`PAT-010`) and signed snapshot + attachment manifest export (`EMR-014`) |
| POST `/api/v1/org/branch-scope-grants` & GET `/api/v1/org/multi-branch-aggregates` | `staff.manage` | `BranchScopeGrantCreate` | Aggregate-only multi-branch owner KPIs without chart pooling (`ORG-007`) |
| GET/POST `/api/v1/auth/delegations` & `/{id}/revoke` | `staff.manage` | `TemporaryDelegationCreate` | Auto-expiring operational delegation (`422` on clinical signing delegation, `ORG-009`) |
| GET/POST `/api/v1/operations/staff-tasks`, `/escalate-overdue`, `/handoffs` | `operations.*`/`handoff.*` | `StaffOperationalTaskCreate` / `InternalHandoffCreate` | Overdue task escalations (`HR-005`) and patient/task-tied audited handoffs (`HR-006`) |
| GET/POST `/api/v1/patients/{id}/contact-timeline` & `/api/v1/crm/complaints` | `operations.recall`/`complaint.*` | `PatientContactLogCreate` / `ServiceComplaintCreate` | Portal-isolated `internal_staff_only` logs (`CRM-001`) and leadership-redacted complaint notes (`CRM-009`) |
| POST `/api/v1/ai/ops-assistant/query` | `context.read` + tool RBAC | `OpsAssistantQueryRequest` | Allowlisted read-only ops tools + injection firewall (`executed_any_write=False`, `AI-005`) |
| GET/POST `/api/v1/org/facility-profile` & `/scope-check` | `context.read`/`staff.manage` | `FacilityLicenseProfileCreate` | Explicit synthetic `DEMO-*`/`SYN-*` license scope (`422` unprefixed); never inferred from display name (`ORG-001`) |
| GET/POST `/api/v1/scheduling/duration-templates` & `/duration-estimate` | `appointment.read`/`plan.review` | `ProcedureDurationTemplateCreate` | Clinician-approved duration templates with 30-min safe fallback (`SCH-011`) |
| POST `/api/v1/scheduling/optimizer/propose` & `/proposals/{id}/accept` | `appointment.write` | `ScheduleOptimizerProposeRequest` / `Accept` | Non-mutating constraint slot optimizer (`altered_confirmed_appointments=0`) + explicit human booking (`SCH-012`) |
| GET/POST `/api/v1/finance/payments/{id}/receipt-exports` | `finance.read`/`write` | `FinancialReceiptExportCreate` | HMAC-signed traceable payment/allocation/ledger receipt (`409` on fabricated bank settlement claim, `FIN-013`) |
| GET/POST `/api/v1/hr/attendance` & `/api/v1/hr/overtime-summary` | `operations.checkin`/`staff.manage` | `StaffAttendanceCreate` | `Asia/Ho_Chi_Minh` local-date attendance & `>480m` overtime isolated from clinical authorship (`HR-001`, `HR-010`) |
| GET/POST `/api/v1/crm/reminder-templates` & `/api/v1/ai/communication-drafts` | `staff.manage`/`operations.recall` | `ReminderTemplateCreate` / `CommunicationDraftCreate` | Send-window, consent & injection-gated communication drafts (`auto_sent=False`, urgent clinical escalation, `CRM-002`, `AI-006`) |
| POST `/api/v1/crm/satisfaction/tokens`, `/submit`, GET `/summary` | `operations.checkin` / token / `dashboard.read` | `SatisfactionSurveySubmit` | Decoupled single-use anonymous 1–5 survey rejecting phone/email/ID PII (`422`, `CRM-011`) |
| GET/POST `/api/v1/migration/incumbent-exports`, `/{id}/approve-quarantine`, `/cutover-plans` | `migration.read`/`write`/`staff.manage` | `IncumbentExportIngestCreate` / `CutoverPlanCreate` | Canonical SHA-256 & export-license check, two-person quarantine review, and legacy write-freeze cutover guard (`INT-012`, `MIG-009`, `MIG-010`) |
| GET/POST `/api/v1/ops/telemetry-events` | `audit.read`/`operations.read` | `RedactedTelemetryCreate` | Scrubs sensitive note/PII keys, phones, emails, JWTs, and clinic patient names (`OPS-005`) |
| GET/POST `/api/v1/ops/onboarding-config` | `staff.manage` | `ClinicOnboardingConfigCreate` | Isolated per-clinic roles, catalog & form readiness check (`409` if unseeded in clinic, `OPS-010`) |
| POST `/api/v1/ops/support/grants`, `/{id}/revoke`, `/diagnostic-export` | `staff.manage` | `SupportConsentGrantCreate` / `ExportRequest` | Consent-gated redacted diagnostic bundle (`403` absent/revoked grant; `409` on live PHI, `OPS-012`) |
| GET/POST `/api/v1/security/incidents` & `/{id}/transition` | `staff.manage` | `SecurityIncidentCreate` / `Transition` | Preserves `AuditEvent` head digest; blocks `high`/`critical` close without counsel guidance (`SEC-012`) |
| POST `/api/v1/security/supply-chain/verify` | `staff.manage` | `SupplyChainVerifyRequest` | Verifies exact `==` Python pins + npm lockfile & signs CycloneDX-subset SBOM (`409` unpinned, `SEC-013`) |
| GET/POST `/api/v1/patients/{id}/access-requests` | `patient.read`/`consent.write` | `PatientAccessRequestCreate` | Verifies self/guardian authority (`403`), blocks clinical retention erasure (`409`), omits internal notes (`PAT-011`) |
| POST `/api/v1/scheduling/appointments/{id}/cancellation-recovery` | `appointment.write` | `CancellationRecoveryRequest` | FIFO consent-filtered waitlist candidates (`409` if uncancelled or clinical urgency inferred, `SCH-014`) |
| POST `/api/v1/patient-portal/uploads`, GET `/api/v1/portal/uploads`, POST `/{id}/review` | `patient_portal` / `referral.*` | `PortalUploadCreate` / `Review` | Blocks EICAR/PE/ELF/scripts (`422`) and holds clean PDFs/images in quarantine until clinician review (`PORT-008`) |
| POST `/api/v1/patient-portal/support-messages`, GET `/api/v1/portal/support-messages`, POST `/{id}/reply` | `patient_portal` / `handoff.*` | `PortalSupportMessageCreate` / `Reply` | Flags urgent symptoms for human triage (`OutboxEvent`), blocks AI autonomous replies (`422`, `PORT-010`) |
| GET/POST `/api/v1/hr/competencies`, `/validate-assignment`, GET `/api/v1/hr/commission-preview` | `staff.manage`/`appointment.write` | `StaffCompetencyUpsert` / `Validate` | Blocks expired competency assignments/procedures (`409`, `HR-009`) & separates performed vs collected (`HR-007`) |
| GET `/api/v1/dashboard` | `dashboard.read` | basic counts | No clinical or financial inference |
| GET `/api/v1/audit-events` | `audit.read` | demo history | Includes mutation and sensitive clinical read/denial events |

## HTTP and semantics
- 201 creation, 200 query/action, 401 unauthenticated/expired/revoked token, 403 unauthorized role/cross-origin/reused signed URL, 404 unknown/wrong-clinic scope, 409 immutable/conflict/precondition/clinical gate block, 422 validation error, 503 identity provider unavailable.
- IDs opaque UUID strings; never use phone as an identifier. All amounts integer VND, not float.
- Dates with timezone offset; stored UTC. UI displays clinic timezone.
