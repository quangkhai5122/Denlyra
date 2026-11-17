"""Loopback-only DEMO API. No legal EMR signing, medical decisions or real payments.

Deliberately lacks authentication. All 'X-Demo-*' headers are untrusted simulation selectors.
Never deploy this API publicly or import real patient data.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from collections.abc import Generator

from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .config import Settings
from .db import build_engine, init_demo_schema, session_factory
from .schemas import (
    PatientCreate, AppointmentCreate, EncounterCreate, NoteCreate, NoteUpdate,
    PlanCreate, TaskCreate, LabCaseCreate, LabStateUpdate, ChargeCreate,
    PaymentCreate, AllocationCreate, DentalFindingCreate,
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

    app = FastAPI(title="Denlyra Foundation — SYNTHETIC DEMO ONLY", version="0.1.0",
                  lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])

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

    def ctx(db: Session = Depends(get_db),
            x_demo_clinic: str | None = Header(None),
            x_demo_actor: str | None = Header(None)):
        clinic_id = x_demo_clinic or svc.DEMO_CLINICS[0][0]
        clinic = db.get(m.Clinic, clinic_id)
        if not clinic or not clinic.demo_only:
            raise HTTPException(404, "Demo clinic not found")
        return db, clinic_id, (x_demo_actor or "demo-operator")[:100]

    @app.get("/health")
    def health():
        return {"status": "ok", "demo_only": True, "certified_emr": False}

    @app.get("/api/v1/capabilities")
    def capabilities():
        return {
            "demo_only": True, "use_real_patients": False, "clinical_e_signature": False,
            "emr_certified": False, "patient_portal": False, "production_auth": False,
            "ai_diagnosis": False, "ai_sends_patient_data": False,
            "hospital_integration": False, "live_payments": False,
            "postgres_concurrent_booking_verified": False,
            "real_data_import": False, "legacy_paper_legal_conversion": False,
        }

    @app.get("/api/v1/demo/context")
    def context(context=Depends(ctx)):
        db, clinic_id, _ = context
        return {
            "clinics": [doc(c) for c in db.scalars(select(m.Clinic)).all()],
            "clinic_id": clinic_id,
            "staff": [doc(s) for s in db.scalars(select(m.Staff).where(m.Staff.clinic_id == clinic_id))],
            "chairs": [doc(r) for r in db.scalars(select(m.Resource).where(
                m.Resource.clinic_id == clinic_id, m.Resource.kind == "chair"))],
            "warning": "Synthetic demo only. Headers are not authentication. No legal EMR signature.",
        }

    @app.get("/api/v1/patients")
    def list_patients(context=Depends(ctx)):
        db, clinic_id, _ = context
        return [doc(p) for p in db.scalars(select(m.Patient).where(
            m.Patient.clinic_id == clinic_id).order_by(m.Patient.created_at.desc()))]

    @app.post("/api/v1/patients", status_code=201)
    def create_patient(payload: PatientCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        patient = m.Patient(clinic_id=clinic_id, display_name=payload.display_name.strip(),
                            birth_year=payload.birth_year, phone_demo=payload.phone_demo)
        db.add(patient)
        db.flush()
        svc.audit(db, clinic_id, actor, "patient.created_demo", "patient", patient.id)
        db.commit()
        return doc(patient)

    @app.get("/api/v1/patients/{patient_id}")
    def get_patient(patient_id: str, context=Depends(ctx)):
        db, clinic_id, _ = context
        return doc(svc.ensure(db, m.Patient, patient_id, clinic_id))

    @app.get("/api/v1/appointments")
    def appointments(context=Depends(ctx)):
        db, clinic_id, _ = context
        return [doc(a) for a in db.scalars(select(m.Appointment).where(
            m.Appointment.clinic_id == clinic_id).order_by(m.Appointment.start_at))]

    @app.post("/api/v1/appointments", status_code=201)
    def create_appointment(payload: AppointmentCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.schedule(db, clinic_id, payload, actor))

    @app.post("/api/v1/appointments/{appointment_id}/cancel")
    def cancel(appointment_id: str, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.cancel_appointment(db, clinic_id, appointment_id, actor))

    @app.get("/api/v1/encounters")
    def encounters(context=Depends(ctx)):
        db, clinic_id, _ = context
        return [doc(e) for e in db.scalars(select(m.Encounter).where(
            m.Encounter.clinic_id == clinic_id).order_by(m.Encounter.created_at.desc()))]

    @app.post("/api/v1/encounters", status_code=201)
    def create_encounter(payload: EncounterCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        svc.doctor(db, payload.practitioner_id, clinic_id)
        item = m.Encounter(clinic_id=clinic_id, patient_id=payload.patient_id,
                           practitioner_id=payload.practitioner_id)
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "encounter.created_demo", "encounter", item.id)
        db.commit()
        return doc(item)

    @app.get("/api/v1/encounters/{encounter_id}/notes")
    def list_notes(encounter_id: str, context=Depends(ctx)):
        db, clinic_id, _ = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        notes = db.scalars(select(m.ClinicalNote).where(m.ClinicalNote.encounter_id == encounter_id)).all()
        out = []
        for note in notes:
            item = doc(note)
            item["revisions"] = [doc(r) for r in db.scalars(select(m.NoteRevision).where(
                m.NoteRevision.note_id == note.id).order_by(m.NoteRevision.revision_no))]
            out.append(item)
        return out

    @app.post("/api/v1/encounters/{encounter_id}/notes", status_code=201)
    def create_note(encounter_id: str, payload: NoteCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        note = svc.create_note(db, clinic_id, encounter_id, payload.content, actor,
                               payload.parent_note_id)
        return doc(note)

    @app.put("/api/v1/notes/{note_id}")
    def revise_note(note_id: str, payload: NoteUpdate, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.update_note(db, clinic_id, note_id, payload.content,
                                   payload.expected_revision, actor))

    @app.post("/api/v1/notes/{note_id}/demo-lock")
    def lock_note(note_id: str, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.lock_note_demo(db, clinic_id, note_id, actor))

    @app.get("/api/v1/encounters/{encounter_id}/findings")
    def list_dental_findings(encounter_id: str, context=Depends(ctx)):
        db, clinic_id, _ = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        rows = db.scalars(select(m.DentalFinding).where(
            m.DentalFinding.clinic_id == clinic_id,
            m.DentalFinding.encounter_id == encounter_id
        ).order_by(m.DentalFinding.created_at)).all()
        return [doc(x) for x in rows]

    @app.post("/api/v1/encounters/{encounter_id}/findings", status_code=201)
    def add_dental_finding(encounter_id: str, payload: DentalFindingCreate,
                           context=Depends(ctx)):
        db, clinic_id, actor = context
        svc.ensure(db, m.Encounter, encounter_id, clinic_id)
        item = m.DentalFinding(clinic_id=clinic_id, encounter_id=encounter_id,
                               tooth_code=payload.tooth_code, surface=payload.surface,
                               finding_text_demo=payload.finding_text_demo, actor_demo=actor)
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "odontogram.demo_finding_added", "dental_finding", item.id,
                  {"tooth_code": payload.tooth_code, "surface": payload.surface})
        db.commit()
        return doc(item)

    @app.get("/api/v1/patients/{patient_id}/odontogram")
    def patient_odontogram(patient_id: str, context=Depends(ctx)):
        db, clinic_id, _ = context
        svc.ensure(db, m.Patient, patient_id, clinic_id)
        rows = db.scalars(select(m.DentalFinding).join(
            m.Encounter, m.DentalFinding.encounter_id == m.Encounter.id
        ).where(m.Encounter.clinic_id == clinic_id,
                m.Encounter.patient_id == patient_id).order_by(m.DentalFinding.created_at)).all()
        return {"patient_id": patient_id, "findings": [doc(x) for x in rows],
                "warning": "Demo FDI events only, not a clinical chart or diagnosis."}

    @app.get("/api/v1/treatment-plans")
    def list_plans(context=Depends(ctx)):
        db, clinic_id, _ = context
        plans = db.scalars(select(m.TreatmentPlan).where(m.TreatmentPlan.clinic_id == clinic_id)).all()
        return [doc(p) for p in plans]

    @app.post("/api/v1/treatment-plans", status_code=201)
    def create_plan(payload: PlanCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        plan = m.TreatmentPlan(clinic_id=clinic_id, patient_id=payload.patient_id, title=payload.title)
        db.add(plan)
        db.flush()
        version = m.PlanVersion(plan_id=plan.id, number=1)
        db.add(version)
        db.flush()
        svc.audit(db, clinic_id, actor, "plan.draft_created", "treatment_plan", plan.id)
        db.commit()
        return {**doc(plan), "version_id": version.id, "status": version.status}

    @app.get("/api/v1/treatment-plans/{plan_id}")
    def get_plan(plan_id: str, context=Depends(ctx)):
        db, clinic_id, _ = context
        plan, version = svc.get_plan_version(db, clinic_id, plan_id)
        tasks = db.scalars(select(m.PlanTask).where(m.PlanTask.plan_version_id == version.id)).all()
        return {"plan": doc(plan), "version": doc(version), "tasks": [doc(t) for t in tasks]}

    @app.post("/api/v1/treatment-plans/{plan_id}/tasks", status_code=201)
    def add_task(plan_id: str, payload: TaskCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.add_task(db, clinic_id, plan_id, payload, actor))

    @app.post("/api/v1/treatment-plans/{plan_id}/demo-review")
    def review_plan(plan_id: str, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.review_plan_demo(db, clinic_id, plan_id, actor))

    @app.post("/api/v1/treatment-plans/{plan_id}/versions", status_code=201)
    def plan_new_version(plan_id: str, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.new_version(db, clinic_id, plan_id, actor))

    @app.post("/api/v1/treatment-tasks/{task_id}/demo-complete")
    def complete_task(task_id: str, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.complete_task_demo(db, clinic_id, task_id, actor))

    @app.get("/api/v1/lab-cases")
    def list_lab(context=Depends(ctx)):
        db, clinic_id, _ = context
        return [doc(x) for x in db.scalars(select(m.LabCase).where(m.LabCase.clinic_id == clinic_id))]

    @app.post("/api/v1/lab-cases", status_code=201)
    def new_lab(payload: LabCaseCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        item = m.LabCase(clinic_id=clinic_id, patient_id=payload.patient_id, title=payload.title)
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "lab.case_demo_created", "lab_case", item.id)
        db.commit()
        return doc(item)

    @app.post("/api/v1/lab-cases/{lab_id}/state")
    def lab_transition(lab_id: str, payload: LabStateUpdate, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.set_lab_status(db, clinic_id, lab_id, payload.next_status, actor))

    @app.get("/api/v1/finance/charges")
    def list_charges(context=Depends(ctx)):
        db, clinic_id, _ = context
        return [doc(c) for c in db.scalars(select(m.Charge).where(m.Charge.clinic_id == clinic_id))]

    @app.post("/api/v1/finance/charges", status_code=201)
    def new_charge(payload: ChargeCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        item = m.Charge(clinic_id=clinic_id, patient_id=payload.patient_id,
                        label=payload.label, amount_vnd=payload.amount_vnd)
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "finance.charge_demo_created", "charge", item.id)
        db.commit()
        return doc(item)

    @app.get("/api/v1/finance/payments")
    def list_payments(context=Depends(ctx)):
        db, clinic_id, _ = context
        return [doc(p) for p in db.scalars(select(m.Payment).where(m.Payment.clinic_id == clinic_id))]

    @app.post("/api/v1/finance/payments", status_code=201)
    def new_payment(payload: PaymentCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        svc.ensure(db, m.Patient, payload.patient_id, clinic_id)
        item = m.Payment(clinic_id=clinic_id, patient_id=payload.patient_id,
                         amount_vnd=payload.amount_vnd,
                         external_reference=payload.external_reference)
        db.add(item)
        db.flush()
        svc.audit(db, clinic_id, actor, "finance.payment_demo_recorded", "payment", item.id)
        db.commit()
        return doc(item)

    @app.post("/api/v1/finance/allocations", status_code=201)
    def new_allocation(payload: AllocationCreate, context=Depends(ctx)):
        db, clinic_id, actor = context
        return doc(svc.allocate(db, clinic_id, payload.charge_id,
                                payload.payment_id, payload.amount_vnd, actor))

    @app.get("/api/v1/dashboard")
    def dashboard(context=Depends(ctx)):
        db, clinic_id, _ = context
        def count(model):
            return db.scalar(select(func.count()).select_from(model).where(
                model.clinic_id == clinic_id))
        return {
            "patient_count": count(m.Patient), "appointment_count": count(m.Appointment),
            "open_appointments": db.scalar(select(func.count()).select_from(m.Appointment).where(
                m.Appointment.clinic_id == clinic_id, m.Appointment.status == "confirmed")),
            "encounter_count": count(m.Encounter), "treatment_plan_count": count(m.TreatmentPlan),
            "lab_case_count": count(m.LabCase),
            "demo_only": True, "clinical_records_not_certified": True,
        }

    @app.get("/api/v1/audit-events")
    def audit_events(context=Depends(ctx)):
        db, clinic_id, _ = context
        return [doc(a) for a in db.scalars(select(m.AuditEvent).where(
            m.AuditEvent.clinic_id == clinic_id).order_by(m.AuditEvent.created_at.desc()).limit(150))]

    @app.get("/")
    def homepage():
        return FileResponse(DEMO_WEB / "index.html")

    if DEMO_WEB.exists():
        app.mount("/assets", StaticFiles(directory=DEMO_WEB), name="assets")
    app.state.factory = factory
    return app
