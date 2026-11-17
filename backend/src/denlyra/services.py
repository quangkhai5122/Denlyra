"""Demonstration domain use-cases. NOT medical care, accounting, or legal signature.

Demo-only actor headers are not authentication. PostgreSQL must enforce resource overlap
with an EXCLUDE constraint; SQLite cannot prove concurrent booking safety.
"""
from __future__ import annotations

import hashlib
import json
from datetime import timezone


from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .schemas import AppointmentCreate, TaskCreate


DEMO_CLINICS = [
    ("11111111-1111-4111-8111-111111111111", "Phòng khám Demo A"),
    ("22222222-2222-4222-8222-222222222222", "Phòng khám Demo B"),
]


def demo_seed(db: Session) -> None:
    for clinic_id, clinic_name in DEMO_CLINICS:
        if db.get(m.Clinic, clinic_id):
            continue
        db.add(m.Clinic(id=clinic_id, name=clinic_name, demo_only=True))
        db.add(m.Staff(id=m.uid(), clinic_id=clinic_id, display_name="Bác sĩ demo", role="dentist"))
        db.add(m.Staff(id=m.uid(), clinic_id=clinic_id, display_name="Lễ tân demo", role="receptionist"))
        db.add(m.Resource(id=m.uid(), clinic_id=clinic_id, name="Ghế số 1", kind="chair"))
        db.add(m.Resource(id=m.uid(), clinic_id=clinic_id, name="Ghế số 2", kind="chair"))
    db.commit()


def ensure(db: Session, cls, item_id: str, clinic_id: str | None = None):
    obj = db.get(cls, item_id)
    if obj is None or (clinic_id is not None and getattr(obj, "clinic_id", None) != clinic_id):
        raise HTTPException(404, "Object not found in this demo clinic")
    return obj


def doctor(db: Session, doctor_id: str, clinic_id: str) -> m.Staff:
    s = ensure(db, m.Staff, doctor_id, clinic_id)
    if s.role != "dentist" or not s.active:
        raise HTTPException(422, "Assigned practitioner must be an active demo dentist")
    return s


def chair(db: Session, chair_id: str, clinic_id: str) -> m.Resource:
    r = ensure(db, m.Resource, chair_id, clinic_id)
    if r.kind != "chair":
        raise HTTPException(422, "Assigned resource must be a chair")
    return r


def audit(db: Session, clinic_id: str, actor: str, action: str, typ: str, subject_id: str,
          extra: dict | None = None) -> None:
    db.add(m.AuditEvent(clinic_id=clinic_id, actor_demo=actor[:100], action=action,
                        subject_type=typ, subject_id=subject_id,
                        metadata_json=json.dumps(extra or {}, ensure_ascii=False)))


def dt_utc_naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def schedule(db: Session, clinic_id: str, data: AppointmentCreate, actor: str):
    ensure(db, m.Patient, data.patient_id, clinic_id)
    doctor(db, data.practitioner_id, clinic_id)
    chair(db, data.chair_id, clinic_id)
    start, end = dt_utc_naive(data.start_at), dt_utc_naive(data.end_at)
    resource_keys = [f"dentist:{data.practitioner_id}", f"chair:{data.chair_id}"]
    overlaps = db.scalars(select(m.ResourceBooking).where(
        m.ResourceBooking.clinic_id == clinic_id,
        m.ResourceBooking.state == "active",
        m.ResourceBooking.resource_key.in_(resource_keys),
        m.ResourceBooking.start_at < end,
        m.ResourceBooking.end_at > start,
    )).first()
    if overlaps:
        raise HTTPException(409, "Time conflict: clinician or chair already reserved")
    item = m.Appointment(clinic_id=clinic_id, patient_id=data.patient_id,
                         practitioner_id=data.practitioner_id, chair_id=data.chair_id,
                         start_at=start, end_at=end, reason_demo=data.reason_demo)
    db.add(item)
    db.flush()
    for key in resource_keys:
        db.add(m.ResourceBooking(clinic_id=clinic_id, appointment_id=item.id,
                                 resource_key=key, start_at=start, end_at=end))
    audit(db, clinic_id, actor, "appointment.created", "appointment", item.id)
    db.commit()
    return item


def cancel_appointment(db: Session, clinic_id: str, appointment_id: str, actor: str):
    item = ensure(db, m.Appointment, appointment_id, clinic_id)
    if item.status == "cancelled":
        raise HTTPException(409, "Already cancelled")
    item.status = "cancelled"
    item.version += 1
    for booking in db.scalars(select(m.ResourceBooking).where(
        m.ResourceBooking.clinic_id == clinic_id,
        m.ResourceBooking.appointment_id == item.id, m.ResourceBooking.state == "active"
    )).all():
        booking.state = "cancelled"
    audit(db, clinic_id, actor, "appointment.cancelled", "appointment", item.id)
    db.commit()
    return item


def create_note(db: Session, clinic_id: str, encounter_id: str, content: str,
                actor: str, parent_note_id: str | None = None):
    ensure(db, m.Encounter, encounter_id, clinic_id)
    if parent_note_id:
        original = ensure(db, m.ClinicalNote, parent_note_id, clinic_id)
        if original.encounter_id != encounter_id or original.status != "demo_locked":
            raise HTTPException(422, "Addendum requires a locked parent note in same encounter")
    note = m.ClinicalNote(clinic_id=clinic_id, encounter_id=encounter_id,
                          parent_note_id=parent_note_id, status="draft")
    db.add(note)
    db.flush()
    db.add(m.NoteRevision(note_id=note.id, revision_no=1, content=content,
                          actor_demo=actor, source_type="manual_demo"))
    audit(db, clinic_id, actor, "note.draft_created", "clinical_note", note.id)
    db.commit()
    return note


def update_note(db: Session, clinic_id: str, note_id: str, new_content: str,
                expected_revision: int, actor: str):
    note = ensure(db, m.ClinicalNote, note_id, clinic_id)
    if note.status != "draft":
        raise HTTPException(409, "Demo-locked note cannot be rewritten. Create an addendum.")
    if expected_revision != note.latest_revision:
        raise HTTPException(409, "Optimistic concurrency conflict: note revision changed")
    note.latest_revision += 1
    db.add(m.NoteRevision(note_id=note.id, revision_no=note.latest_revision,
                          content=new_content, actor_demo=actor))
    audit(db, clinic_id, actor, "note.revised", "clinical_note", note.id,
          {"revision": note.latest_revision})
    db.commit()
    return note


def lock_note_demo(db: Session, clinic_id: str, note_id: str, actor: str):
    note = ensure(db, m.ClinicalNote, note_id, clinic_id)
    if note.status != "draft":
        raise HTTPException(409, "Only drafts can be demo-locked")
    revision = db.scalar(select(m.NoteRevision).where(
        m.NoteRevision.note_id == note.id,
        m.NoteRevision.revision_no == note.latest_revision,
    ))
    digest_input = json.dumps({"note_id": note.id, "revision": note.latest_revision,
                               "content": revision.content}, ensure_ascii=False,
                              sort_keys=True).encode("utf-8")
    note.locked_digest = hashlib.sha256(digest_input).hexdigest()
    note.status = "demo_locked"
    audit(db, clinic_id, actor, "note.demo_locked_NOT_signed", "clinical_note", note.id,
          {"digest": note.locked_digest})
    db.commit()
    return note


def get_plan_version(db: Session, clinic_id: str, plan_id: str):
    plan = ensure(db, m.TreatmentPlan, plan_id, clinic_id)
    version = db.scalar(select(m.PlanVersion).where(
        m.PlanVersion.plan_id == plan.id, m.PlanVersion.number == plan.current_version
    ))
    if version is None:
        raise HTTPException(500, "Plan version missing")
    return plan, version


def add_task(db: Session, clinic_id: str, plan_id: str, data: TaskCreate, actor: str):
    plan, version = get_plan_version(db, clinic_id, plan_id)
    if version.status != "draft":
        raise HTTPException(409, "Reviewed plan version is immutable; create a new version")
    if data.depends_on_task_id:
        dependency = db.get(m.PlanTask, data.depends_on_task_id)
        if not dependency or dependency.plan_version_id != version.id:
            raise HTTPException(422, "Dependency must exist in this plan version")
    task = m.PlanTask(plan_version_id=version.id, title=data.title, phase=data.phase,
                      depends_on_task_id=data.depends_on_task_id)
    db.add(task)
    db.flush()
    audit(db, clinic_id, actor, "plan.task_created", "plan_task", task.id)
    db.commit()
    return task


def new_version(db: Session, clinic_id: str, plan_id: str, actor: str):
    plan, current = get_plan_version(db, clinic_id, plan_id)
    if current.status != "demo_reviewed":
        raise HTTPException(409, "Only a demo-reviewed version can be branched")
    items = db.scalars(select(m.PlanTask).where(m.PlanTask.plan_version_id == current.id)).all()
    new = m.PlanVersion(plan_id=plan.id, number=plan.current_version + 1, status="draft")
    db.add(new)
    db.flush()
    id_map = {}
    for old in items:
        replacement = m.PlanTask(plan_version_id=new.id, title=old.title, phase=old.phase,
                                 status="pending")
        db.add(replacement)
        db.flush()
        id_map[old.id] = replacement
    for old in items:
        if old.depends_on_task_id:
            id_map[old.id].depends_on_task_id = id_map[old.depends_on_task_id].id
    plan.current_version += 1
    audit(db, clinic_id, actor, "plan.version_created", "treatment_plan", plan.id,
          {"number": new.number})
    db.commit()
    return new


def review_plan_demo(db: Session, clinic_id: str, plan_id: str, actor: str):
    plan, version = get_plan_version(db, clinic_id, plan_id)
    if version.status != "draft":
        raise HTTPException(409, "Already reviewed")
    tasks = db.scalars(select(m.PlanTask).where(m.PlanTask.plan_version_id == version.id)).all()
    if not tasks:
        raise HTTPException(422, "A plan must have tasks")
    version.status = "demo_reviewed"
    version.reviewer_demo = actor
    audit(db, clinic_id, actor, "plan.demo_reviewed_NOT_clinical_approval", "plan_version", version.id)
    db.commit()
    return version


def complete_task_demo(db: Session, clinic_id: str, task_id: str, actor: str):
    task = db.get(m.PlanTask, task_id)
    if task is None:
        raise HTTPException(404, "Unknown task")
    version = db.get(m.PlanVersion, task.plan_version_id)
    plan = ensure(db, m.TreatmentPlan, version.plan_id, clinic_id)
    if version.number != plan.current_version or version.status != "demo_reviewed":
        raise HTTPException(409, "Only the current demo-reviewed version can be progressed")
    if task.status == "completed":
        raise HTTPException(409, "Already completed")
    if task.depends_on_task_id:
        dependency = db.get(m.PlanTask, task.depends_on_task_id)
        if dependency.status != "completed":
            raise HTTPException(409, "Prerequisite task not completed")
    task.status = "completed"
    task.completed_at = m.utcnow()
    audit(db, clinic_id, actor, "plan.task_demo_completed_NOT_procedure", "plan_task", task.id)
    db.commit()
    return task


LAB_TRANSITIONS = {
    "requested": {"accepted", "cancelled"},
    "accepted": {"in_progress", "cancelled"},
    "in_progress": {"ready", "revision_requested"},
    "ready": {"received", "revision_requested"},
    "received": {"verified", "revision_requested"},
    "revision_requested": {"in_progress", "cancelled"},
    "verified": set(), "cancelled": set(),
}


def set_lab_status(db: Session, clinic_id: str, lab_id: str, next_status: str, actor: str):
    item = ensure(db, m.LabCase, lab_id, clinic_id)
    if next_status not in LAB_TRANSITIONS.get(item.status, set()):
        raise HTTPException(409, f"Invalid lab state transition: {item.status} -> {next_status}")
    before = item.status
    item.status = next_status
    audit(db, clinic_id, actor, "lab.status_changed", "lab_case", item.id,
          {"from": before, "to": next_status})
    db.commit()
    return item


def allocate(db: Session, clinic_id: str, charge_id: str, payment_id: str,
             amount_vnd: int, actor: str):
    # with_for_update() provides row locks on PostgreSQL, but NOT SQLite.
    charge = db.scalar(select(m.Charge).where(
        m.Charge.id == charge_id, m.Charge.clinic_id == clinic_id).with_for_update())
    payment = db.scalar(select(m.Payment).where(
        m.Payment.id == payment_id, m.Payment.clinic_id == clinic_id).with_for_update())
    if not charge or not payment or charge.patient_id != payment.patient_id:
        raise HTTPException(422, "Charge and payment must belong to same demo patient and clinic")
    a = db.scalar(select(func.coalesce(func.sum(m.PaymentAllocation.amount_vnd), 0)).where(
        m.PaymentAllocation.charge_id == charge.id))
    b = db.scalar(select(func.coalesce(func.sum(m.PaymentAllocation.amount_vnd), 0)).where(
        m.PaymentAllocation.payment_id == payment.id))
    if a + amount_vnd > charge.amount_vnd or b + amount_vnd > payment.amount_vnd:
        raise HTTPException(409, "Allocation exceeds charge or available payment")
    item = m.PaymentAllocation(charge_id=charge.id, payment_id=payment.id,
                               amount_vnd=amount_vnd)
    db.add(item)
    db.flush()
    audit(db, clinic_id, actor, "payment.demo_allocated", "payment_allocation", item.id)
    db.commit()
    return item
