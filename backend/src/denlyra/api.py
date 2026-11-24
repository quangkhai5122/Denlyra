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
    fhir_interop,
    inventory,
    models as m,
    operations,
    services as svc,
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
    CashierReconciliationCreate,
    ChairTurnoverCompleteRequest,
    ChairTurnoverCreate,
    ChargeCreate,
    CheckinCreate,
    CheckinStatusUpdate,
    ConsentCreate,
    ConsentWithdrawRequest,
    DentalFindingCreate,
    DocumentAddendumCreate,
    DocumentEnterInErrorRequest,
    DocumentSnapshotCreate,
    DocumentSyntheticSignRequest,
    EncounterCreate,
    EstimateAcceptRequest,
    EstimateCreate,
    FhirBundleValidateRequest,
    FormOfficialExportRequest,
    FormTemplateCreate,
    FormValidatePreviewRequest,
    LabCaseCreate,
    LabPartnerGrantCreate,
    LabPartnerMilestoneUpdate,
    LabReceiveRequest,
    LabRemakeCreate,
    LabStateUpdate,
    NoteCreate,
    NoteUpdate,
    PaperBatchCreate,
    PaperBatchRollbackRequest,
    PaperItemCreate,
    PaperItemVerifyLinkRequest,
    PatientCreate,
    PaymentCreate,
    PlanCreate,
    PlanReassessmentCreate,
    PurchaseOrderCreate,
    PurchaseOrderReceiveRequest,
    RecallCloseRequest,
    RecallCreate,
    RefundCreate,
    ResourceCreateRequest,
    ResourceDowntimeCreate,
    RestoreDrillRequest,
    SignedUrlCreateRequest,
    SkuCreate,
    StaffCreateRequest,
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
    TokenIssueRequest,
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

    @app.get("/api/v1/patients/{patient_id}")
    def get_patient(patient_id: str, context=Depends(require_perm("patient.read"))):
        db, clinic_id, _ = context
        return doc(svc.ensure(db, m.Patient, patient_id, clinic_id))

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
        return {
            "patient_id": patient_id,
            "findings": [doc(x) for x in rows],
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
