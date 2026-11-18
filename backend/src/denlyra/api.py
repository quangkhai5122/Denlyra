"""Loopback-only DEMO API. No legal EMR signing, medical decisions or real payments.

Supports T001 verified token/session + deny-by-default RBAC/ABAC foundation (ADR-007),
T002 atomic multi-resource booking, T003 quarantined FormRegistry, T004 synthetic
SignatureProvider envelope, and T005 multi-dependency Treatment Journey (ADR-008).
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

from . import auth, models as m, services as svc
from .config import Settings
from .db import build_engine, init_demo_schema, session_factory
from .schemas import (
    AllocationCreate,
    AppointmentCreate,
    AppointmentReschedule,
    ChargeCreate,
    DentalFindingCreate,
    DocumentAddendumCreate,
    DocumentEnterInErrorRequest,
    DocumentSnapshotCreate,
    DocumentSyntheticSignRequest,
    EncounterCreate,
    FormOfficialExportRequest,
    FormTemplateCreate,
    FormValidatePreviewRequest,
    LabCaseCreate,
    LabStateUpdate,
    NoteCreate,
    NoteUpdate,
    PatientCreate,
    PaymentCreate,
    PlanCreate,
    PlanReassessmentCreate,
    RefundCreate,
    ResourceCreateRequest,
    SignedUrlCreateRequest,
    StaffCreateRequest,
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
        if column.name == "metadata_json":
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

    @app.get("/api/v1/patients/{patient_id}")
    def get_patient(patient_id: str, context=Depends(require_perm("patient.read"))):
        db, clinic_id, _ = context
        return doc(svc.ensure(db, m.Patient, patient_id, clinic_id))

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
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        item = m.LabCase(
            clinic_id=clinic_id, patient_id=payload.patient_id, title=payload.title
        )
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "lab.case_demo_created", "lab_case", item.id)
        db.commit()
        return doc(item)

    @app.post("/api/v1/lab-cases/{lab_id}/state")
    def lab_transition(
        lab_id: str, payload: LabStateUpdate, context=Depends(require_perm("lab.write"))
    ):
        db, clinic_id, actor = context
        return doc(svc.set_lab_status(db, clinic_id, lab_id, payload.next_status, actor))

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
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        item = m.Charge(
            clinic_id=clinic_id,
            patient_id=payload.patient_id,
            label=payload.label,
            amount_vnd=payload.amount_vnd,
        )
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "finance.charge_demo_created", "charge", item.id)
        db.commit()
        return doc(item)

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
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        item = m.Payment(
            clinic_id=clinic_id,
            patient_id=payload.patient_id,
            amount_vnd=payload.amount_vnd,
            external_reference=payload.external_reference,
        )
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "finance.payment_demo_recorded", "payment", item.id)
        db.commit()
        return doc(item)

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
