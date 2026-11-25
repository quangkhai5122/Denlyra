"""Loopback-only DEMO API. No legal EMR signing, medical decisions or real payments.

Supports T001 verified token/session + deny-by-default RBAC/ABAC foundation (ADR-007),
T002 atomic multi-resource booking, T003 quarantined FormRegistry, T004 synthetic
SignatureProvider envelope, T005 multi-dependency Treatment Journey (ADR-008),
T006 paper quarantine importer, T007 consent/lab partner portal, and T008 revenue ledger (ADR-009).
Never deploy this API publicly or import real patient data.
"""
from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import (
    ai_harness,
    archive_dr,
    audit_chain,
    auth,
    channel_contracts_zalo_sms_email,
    clinical_lifecycle,
    comms_satisfaction_cutover,
    continuity_governance,
    dicom_speech_accounting_security,
    facility_optimizer_receipts_hr,
    fhir_interop,
    governance_analytics,
    iac_insurance_lora_plan_attestation,
    inventory,
    models as m,
    odontogram_referrals_export,
    operations,
    ops_security_governance,
    org_crm_ops_assistant,
    patient_portal,
    portal_access_recovery_hr,
    release_sync_and_scheduling_ai,
    sandbox_contracts_benchmark_oidc,
    schemas as sch,
    services as svc,
    terminology_templates_lab_reports,
)
from .config import Settings
from .db import build_engine, init_demo_schema, session_factory
from .schemas import (
    AIDictationExtractRequest,
    AIDraftAcceptRequest,
    AITimelineSummaryRequest,
    AllocationCreate,
    AppointmentConfirmationCreate,
    AppointmentCreate,
    AppointmentReschedule,
    ArchiveLegalHoldRequest,
    ArchiveObjectCreate,
    BackupCreateRequest,
    BranchScopeGrantCreate,
    BreakGlassCreateRequest,
    BreakGlassReviewRequest,
    CashierReconciliationCreate,
    ChairTurnoverCompleteRequest,
    ChairTurnoverCreate,
    ChargeCreate,
    CheckinCreate,
    CheckinStatusUpdate,
    ConsentCreate,
    ConsentWithdrawRequest,
    DentalFindingCreate,
    DiscountDecisionRequest,
    DiscountRequestCreate,
    DocumentAddendumCreate,
    DocumentEnterInErrorRequest,
    DocumentSnapshotCreate,
    DocumentSyntheticSignRequest,
    EncounterCreate,
    EncounterDiagnosisCreate,
    EstimateAcceptRequest,
    EstimateCreate,
    EstimateFromCatalogCreate,
    ExternalReferralCreate,
    ExternalReferralReviewRequest,
    FhirBundleValidateRequest,
    FormOfficialExportRequest,
    FormTemplateCreate,
    FormValidatePreviewRequest,
    InstallmentScheduleCreate,
    InternalHandoffCreate,
    LabCaseCreate,
    LabPartnerGrantCreate,
    LabPartnerMilestoneUpdate,
    LabReceiveRequest,
    LabRemakeCreate,
    LabStateUpdate,
    MedicalRiskReviewCreate,
    MilestoneChecklistCreate,
    MilestoneEvaluateRequest,
    NoteCreate,
    NoteUpdate,
    OdontogramLegendCreate,
    OdontogramRestorationUpsert,
    OpsAssistantQueryRequest,
    PaperBatchCreate,
    PaperBatchRollbackRequest,
    PaperItemCreate,
    PaperItemVerifyLinkRequest,
    PatientContactLogCreate,
    PatientCreate,
    PatientMergeConfirmRequest,
    PatientMergeCreate,
    PatientMergeReverseRequest,
    PaymentCreate,
    PerformedProcedureCreate,
    PlanCreate,
    PlanLifecycleTransitionCreate,
    PlanReassessmentCreate,
    PortalGrantCreate,
    PortalInstructionPublish,
    PortalIntakeCreate,
    PortalPlanSummaryPublish,
    PortalRescheduleCreate,
    PortalRescheduleDecisionRequest,
    PriceCatalogCreate,
    PurchaseOrderCreate,
    PurchaseOrderReceiveRequest,
    QualityIncidentCreate,
    RecallCloseRequest,
    RecallCreate,
    RefundCreate,
    ResourceCreateRequest,
    ResourceDowntimeCreate,
    RestoreDrillRequest,
    ServiceComplaintCreate,
    SignedUrlCreateRequest,
    SkuCreate,
    StaffCreateRequest,
    StaffOperationalTaskCreate,
    StaffShiftCreate,
    StockAdjustmentApproveRequest,
    StockAdjustmentCreate,
    StockConsumptionCreate,
    StockReservationCreate,
    StockReservationReleaseRequest,
    SupplierCreate,
    TaskCoordinationLinkCreate,
    TaskCreate,
    TaskDependenciesUpdate,
    TemporaryDelegationCreate,
    TokenIssueRequest,
    WaitlistCreate,
    CommunicationDraftCreate,
    FacilityLicenseProfileCreate,
    FinancialReceiptExportCreate,
    IncumbentExportApproveRequest,
    IncumbentExportIngestCreate,
    MigrationCutoverPlanCreate,
    ProcedureDurationTemplateCreate,
    ReminderTemplateCreate,
    SatisfactionSurveySubmit,
    SatisfactionTokenIssueRequest,
    ScheduleOptimizerAcceptRequest,
    ScheduleOptimizerProposeRequest,
    StaffAttendanceCreate,
    CancellationRecoveryRequest,
    ClinicOnboardingConfigCreate,
    PatientAccessRequestCreate,
    PortalSupportMessageCreate,
    PortalSupportReplyRequest,
    PortalUploadCreate,
    PortalUploadReviewRequest,
    RedactedTelemetryCreate,
    SecurityIncidentCreate,
    SecurityIncidentTransitionRequest,
    StaffCompetencyUpsert,
    StaffCompetencyValidateRequest,
    SupplyChainVerifyRequest,
    SupportConsentGrantCreate,
    SupportDiagnosticExportRequest,
)

ROOT = Path(__file__).resolve().parents[3]
DEMO_WEB = ROOT / "apps" / "demo-web"


def doc(item):
    """Serialize only fields explicitly safe for synthetic demo output."""
    output = {}
    for column in item.__table__.columns:
        if column.name in {
            "metadata_json",
            "wrapped_dek_b64",
            "manifest_json",
            "extracted_json",
            "details_json",
        }:
            continue
        value = getattr(item, column.name)
        output[column.name] = value.isoformat() + "Z" if isinstance(value, datetime) else value
    return output


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    cfg.validate()
    engine = build_engine(cfg.db_url)
    factory = session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app):
        init_demo_schema(engine)
        with factory() as db:
            svc.demo_seed(db)
        yield
        engine.dispose()

    app = FastAPI(
        title="Denlyra Foundation — SYNTHETIC DEMO ONLY",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )

    @app.middleware("http")
    async def demo_guard(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse(status_code=403, content={"detail": "Cross-site request rejected"})
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                return JSONResponse(status_code=403, content={"detail": "Cross-origin request rejected"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Denlyra-Demo-Only"] = "no-real-patient-data"
        return response

    def get_db() -> Generator[Session, None, None]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    def resolve_ctx(
        db: Session = Depends(get_db),
        authorization: str | None = Header(None),
        x_demo_clinic: str | None = Header(None),
        x_demo_actor: str | None = Header(None),
    ) -> tuple[Session, str, str, auth.Principal]:
        if not cfg.auth_provider_available:
            raise HTTPException(503, "Identity provider unavailable; failing closed")
        if authorization:
            scheme, _, raw_token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not raw_token.strip():
                raise HTTPException(401, "Bearer token required")
            principal = auth.resolve_principal_from_token(db, raw_token.strip(), cfg.auth_secret)
            if x_demo_clinic and x_demo_clinic != principal.clinic_id:
                svc.audit(
                    db,
                    principal.clinic_id,
                    principal.actor_label,
                    "auth.clinic_header_mismatch_denied",
                    "clinic",
                    x_demo_clinic[:36],
                )
                db.commit()
                raise HTTPException(403, "Mismatched clinic scope between token and header")
            return db, principal.clinic_id, principal.actor_label, principal
        if cfg.require_auth:
            raise HTTPException(
                401,
                "Authentication required: X-Demo-* headers are not accepted when require_auth is enabled",
            )
        clinic_id = x_demo_clinic or svc.DEMO_CLINICS[0][0]
        clinic = db.get(m.Clinic, clinic_id)
        if not clinic or not clinic.demo_only:
            raise HTTPException(404, "Demo clinic not found")
        actor = (x_demo_actor or "demo-operator")[:100]
        dentist_staff = db.scalar(
            select(m.Staff).where(m.Staff.clinic_id == clinic_id, m.Staff.role == "dentist")
        )
        legacy_principal = auth.Principal(
            staff_id=dentist_staff.id if dentist_staff else "demo-legacy",
            clinic_id=clinic_id,
            branch_id="branch-main",
            role="dentist",
            actor_label=actor,
            jti="legacy-demo",
            authenticated=False,
        )
        return db, clinic_id, actor, legacy_principal

    def require_perm(permission: str, audit_read: bool = False):
        def _dep(ctx_tuple: tuple[Session, str, str, auth.Principal] = Depends(resolve_ctx)):
            db, clinic_id, actor, principal = ctx_tuple
            if principal.authenticated or cfg.require_auth:
                auth.check_permission(
                    db,
                    principal,
                    permission,
                    subject_type=permission.split(".")[0],
                    subject_id=clinic_id,
                    audit_read=audit_read,
                )
            return db, clinic_id, actor

        return _dep

    def require_principal_perm(permission: str, audit_read: bool = False):
        def _dep(ctx_tuple: tuple[Session, str, str, auth.Principal] = Depends(resolve_ctx)):
            db, clinic_id, actor, principal = ctx_tuple
            if principal.authenticated or cfg.require_auth:
                auth.check_permission(
                    db,
                    principal,
                    permission,
                    subject_type=permission.split(".")[0],
                    subject_id=clinic_id,
                    audit_read=audit_read,
                )
            return db, clinic_id, actor, principal

        return _dep

    @app.get("/health")
    def health():
        return {"status": "ok", "demo_only": True, "certified_emr": False}

    @app.get("/api/v1/capabilities")
    def capabilities():
        return {
            "demo_only": True,
            "use_real_patients": False,
            "clinical_e_signature": False,
            "emr_certified": False,
            "patient_portal": False,
            "synthetic_patient_portal_foundation": True,
            "production_auth": False,
            "synthetic_auth_foundation": True,
            "synthetic_signature_test_double": True,
            "ai_diagnosis": False,
            "ai_sends_patient_data": False,
            "hospital_integration": False,
            "live_payments": False,
            "postgres_concurrent_booking_verified": False,
            "real_data_import": False,
            "legacy_paper_legal_conversion": False,
        }

    @app.post("/api/v1/auth/token", status_code=201)
    def issue_token(payload: TokenIssueRequest, db: Session = Depends(get_db)):
        if not cfg.auth_provider_available:
            raise HTTPException(503, "Identity provider unavailable; failing closed")
        return auth.issue_synthetic_staff_token(
            db=db,
            secret=cfg.auth_secret,
            clinic_id=payload.clinic_id,
            role=payload.role,
            staff_id=payload.staff_id,
            branch_id=payload.branch_id,
            ttl_seconds=payload.ttl_seconds,
        )

    @app.post("/api/v1/auth/revoke")
    def revoke_session(ctx_tuple=Depends(resolve_ctx)):
        db, _, _, principal = ctx_tuple
        if not principal.authenticated:
            raise HTTPException(401, "Bearer token required to revoke session")
        auth.revoke_token(db, principal)
        return {"status": "revoked", "jti": principal.jti}

    @app.post("/api/v1/auth/signed-urls", status_code=201)
    def mint_signed_url(payload: SignedUrlCreateRequest, ctx_tuple=Depends(resolve_ctx)):
        db, _, _, principal = ctx_tuple
        if not principal.authenticated:
            raise HTTPException(401, "Bearer token required to mint signed URL")
        return auth.create_signed_url_grant(
            db=db,
            principal=principal,
            secret=cfg.auth_secret,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            ttl_seconds=payload.ttl_seconds,
        )

    @app.get("/api/v1/signed-download/{grant_token}")
    def download_signed_url(grant_token: str, ctx_tuple=Depends(resolve_ctx)):
        db, _, _, principal = ctx_tuple
        if not principal.authenticated:
            raise HTTPException(401, "Bearer token required to consume signed URL")
        return auth.consume_signed_url_grant(db, principal, cfg.auth_secret, grant_token)

    @app.post("/api/v1/staff", status_code=201)
    def create_staff(payload: StaffCreateRequest, context=Depends(require_perm("staff.manage"))):
        db, clinic_id, actor = context
        return doc(svc.create_staff(db, clinic_id, payload, actor))

    @app.post("/api/v1/staff/{staff_id}/deactivate")
    def deactivate_staff(staff_id: str, context=Depends(require_perm("staff.manage"))):
        db, clinic_id, actor = context
        return doc(svc.deactivate_staff(db, clinic_id, staff_id, actor))

    @app.post("/api/v1/resources", status_code=201)
    def create_resource(
        payload: ResourceCreateRequest, context=Depends(require_perm("resource.manage"))
    ):
        db, clinic_id, actor = context
        return doc(svc.create_resource(db, clinic_id, payload, actor))

    @app.get("/api/v1/demo/context")
    def context(context=Depends(require_perm("context.read"))):
        db, clinic_id, _ = context
        return {
            "clinics": [doc(c) for c in db.scalars(select(m.Clinic)).all()],
            "clinic_id": clinic_id,
            "staff": [
                doc(s) for s in db.scalars(select(m.Staff).where(m.Staff.clinic_id == clinic_id))
            ],
            "chairs": [
                doc(r)
                for r in db.scalars(
                    select(m.Resource).where(
                        m.Resource.clinic_id == clinic_id, m.Resource.kind == "chair"
                    )
                )
            ],
            "warning": "Synthetic demo only. Headers are not authentication. No legal EMR signature.",
        }

    @app.get("/api/v1/patients")
    def list_patients(context=Depends(require_perm("patient.read"))):
        db, clinic_id, _ = context
        return [
            doc(p)
            for p in db.scalars(
                select(m.Patient)
                .where(m.Patient.clinic_id == clinic_id)
                .order_by(m.Patient.created_at.desc())
            )
        ]

    @app.post("/api/v1/patients", status_code=201)
    def create_patient(payload: PatientCreate, context=Depends(require_perm("patient.write"))):
        db, clinic_id, actor = context
        patient = m.Patient(
            clinic_id=clinic_id,
            display_name=payload.display_name.strip(),
            birth_year=payload.birth_year,
            phone_demo=payload.phone_demo,
        )
        db.add(patient)
        db.flush()
        svc.audit(db, clinic_id, actor, "patient.created_demo", "patient", patient.id)
        db.commit()
        return doc(patient)

    @app.get("/api/v1/patients/page")
    def list_patients_paginated(
        q: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
        context=Depends(require_perm("patient.read")),
    ):
        db, clinic_id, _ = context
        return audit_chain.paginate_patients(db, clinic_id, cfg.auth_secret, q, limit, cursor)

    @app.get("/api/v1/patients/merges")
    def list_patient_merges(context=Depends(require_perm("patient.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.PatientMergeRequest)
            .where(m.PatientMergeRequest.clinic_id == clinic_id)
            .order_by(m.PatientMergeRequest.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/patients/merges", status_code=201)
    def request_patient_merge(
        payload: PatientMergeCreate,
        ctx_tuple=Depends(require_principal_perm("patient.merge_request")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            patient_portal.create_patient_merge_request(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/patients/merges/{merge_id}/confirm")
    def confirm_patient_merge(
        merge_id: str,
        payload: PatientMergeConfirmRequest,
        ctx_tuple=Depends(require_principal_perm("patient.merge_approve")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            patient_portal.confirm_patient_merge_request(
                db, clinic_id, merge_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/patients/merges/{merge_id}/reverse")
    def reverse_patient_merge(
        merge_id: str,
        payload: PatientMergeReverseRequest,
        ctx_tuple=Depends(require_principal_perm("patient.merge_approve")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            patient_portal.reverse_patient_merge_request(
                db, clinic_id, merge_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/patients/{patient_id}")
    def get_patient(patient_id: str, context=Depends(require_perm("patient.read"))):
        db, clinic_id, _ = context
        return doc(svc.ensure(db, m.Patient, patient_id, clinic_id))

    @app.get("/api/v1/patients/{patient_id}/unified-summary")
    def get_patient_unified_summary(
        patient_id: str, context=Depends(require_perm("patient.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        return patient_portal.get_patient_unified_summary(db, clinic_id, patient_id)

    @app.post("/api/v1/consents", status_code=201)
    def create_consent(payload: ConsentCreate, context=Depends(require_perm("consent.write"))):
        db, clinic_id, actor = context
        return doc(svc.create_consent(db, clinic_id, payload, actor))

    @app.get("/api/v1/patients/{patient_id}/consents")
    def list_patient_consents(
        patient_id: str, context=Depends(require_perm("consent.read"))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Patient, patient_id, clinic_id)
        rows = db.scalars(
            select(m.ConsentRecord)
            .where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == patient_id,
            )
            .order_by(m.ConsentRecord.created_at)
        ).all()
        return [doc(c) for c in rows]

    @app.post("/api/v1/consents/{consent_id}/withdraw")
    def withdraw_consent(
        consent_id: str,
        payload: ConsentWithdrawRequest,
        context=Depends(require_perm("consent.write")),
    ):
        db, clinic_id, actor = context
        return doc(svc.withdraw_consent(db, clinic_id, consent_id, payload, actor))

    @app.get("/api/v1/appointments")
    def appointments(context=Depends(require_perm("appointment.read"))):
        db, clinic_id, _ = context
        return [
            doc(a)
            for a in db.scalars(
                select(m.Appointment)
                .where(m.Appointment.clinic_id == clinic_id)
                .order_by(m.Appointment.start_at)
            )
        ]

    @app.post("/api/v1/appointments", status_code=201)
    def create_appointment(
        payload: AppointmentCreate, context=Depends(require_perm("appointment.write"))
    ):
        db, clinic_id, actor = context
        return doc(svc.schedule(db, clinic_id, payload, actor))

    @app.get("/api/v1/appointments/page")
    def list_appointments_paginated(
        limit: int = 20,
        cursor: str | None = None,
        context=Depends(require_perm("appointment.read")),
    ):
        db, clinic_id, _ = context
        return audit_chain.paginate_appointments(db, clinic_id, cfg.auth_secret, limit, cursor)

    @app.get("/api/v1/appointments/{appointment_id}/confirmations")
    def get_appointment_confirmations(
        appointment_id: str, context=Depends(require_perm("appointment.read"))
    ):
        db, clinic_id, _ = context
        return operations.get_appointment_confirmation_summary(db, clinic_id, appointment_id)

    @app.post("/api/v1/appointments/{appointment_id}/confirmations", status_code=201)
    def post_appointment_confirmation(
        appointment_id: str,
        payload: AppointmentConfirmationCreate,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            operations.record_appointment_confirmation(
                db, clinic_id, appointment_id, payload, actor
            )
        )

    @app.post("/api/v1/appointments/{appointment_id}/cancel")
    def cancel(appointment_id: str, context=Depends(require_perm("appointment.write"))):
        db, clinic_id, actor = context
        return doc(svc.cancel_appointment(db, clinic_id, appointment_id, actor))

    @app.post("/api/v1/appointments/{appointment_id}/reschedule", status_code=201)
    def reschedule(
        appointment_id: str,
        payload: AppointmentReschedule,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return doc(svc.reschedule_appointment(db, clinic_id, appointment_id, payload, actor))

    @app.get("/api/v1/encounters")
    def encounters(context=Depends(require_perm("encounter.read", audit_read=True))):
        db, clinic_id, _ = context
        return [
            doc(e)
            for e in db.scalars(
                select(m.Encounter)
                .where(m.Encounter.clinic_id == clinic_id)
                .order_by(m.Encounter.created_at.desc())
            )
        ]

    @app.post("/api/v1/encounters", status_code=201)
    def create_encounter(
        payload: EncounterCreate, context=Depends(require_perm("encounter.create"))
    ):
        db, clinic_id, actor = context
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        svc._assert_not_merged_secondary(db, clinic_id, payload.patient_id)
        svc.doctor(db, payload.practitioner_id, clinic_id)
        item = m.Encounter(
            clinic_id=clinic_id,
            patient_id=payload.patient_id,
            practitioner_id=payload.practitioner_id,
        )
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "encounter.created_demo", "encounter", item.id)
        db.commit()
        return doc(item)

    @app.get("/api/v1/encounters/{encounter_id}/notes")
    def list_notes(
        encounter_id: str, context=Depends(require_perm("note.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        notes = db.scalars(
            select(m.ClinicalNote).where(m.ClinicalNote.encounter_id == encounter_id)
        ).all()
        out = []
        for note in notes:
            item = doc(note)
            item["revisions"] = [
                doc(r)
                for r in db.scalars(
                    select(m.NoteRevision)
                    .where(m.NoteRevision.note_id == note.id)
                    .order_by(m.NoteRevision.revision_no)
                )
            ]
            out.append(item)
        return out

    @app.post("/api/v1/encounters/{encounter_id}/notes", status_code=201)
    def create_note(
        encounter_id: str, payload: NoteCreate, context=Depends(require_perm("note.write"))
    ):
        db, clinic_id, actor = context
        note = svc.create_note(
            db, clinic_id, encounter_id, payload.content, actor, payload.parent_note_id
        )
        return doc(note)

    @app.put("/api/v1/notes/{note_id}")
    def revise_note(
        note_id: str, payload: NoteUpdate, context=Depends(require_perm("note.write"))
    ):
        db, clinic_id, actor = context
        return doc(
            svc.update_note(
                db, clinic_id, note_id, payload.content, payload.expected_revision, actor
            )
        )

    @app.post("/api/v1/notes/{note_id}/demo-lock")
    def lock_note(note_id: str, context=Depends(require_perm("note.lock"))):
        db, clinic_id, actor = context
        return doc(svc.lock_note_demo(db, clinic_id, note_id, actor))

    @app.post("/api/v1/clinical-documents/snapshots", status_code=201)
    def prepare_snapshot(
        payload: DocumentSnapshotCreate,
        context=Depends(require_perm("clinical_doc.write")),
    ):
        db, clinic_id, actor = context
        snap = svc.create_document_snapshot(db, clinic_id, payload, actor)
        return svc._serialize_snapshot(snap)

    @app.get("/api/v1/clinical-documents/{snapshot_id}")
    def get_snapshot(
        snapshot_id: str,
        context=Depends(require_perm("clinical_doc.read", audit_read=True)),
    ):
        db, clinic_id, _ = context
        snap = svc.ensure(db, m.ClinicalDocumentSnapshot, snapshot_id, clinic_id)
        return svc._serialize_snapshot(snap)

    @app.post("/api/v1/clinical-documents/{snapshot_id}/sign-synthetic")
    def sign_snapshot_synthetic(
        snapshot_id: str,
        payload: DocumentSyntheticSignRequest,
        ctx_tuple=Depends(require_principal_perm("clinical_doc.sign")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return svc.sign_document_snapshot_synthetic(
            db=db,
            clinic_id=clinic_id,
            snapshot_id=snapshot_id,
            signer_staff_id=principal.staff_id,
            actor=actor,
            secret=cfg.auth_secret,
            data=payload,
        )

    @app.get("/api/v1/clinical-documents/{snapshot_id}/verify")
    def verify_snapshot(
        snapshot_id: str,
        context=Depends(require_perm("clinical_doc.read", audit_read=True)),
    ):
        db, clinic_id, _ = context
        return svc.verify_document_snapshot(db, clinic_id, snapshot_id, cfg.auth_secret)

    @app.post("/api/v1/clinical-documents/{snapshot_id}/addenda", status_code=201)
    def create_snapshot_addendum(
        snapshot_id: str,
        payload: DocumentAddendumCreate,
        context=Depends(require_perm("clinical_doc.write")),
    ):
        db, clinic_id, actor = context
        return svc.create_document_addendum(db, clinic_id, snapshot_id, payload, actor)

    @app.post("/api/v1/clinical-documents/{snapshot_id}/enter-in-error")
    def mark_snapshot_entered_in_error(
        snapshot_id: str,
        payload: DocumentEnterInErrorRequest,
        context=Depends(require_perm("clinical_doc.write")),
    ):
        db, clinic_id, actor = context
        return svc.enter_document_in_error(db, clinic_id, snapshot_id, payload, actor)

    @app.get("/api/v1/encounters/{encounter_id}/findings")
    def list_dental_findings(
        encounter_id: str, context=Depends(require_perm("finding.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        rows = db.scalars(
            select(m.DentalFinding)
            .where(
                m.DentalFinding.clinic_id == clinic_id,
                m.DentalFinding.encounter_id == encounter_id,
            )
            .order_by(m.DentalFinding.created_at)
        ).all()
        return [doc(x) for x in rows]

    @app.post("/api/v1/encounters/{encounter_id}/findings", status_code=201)
    def add_dental_finding(
        encounter_id: str,
        payload: DentalFindingCreate,
        context=Depends(require_perm("finding.write")),
    ):
        db, clinic_id, actor = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        item = m.DentalFinding(
            clinic_id=clinic_id,
            encounter_id=encounter_id,
            tooth_code=payload.tooth_code,
            surface=payload.surface,
            finding_text_demo=payload.finding_text_demo,
            actor_demo=actor,
        )
        db.add(item)
        db.flush()
        svc.audit(
            db,
            clinic_id,
            actor,
            "odontogram.demo_finding_added",
            "dental_finding",
            item.id,
            {"tooth_code": payload.tooth_code, "surface": payload.surface},
        )
        db.commit()
        return doc(item)

    @app.get("/api/v1/patients/{patient_id}/odontogram")
    def patient_odontogram(
        patient_id: str, context=Depends(require_perm("odontogram.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Patient, patient_id, clinic_id)
        rows = db.scalars(
            select(m.DentalFinding)
            .join(m.Encounter, m.DentalFinding.encounter_id == m.Encounter.id)
            .where(
                m.Encounter.clinic_id == clinic_id,
                m.Encounter.patient_id == patient_id,
            )
            .order_by(m.DentalFinding.created_at)
        ).all()
        procs = db.scalars(
            select(m.PerformedProcedureEvidence)
            .where(
                m.PerformedProcedureEvidence.clinic_id == clinic_id,
                m.PerformedProcedureEvidence.patient_id == patient_id,
            )
            .order_by(m.PerformedProcedureEvidence.created_at)
        ).all()
        return {
            "patient_id": patient_id,
            "findings": [doc(x) for x in rows],
            "performed_procedures": [doc(p) for p in procs],
            "warning": "Demo FDI events only, not a clinical chart or diagnosis.",
        }

    @app.get("/api/v1/treatment-plans")
    def list_plans(context=Depends(require_perm("plan.read"))):
        db, clinic_id, _ = context
        plans = db.scalars(
            select(m.TreatmentPlan).where(m.TreatmentPlan.clinic_id == clinic_id)
        ).all()
        return [doc(p) for p in plans]

    @app.post("/api/v1/treatment-plans", status_code=201)
    def create_plan(payload: PlanCreate, context=Depends(require_perm("plan.write"))):
        db, clinic_id, actor = context
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        plan = m.TreatmentPlan(
            clinic_id=clinic_id, patient_id=payload.patient_id, title=payload.title
        )
        db.add(plan)
        db.flush()
        version = m.PlanVersion(plan_id=plan.id, number=1)
        db.add(version)
        db.flush()
        svc.audit(db, clinic_id, actor, "plan.draft_created", "treatment_plan", plan.id)
        db.commit()
        return {**doc(plan), "version_id": version.id, "status": version.status}

    @app.get("/api/v1/treatment-plans/{plan_id}")
    def get_plan(plan_id: str, context=Depends(require_perm("plan.read"))):
        db, clinic_id, _ = context
        plan, version = svc.get_plan_version(db, clinic_id, plan_id)
        tasks = db.scalars(
            select(m.PlanTask).where(m.PlanTask.plan_version_id == version.id)
        ).all()
        return {"plan": doc(plan), "version": doc(version), "tasks": [doc(t) for t in tasks]}

    @app.get("/api/v1/treatment-plans/{plan_id}/timeline")
    def plan_timeline(plan_id: str, context=Depends(require_perm("plan.read"))):
        db, clinic_id, _ = context
        return svc.get_plan_timeline(db, clinic_id, plan_id)

    @app.post("/api/v1/treatment-plans/{plan_id}/tasks", status_code=201)
    def add_task(
        plan_id: str, payload: TaskCreate, context=Depends(require_perm("plan.write"))
    ):
        db, clinic_id, actor = context
        return doc(svc.add_task(db, clinic_id, plan_id, payload, actor))

    @app.post("/api/v1/treatment-tasks/{task_id}/dependencies")
    def update_task_dependencies(
        task_id: str,
        payload: TaskDependenciesUpdate,
        context=Depends(require_perm("plan.write")),
    ):
        db, clinic_id, actor = context
        return doc(svc.set_task_dependencies(db, clinic_id, task_id, payload, actor))

    @app.post("/api/v1/treatment-tasks/{task_id}/links", status_code=201)
    def link_task(
        task_id: str,
        payload: TaskCoordinationLinkCreate,
        context=Depends(require_perm("plan.write")),
    ):
        db, clinic_id, actor = context
        return svc.link_task_coordination(db, clinic_id, task_id, payload, actor)

    @app.post("/api/v1/treatment-plans/{plan_id}/demo-review")
    def review_plan(plan_id: str, context=Depends(require_perm("plan.review"))):
        db, clinic_id, actor = context
        return doc(svc.review_plan_demo(db, clinic_id, plan_id, actor))

    @app.post("/api/v1/treatment-plans/{plan_id}/versions", status_code=201)
    def plan_new_version(plan_id: str, context=Depends(require_perm("plan.write"))):
        db, clinic_id, actor = context
        return doc(svc.new_version(db, clinic_id, plan_id, actor))

    @app.post("/api/v1/treatment-plans/{plan_id}/reassessments", status_code=201)
    def plan_reassess(
        plan_id: str,
        payload: PlanReassessmentCreate,
        context=Depends(require_perm("plan.reassess")),
    ):
        db, clinic_id, actor = context
        return svc.reassess_plan(db, clinic_id, plan_id, payload, actor)

    @app.post("/api/v1/treatment-tasks/{task_id}/demo-complete")
    def complete_task(
        task_id: str, context=Depends(require_perm("plan.complete_task"))
    ):
        db, clinic_id, actor = context
        return doc(svc.complete_task_demo(db, clinic_id, task_id, actor))

    @app.get("/api/v1/lab-cases")
    def list_lab(context=Depends(require_perm("lab.read"))):
        db, clinic_id, _ = context
        return [
            doc(x)
            for x in db.scalars(select(m.LabCase).where(m.LabCase.clinic_id == clinic_id))
        ]

    @app.post("/api/v1/lab-cases", status_code=201)
    def new_lab(payload: LabCaseCreate, context=Depends(require_perm("lab.write"))):
        db, clinic_id, actor = context
        return doc(svc.create_lab_case(db, clinic_id, payload, actor))

    @app.get("/api/v1/lab-cases/{lab_id}/alerts")
    def lab_alerts(lab_id: str, context=Depends(require_perm("lab.read"))):
        db, clinic_id, _ = context
        return svc.get_lab_alerts(db, clinic_id, lab_id)

    @app.post("/api/v1/lab-cases/{lab_id}/partner-grants", status_code=201)
    def mint_lab_partner_grant(
        lab_id: str,
        payload: LabPartnerGrantCreate,
        ctx_tuple=Depends(require_principal_perm("lab.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return svc.create_lab_partner_grant(
            db, clinic_id, lab_id, principal.staff_id, actor, cfg.auth_secret, payload
        )

    @app.get("/api/v1/lab-portal/cases/{grant_token}")
    def get_lab_portal_case(
        grant_token: str,
        db: Session = Depends(get_db),
        x_demo_clinic: str | None = Header(None),
    ):
        return svc.get_lab_portal_case(db, grant_token, cfg.auth_secret, x_demo_clinic)

    @app.post("/api/v1/lab-portal/cases/{grant_token}/milestones")
    def update_lab_portal_milestone(
        grant_token: str,
        payload: LabPartnerMilestoneUpdate,
        db: Session = Depends(get_db),
        x_demo_clinic: str | None = Header(None),
    ):
        return svc.update_lab_portal_milestone(
            db, grant_token, cfg.auth_secret, payload, x_demo_clinic
        )

    @app.post("/api/v1/lab-cases/{lab_id}/receive")
    def receive_lab(
        lab_id: str,
        payload: LabReceiveRequest,
        context=Depends(require_perm("lab.write")),
    ):
        db, clinic_id, actor = context
        return doc(svc.receive_lab_case(db, clinic_id, lab_id, payload, actor))

    @app.post("/api/v1/lab-cases/{lab_id}/remakes", status_code=201)
    def remake_lab(
        lab_id: str,
        payload: LabRemakeCreate,
        context=Depends(require_perm("lab.write")),
    ):
        db, clinic_id, actor = context
        return doc(svc.remake_lab_case(db, clinic_id, lab_id, payload, actor))

    @app.post("/api/v1/lab-cases/{lab_id}/state")
    def lab_transition(
        lab_id: str, payload: LabStateUpdate, context=Depends(require_perm("lab.write"))
    ):
        db, clinic_id, actor = context
        return doc(svc.set_lab_status(db, clinic_id, lab_id, payload.next_status, actor))

    @app.post("/api/v1/finance/estimates", status_code=201)
    def create_estimate(
        payload: EstimateCreate, context=Depends(require_perm("finance.write"))
    ):
        db, clinic_id, actor = context
        return doc(svc.create_estimate(db, clinic_id, payload, actor))

    @app.post("/api/v1/finance/estimates/{estimate_id}/accept")
    def accept_estimate(
        estimate_id: str,
        payload: EstimateAcceptRequest,
        context=Depends(require_perm("finance.write")),
    ):
        db, clinic_id, actor = context
        return doc(svc.accept_estimate(db, clinic_id, estimate_id, payload, actor))

    @app.get("/api/v1/finance/charges")
    def list_charges(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        return [
            doc(c)
            for c in db.scalars(select(m.Charge).where(m.Charge.clinic_id == clinic_id))
        ]

    @app.post("/api/v1/finance/charges", status_code=201)
    def new_charge(payload: ChargeCreate, context=Depends(require_perm("finance.write"))):
        db, clinic_id, actor = context
        return doc(svc.create_charge(db, clinic_id, payload, actor))

    @app.get("/api/v1/finance/payments")
    def list_payments(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        return [
            doc(p)
            for p in db.scalars(select(m.Payment).where(m.Payment.clinic_id == clinic_id))
        ]

    @app.post("/api/v1/finance/payments", status_code=201)
    def new_payment(payload: PaymentCreate, context=Depends(require_perm("finance.write"))):
        db, clinic_id, actor = context
        return doc(svc.create_payment(db, clinic_id, payload, actor))

    @app.post("/api/v1/finance/allocations", status_code=201)
    def new_allocation(
        payload: AllocationCreate, context=Depends(require_perm("finance.allocate"))
    ):
        db, clinic_id, actor = context
        return doc(
            svc.allocate(
                db,
                clinic_id,
                payload.charge_id,
                payload.payment_id,
                payload.amount_vnd,
                actor,
                idempotency_key=payload.idempotency_key,
            )
        )

    @app.post("/api/v1/finance/payments/{payment_id}/refunds", status_code=201)
    def new_refund(
        payment_id: str,
        payload: RefundCreate,
        context=Depends(require_perm("finance.refund")),
    ):
        db, clinic_id, actor = context
        return doc(svc.refund_payment(db, clinic_id, payment_id, payload, actor))

    @app.get("/api/v1/patients/{patient_id}/revenue-account")
    def get_revenue_account(
        patient_id: str, context=Depends(require_perm("finance.read"))
    ):
        db, clinic_id, _ = context
        return svc.get_patient_revenue_account(db, clinic_id, patient_id)

    @app.post("/api/v1/finance/reconciliations", status_code=201)
    def reconcile_cashier(
        payload: CashierReconciliationCreate,
        context=Depends(require_perm("finance.allocate")),
    ):
        db, clinic_id, actor = context
        return doc(svc.reconcile_cashier_daily(db, clinic_id, payload, actor))

    @app.post("/api/v1/migrations/paper-batches", status_code=201)
    def create_paper_batch(
        payload: PaperBatchCreate, context=Depends(require_perm("migration.write"))
    ):
        db, clinic_id, actor = context
        return doc(svc.create_paper_batch(db, clinic_id, payload, actor))

    @app.post("/api/v1/migrations/paper-batches/{batch_id}/items", status_code=201)
    def ingest_paper_item(
        batch_id: str,
        payload: PaperItemCreate,
        context=Depends(require_perm("migration.write")),
    ):
        db, clinic_id, actor = context
        return svc.ingest_paper_item(db, clinic_id, batch_id, payload, actor)

    @app.post("/api/v1/migrations/paper-items/{item_id}/verify-link")
    def verify_paper_item(
        item_id: str,
        payload: PaperItemVerifyLinkRequest,
        context=Depends(require_perm("migration.write")),
    ):
        db, clinic_id, actor = context
        return svc.verify_and_link_paper_item(db, clinic_id, item_id, payload, actor)

    @app.get("/api/v1/migrations/paper-batches/{batch_id}/reconciliation")
    def paper_batch_reconciliation(
        batch_id: str, context=Depends(require_perm("migration.read"))
    ):
        db, clinic_id, _ = context
        return svc.get_paper_batch_reconciliation(db, clinic_id, batch_id)

    @app.post("/api/v1/migrations/paper-batches/{batch_id}/rollback")
    def paper_batch_rollback(
        batch_id: str,
        payload: PaperBatchRollbackRequest,
        context=Depends(require_perm("migration.write")),
    ):
        db, clinic_id, actor = context
        return svc.rollback_paper_batch(db, clinic_id, batch_id, payload, actor)

    @app.get("/api/v1/clinical-forms/templates")
    def get_form_templates(context=Depends(require_perm("clinical_form.read"))):
        db, clinic_id, _ = context
        return svc.list_form_templates(db, clinic_id)

    @app.post("/api/v1/clinical-forms/templates", status_code=201)
    def create_form_template(
        payload: FormTemplateCreate, context=Depends(require_perm("clinical_form.write"))
    ):
        db, clinic_id, actor = context
        return svc.register_form_template(db, clinic_id, payload, actor)

    @app.post("/api/v1/clinical-forms/templates/{template_id}/approve")
    def approve_form_template(
        template_id: str, context=Depends(require_perm("clinical_form.write"))
    ):
        db, clinic_id, actor = context
        return svc.approve_form_template_blocked(db, clinic_id, template_id, actor)

    @app.post("/api/v1/clinical-forms/validate-preview")
    def validate_form(
        payload: FormValidatePreviewRequest,
        context=Depends(require_perm("clinical_form.read")),
    ):
        db, clinic_id, actor = context
        return svc.validate_form_preview(db, clinic_id, payload, actor)

    @app.post("/api/v1/clinical-forms/official-export")
    def export_official_form(
        payload: FormOfficialExportRequest,
        context=Depends(require_perm("clinical_form.write")),
    ):
        db, clinic_id, actor = context
        return svc.export_official_form_blocked(db, clinic_id, payload, actor)

    @app.get("/api/v1/encounters/{encounter_id}/snapshots")
    def list_encounter_snapshots(
        encounter_id: str,
        context=Depends(require_perm("clinical_doc.read", audit_read=True)),
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        rows = db.scalars(
            select(m.ClinicalDocumentSnapshot)
            .where(
                m.ClinicalDocumentSnapshot.clinic_id == clinic_id,
                m.ClinicalDocumentSnapshot.encounter_id == encounter_id,
            )
            .order_by(m.ClinicalDocumentSnapshot.created_at)
        ).all()
        return [svc._serialize_snapshot(s) for s in rows]

    @app.get("/api/v1/finance/estimates")
    def list_estimates(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        return [
            doc(e)
            for e in db.scalars(
                select(m.EstimateVersion)
                .where(m.EstimateVersion.clinic_id == clinic_id)
                .order_by(m.EstimateVersion.created_at.desc())
            )
        ]

    @app.get("/api/v1/finance/reconciliations")
    def list_reconciliations(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        return [
            doc(r)
            for r in db.scalars(
                select(m.CashierReconciliation)
                .where(m.CashierReconciliation.clinic_id == clinic_id)
                .order_by(m.CashierReconciliation.created_at.desc())
            )
        ]

    @app.get("/api/v1/archive/keys")
    def list_archive_keys(context=Depends(require_perm("archive.read"))):
        db, clinic_id, _ = context
        return [
            doc(k)
            for k in db.scalars(
                select(m.TenantEncryptionKey)
                .where(m.TenantEncryptionKey.clinic_id == clinic_id)
                .order_by(m.TenantEncryptionKey.key_version.desc())
            )
        ]

    @app.post("/api/v1/archive/keys/rotate", status_code=201)
    def rotate_archive_key(context=Depends(require_perm("archive.key_manage"))):
        db, clinic_id, actor = context
        return doc(
            archive_dr.rotate_tenant_key(db, clinic_id, cfg.archive_master_secret, actor)
        )

    @app.post("/api/v1/archive/keys/{key_id}/revoke")
    def revoke_archive_key(
        key_id: str, context=Depends(require_perm("archive.key_manage"))
    ):
        db, clinic_id, actor = context
        return doc(archive_dr.revoke_tenant_key(db, clinic_id, key_id, actor))

    @app.get("/api/v1/archive/objects")
    def list_archive_objects(context=Depends(require_perm("archive.read"))):
        db, clinic_id, _ = context
        return [
            doc(o)
            for o in db.scalars(
                select(m.ArchiveObject)
                .where(m.ArchiveObject.clinic_id == clinic_id)
                .order_by(m.ArchiveObject.created_at.desc())
            )
        ]

    @app.post("/api/v1/archive/objects", status_code=201)
    def upload_archive_object(
        payload: ArchiveObjectCreate, context=Depends(require_perm("archive.write"))
    ):
        db, clinic_id, actor = context
        return doc(
            archive_dr.store_archive_object(
                db,
                clinic_id,
                cfg.archive_dir,
                cfg.archive_master_secret,
                payload,
                actor,
            )
        )

    @app.get("/api/v1/archive/objects/{object_id}/verify")
    def verify_archive_object_endpoint(
        object_id: str, context=Depends(require_perm("archive.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        return archive_dr.verify_archive_object(
            db, clinic_id, object_id, cfg.archive_dir, cfg.archive_master_secret
        )

    @app.post("/api/v1/archive/objects/{object_id}/legal-hold")
    def hold_archive_object(
        object_id: str,
        payload: ArchiveLegalHoldRequest,
        context=Depends(require_perm("archive.key_manage")),
    ):
        db, clinic_id, actor = context
        return doc(
            archive_dr.place_legal_hold(db, clinic_id, object_id, payload.reason, actor)
        )

    @app.delete("/api/v1/archive/objects/{object_id}")
    def delete_archive_object(
        object_id: str, context=Depends(require_perm("archive.key_manage"))
    ):
        db, clinic_id, actor = context
        return archive_dr.delete_archive_object_blocked(db, clinic_id, object_id, actor)

    @app.get("/api/v1/archive/backups")
    def list_archive_backups(context=Depends(require_perm("archive.read"))):
        db, clinic_id, _ = context
        return [
            doc(b)
            for b in db.scalars(
                select(m.BackupManifest)
                .where(m.BackupManifest.clinic_id == clinic_id)
                .order_by(m.BackupManifest.created_at.desc())
            )
        ]

    @app.post("/api/v1/archive/backups", status_code=201)
    def create_archive_backup(
        payload: BackupCreateRequest, context=Depends(require_perm("archive.restore"))
    ):
        db, clinic_id, actor = context
        return doc(
            archive_dr.create_backup_snapshot(
                db, clinic_id, cfg.archive_dir, cfg.auth_secret, payload, actor
            )
        )

    @app.post("/api/v1/archive/backups/{backup_id}/restore-drill")
    def execute_restore_drill(
        backup_id: str,
        payload: RestoreDrillRequest,
        context=Depends(require_perm("archive.restore")),
    ):
        db, clinic_id, actor = context
        return archive_dr.run_isolated_restore_drill(
            db,
            clinic_id,
            backup_id,
            cfg.archive_dir,
            cfg.archive_master_secret,
            cfg.auth_secret,
            payload,
            actor,
        )

    @app.get("/api/v1/archive/restore-drills")
    def list_restore_drills(context=Depends(require_perm("archive.read"))):
        db, clinic_id, _ = context
        return [
            doc(d)
            for d in db.scalars(
                select(m.RestoreDrillRun)
                .where(m.RestoreDrillRun.clinic_id == clinic_id)
                .order_by(m.RestoreDrillRun.created_at.desc())
            )
        ]

    @app.get("/api/v1/inventory/suppliers")
    def list_suppliers(context=Depends(require_perm("inventory.read"))):
        db, clinic_id, _ = context
        return [
            doc(s)
            for s in db.scalars(
                select(m.InventorySupplier)
                .where(m.InventorySupplier.clinic_id == clinic_id)
                .order_by(m.InventorySupplier.created_at.desc())
            )
        ]

    @app.post("/api/v1/inventory/suppliers", status_code=201)
    def add_supplier(
        payload: SupplierCreate, context=Depends(require_perm("inventory.write"))
    ):
        db, clinic_id, actor = context
        return doc(inventory.create_supplier(db, clinic_id, payload, actor))

    @app.get("/api/v1/inventory/skus")
    def list_skus(context=Depends(require_perm("inventory.read"))):
        db, clinic_id, _ = context
        return [
            inventory.get_sku_stock_summary(db, clinic_id, s.id)
            for s in db.scalars(
                select(m.InventorySku)
                .where(m.InventorySku.clinic_id == clinic_id)
                .order_by(m.InventorySku.sku_code)
            )
        ]

    @app.post("/api/v1/inventory/skus", status_code=201)
    def add_sku(payload: SkuCreate, context=Depends(require_perm("inventory.write"))):
        db, clinic_id, actor = context
        return doc(inventory.create_sku(db, clinic_id, payload, actor))

    @app.get("/api/v1/inventory/skus/{sku_id}/stock")
    def sku_stock(sku_id: str, context=Depends(require_perm("inventory.read"))):
        db, clinic_id, _ = context
        return inventory.get_sku_stock_summary(db, clinic_id, sku_id)

    @app.get("/api/v1/inventory/skus/{sku_id}/fefo-picks")
    def sku_fefo_picks(
        sku_id: str,
        required_qty: int = 1,
        as_of_date: str | None = None,
        context=Depends(require_perm("inventory.read")),
    ):
        db, clinic_id, _ = context
        return inventory.get_fefo_picks(db, clinic_id, sku_id, required_qty, as_of_date)

    @app.post("/api/v1/inventory/purchase-orders", status_code=201)
    def add_purchase_order(
        payload: PurchaseOrderCreate, context=Depends(require_perm("inventory.write"))
    ):
        db, clinic_id, actor = context
        return doc(inventory.create_purchase_order(db, clinic_id, payload, actor))

    @app.post("/api/v1/inventory/purchase-orders/{po_id}/receive", status_code=201)
    def receive_po(
        po_id: str,
        payload: PurchaseOrderReceiveRequest,
        context=Depends(require_perm("inventory.write")),
    ):
        db, clinic_id, actor = context
        return inventory.receive_purchase_order(db, clinic_id, po_id, payload, actor)

    @app.post("/api/v1/inventory/reservations", status_code=201)
    def add_stock_reservation(
        payload: StockReservationCreate,
        context=Depends(require_perm("inventory.write")),
    ):
        db, clinic_id, actor = context
        return doc(inventory.create_reservation(db, clinic_id, payload, actor))

    @app.post("/api/v1/inventory/reservations/{reservation_id}/release")
    def release_stock_reservation(
        reservation_id: str,
        payload: StockReservationReleaseRequest,
        context=Depends(require_perm("inventory.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            inventory.release_reservation(db, clinic_id, reservation_id, payload, actor)
        )

    @app.post("/api/v1/inventory/consumptions", status_code=201)
    def consume_stock(
        payload: StockConsumptionCreate,
        context=Depends(require_perm("inventory.consume")),
    ):
        db, clinic_id, actor = context
        return doc(inventory.consume_for_procedure(db, clinic_id, payload, actor))

    @app.post("/api/v1/inventory/adjustments", status_code=201)
    def request_adjustment(
        payload: StockAdjustmentCreate,
        ctx_tuple=Depends(require_principal_perm("inventory.adjust_request")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            inventory.request_stock_adjustment(
                db, clinic_id, principal.staff_id, payload, actor
            )
        )

    @app.post("/api/v1/inventory/adjustments/{adjustment_id}/approve")
    def approve_adjustment(
        adjustment_id: str,
        payload: StockAdjustmentApproveRequest,
        ctx_tuple=Depends(require_principal_perm("inventory.adjust_approve")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            inventory.approve_stock_adjustment(
                db, clinic_id, adjustment_id, principal.staff_id, payload, actor
            )
        )

    @app.get("/api/v1/inventory/alerts")
    def inventory_alerts(
        as_of_date: str | None = None,
        context=Depends(require_perm("inventory.read")),
    ):
        db, clinic_id, _ = context
        return inventory.get_inventory_alerts(db, clinic_id, as_of_date)

    @app.get("/api/v1/interop/fhir/r4/patients/{patient_id}/bundle")
    def export_fhir_patient_bundle(
        patient_id: str,
        context=Depends(require_perm("interop.fhir_read", audit_read=True)),
    ):
        db, clinic_id, _ = context
        return fhir_interop.export_patient_fhir_r4_bundle(db, clinic_id, patient_id)

    @app.post("/api/v1/interop/fhir/r4/validate-bundle")
    def validate_fhir_bundle_endpoint(
        payload: FhirBundleValidateRequest,
        context=Depends(require_perm("interop.fhir_read")),
    ):
        _, clinic_id, _ = context
        return fhir_interop.validate_fhir_r4_bundle(clinic_id, payload.bundle)

    @app.get("/api/v1/ai/models")
    def list_ai_models(context=Depends(require_perm("ai.draft"))):
        db, _, _ = context
        return ai_harness.list_registered_models(db)

    @app.post("/api/v1/ai/drafts/dictation-extract", status_code=201)
    def ai_dictation_extract(
        payload: AIDictationExtractRequest,
        context=Depends(require_perm("ai.draft")),
    ):
        db, clinic_id, actor = context
        return ai_harness.create_dictation_extract_draft(
            db, clinic_id, cfg.ai_assist_enabled, payload, actor
        )

    @app.post("/api/v1/ai/drafts/timeline-summary", status_code=201)
    def ai_timeline_summary(
        payload: AITimelineSummaryRequest,
        context=Depends(require_perm("ai.draft")),
    ):
        db, clinic_id, actor = context
        return ai_harness.create_timeline_summary_draft(
            db, clinic_id, cfg.ai_assist_enabled, payload, actor
        )

    @app.post("/api/v1/ai/drafts/{draft_id}/accept-into-note-draft", status_code=201)
    def ai_accept_draft(
        draft_id: str,
        payload: AIDraftAcceptRequest,
        ctx_tuple=Depends(require_principal_perm("ai.accept_clinical")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return ai_harness.accept_ai_draft_into_note(
            db, clinic_id, draft_id, principal.staff_id, payload, actor
        )

    @app.post("/api/v1/ai/evaluations/run", status_code=201)
    def run_ai_evaluation(context=Depends(require_perm("ai.evaluate"))):
        db, clinic_id, actor = context
        return ai_harness.run_offline_evaluation_suite(db, clinic_id, actor)

    @app.get("/api/v1/ai/evaluations")
    def list_ai_evaluations(context=Depends(require_perm("ai.evaluate"))):
        db, clinic_id, _ = context
        return [
            doc(r)
            for r in db.scalars(
                select(m.AIEvaluationRun)
                .where(m.AIEvaluationRun.clinic_id == clinic_id)
                .order_by(m.AIEvaluationRun.created_at.desc())
            )
        ]

    @app.get("/api/v1/operations/shifts")
    def list_shifts(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        return [
            doc(s)
            for s in db.scalars(
                select(m.StaffShift)
                .where(m.StaffShift.clinic_id == clinic_id)
                .order_by(m.StaffShift.start_at)
            )
        ]

    @app.post("/api/v1/operations/shifts", status_code=201)
    def add_shift(
        payload: StaffShiftCreate, context=Depends(require_perm("operations.shift_manage"))
    ):
        db, clinic_id, actor = context
        return doc(operations.create_staff_shift(db, clinic_id, payload, actor))

    @app.get("/api/v1/operations/downtimes")
    def list_downtimes(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        return [
            doc(d)
            for d in db.scalars(
                select(m.ResourceDowntime)
                .where(m.ResourceDowntime.clinic_id == clinic_id)
                .order_by(m.ResourceDowntime.start_at)
            )
        ]

    @app.post("/api/v1/operations/downtimes", status_code=201)
    def add_downtime(
        payload: ResourceDowntimeCreate,
        context=Depends(require_perm("operations.downtime_manage")),
    ):
        db, clinic_id, actor = context
        return doc(operations.create_resource_downtime(db, clinic_id, payload, actor))

    @app.post("/api/v1/operations/downtimes/{downtime_id}/resolve")
    def resolve_downtime(
        downtime_id: str,
        context=Depends(require_perm("operations.downtime_manage")),
    ):
        db, clinic_id, actor = context
        return doc(operations.resolve_resource_downtime(db, clinic_id, downtime_id, actor))

    @app.get("/api/v1/operations/turnovers")
    def list_turnovers(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        return [
            doc(t)
            for t in db.scalars(
                select(m.ChairTurnoverChecklist)
                .where(m.ChairTurnoverChecklist.clinic_id == clinic_id)
                .order_by(m.ChairTurnoverChecklist.created_at.desc())
            )
        ]

    @app.post("/api/v1/operations/turnovers", status_code=201)
    def add_turnover(
        payload: ChairTurnoverCreate,
        context=Depends(require_perm("operations.turnover")),
    ):
        db, clinic_id, actor = context
        return doc(operations.create_chair_turnover(db, clinic_id, payload, actor))

    @app.post("/api/v1/operations/turnovers/{checklist_id}/complete")
    def finish_turnover(
        checklist_id: str,
        payload: ChairTurnoverCompleteRequest,
        context=Depends(require_perm("operations.turnover")),
    ):
        db, clinic_id, actor = context
        return doc(
            operations.complete_chair_turnover(db, clinic_id, checklist_id, payload, actor)
        )

    @app.get("/api/v1/operations/checkins")
    def list_checkins(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        return [
            doc(c)
            for c in db.scalars(
                select(m.CheckinQueueItem)
                .where(m.CheckinQueueItem.clinic_id == clinic_id)
                .order_by(m.CheckinQueueItem.created_at.desc())
            )
        ]

    @app.post("/api/v1/operations/checkins", status_code=201)
    def add_checkin(
        payload: CheckinCreate, context=Depends(require_perm("operations.checkin"))
    ):
        db, clinic_id, actor = context
        return doc(operations.create_checkin(db, clinic_id, payload, actor))

    @app.post("/api/v1/operations/checkins/{checkin_id}/status")
    def update_checkin_status(
        checkin_id: str,
        payload: CheckinStatusUpdate,
        context=Depends(require_perm("operations.checkin")),
    ):
        db, clinic_id, actor = context
        return doc(
            operations.transition_checkin_status(db, clinic_id, checkin_id, payload, actor)
        )

    @app.get("/api/v1/operations/recalls")
    def list_recalls(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        return [
            doc(r)
            for r in db.scalars(
                select(m.RecallFollowupItem)
                .where(m.RecallFollowupItem.clinic_id == clinic_id)
                .order_by(m.RecallFollowupItem.due_date.asc())
            )
        ]

    @app.post("/api/v1/operations/recalls", status_code=201)
    def add_recall(
        payload: RecallCreate, context=Depends(require_perm("operations.recall"))
    ):
        db, clinic_id, actor = context
        return doc(operations.create_recall_item(db, clinic_id, payload, actor))

    @app.post("/api/v1/operations/recalls/{recall_id}/close")
    def finish_recall(
        recall_id: str,
        payload: RecallCloseRequest,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(operations.close_recall_item(db, clinic_id, recall_id, payload, actor))

    @app.get("/api/v1/auth/break-glass")
    def list_break_glass_grants(context=Depends(require_perm("audit.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.BreakGlassGrant)
            .where(m.BreakGlassGrant.clinic_id == clinic_id)
            .order_by(m.BreakGlassGrant.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/auth/break-glass", status_code=201)
    def activate_break_glass(
        payload: BreakGlassCreateRequest,
        ctx_tuple=Depends(require_principal_perm("auth.break_glass")),
    ):
        db, _, _, principal = ctx_tuple
        if not principal.authenticated:
            raise HTTPException(401, "Authenticated staff token required for break-glass")
        return doc(patient_portal.create_break_glass_grant(db, principal, payload))

    @app.get("/api/v1/auth/break-glass/{grant_id}/patient-chart")
    def read_break_glass_patient_chart(grant_id: str, ctx_tuple=Depends(resolve_ctx)):
        db, _, _, principal = ctx_tuple
        if not principal.authenticated:
            raise HTTPException(401, "Authenticated staff token required for break-glass read")
        return patient_portal.read_break_glass_chart(db, principal, grant_id)

    @app.post("/api/v1/auth/break-glass/{grant_id}/revoke")
    def revoke_break_glass(
        grant_id: str, context=Depends(require_perm("staff.manage"))
    ):
        db, clinic_id, actor = context
        return doc(patient_portal.revoke_break_glass_grant(db, clinic_id, grant_id, actor))

    @app.post("/api/v1/auth/break-glass/{grant_id}/review")
    def review_break_glass(
        grant_id: str,
        payload: BreakGlassReviewRequest,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            patient_portal.review_break_glass_grant(
                db, clinic_id, grant_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/portal/grants", status_code=201)
    def create_portal_grant(
        payload: PortalGrantCreate,
        ctx_tuple=Depends(require_principal_perm("portal.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return patient_portal.issue_portal_session_grant(
            db, clinic_id, principal.staff_id, actor, cfg.auth_secret, payload
        )

    @app.post("/api/v1/portal/instructions", status_code=201)
    def publish_instruction(
        payload: PortalInstructionPublish,
        ctx_tuple=Depends(require_principal_perm("portal.publish")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            patient_portal.publish_portal_instruction(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/portal/plan-summaries", status_code=201)
    def publish_plan_summary(
        payload: PortalPlanSummaryPublish,
        ctx_tuple=Depends(require_principal_perm("portal.publish")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            patient_portal.publish_portal_plan_summary(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/portal/reschedule-requests")
    def list_portal_reschedule_requests(context=Depends(require_perm("appointment.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.PortalRescheduleRequest)
            .where(m.PortalRescheduleRequest.clinic_id == clinic_id)
            .order_by(m.PortalRescheduleRequest.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/portal/reschedule-requests/{request_id}/approve")
    def approve_portal_reschedule(
        request_id: str,
        payload: PortalRescheduleDecisionRequest,
        ctx_tuple=Depends(require_principal_perm("appointment.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            patient_portal.approve_portal_reschedule_request(
                db, clinic_id, request_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/patient-portal/overview")
    def patient_portal_overview(
        db: Session = Depends(get_db),
        authorization: str | None = Header(None),
    ):
        portal = patient_portal.resolve_portal_principal(db, authorization, cfg.auth_secret)
        return patient_portal.get_patient_portal_overview(db, portal)

    @app.post("/api/v1/patient-portal/appointments/{appointment_id}/confirm", status_code=201)
    def patient_portal_confirm_appointment(
        appointment_id: str,
        db: Session = Depends(get_db),
        authorization: str | None = Header(None),
    ):
        portal = patient_portal.resolve_portal_principal(db, authorization, cfg.auth_secret)
        return doc(patient_portal.confirm_portal_appointment(db, portal, appointment_id))

    @app.post(
        "/api/v1/patient-portal/appointments/{appointment_id}/reschedule-requests",
        status_code=201,
    )
    def patient_portal_request_reschedule(
        appointment_id: str,
        payload: PortalRescheduleCreate,
        db: Session = Depends(get_db),
        authorization: str | None = Header(None),
    ):
        portal = patient_portal.resolve_portal_principal(db, authorization, cfg.auth_secret)
        return doc(
            patient_portal.create_portal_reschedule_request(
                db, portal, appointment_id, payload
            )
        )

    @app.post("/api/v1/patient-portal/intake-forms", status_code=201)
    def patient_portal_submit_intake(
        payload: PortalIntakeCreate,
        db: Session = Depends(get_db),
        authorization: str | None = Header(None),
    ):
        portal = patient_portal.resolve_portal_principal(db, authorization, cfg.auth_secret)
        return doc(patient_portal.submit_portal_intake_form(db, portal, payload))

    @app.get("/api/v1/finance/price-catalog")
    def list_price_catalog(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ServicePriceCatalogItem)
            .where(m.ServicePriceCatalogItem.clinic_id == clinic_id)
            .order_by(
                m.ServicePriceCatalogItem.service_code.asc(),
                m.ServicePriceCatalogItem.version_number.desc(),
            )
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/finance/price-catalog", status_code=201)
    def publish_price_catalog_item(
        payload: PriceCatalogCreate,
        context=Depends(require_perm("finance.catalog_manage")),
    ):
        db, clinic_id, actor = context
        return doc(
            governance_analytics.publish_price_catalog_version(db, clinic_id, actor, payload)
        )

    @app.post("/api/v1/finance/estimates/from-catalog", status_code=201)
    def create_estimate_from_catalog_endpoint(
        payload: EstimateFromCatalogCreate,
        context=Depends(require_perm("finance.write")),
    ):
        db, clinic_id, actor = context
        return governance_analytics.create_estimate_from_catalog(
            db, clinic_id, actor, payload
        )

    @app.get("/api/v1/finance/estimates/{estimate_id}/lines")
    def get_estimate_lines_endpoint(
        estimate_id: str, context=Depends(require_perm("finance.read"))
    ):
        db, clinic_id, _ = context
        return governance_analytics.get_estimate_with_lines(db, clinic_id, estimate_id)

    @app.get("/api/v1/finance/discount-requests")
    def list_discount_requests(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.DiscountApprovalRequest)
            .where(m.DiscountApprovalRequest.clinic_id == clinic_id)
            .order_by(m.DiscountApprovalRequest.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/finance/estimates/{estimate_id}/discounts", status_code=201)
    def request_discount_endpoint(
        estimate_id: str,
        payload: DiscountRequestCreate,
        ctx_tuple=Depends(require_principal_perm("finance.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            governance_analytics.request_estimate_discount(
                db, clinic_id, estimate_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/finance/discount-requests/{request_id}/decide")
    def decide_discount_endpoint(
        request_id: str,
        payload: DiscountDecisionRequest,
        ctx_tuple=Depends(require_principal_perm("finance.discount_approve")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            governance_analytics.decide_discount_request(
                db, clinic_id, request_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/reports/dictionary")
    def get_kpi_dictionary(context=Depends(require_perm("dashboard.read"))):
        return governance_analytics.get_metric_dictionary()

    @app.get("/api/v1/reports/kpi-lineage")
    def get_kpi_lineage(context=Depends(require_perm("dashboard.read"))):
        db, clinic_id, _ = context
        return governance_analytics.compute_kpi_lineage_report(db, clinic_id)

    @app.get("/api/v1/patients/{patient_id}/medical-risk-reviews")
    def list_medical_risk_reviews(
        patient_id: str, context=Depends(require_perm("encounter.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Patient, patient_id, clinic_id)
        rows = db.scalars(
            select(m.PatientMedicalRiskReview)
            .where(
                m.PatientMedicalRiskReview.clinic_id == clinic_id,
                m.PatientMedicalRiskReview.patient_id == patient_id,
            )
            .order_by(m.PatientMedicalRiskReview.revision_number.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/patients/{patient_id}/medical-risk-reviews", status_code=201)
    def post_medical_risk_review(
        patient_id: str,
        payload: MedicalRiskReviewCreate,
        ctx_tuple=Depends(require_principal_perm("medical_risk.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            clinical_lifecycle.create_medical_risk_review(
                db, clinic_id, patient_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/encounters/{encounter_id}/closure-checklist")
    def get_encounter_closure_checklist_endpoint(
        encounter_id: str, context=Depends(require_perm("encounter.read"))
    ):
        db, clinic_id, _ = context
        return clinical_lifecycle.get_encounter_closure_checklist(db, clinic_id, encounter_id)

    @app.post("/api/v1/encounters/{encounter_id}/notify-missing-signatures")
    def notify_missing_signatures_endpoint(
        encounter_id: str, context=Depends(require_perm("encounter.read"))
    ):
        db, clinic_id, actor = context
        return clinical_lifecycle.notify_missing_signatures(db, clinic_id, encounter_id, actor)

    @app.post("/api/v1/encounters/{encounter_id}/close-demo")
    def close_encounter_demo_endpoint(
        encounter_id: str, context=Depends(require_perm("encounter.close"))
    ):
        db, clinic_id, actor = context
        return doc(clinical_lifecycle.close_encounter_demo(db, clinic_id, encounter_id, actor))

    @app.get("/api/v1/encounters/{encounter_id}/diagnoses")
    def list_encounter_diagnoses(
        encounter_id: str, context=Depends(require_perm("encounter.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        rows = db.scalars(
            select(m.EncounterDiagnosisDemo)
            .where(
                m.EncounterDiagnosisDemo.clinic_id == clinic_id,
                m.EncounterDiagnosisDemo.encounter_id == encounter_id,
            )
            .order_by(m.EncounterDiagnosisDemo.created_at.asc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/encounters/{encounter_id}/diagnoses", status_code=201)
    def add_encounter_diagnosis(
        encounter_id: str,
        payload: EncounterDiagnosisCreate,
        ctx_tuple=Depends(require_principal_perm("diagnosis.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            clinical_lifecycle.record_encounter_diagnosis_demo(
                db, clinic_id, encounter_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/encounters/{encounter_id}/performed-procedures")
    def list_performed_procedures(
        encounter_id: str, context=Depends(require_perm("encounter.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        rows = db.scalars(
            select(m.PerformedProcedureEvidence)
            .where(
                m.PerformedProcedureEvidence.clinic_id == clinic_id,
                m.PerformedProcedureEvidence.encounter_id == encounter_id,
            )
            .order_by(m.PerformedProcedureEvidence.created_at.asc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/encounters/{encounter_id}/performed-procedures", status_code=201)
    def add_performed_procedure(
        encounter_id: str,
        payload: PerformedProcedureCreate,
        ctx_tuple=Depends(require_principal_perm("procedure.record_performed")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            clinical_lifecycle.record_performed_procedure_evidence(
                db, clinic_id, encounter_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/treatment-tasks/{task_id}/milestones", status_code=201)
    def add_task_milestone(
        task_id: str,
        payload: MilestoneChecklistCreate,
        context=Depends(require_perm("plan.review")),
    ):
        db, clinic_id, actor = context
        return doc(
            continuity_governance.create_milestone_checklist(db, clinic_id, task_id, actor, payload)
        )

    @app.post("/api/v1/treatment-milestones/{milestone_id}/evaluate")
    def evaluate_task_milestone(
        milestone_id: str,
        payload: MilestoneEvaluateRequest,
        ctx_tuple=Depends(require_principal_perm("plan.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            continuity_governance.evaluate_milestone_checklist(
                db, clinic_id, milestone_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/treatment-plans/{plan_id}/lifecycle")
    def list_plan_lifecycle_events(
        plan_id: str, context=Depends(require_perm("plan.read"))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.TreatmentPlan, plan_id, clinic_id)
        rows = db.scalars(
            select(m.TreatmentPlanLifecycleEvent)
            .where(
                m.TreatmentPlanLifecycleEvent.clinic_id == clinic_id,
                m.TreatmentPlanLifecycleEvent.plan_id == plan_id,
            )
            .order_by(m.TreatmentPlanLifecycleEvent.created_at.asc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/treatment-plans/{plan_id}/lifecycle", status_code=201)
    def post_plan_lifecycle_event(
        plan_id: str,
        payload: PlanLifecycleTransitionCreate,
        ctx_tuple=Depends(require_principal_perm("plan.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            continuity_governance.transition_plan_lifecycle(
                db, clinic_id, plan_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/operations/waitlist")
    def list_waitlist_entries(context=Depends(require_perm("appointment.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ScheduleWaitlistEntry)
            .where(m.ScheduleWaitlistEntry.clinic_id == clinic_id)
            .order_by(m.ScheduleWaitlistEntry.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/operations/waitlist", status_code=201)
    def create_waitlist_endpoint(
        payload: WaitlistCreate, context=Depends(require_perm("appointment.write"))
    ):
        db, clinic_id, actor = context
        return doc(continuity_governance.create_waitlist_entry(db, clinic_id, actor, payload))

    @app.post("/api/v1/operations/waitlist/{entry_id}/prepare-outreach")
    def prepare_waitlist_outreach_endpoint(
        entry_id: str, context=Depends(require_perm("appointment.write"))
    ):
        db, clinic_id, actor = context
        return doc(continuity_governance.prepare_waitlist_outreach(db, clinic_id, entry_id, actor))

    @app.post("/api/v1/operations/waitlist/{entry_id}/confirm-booking", status_code=201)
    def confirm_waitlist_booking_endpoint(
        entry_id: str,
        payload: AppointmentCreate,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            continuity_governance.confirm_waitlist_booking(db, clinic_id, entry_id, actor, payload)
        )

    @app.get("/api/v1/finance/installments")
    def list_installment_schedules(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.InstallmentSchedule)
            .where(m.InstallmentSchedule.clinic_id == clinic_id)
            .order_by(m.InstallmentSchedule.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/finance/installments", status_code=201)
    def create_installment_schedule_endpoint(
        payload: InstallmentScheduleCreate,
        context=Depends(require_perm("finance.write")),
    ):
        db, clinic_id, actor = context
        return continuity_governance.create_installment_schedule(db, clinic_id, actor, payload)

    @app.post("/api/v1/finance/installments/{schedule_id}/tranches/{tranche_id}/log-reminder")
    def log_installment_reminder_endpoint(
        schedule_id: str,
        tranche_id: str,
        context=Depends(require_perm("finance.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            continuity_governance.log_installment_tranche_reminder(
                db, clinic_id, schedule_id, tranche_id, actor
            )
        )

    @app.get("/api/v1/operations/incidents")
    def list_quality_incidents(context=Depends(require_perm("quality.report_read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.QualityIncidentReport)
            .where(m.QualityIncidentReport.clinic_id == clinic_id)
            .order_by(m.QualityIncidentReport.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/operations/incidents", status_code=201)
    def create_quality_incident(
        payload: QualityIncidentCreate,
        ctx_tuple=Depends(require_principal_perm("quality.report_create")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            continuity_governance.create_quality_incident_report(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/odontogram/legend")
    def list_odontogram_legend(context=Depends(require_perm("odontogram.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.OdontogramLegendEntry)
            .where(m.OdontogramLegendEntry.clinic_id == clinic_id)
            .order_by(
                m.OdontogramLegendEntry.code.asc(),
                m.OdontogramLegendEntry.version_number.desc(),
            )
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/odontogram/legend", status_code=201)
    def publish_odontogram_legend_endpoint(
        payload: OdontogramLegendCreate,
        ctx_tuple=Depends(require_principal_perm("odontogram.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            odontogram_referrals_export.publish_odontogram_legend_version(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.put("/api/v1/patients/{patient_id}/odontogram/restorations/{tooth_code}")
    def upsert_tooth_restoration_endpoint(
        patient_id: str,
        tooth_code: str,
        payload: OdontogramRestorationUpsert,
        ctx_tuple=Depends(require_principal_perm("odontogram.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            odontogram_referrals_export.upsert_tooth_restoration_optimistic(
                db, clinic_id, patient_id, tooth_code, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/patients/{patient_id}/odontogram/export")
    def export_odontogram_endpoint(
        patient_id: str, context=Depends(require_perm("odontogram.read", audit_read=True))
    ):
        db, clinic_id, actor = context
        return odontogram_referrals_export.export_patient_odontogram(
            db, clinic_id, patient_id, actor
        )

    @app.get("/api/v1/patients/{patient_id}/referrals")
    def list_external_referrals(
        patient_id: str, context=Depends(require_perm("encounter.read", audit_read=True))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Patient, patient_id, clinic_id)
        rows = db.scalars(
            select(m.ExternalReferralDocument)
            .where(
                m.ExternalReferralDocument.clinic_id == clinic_id,
                m.ExternalReferralDocument.patient_id == patient_id,
            )
            .order_by(m.ExternalReferralDocument.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/patients/{patient_id}/referrals", status_code=201)
    def create_external_referral_endpoint(
        patient_id: str,
        payload: ExternalReferralCreate,
        context=Depends(require_perm("referral.intake")),
    ):
        db, clinic_id, actor = context
        return doc(
            odontogram_referrals_export.create_external_referral(
                db, clinic_id, patient_id, actor, payload
            )
        )

    @app.post("/api/v1/referrals/{referral_id}/review")
    def review_external_referral_endpoint(
        referral_id: str,
        payload: ExternalReferralReviewRequest,
        ctx_tuple=Depends(require_principal_perm("referral.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            odontogram_referrals_export.review_external_referral(
                db, clinic_id, referral_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/patients/{patient_id}/document-eligibility")
    def get_document_eligibility_endpoint(
        patient_id: str, context=Depends(require_perm("patient.read"))
    ):
        db, clinic_id, _ = context
        return odontogram_referrals_export.evaluate_patient_document_eligibility(
            db, clinic_id, patient_id
        )

    @app.get("/api/v1/clinical-documents/{snapshot_id}/structured-export")
    def get_structured_clinical_export_endpoint(
        snapshot_id: str,
        context=Depends(require_perm("clinical_doc.read", audit_read=True)),
    ):
        db, clinic_id, actor = context
        return odontogram_referrals_export.export_structured_clinical_document(
            db, clinic_id, snapshot_id, actor
        )

    @app.post("/api/v1/org/branch-scope-grants", status_code=201)
    def post_branch_scope_grant(
        payload: BranchScopeGrantCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            org_crm_ops_assistant.grant_owner_branch_scope(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/org/multi-branch-aggregates")
    def get_multi_branch_aggregates_endpoint(
        owner_group_key: str,
        context=Depends(require_perm("staff.manage")),
    ):
        db, clinic_id, actor = context
        return org_crm_ops_assistant.get_multi_branch_aggregates(
            db, clinic_id, actor, owner_group_key
        )

    @app.get("/api/v1/auth/delegations")
    def list_delegations(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.TemporaryDelegationGrant)
            .where(m.TemporaryDelegationGrant.clinic_id == clinic_id)
            .order_by(m.TemporaryDelegationGrant.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/auth/delegations", status_code=201)
    def create_delegation_endpoint(
        payload: TemporaryDelegationCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            org_crm_ops_assistant.create_temporary_delegation(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/auth/delegations/{grant_id}/revoke")
    def revoke_delegation_endpoint(
        grant_id: str, context=Depends(require_perm("staff.manage"))
    ):
        db, clinic_id, actor = context
        return doc(
            org_crm_ops_assistant.revoke_temporary_delegation(db, clinic_id, grant_id, actor)
        )

    @app.get("/api/v1/operations/staff-tasks")
    def list_staff_operational_tasks(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.StaffOperationalTask)
            .where(m.StaffOperationalTask.clinic_id == clinic_id)
            .order_by(m.StaffOperationalTask.due_at.asc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/operations/staff-tasks", status_code=201)
    def create_staff_operational_task_endpoint(
        payload: StaffOperationalTaskCreate,
        context=Depends(require_perm("operations.checkin")),
    ):
        db, clinic_id, actor = context
        return doc(
            org_crm_ops_assistant.create_staff_operational_task(db, clinic_id, actor, payload)
        )

    @app.post("/api/v1/operations/staff-tasks/escalate-overdue")
    def escalate_overdue_staff_tasks_endpoint(
        context=Depends(require_perm("operations.checkin")),
    ):
        db, clinic_id, actor = context
        return org_crm_ops_assistant.escalate_overdue_staff_tasks(db, clinic_id, actor)

    @app.get("/api/v1/operations/handoffs")
    def list_handoffs_endpoint(
        context=Depends(require_perm("handoff.read", audit_read=True)),
    ):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.InternalHandoffNote)
            .where(m.InternalHandoffNote.clinic_id == clinic_id)
            .order_by(m.InternalHandoffNote.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/operations/handoffs", status_code=201)
    def create_handoff_endpoint(
        payload: InternalHandoffCreate,
        ctx_tuple=Depends(require_principal_perm("handoff.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            org_crm_ops_assistant.create_internal_handoff_note(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/patients/{patient_id}/contact-timeline")
    def list_patient_contact_timeline(
        patient_id: str, context=Depends(require_perm("operations.read"))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Patient, patient_id, clinic_id)
        rows = db.scalars(
            select(m.PatientContactLog)
            .where(
                m.PatientContactLog.clinic_id == clinic_id,
                m.PatientContactLog.patient_id == patient_id,
            )
            .order_by(m.PatientContactLog.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/patients/{patient_id}/contact-timeline", status_code=201)
    def post_patient_contact_timeline(
        patient_id: str,
        payload: PatientContactLogCreate,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(
            org_crm_ops_assistant.create_patient_contact_log(
                db, clinic_id, patient_id, actor, payload
            )
        )

    @app.get("/api/v1/crm/complaints")
    def list_complaints_endpoint(
        ctx_tuple=Depends(require_principal_perm("complaint.read")),
    ):
        db, _, _, principal = ctx_tuple
        return org_crm_ops_assistant.list_service_complaints_scoped(db, principal)

    @app.post("/api/v1/crm/complaints", status_code=201)
    def create_complaint_endpoint(
        payload: ServiceComplaintCreate,
        context=Depends(require_perm("complaint.create")),
    ):
        db, clinic_id, actor = context
        return doc(
            org_crm_ops_assistant.create_service_complaint(db, clinic_id, actor, payload)
        )

    @app.post("/api/v1/ai/ops-assistant/query")
    def query_ops_assistant_endpoint(
        payload: OpsAssistantQueryRequest,
        ctx_tuple=Depends(require_principal_perm("context.read")),
    ):
        db, _, _, principal = ctx_tuple
        return org_crm_ops_assistant.query_policy_aware_ops_assistant(
            db, principal, cfg.ai_assist_enabled, payload
        )

    @app.get("/api/v1/org/facility-profile")
    def list_facility_profiles_endpoint(context=Depends(require_perm("context.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.FacilityLicenseProfile)
            .where(m.FacilityLicenseProfile.clinic_id == clinic_id)
            .order_by(m.FacilityLicenseProfile.version_number.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/org/facility-profile", status_code=201)
    def publish_facility_profile_endpoint(
        payload: FacilityLicenseProfileCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            facility_optimizer_receipts_hr.publish_facility_license_profile(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/org/facility-profile/scope-check")
    def check_facility_scope_endpoint(
        scope: str, context=Depends(require_perm("context.read"))
    ):
        db, clinic_id, _ = context
        return facility_optimizer_receipts_hr.evaluate_facility_scope(db, clinic_id, scope)

    @app.get("/api/v1/scheduling/duration-templates")
    def list_duration_templates_endpoint(context=Depends(require_perm("appointment.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ProcedureDurationTemplate)
            .where(m.ProcedureDurationTemplate.clinic_id == clinic_id)
            .order_by(m.ProcedureDurationTemplate.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/scheduling/duration-templates", status_code=201)
    def publish_duration_template_endpoint(
        payload: ProcedureDurationTemplateCreate,
        ctx_tuple=Depends(require_principal_perm("plan.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            facility_optimizer_receipts_hr.publish_procedure_duration_template(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/scheduling/duration-estimate")
    def estimate_duration_endpoint(
        procedure_code: str, context=Depends(require_perm("appointment.read"))
    ):
        db, clinic_id, _ = context
        return facility_optimizer_receipts_hr.estimate_procedure_duration(
            db, clinic_id, procedure_code
        )

    @app.post("/api/v1/scheduling/optimizer/propose", status_code=201)
    def propose_schedule_optimizer_endpoint(
        payload: ScheduleOptimizerProposeRequest,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return facility_optimizer_receipts_hr.propose_optimized_slots(
            db, clinic_id, actor, payload
        )

    @app.post("/api/v1/scheduling/optimizer/proposals/{proposal_id}/accept")
    def accept_schedule_optimizer_endpoint(
        proposal_id: str,
        payload: ScheduleOptimizerAcceptRequest,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return facility_optimizer_receipts_hr.accept_optimized_slot(
            db, clinic_id, proposal_id, actor, payload
        )

    @app.get("/api/v1/finance/payments/{payment_id}/receipt-exports")
    def list_financial_receipt_exports_endpoint(
        payment_id: str, context=Depends(require_perm("finance.read"))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Payment, payment_id, clinic_id)
        rows = db.scalars(
            select(m.FinancialReceiptExport)
            .where(
                m.FinancialReceiptExport.clinic_id == clinic_id,
                m.FinancialReceiptExport.payment_id == payment_id,
            )
            .order_by(m.FinancialReceiptExport.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/finance/payments/{payment_id}/receipt-exports", status_code=201)
    def export_financial_receipt_endpoint(
        payment_id: str,
        payload: FinancialReceiptExportCreate,
        ctx_tuple=Depends(require_principal_perm("finance.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            facility_optimizer_receipts_hr.export_financial_receipt(
                db,
                clinic_id,
                payment_id,
                principal.staff_id,
                actor,
                cfg.auth_secret,
                payload,
            )
        )

    @app.get("/api/v1/hr/attendance")
    def list_staff_attendance_endpoint(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.StaffAttendanceLog)
            .where(m.StaffAttendanceLog.clinic_id == clinic_id)
            .order_by(m.StaffAttendanceLog.check_in_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/hr/attendance", status_code=201)
    def record_staff_attendance_endpoint(
        payload: StaffAttendanceCreate,
        ctx_tuple=Depends(require_principal_perm("operations.checkin")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            facility_optimizer_receipts_hr.record_staff_attendance(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/hr/overtime-summary")
    def get_overtime_summary_endpoint(
        local_date_hcm: str, context=Depends(require_perm("staff.manage"))
    ):
        db, clinic_id, _ = context
        return facility_optimizer_receipts_hr.get_overtime_summary(
            db, clinic_id, local_date_hcm
        )

    @app.get("/api/v1/crm/reminder-templates")
    def list_reminder_templates_endpoint(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ReminderTemplateVersion)
            .where(m.ReminderTemplateVersion.clinic_id == clinic_id)
            .order_by(m.ReminderTemplateVersion.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/crm/reminder-templates", status_code=201)
    def publish_reminder_template_endpoint(
        payload: ReminderTemplateCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            comms_satisfaction_cutover.publish_reminder_template(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/ai/communication-drafts")
    def list_communication_drafts_endpoint(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.CommunicationDraftRecord)
            .where(m.CommunicationDraftRecord.clinic_id == clinic_id)
            .order_by(m.CommunicationDraftRecord.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ai/communication-drafts", status_code=201)
    def create_communication_draft_endpoint(
        payload: CommunicationDraftCreate,
        ctx_tuple=Depends(require_principal_perm("operations.recall")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            comms_satisfaction_cutover.create_communication_draft(
                db,
                clinic_id,
                principal.staff_id,
                actor,
                cfg.ai_assist_enabled,
                payload,
            )
        )

    @app.post("/api/v1/crm/satisfaction/tokens", status_code=201)
    def issue_satisfaction_token_endpoint(
        payload: SatisfactionTokenIssueRequest,
        context=Depends(require_perm("operations.checkin")),
    ):
        db, clinic_id, actor = context
        return comms_satisfaction_cutover.issue_satisfaction_survey_token(
            db, clinic_id, actor, cfg.auth_secret, payload
        )

    @app.post("/api/v1/crm/satisfaction/submit", status_code=201)
    def submit_satisfaction_survey_endpoint(
        payload: SatisfactionSurveySubmit,
        db: Session = Depends(get_db),
    ):
        return comms_satisfaction_cutover.submit_anonymous_satisfaction_survey(
            db, cfg.auth_secret, payload
        )

    @app.get("/api/v1/crm/satisfaction/summary")
    def get_satisfaction_summary_endpoint(context=Depends(require_perm("dashboard.read"))):
        db, clinic_id, _ = context
        return comms_satisfaction_cutover.get_satisfaction_summary(db, clinic_id)

    @app.get("/api/v1/migration/incumbent-exports")
    def list_incumbent_exports_endpoint(context=Depends(require_perm("migration.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.IncumbentExportPackage)
            .where(m.IncumbentExportPackage.clinic_id == clinic_id)
            .order_by(m.IncumbentExportPackage.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/migration/incumbent-exports", status_code=201)
    def ingest_incumbent_export_endpoint(
        payload: IncumbentExportIngestCreate,
        ctx_tuple=Depends(require_principal_perm("migration.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            comms_satisfaction_cutover.ingest_incumbent_export_package(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/migration/incumbent-exports/{package_id}/approve-quarantine")
    def approve_incumbent_export_endpoint(
        package_id: str,
        payload: IncumbentExportApproveRequest,
        ctx_tuple=Depends(require_principal_perm("migration.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            comms_satisfaction_cutover.approve_incumbent_export_quarantine(
                db, clinic_id, package_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/migration/cutover-plans")
    def list_cutover_plans_endpoint(context=Depends(require_perm("migration.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.MigrationCutoverPlan)
            .where(m.MigrationCutoverPlan.clinic_id == clinic_id)
            .order_by(m.MigrationCutoverPlan.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/migration/cutover-plans", status_code=201)
    def create_cutover_plan_endpoint(
        payload: MigrationCutoverPlanCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            comms_satisfaction_cutover.create_migration_cutover_plan(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/ops/telemetry-events")
    def list_redacted_telemetry_endpoint(context=Depends(require_perm("audit.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.RedactedTelemetryEvent)
            .where(m.RedactedTelemetryEvent.clinic_id == clinic_id)
            .order_by(m.RedactedTelemetryEvent.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ops/telemetry-events", status_code=201)
    def emit_redacted_telemetry_endpoint(
        payload: RedactedTelemetryCreate,
        context=Depends(require_perm("operations.read")),
    ):
        db, clinic_id, actor = context
        return doc(
            ops_security_governance.emit_redacted_telemetry_event(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/ops/onboarding-config")
    def list_clinic_onboarding_config_endpoint(
        context=Depends(require_perm("staff.manage")),
    ):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ClinicOnboardingConfig)
            .where(m.ClinicOnboardingConfig.clinic_id == clinic_id)
            .order_by(m.ClinicOnboardingConfig.version_number.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ops/onboarding-config", status_code=201)
    def configure_clinic_onboarding_endpoint(
        payload: ClinicOnboardingConfigCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            ops_security_governance.configure_clinic_onboarding(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/ops/support/grants", status_code=201)
    def create_support_grant_endpoint(
        payload: SupportConsentGrantCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            ops_security_governance.create_support_consent_grant(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/ops/support/grants/{grant_id}/revoke")
    def revoke_support_grant_endpoint(
        grant_id: str, context=Depends(require_perm("staff.manage"))
    ):
        db, clinic_id, actor = context
        return doc(
            ops_security_governance.revoke_support_consent_grant(
                db, clinic_id, grant_id, actor
            )
        )

    @app.post("/api/v1/ops/support/diagnostic-export", status_code=201)
    def export_support_diagnostics_endpoint(
        payload: SupportDiagnosticExportRequest,
        context=Depends(require_perm("staff.manage")),
    ):
        db, clinic_id, actor = context
        return doc(
            ops_security_governance.export_support_diagnostic_bundle(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/security/incidents")
    def list_security_incidents_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.SecurityIncidentCase)
            .where(m.SecurityIncidentCase.clinic_id == clinic_id)
            .order_by(m.SecurityIncidentCase.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/security/incidents", status_code=201)
    def open_security_incident_endpoint(
        payload: SecurityIncidentCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            ops_security_governance.open_security_incident_case(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/security/incidents/{incident_id}/transition")
    def transition_security_incident_endpoint(
        incident_id: str,
        payload: SecurityIncidentTransitionRequest,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            ops_security_governance.transition_security_incident_case(
                db, clinic_id, incident_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/security/supply-chain/verify", status_code=201)
    def verify_supply_chain_endpoint(
        payload: SupplyChainVerifyRequest,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            ops_security_governance.verify_supply_chain_sbom(
                db,
                clinic_id,
                principal.staff_id,
                actor,
                cfg.auth_secret,
                payload,
            )
        )

    @app.get("/api/v1/patients/{patient_id}/access-requests")
    def list_patient_access_requests_endpoint(
        patient_id: str, context=Depends(require_perm("patient.read"))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Patient, patient_id, clinic_id)
        rows = db.scalars(
            select(m.PatientAccessRequest)
            .where(
                m.PatientAccessRequest.clinic_id == clinic_id,
                m.PatientAccessRequest.patient_id == patient_id,
            )
            .order_by(m.PatientAccessRequest.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/patients/{patient_id}/access-requests", status_code=201)
    def create_patient_access_request_endpoint(
        patient_id: str,
        payload: PatientAccessRequestCreate,
        ctx_tuple=Depends(require_principal_perm("consent.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            portal_access_recovery_hr.handle_patient_access_request(
                db, clinic_id, patient_id, principal.staff_id, actor, payload
            )
        )

    @app.post(
        "/api/v1/scheduling/appointments/{appointment_id}/cancellation-recovery",
        status_code=201,
    )
    def suggest_cancellation_recovery_endpoint(
        appointment_id: str,
        payload: CancellationRecoveryRequest,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return portal_access_recovery_hr.suggest_cancellation_slot_recovery(
            db, clinic_id, appointment_id, actor, payload
        )

    @app.post("/api/v1/patient-portal/uploads", status_code=201)
    def patient_portal_upload_endpoint(
        payload: PortalUploadCreate,
        db: Session = Depends(get_db),
        authorization: str | None = Header(None),
    ):
        portal = patient_portal.resolve_portal_principal(db, authorization, cfg.auth_secret)
        return doc(
            portal_access_recovery_hr.upload_portal_quarantined_file(db, portal, payload)
        )

    @app.get("/api/v1/portal/uploads")
    def list_portal_uploads_endpoint(context=Depends(require_perm("referral.intake"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.PortalQuarantinedUpload)
            .where(m.PortalQuarantinedUpload.clinic_id == clinic_id)
            .order_by(m.PortalQuarantinedUpload.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/portal/uploads/{upload_id}/review")
    def review_portal_upload_endpoint(
        upload_id: str,
        payload: PortalUploadReviewRequest,
        ctx_tuple=Depends(require_principal_perm("referral.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            portal_access_recovery_hr.review_portal_quarantined_upload(
                db, clinic_id, upload_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/patient-portal/support-messages", status_code=201)
    def patient_portal_support_message_endpoint(
        payload: PortalSupportMessageCreate,
        db: Session = Depends(get_db),
        authorization: str | None = Header(None),
    ):
        portal = patient_portal.resolve_portal_principal(db, authorization, cfg.auth_secret)
        return doc(
            portal_access_recovery_hr.create_portal_support_message(db, portal, payload)
        )

    @app.get("/api/v1/portal/support-messages")
    def list_portal_support_messages_endpoint(
        context=Depends(require_perm("handoff.read")),
    ):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.PortalSupportMessage)
            .where(m.PortalSupportMessage.clinic_id == clinic_id)
            .order_by(m.PortalSupportMessage.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/portal/support-messages/{message_id}/reply")
    def reply_portal_support_message_endpoint(
        message_id: str,
        payload: PortalSupportReplyRequest,
        ctx_tuple=Depends(require_principal_perm("handoff.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            portal_access_recovery_hr.reply_portal_support_message(
                db, clinic_id, message_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/hr/competencies")
    def list_staff_competencies_endpoint(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.StaffCompetencyRecord)
            .where(m.StaffCompetencyRecord.clinic_id == clinic_id)
            .order_by(m.StaffCompetencyRecord.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/hr/competencies", status_code=201)
    def upsert_staff_competency_endpoint(
        payload: StaffCompetencyUpsert,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            portal_access_recovery_hr.upsert_staff_competency(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/hr/competencies/validate-assignment")
    def validate_staff_competency_endpoint(
        payload: StaffCompetencyValidateRequest,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return portal_access_recovery_hr.validate_staff_competency_assignment(
            db, clinic_id, actor, payload
        )

    @app.get("/api/v1/hr/commission-preview")
    def get_commission_preview_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        return portal_access_recovery_hr.get_commission_payroll_preview(db, clinic_id)

    @app.get("/api/v1/terminology/codes")
    def list_terminology_codes_endpoint(context=Depends(require_perm("encounter.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.TerminologyCodeEntry)
            .where(m.TerminologyCodeEntry.clinic_id == clinic_id)
            .order_by(m.TerminologyCodeEntry.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/terminology/codes", status_code=201)
    def publish_terminology_code_endpoint(
        payload: sch.TerminologyCodeCreate,
        ctx_tuple=Depends(require_principal_perm("plan.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            terminology_templates_lab_reports.publish_terminology_code(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/terminology/mappings")
    def list_terminology_mappings_endpoint(context=Depends(require_perm("encounter.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.TerminologyMappingRule)
            .where(m.TerminologyMappingRule.clinic_id == clinic_id)
            .order_by(m.TerminologyMappingRule.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/terminology/mappings", status_code=201)
    def publish_terminology_mapping_endpoint(
        payload: sch.TerminologyMappingCreate,
        ctx_tuple=Depends(require_principal_perm("plan.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            terminology_templates_lab_reports.publish_terminology_mapping(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/terminology/resolve")
    def resolve_terminology_mapping_endpoint(
        source_code: str,
        target_code_system: str,
        context=Depends(require_perm("encounter.read")),
    ):
        db, clinic_id, _ = context
        return terminology_templates_lab_reports.resolve_terminology_mapping(
            db, clinic_id, source_code, target_code_system
        )

    @app.get("/api/v1/treatment-plans/specialty-templates")
    def list_specialty_templates_endpoint(context=Depends(require_perm("plan.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.SpecialtyPlanTemplate)
            .where(m.SpecialtyPlanTemplate.clinic_id == clinic_id)
            .order_by(m.SpecialtyPlanTemplate.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/treatment-plans/specialty-templates", status_code=201)
    def create_specialty_template_endpoint(
        payload: sch.SpecialtyPlanTemplateCreate,
        context=Depends(require_perm("plan.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            terminology_templates_lab_reports.create_specialty_plan_template(
                db, clinic_id, actor, payload
            )
        )

    @app.post("/api/v1/treatment-plans/specialty-templates/{template_id}/review")
    def review_specialty_template_endpoint(
        template_id: str,
        ctx_tuple=Depends(require_principal_perm("plan.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            terminology_templates_lab_reports.review_specialty_plan_template(
                db, clinic_id, template_id, principal.staff_id, actor
            )
        )

    @app.post("/api/v1/treatment-plans/from-specialty-template", status_code=201)
    def instantiate_specialty_template_endpoint(
        payload: sch.InstantiateSpecialtyTemplateRequest,
        context=Depends(require_perm("plan.write")),
    ):
        db, clinic_id, actor = context
        return terminology_templates_lab_reports.instantiate_plan_from_specialty_template(
            db, clinic_id, actor, payload
        )

    @app.get("/api/v1/lab/price-list")
    def list_lab_price_list_endpoint(context=Depends(require_perm("lab.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.LabVendorPriceItem)
            .where(m.LabVendorPriceItem.clinic_id == clinic_id)
            .order_by(m.LabVendorPriceItem.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/lab/price-list", status_code=201)
    def publish_lab_price_item_endpoint(
        payload: sch.LabVendorPriceCreate,
        context=Depends(require_perm("lab.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            terminology_templates_lab_reports.publish_lab_vendor_price_item(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/lab-cases/{lab_case_id}/invoice-reconciliations")
    def list_lab_invoice_reconciliations_endpoint(
        lab_case_id: str, context=Depends(require_perm("lab.read"))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.LabCase, lab_case_id, clinic_id)
        rows = db.scalars(
            select(m.LabInvoiceReconciliation)
            .where(
                m.LabInvoiceReconciliation.clinic_id == clinic_id,
                m.LabInvoiceReconciliation.lab_case_id == lab_case_id,
            )
            .order_by(m.LabInvoiceReconciliation.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/lab-cases/{lab_case_id}/invoice-reconciliations", status_code=201)
    def reconcile_lab_invoice_endpoint(
        lab_case_id: str,
        payload: sch.LabInvoiceReconcileCreate,
        context=Depends(require_perm("lab.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            terminology_templates_lab_reports.reconcile_lab_vendor_invoice(
                db, clinic_id, lab_case_id, actor, payload
            )
        )

    @app.get("/api/v1/patients/{patient_id}/odontogram/imaging-overlays")
    def list_imaging_overlays_endpoint(
        patient_id: str, context=Depends(require_perm("odontogram.read"))
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.Patient, patient_id, clinic_id)
        rows = db.scalars(
            select(m.LongitudinalImagingOverlay)
            .where(
                m.LongitudinalImagingOverlay.clinic_id == clinic_id,
                m.LongitudinalImagingOverlay.patient_id == patient_id,
            )
            .order_by(m.LongitudinalImagingOverlay.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/patients/{patient_id}/odontogram/imaging-overlays", status_code=201)
    def create_imaging_overlay_endpoint(
        patient_id: str,
        payload: sch.LongitudinalOverlayCreate,
        ctx_tuple=Depends(require_principal_perm("odontogram.write")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            terminology_templates_lab_reports.create_longitudinal_imaging_overlay(
                db, clinic_id, patient_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/reports/scheduled-exports")
    def list_scheduled_report_exports_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ScheduledReportExport)
            .where(m.ScheduledReportExport.clinic_id == clinic_id)
            .order_by(m.ScheduledReportExport.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/reports/scheduled-exports", status_code=201)
    def create_scheduled_report_export_endpoint(
        payload: sch.ScheduledReportExportCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            terminology_templates_lab_reports.create_encrypted_scheduled_report_export(
                db,
                clinic_id,
                principal.staff_id,
                actor,
                cfg.archive_master_secret,
                payload,
            )
        )

    @app.get("/api/v1/ops/releases")
    def list_releases_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ReleaseChangeApproval)
            .where(m.ReleaseChangeApproval.clinic_id == clinic_id)
            .order_by(m.ReleaseChangeApproval.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ops/releases", status_code=201)
    def create_release_proposal_endpoint(
        payload: sch.ReleaseProposalCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            release_sync_and_scheduling_ai.create_release_proposal(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/ops/releases/{release_id}/approve-canary")
    def approve_release_canary_endpoint(
        release_id: str,
        payload: sch.ReleaseCanaryApproveRequest,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            release_sync_and_scheduling_ai.approve_release_canary_stage(
                db, clinic_id, release_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/ops/multibranch-operators")
    def list_multibranch_operators_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.MultibranchOperatorAssignment)
            .where(m.MultibranchOperatorAssignment.home_clinic_id == clinic_id)
            .order_by(m.MultibranchOperatorAssignment.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ops/multibranch-operators", status_code=201)
    def assign_multibranch_operator_endpoint(
        payload: sch.MultibranchOperatorCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            release_sync_and_scheduling_ai.assign_multibranch_operator(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/ops/offline-sync")
    def list_offline_sync_mutations_endpoint(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.OfflineSyncMutation)
            .where(m.OfflineSyncMutation.clinic_id == clinic_id)
            .order_by(m.OfflineSyncMutation.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ops/offline-sync", status_code=201)
    def apply_offline_sync_endpoint(
        payload: sch.OfflineSyncMutationCreate,
        ctx_tuple=Depends(require_principal_perm("context.read")),
    ):
        db, _, _, principal = ctx_tuple
        return doc(
            release_sync_and_scheduling_ai.apply_offline_sync_mutation(db, principal, payload)
        )

    @app.post("/api/v1/ai/appointments/{appointment_id}/noshow-risk", status_code=201)
    def evaluate_noshow_risk_endpoint(
        appointment_id: str,
        payload: sch.NoshowRiskRequest,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            release_sync_and_scheduling_ai.evaluate_calibrated_noshow_risk(
                db, clinic_id, appointment_id, actor, cfg.ai_assist_enabled, payload
            )
        )

    @app.post("/api/v1/ai/scheduling/cpsat-optimize", status_code=201)
    def run_cpsat_optimize_endpoint(
        payload: sch.CpsatOptimizeRequest,
        context=Depends(require_perm("appointment.write")),
    ):
        db, clinic_id, actor = context
        return release_sync_and_scheduling_ai.run_timeout_safe_cpsat_optimizer(
            db, clinic_id, actor, payload
        )

    @app.get("/api/v1/crm/cancellation-outreach-policies")
    def list_cancellation_outreach_policies_endpoint(
        context=Depends(require_perm("operations.read")),
    ):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.CancellationOutreachPolicy)
            .where(m.CancellationOutreachPolicy.clinic_id == clinic_id)
            .order_by(m.CancellationOutreachPolicy.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/crm/cancellation-outreach-policies", status_code=201)
    def create_cancellation_outreach_policy_endpoint(
        payload: sch.CancellationOutreachPolicyCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            sandbox_contracts_benchmark_oidc.create_cancellation_outreach_policy(
                db, clinic_id, principal.staff_id, principal.role, actor, payload
            )
        )

    @app.post(
        "/api/v1/crm/appointments/{appointment_id}/cancellation-outreach",
        status_code=201,
    )
    def execute_cancellation_outreach_endpoint(
        appointment_id: str,
        payload: sch.CancellationOutreachExecuteRequest,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(
            sandbox_contracts_benchmark_oidc.execute_cancellation_outreach(
                db, clinic_id, appointment_id, actor, payload
            )
        )

    @app.get("/api/v1/ops/load-benchmarks")
    def list_load_benchmarks_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.LoadBenchmarkRun)
            .where(m.LoadBenchmarkRun.clinic_id == clinic_id)
            .order_by(m.LoadBenchmarkRun.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ops/load-benchmarks/run", status_code=201)
    def run_load_benchmark_endpoint(
        payload: sch.LoadBenchmarkRunRequest,
        context=Depends(require_perm("staff.manage")),
    ):
        db, clinic_id, actor = context
        return doc(
            sandbox_contracts_benchmark_oidc.run_local_load_benchmark(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/auth/oidc/group-mappings")
    def list_oidc_group_mappings_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.OidcGroupMappingRule)
            .where(m.OidcGroupMappingRule.clinic_id == clinic_id)
            .order_by(m.OidcGroupMappingRule.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/auth/oidc/group-mappings", status_code=201)
    def create_oidc_group_mapping_endpoint(
        payload: sch.OidcGroupMappingCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            sandbox_contracts_benchmark_oidc.create_oidc_group_mapping(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/auth/oidc/directory-sync", status_code=201)
    def sync_oidc_directory_endpoint(
        payload: sch.OidcDirectorySyncRequest,
        context=Depends(require_perm("staff.manage")),
    ):
        db, clinic_id, actor = context
        return doc(
            sandbox_contracts_benchmark_oidc.sync_oidc_directory_membership(
                db, clinic_id, actor, payload
            )
        )

    @app.post("/api/v1/integrations/messaging-sandbox/opt-out-webhook", status_code=201)
    def messaging_opt_out_webhook_endpoint(
        payload: sch.MessagingOptOutWebhookRequest,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(
            sandbox_contracts_benchmark_oidc.record_messaging_opt_out_webhook(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/integrations/messaging-sandbox/dispatches")
    def list_messaging_sandbox_dispatches_endpoint(
        context=Depends(require_perm("operations.read")),
    ):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.MessagingSandboxDispatch)
            .where(m.MessagingSandboxDispatch.clinic_id == clinic_id)
            .order_by(m.MessagingSandboxDispatch.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/integrations/messaging-sandbox/send", status_code=201)
    def send_messaging_sandbox_endpoint(
        payload: sch.MessagingSandboxSendRequest,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(
            sandbox_contracts_benchmark_oidc.send_sandbox_message(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/integrations/payment-sandbox/webhooks")
    def list_payment_sandbox_webhooks_endpoint(
        context=Depends(require_perm("finance.read")),
    ):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.PaymentWebhookInbox)
            .where(m.PaymentWebhookInbox.clinic_id == clinic_id)
            .order_by(m.PaymentWebhookInbox.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/integrations/payment-sandbox/webhook", status_code=201)
    def process_payment_sandbox_webhook_endpoint(
        payload: sch.PaymentSandboxWebhookRequest,
        context=Depends(require_perm("finance.write")),
    ):
        db, clinic_id, actor = context
        return sandbox_contracts_benchmark_oidc.process_signed_payment_webhook(
            db, clinic_id, cfg.auth_secret, actor, payload
        )

    @app.get("/api/v1/interop/dicom/modalities")
    def list_dicom_modalities_endpoint(context=Depends(require_perm("odontogram.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.DicomModalityRegistration)
            .where(m.DicomModalityRegistration.clinic_id == clinic_id)
            .order_by(m.DicomModalityRegistration.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/interop/dicom/modalities", status_code=201)
    def register_dicom_modality_endpoint(
        payload: sch.DicomModalityRegisterCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            dicom_speech_accounting_security.register_dicom_modality(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/interop/dicom/studies")
    def list_dicom_studies_endpoint(context=Depends(require_perm("odontogram.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.DicomStudyQuarantineManifest)
            .where(m.DicomStudyQuarantineManifest.clinic_id == clinic_id)
            .order_by(m.DicomStudyQuarantineManifest.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/interop/dicom/studies/ingest-manifest", status_code=201)
    def ingest_dicom_study_manifest_endpoint(
        payload: sch.DicomStudyManifestIngestCreate,
        context=Depends(require_perm("odontogram.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            dicom_speech_accounting_security.ingest_dicom_study_manifest(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/ai/speech-drafts")
    def list_speech_drafts_endpoint(context=Depends(require_perm("ai.draft"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.SpeechTranscriptionDraft)
            .where(m.SpeechTranscriptionDraft.clinic_id == clinic_id)
            .order_by(m.SpeechTranscriptionDraft.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ai/speech-drafts/transcribe", status_code=201)
    def transcribe_speech_draft_endpoint(
        payload: sch.SpeechDictationTranscribeRequest,
        context=Depends(require_perm("ai.draft")),
    ):
        db, clinic_id, actor = context
        return doc(
            dicom_speech_accounting_security.transcribe_speech_dictation_draft(
                db, clinic_id, actor, cfg.ai_assist_enabled, payload
            )
        )

    @app.get("/api/v1/finance/accounting-exports")
    def list_accounting_exports_endpoint(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.AccountingExportBatch)
            .where(m.AccountingExportBatch.clinic_id == clinic_id)
            .order_by(m.AccountingExportBatch.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/finance/accounting-exports", status_code=201)
    def create_accounting_export_endpoint(
        payload: sch.AccountingExportCreate,
        context=Depends(require_perm("finance.allocate")),
    ):
        db, clinic_id, actor = context
        return doc(
            dicom_speech_accounting_security.export_phi_free_accounting_batch(
                db, clinic_id, actor, payload
            )
        )

    @app.post("/api/v1/security/adversarial-suite/run", status_code=201)
    def run_adversarial_security_suite_endpoint(
        payload: sch.AdversarialSecurityRunRequest,
        context=Depends(require_perm("staff.manage")),
    ):
        db, clinic_id, actor = context
        return doc(
            dicom_speech_accounting_security.run_adversarial_security_suite(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/security/release-gates")
    def list_release_gates_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ReleaseGateEvaluation)
            .where(m.ReleaseGateEvaluation.clinic_id == clinic_id)
            .order_by(m.ReleaseGateEvaluation.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/security/release-gates/evaluate", status_code=201)
    def evaluate_release_gate_endpoint(
        payload: sch.ProductionReleaseGateRequest,
        context=Depends(require_perm("staff.manage")),
    ):
        db, clinic_id, actor = context
        return doc(
            dicom_speech_accounting_security.evaluate_production_release_gate(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/ops/iac-blueprints")
    def list_iac_blueprints_endpoint(context=Depends(require_perm("staff.manage"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.IacBlueprintValidation)
            .where(m.IacBlueprintValidation.clinic_id == clinic_id)
            .order_by(m.IacBlueprintValidation.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ops/iac-blueprints/validate", status_code=201)
    def validate_iac_blueprint_endpoint(
        payload: sch.IacBlueprintValidateRequest,
        context=Depends(require_perm("staff.manage")),
    ):
        db, clinic_id, actor = context
        return doc(
            iac_insurance_lora_plan_attestation.validate_iac_blueprint(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/finance/insurance-partners")
    def list_insurance_partners_endpoint(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.InsurancePartnerContract)
            .where(m.InsurancePartnerContract.clinic_id == clinic_id)
            .order_by(m.InsurancePartnerContract.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/finance/insurance-partners", status_code=201)
    def register_insurance_partner_endpoint(
        payload: sch.InsurancePartnerCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            iac_insurance_lora_plan_attestation.register_insurance_partner(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.get("/api/v1/finance/insurance-claims")
    def list_insurance_claims_endpoint(context=Depends(require_perm("finance.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.InsuranceClaimDraft)
            .where(m.InsuranceClaimDraft.clinic_id == clinic_id)
            .order_by(m.InsuranceClaimDraft.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/finance/insurance-claims", status_code=201)
    def create_insurance_claim_endpoint(
        payload: sch.InsuranceClaimDraftCreate,
        context=Depends(require_perm("finance.write")),
    ):
        db, clinic_id, actor = context
        return doc(
            iac_insurance_lora_plan_attestation.create_insurance_claim_draft(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/ai/adaptation-runs")
    def list_ai_adaptation_runs_endpoint(context=Depends(require_perm("ai.evaluate"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.AiAdaptationRun)
            .where(m.AiAdaptationRun.clinic_id == clinic_id)
            .order_by(m.AiAdaptationRun.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/ai/adaptation-runs/evaluate", status_code=201)
    def evaluate_ai_adaptation_run_endpoint(
        payload: sch.AiAdaptationEvaluateRequest,
        context=Depends(require_perm("ai.evaluate")),
    ):
        db, clinic_id, actor = context
        return doc(
            iac_insurance_lora_plan_attestation.evaluate_ai_adaptation_run(
                db, clinic_id, actor, cfg.ai_assist_enabled, payload
            )
        )

    @app.get("/api/v1/treatment-plans/{plan_id}/review-attestations")
    def list_plan_review_attestations_endpoint(
        plan_id: str,
        context=Depends(require_perm("plan.read")),
    ):
        db, clinic_id, _ = context
        svc.ensure(db, m.TreatmentPlan, plan_id, clinic_id)
        rows = db.scalars(
            select(m.PlanReviewAttestation)
            .where(
                m.PlanReviewAttestation.clinic_id == clinic_id,
                m.PlanReviewAttestation.plan_id == plan_id,
            )
            .order_by(m.PlanReviewAttestation.version_number.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/treatment-plans/{plan_id}/review-attestations", status_code=201)
    def attest_plan_version_endpoint(
        plan_id: str,
        payload: sch.PlanReviewAttestationCreate,
        ctx_tuple=Depends(require_principal_perm("plan.review")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            iac_insurance_lora_plan_attestation.attest_plan_version_simulation(
                db, clinic_id, plan_id, principal.staff_id, principal.role, actor, payload
            )
        )

    @app.get("/api/v1/crm/channels/zalo-zns/contracts")
    def list_zalo_zns_contracts_endpoint(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.ZaloZnsContract)
            .where(m.ZaloZnsContract.clinic_id == clinic_id)
            .order_by(m.ZaloZnsContract.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/crm/channels/zalo-zns/contracts", status_code=201)
    def create_zalo_zns_contract_endpoint(
        payload: sch.ZaloZnsContractCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            channel_contracts_zalo_sms_email.create_zalo_zns_contract(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/crm/channels/zalo-zns/preview-dispatch", status_code=201)
    def preview_zalo_zns_dispatch_endpoint(
        payload: sch.ZaloZnsPreviewDispatchRequest,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(
            channel_contracts_zalo_sms_email.preview_zalo_zns_dispatch(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/crm/channels/sms/dispatches")
    def list_sms_sandbox_dispatches_endpoint(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.SmsSandboxDispatch)
            .where(m.SmsSandboxDispatch.clinic_id == clinic_id)
            .order_by(m.SmsSandboxDispatch.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/crm/channels/sms/send-sandbox", status_code=201)
    def send_sms_sandbox_endpoint(
        payload: sch.SmsSandboxDispatchCreate,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(
            channel_contracts_zalo_sms_email.send_sms_sandbox(db, clinic_id, actor, payload)
        )

    @app.post("/api/v1/crm/channels/sms/dispatches/{dispatch_id}/dlr-receipt", status_code=201)
    def record_sms_dlr_receipt_endpoint(
        dispatch_id: str,
        payload: sch.SmsDeliveryReceiptCreate,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(
            channel_contracts_zalo_sms_email.record_sms_dlr_receipt(
                db, clinic_id, dispatch_id, actor, payload
            )
        )

    @app.get("/api/v1/crm/channels/email/senders")
    def list_email_senders_endpoint(context=Depends(require_perm("operations.read"))):
        db, clinic_id, _ = context
        rows = db.scalars(
            select(m.EmailVerifiedSender)
            .where(m.EmailVerifiedSender.clinic_id == clinic_id)
            .order_by(m.EmailVerifiedSender.created_at.desc())
        ).all()
        return [doc(r) for r in rows]

    @app.post("/api/v1/crm/channels/email/senders", status_code=201)
    def register_email_sender_endpoint(
        payload: sch.EmailVerifiedSenderCreate,
        ctx_tuple=Depends(require_principal_perm("staff.manage")),
    ):
        db, clinic_id, actor, principal = ctx_tuple
        return doc(
            channel_contracts_zalo_sms_email.register_email_sender(
                db, clinic_id, principal.staff_id, actor, payload
            )
        )

    @app.post("/api/v1/crm/channels/email/send-sandbox", status_code=201)
    def send_email_sandbox_endpoint(
        payload: sch.EmailSandboxSendCreate,
        context=Depends(require_perm("operations.recall")),
    ):
        db, clinic_id, actor = context
        return doc(
            channel_contracts_zalo_sms_email.send_email_sandbox(
                db, clinic_id, actor, payload
            )
        )

    @app.get("/api/v1/audit-events/page")
    def list_audit_events_paginated(
        limit: int = 50,
        cursor: str | None = None,
        context=Depends(require_perm("audit.read")),
    ):
        db, clinic_id, _ = context
        return audit_chain.paginate_audit_events(db, clinic_id, cfg.auth_secret, limit, cursor)

    @app.get("/api/v1/audit-events/verify-chain")
    def verify_audit_chain_endpoint(context=Depends(require_perm("audit.read"))):
        db, clinic_id, _ = context
        return audit_chain.verify_clinic_audit_chain(db, clinic_id)

    @app.get("/api/v1/dashboard")
    def dashboard(context=Depends(require_perm("dashboard.read"))):
        db, clinic_id, _ = context

        def count(model):
            return db.scalar(
                select(func.count()).select_from(model).where(model.clinic_id == clinic_id)
            )

        return {
            "patient_count": count(m.Patient),
            "appointment_count": count(m.Appointment),
            "open_appointments": db.scalar(
                select(func.count())
                .select_from(m.Appointment)
                .where(
                    m.Appointment.clinic_id == clinic_id,
                    m.Appointment.status == "confirmed",
                )
            ),
            "encounter_count": count(m.Encounter),
            "treatment_plan_count": count(m.TreatmentPlan),
            "lab_case_count": count(m.LabCase),
            "demo_only": True,
            "clinical_records_not_certified": True,
        }

    @app.get("/api/v1/audit-events")
    def audit_events(context=Depends(require_perm("audit.read"))):
        db, clinic_id, _ = context
        return [
            doc(a)
            for a in db.scalars(
                select(m.AuditEvent)
                .where(m.AuditEvent.clinic_id == clinic_id)
                .order_by(m.AuditEvent.created_at.desc())
                .limit(150)
            )
        ]

    @app.get("/")
    def homepage():
        return FileResponse(DEMO_WEB / "index.html")

    if DEMO_WEB.exists():
        app.mount("/assets", StaticFiles(directory=DEMO_WEB), name="assets")
    app.state.factory = factory
    return app
