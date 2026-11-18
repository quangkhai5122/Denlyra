"""Demonstration domain use-cases. NOT medical care, accounting, or legal signature.

PostgreSQL enforces resource overlap with an EXCLUDE constraint; SQLite uses a BEFORE INSERT
trigger for local synthetic testing. Production requires live PostgreSQL verification (T002)
and independent security/clinical/legal sign-off.
"""
from __future__ import annotations

from datetime import timedelta, timezone
import hashlib
import hmac
import json

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models as m, signing
from .schemas import (
    AppointmentCreate,
    AppointmentReschedule,
    CashierReconciliationCreate,
    ChargeCreate,
    ConsentCreate,
    ConsentWithdrawRequest,
    DocumentAddendumCreate,
    DocumentEnterInErrorRequest,
    DocumentSnapshotCreate,
    DocumentSyntheticSignRequest,
    EstimateAcceptRequest,
    EstimateCreate,
    FormOfficialExportRequest,
    FormTemplateCreate,
    FormValidatePreviewRequest,
    LabCaseCreate,
    LabPartnerGrantCreate,
    LabPartnerMilestoneUpdate,
    LabReceiveRequest,
    LabRemakeCreate,
    PaperBatchCreate,
    PaperBatchRollbackRequest,
    PaperItemCreate,
    PaperItemVerifyLinkRequest,
    PaymentCreate,
    PlanReassessmentCreate,
    RefundCreate,
    ResourceCreateRequest,
    StaffCreateRequest,
    TaskCoordinationLinkCreate,
    TaskCreate,
    TaskDependenciesUpdate,
)


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
        db.add(m.Staff(id=m.uid(), clinic_id=clinic_id, display_name="Kế toán demo", role="finance"))
        db.add(m.Staff(id=m.uid(), clinic_id=clinic_id, display_name="Chủ phòng khám demo", role="clinic_owner"))
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
    if s.role not in {"dentist", "medical_director"} or not s.active:
        raise HTTPException(422, "Assigned practitioner must be an active demo dentist")
    return s


def chair(db: Session, chair_id: str, clinic_id: str) -> m.Resource:
    r = ensure(db, m.Resource, chair_id, clinic_id)
    if r.kind != "chair":
        raise HTTPException(422, "Assigned resource must be a chair")
    return r


def equipment(db: Session, resource_id: str, clinic_id: str) -> m.Resource:
    r = ensure(db, m.Resource, resource_id, clinic_id)
    if r.kind != "device":
        raise HTTPException(422, "Assigned equipment resource must have kind='device'")
    return r


def audit(
    db: Session,
    clinic_id: str,
    actor: str,
    action: str,
    typ: str,
    subject_id: str,
    extra: dict | None = None,
) -> None:
    db.add(
        m.AuditEvent(
            clinic_id=clinic_id,
            actor_demo=actor[:100],
            action=action,
            subject_type=typ,
            subject_id=subject_id,
            metadata_json=json.dumps(extra or {}, ensure_ascii=False),
        )
    )


def outbox(
    db: Session,
    clinic_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict | None = None,
) -> None:
    db.add(
        m.OutboxEvent(
            clinic_id=clinic_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
        )
    )


def ledger(
    db: Session,
    clinic_id: str,
    patient_id: str,
    entry_type: str,
    direction: str,
    amount_vnd: int,
    reference_type: str,
    reference_id: str,
    actor: str,
    payment_method: str | None = None,
) -> None:
    db.add(
        m.LedgerEntry(
            clinic_id=clinic_id,
            patient_id=patient_id,
            entry_type=entry_type,
            direction=direction,
            amount_vnd=amount_vnd,
            payment_method=payment_method,
            reference_type=reference_type,
            reference_id=reference_id,
            actor_demo=actor[:100],
        )
    )


def dt_utc_naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def create_staff(db: Session, clinic_id: str, data: StaffCreateRequest, actor: str) -> m.Staff:
    item = m.Staff(
        id=m.uid(),
        clinic_id=clinic_id,
        branch_id=data.branch_id,
        display_name=data.display_name.strip(),
        role=data.role,
        active=True,
        token_version=1,
    )
    db.add(item)
    db.flush()
    audit(db, clinic_id, actor, "staff.created_demo", "staff", item.id, {"role": item.role})
    db.commit()
    return item


def deactivate_staff(db: Session, clinic_id: str, staff_id: str, actor: str) -> m.Staff:
    staff = ensure(db, m.Staff, staff_id, clinic_id)
    staff.active = False
    staff.token_version = (staff.token_version or 1) + 1
    audit(
        db,
        clinic_id,
        actor,
        "staff.membership_deactivated",
        "staff",
        staff.id,
        {"token_version": staff.token_version},
    )
    db.commit()
    return staff


def create_resource(db: Session, clinic_id: str, data: ResourceCreateRequest, actor: str) -> m.Resource:
    item = m.Resource(
        id=m.uid(),
        clinic_id=clinic_id,
        name=data.name.strip(),
        kind=data.kind,
    )
    db.add(item)
    db.flush()
    audit(db, clinic_id, actor, "resource.created_demo", "resource", item.id, {"kind": item.kind})
    db.commit()
    return item


def schedule(
    db: Session,
    clinic_id: str,
    data: AppointmentCreate,
    actor: str,
    skip_preread: bool = False,
):
    start, end = dt_utc_naive(data.start_at), dt_utc_naive(data.end_at)
    if data.idempotency_key:
        existing = db.scalar(
            select(m.Appointment).where(
                m.Appointment.clinic_id == clinic_id,
                m.Appointment.idempotency_key == data.idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.patient_id == data.patient_id
                and existing.practitioner_id == data.practitioner_id
                and existing.chair_id == data.chair_id
                and existing.start_at == start
                and existing.end_at == end
            ):
                return existing
            raise HTTPException(
                409, "Idempotency key already used with different booking parameters"
            )

    ensure(db, m.Patient, data.patient_id, clinic_id)
    doctor(db, data.practitioner_id, clinic_id)
    chair(db, data.chair_id, clinic_id)
    unique_eq = sorted(set(data.equipment_ids))
    for eq_id in unique_eq:
        equipment(db, eq_id, clinic_id)

    resource_keys = [
        f"dentist:{data.practitioner_id}",
        f"chair:{data.chair_id}",
        *[f"device:{eq_id}" for eq_id in unique_eq],
    ]
    if not skip_preread:
        overlaps = db.scalars(
            select(m.ResourceBooking).where(
                m.ResourceBooking.clinic_id == clinic_id,
                m.ResourceBooking.state == "active",
                m.ResourceBooking.resource_key.in_(resource_keys),
                m.ResourceBooking.start_at < end,
                m.ResourceBooking.end_at > start,
            )
        ).first()
        if overlaps:
            raise HTTPException(409, "Time conflict: clinician, chair, or equipment already reserved")

    try:
        item = m.Appointment(
            clinic_id=clinic_id,
            patient_id=data.patient_id,
            practitioner_id=data.practitioner_id,
            chair_id=data.chair_id,
            start_at=start,
            end_at=end,
            reason_demo=data.reason_demo,
            idempotency_key=data.idempotency_key,
        )
        db.add(item)
        db.flush()
        for key in resource_keys:
            db.add(
                m.ResourceBooking(
                    clinic_id=clinic_id,
                    appointment_id=item.id,
                    resource_key=key,
                    start_at=start,
                    end_at=end,
                )
            )
        audit(
            db,
            clinic_id,
            actor,
            "appointment.created",
            "appointment",
            item.id,
            {"resources": resource_keys},
        )
        outbox(db, clinic_id, "appointment.created", "appointment", item.id, {"patient_id": item.patient_id})
        db.commit()
        return item
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Time conflict: clinician, chair, or equipment already reserved"
        ) from exc


def cancel_appointment(db: Session, clinic_id: str, appointment_id: str, actor: str):
    item = ensure(db, m.Appointment, appointment_id, clinic_id)
    if item.status == "cancelled":
        raise HTTPException(409, "Already cancelled")
    item.status = "cancelled"
    item.version += 1
    for booking in db.scalars(
        select(m.ResourceBooking).where(
            m.ResourceBooking.clinic_id == clinic_id,
            m.ResourceBooking.appointment_id == item.id,
            m.ResourceBooking.state == "active",
        )
    ).all():
        booking.state = "cancelled"
    audit(db, clinic_id, actor, "appointment.cancelled", "appointment", item.id)
    outbox(db, clinic_id, "appointment.cancelled", "appointment", item.id)
    db.commit()
    return item


def reschedule_appointment(
    db: Session,
    clinic_id: str,
    appointment_id: str,
    data: AppointmentReschedule,
    actor: str,
):
    old = ensure(db, m.Appointment, appointment_id, clinic_id)
    if old.status == "cancelled":
        raise HTTPException(409, "Cannot reschedule an already cancelled appointment")
    new_practitioner_id = data.practitioner_id or old.practitioner_id
    new_chair_id = data.chair_id or old.chair_id
    doctor(db, new_practitioner_id, clinic_id)
    chair(db, new_chair_id, clinic_id)
    unique_eq = sorted(set(data.equipment_ids))
    for eq_id in unique_eq:
        equipment(db, eq_id, clinic_id)

    start, end = dt_utc_naive(data.start_at), dt_utc_naive(data.end_at)
    resource_keys = [
        f"dentist:{new_practitioner_id}",
        f"chair:{new_chair_id}",
        *[f"device:{eq_id}" for eq_id in unique_eq],
    ]
    try:
        old.status = "cancelled"
        old.version += 1
        for booking in db.scalars(
            select(m.ResourceBooking).where(
                m.ResourceBooking.clinic_id == clinic_id,
                m.ResourceBooking.appointment_id == old.id,
                m.ResourceBooking.state == "active",
            )
        ).all():
            booking.state = "cancelled"
        db.flush()

        overlaps = db.scalars(
            select(m.ResourceBooking).where(
                m.ResourceBooking.clinic_id == clinic_id,
                m.ResourceBooking.state == "active",
                m.ResourceBooking.resource_key.in_(resource_keys),
                m.ResourceBooking.start_at < end,
                m.ResourceBooking.end_at > start,
            )
        ).first()
        if overlaps:
            db.rollback()
            raise HTTPException(409, "Time conflict on target slot; original appointment preserved")

        replacement = m.Appointment(
            clinic_id=clinic_id,
            patient_id=old.patient_id,
            practitioner_id=new_practitioner_id,
            chair_id=new_chair_id,
            start_at=start,
            end_at=end,
            reason_demo=data.reason_demo,
            rescheduled_from_id=old.id,
        )
        db.add(replacement)
        db.flush()
        for key in resource_keys:
            db.add(
                m.ResourceBooking(
                    clinic_id=clinic_id,
                    appointment_id=replacement.id,
                    resource_key=key,
                    start_at=start,
                    end_at=end,
                )
            )
        audit(
            db,
            clinic_id,
            actor,
            "appointment.rescheduled",
            "appointment",
            replacement.id,
            {"rescheduled_from_id": old.id},
        )
        outbox(
            db,
            clinic_id,
            "appointment.rescheduled",
            "appointment",
            replacement.id,
            {"previous_appointment_id": old.id, "patient_id": old.patient_id},
        )
        db.commit()
        return replacement
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Time conflict on target slot; original appointment preserved"
        ) from exc


def create_note(
    db: Session,
    clinic_id: str,
    encounter_id: str,
    content: str,
    actor: str,
    parent_note_id: str | None = None,
):
    ensure(db, m.Encounter, encounter_id, clinic_id)
    if parent_note_id:
        original = ensure(db, m.ClinicalNote, parent_note_id, clinic_id)
        if original.encounter_id != encounter_id or original.status != "demo_locked":
            raise HTTPException(422, "Addendum requires a locked parent note in same encounter")
    note = m.ClinicalNote(
        clinic_id=clinic_id,
        encounter_id=encounter_id,
        parent_note_id=parent_note_id,
        status="draft",
    )
    db.add(note)
    db.flush()
    db.add(
        m.NoteRevision(
            note_id=note.id,
            revision_no=1,
            content=content,
            actor_demo=actor,
            source_type="manual_demo",
        )
    )
    audit(db, clinic_id, actor, "note.draft_created", "clinical_note", note.id)
    db.commit()
    return note


def update_note(
    db: Session,
    clinic_id: str,
    note_id: str,
    new_content: str,
    expected_revision: int,
    actor: str,
):
    note = ensure(db, m.ClinicalNote, note_id, clinic_id)
    if note.status != "draft":
        raise HTTPException(409, "Demo-locked note cannot be rewritten. Create an addendum.")
    if expected_revision != note.latest_revision:
        raise HTTPException(409, "Optimistic concurrency conflict: note revision changed")
    note.latest_revision += 1
    db.add(
        m.NoteRevision(
            note_id=note.id,
            revision_no=note.latest_revision,
            content=new_content,
            actor_demo=actor,
        )
    )
    audit(
        db,
        clinic_id,
        actor,
        "note.revised",
        "clinical_note",
        note.id,
        {"revision": note.latest_revision},
    )
    db.commit()
    return note


def lock_note_demo(db: Session, clinic_id: str, note_id: str, actor: str):
    note = ensure(db, m.ClinicalNote, note_id, clinic_id)
    if note.status != "draft":
        raise HTTPException(409, "Only drafts can be demo-locked")
    revision = db.scalar(
        select(m.NoteRevision).where(
            m.NoteRevision.note_id == note.id,
            m.NoteRevision.revision_no == note.latest_revision,
        )
    )
    digest_input = json.dumps(
        {"note_id": note.id, "revision": note.latest_revision, "content": revision.content},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    note.locked_digest = hashlib.sha256(digest_input).hexdigest()
    note.status = "demo_locked"
    audit(
        db,
        clinic_id,
        actor,
        "note.demo_locked_NOT_signed",
        "clinical_note",
        note.id,
        {"digest": note.locked_digest},
    )
    db.commit()
    return note


def get_plan_version(db: Session, clinic_id: str, plan_id: str):
    plan = ensure(db, m.TreatmentPlan, plan_id, clinic_id)
    version = db.scalar(
        select(m.PlanVersion).where(
            m.PlanVersion.plan_id == plan.id,
            m.PlanVersion.number == plan.current_version,
        )
    )
    if version is None:
        raise HTTPException(500, "Plan version missing")
    return plan, version


def _validate_acyclic_dependencies(
    db: Session,
    plan_version_id: str,
    target_task_id: str,
    new_dep_ids: list[str],
) -> None:
    tasks = db.scalars(
        select(m.PlanTask).where(m.PlanTask.plan_version_id == plan_version_id)
    ).all()
    valid_ids = {t.id for t in tasks} | {target_task_id}
    for dep_id in new_dep_ids:
        if dep_id == target_task_id:
            raise HTTPException(422, "Cycle detected: task cannot depend on itself")
        if dep_id not in valid_ids:
            raise HTTPException(422, "Dependency must exist in this plan version")

    adj: dict[str, set[str]] = {tid: set() for tid in valid_ids}
    for t in tasks:
        if t.depends_on_task_id:
            adj[t.id].add(t.depends_on_task_id)
    existing_edges = db.scalars(
        select(m.PlanTaskDependency).where(m.PlanTaskDependency.plan_version_id == plan_version_id)
    ).all()
    for edge in existing_edges:
        adj.setdefault(edge.task_id, set()).add(edge.depends_on_task_id)
    for dep_id in new_dep_ids:
        adj.setdefault(target_task_id, set()).add(dep_id)

    state: dict[str, int] = {}

    def dfs(node: str) -> None:
        state[node] = 1
        for nxt in adj.get(node, set()):
            st = state.get(nxt, 0)
            if st == 1:
                raise HTTPException(422, "Cycle detected in treatment plan task graph")
            if st == 0:
                dfs(nxt)
        state[node] = 2

    for node in list(adj.keys()):
        if state.get(node, 0) == 0:
            dfs(node)


def add_task(db: Session, clinic_id: str, plan_id: str, data: TaskCreate, actor: str):
    plan, version = get_plan_version(db, clinic_id, plan_id)
    if version.status != "draft":
        raise HTTPException(409, "Reviewed plan version is immutable; create a new version")
    dep_ids: list[str] = []
    if data.depends_on_task_id:
        dep_ids.append(data.depends_on_task_id)
    for d_id in data.depends_on_task_ids:
        if d_id not in dep_ids:
            dep_ids.append(d_id)

    task_id = m.uid()
    if dep_ids:
        _validate_acyclic_dependencies(db, version.id, task_id, dep_ids)

    due_naive = dt_utc_naive(data.due_at) if data.due_at else None
    task = m.PlanTask(
        id=task_id,
        plan_version_id=version.id,
        title=data.title,
        phase=data.phase,
        owner_role=data.owner_role,
        due_at=due_naive,
        depends_on_task_id=dep_ids[0] if dep_ids else None,
    )
    db.add(task)
    db.flush()
    for dep_id in dep_ids:
        db.add(
            m.PlanTaskDependency(
                plan_version_id=version.id,
                task_id=task.id,
                depends_on_task_id=dep_id,
            )
        )
    audit(db, clinic_id, actor, "plan.task_created", "plan_task", task.id)
    db.commit()
    return task


def set_task_dependencies(
    db: Session,
    clinic_id: str,
    task_id: str,
    data: TaskDependenciesUpdate,
    actor: str,
):
    task = db.get(m.PlanTask, task_id)
    if task is None:
        raise HTTPException(404, "Unknown task")
    version = db.get(m.PlanVersion, task.plan_version_id)
    ensure(db, m.TreatmentPlan, version.plan_id, clinic_id)
    if version.status != "draft":
        raise HTTPException(409, "Reviewed plan version is immutable; create a new version")

    unique_deps = list(dict.fromkeys(data.depends_on_task_ids))
    _validate_acyclic_dependencies(db, version.id, task.id, unique_deps)

    existing = {
        e.depends_on_task_id
        for e in db.scalars(
            select(m.PlanTaskDependency).where(m.PlanTaskDependency.task_id == task.id)
        ).all()
    }
    for dep_id in unique_deps:
        if dep_id not in existing:
            db.add(
                m.PlanTaskDependency(
                    plan_version_id=version.id,
                    task_id=task.id,
                    depends_on_task_id=dep_id,
                )
            )
    if not task.depends_on_task_id and unique_deps:
        task.depends_on_task_id = unique_deps[0]
    audit(
        db,
        clinic_id,
        actor,
        "plan.task_dependencies_updated",
        "plan_task",
        task.id,
        {"depends_on_task_ids": unique_deps},
    )
    db.commit()
    return task


def link_task_coordination(
    db: Session,
    clinic_id: str,
    task_id: str,
    data: TaskCoordinationLinkCreate,
    actor: str,
) -> dict:
    task = db.get(m.PlanTask, task_id)
    if task is None:
        raise HTTPException(404, "Unknown task")
    version = db.get(m.PlanVersion, task.plan_version_id)
    plan = ensure(db, m.TreatmentPlan, version.plan_id, clinic_id)

    if data.target_type == "appointment":
        appt = ensure(db, m.Appointment, data.target_id, clinic_id)
        if appt.patient_id != plan.patient_id:
            raise HTTPException(422, "Appointment belongs to a different patient")
    elif data.target_type == "lab_case":
        lab = ensure(db, m.LabCase, data.target_id, clinic_id)
        if lab.patient_id != plan.patient_id:
            raise HTTPException(422, "Lab case belongs to a different patient")
    elif data.target_type == "charge":
        chg = ensure(db, m.Charge, data.target_id, clinic_id)
        if chg.patient_id != plan.patient_id:
            raise HTTPException(422, "Charge belongs to a different patient")

    link = m.TreatmentCoordinationLink(
        clinic_id=clinic_id,
        task_id=task.id,
        target_type=data.target_type,
        target_id=data.target_id,
        requires_verified_lab=data.requires_verified_lab if data.target_type == "lab_case" else False,
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Coordination link already exists") from exc

    audit(
        db,
        clinic_id,
        actor,
        f"plan.task_linked_{data.target_type}",
        "plan_task",
        task.id,
        {"target_id": data.target_id, "requires_verified_lab": link.requires_verified_lab},
    )
    outbox(
        db,
        clinic_id,
        f"treatment.task_linked.{data.target_type}",
        "plan_task",
        task.id,
        {"target_id": data.target_id},
    )
    db.commit()
    return {
        "id": link.id,
        "task_id": link.task_id,
        "target_type": link.target_type,
        "target_id": link.target_id,
        "requires_verified_lab": link.requires_verified_lab,
    }


def new_version(db: Session, clinic_id: str, plan_id: str, actor: str):
    plan, current = get_plan_version(db, clinic_id, plan_id)
    if current.status != "demo_reviewed":
        raise HTTPException(409, "Only a demo-reviewed version can be branched")
    items = db.scalars(select(m.PlanTask).where(m.PlanTask.plan_version_id == current.id)).all()
    old_edges = db.scalars(
        select(m.PlanTaskDependency).where(m.PlanTaskDependency.plan_version_id == current.id)
    ).all()
    new = m.PlanVersion(plan_id=plan.id, number=plan.current_version + 1, status="draft")
    db.add(new)
    db.flush()
    id_map = {}
    for old in items:
        replacement = m.PlanTask(
            plan_version_id=new.id,
            title=old.title,
            phase=old.phase,
            owner_role=old.owner_role,
            due_at=old.due_at,
            status="pending",
        )
        db.add(replacement)
        db.flush()
        id_map[old.id] = replacement
    for old in items:
        if old.depends_on_task_id and old.depends_on_task_id in id_map:
            id_map[old.id].depends_on_task_id = id_map[old.depends_on_task_id].id
    for edge in old_edges:
        if edge.task_id in id_map and edge.depends_on_task_id in id_map:
            db.add(
                m.PlanTaskDependency(
                    plan_version_id=new.id,
                    task_id=id_map[edge.task_id].id,
                    depends_on_task_id=id_map[edge.depends_on_task_id].id,
                )
            )
    plan.current_version += 1
    audit(
        db,
        clinic_id,
        actor,
        "plan.version_created",
        "treatment_plan",
        plan.id,
        {"number": new.number},
    )
    db.commit()
    return new


def reassess_plan(
    db: Session,
    clinic_id: str,
    plan_id: str,
    data: PlanReassessmentCreate,
    actor: str,
) -> dict:
    plan, current = get_plan_version(db, clinic_id, plan_id)
    if current.status != "demo_reviewed":
        raise HTTPException(409, "Reassessment requires a reviewed current plan version")
    items = db.scalars(select(m.PlanTask).where(m.PlanTask.plan_version_id == current.id)).all()
    source_task = next((t for t in items if t.id == data.source_task_id), None)
    if source_task is None:
        raise HTTPException(422, "source_task_id must belong to the current plan version")

    old_edges = db.scalars(
        select(m.PlanTaskDependency).where(m.PlanTaskDependency.plan_version_id == current.id)
    ).all()
    new_ver = m.PlanVersion(
        plan_id=plan.id,
        number=plan.current_version + 1,
        status="demo_reviewed",
        reviewer_demo=actor,
    )
    db.add(new_ver)
    db.flush()

    id_map: dict[str, m.PlanTask] = {}
    for old in items:
        cloned = m.PlanTask(
            plan_version_id=new_ver.id,
            title=old.title,
            phase=old.phase,
            owner_role=old.owner_role,
            due_at=old.due_at,
            reassessed_from_task_id=old.reassessed_from_task_id,
            completion_evidence_note=old.completion_evidence_note,
            status=old.status,
            completed_at=old.completed_at,
        )
        db.add(cloned)
        db.flush()
        id_map[old.id] = cloned
        old_links = db.scalars(
            select(m.TreatmentCoordinationLink).where(
                m.TreatmentCoordinationLink.task_id == old.id
            )
        ).all()
        for lnk in old_links:
            db.add(
                m.TreatmentCoordinationLink(
                    clinic_id=clinic_id,
                    task_id=cloned.id,
                    target_type=lnk.target_type,
                    target_id=lnk.target_id,
                    requires_verified_lab=lnk.requires_verified_lab,
                )
            )

    for old in items:
        if old.depends_on_task_id and old.depends_on_task_id in id_map:
            id_map[old.id].depends_on_task_id = id_map[old.depends_on_task_id].id
    for edge in old_edges:
        if edge.task_id in id_map and edge.depends_on_task_id in id_map:
            db.add(
                m.PlanTaskDependency(
                    plan_version_id=new_ver.id,
                    task_id=id_map[edge.task_id].id,
                    depends_on_task_id=id_map[edge.depends_on_task_id].id,
                )
            )

    mapped_source = id_map[source_task.id]
    followup = m.PlanTask(
        plan_version_id=new_ver.id,
        title=data.followup_task_title,
        phase=data.followup_phase,
        owner_role=data.owner_role,
        depends_on_task_id=mapped_source.id,
        reassessed_from_task_id=mapped_source.id,
        status="pending",
    )
    db.add(followup)
    db.flush()
    db.add(
        m.PlanTaskDependency(
            plan_version_id=new_ver.id,
            task_id=followup.id,
            depends_on_task_id=mapped_source.id,
        )
    )
    event_row = m.PlanReassessment(
        clinic_id=clinic_id,
        plan_id=plan.id,
        from_version_number=current.number,
        to_version_number=new_ver.number,
        source_task_id=source_task.id,
        followup_task_id=followup.id,
        reason=data.reason,
        actor_demo=actor,
    )
    db.add(event_row)
    plan.current_version = new_ver.number
    audit(
        db,
        clinic_id,
        actor,
        "plan.reassessed_new_version",
        "treatment_plan",
        plan.id,
        {"from": current.number, "to": new_ver.number, "followup_task_id": followup.id},
    )
    outbox(
        db,
        clinic_id,
        "treatment.plan_reassessed",
        "treatment_plan",
        plan.id,
        {"version": new_ver.number},
    )
    db.commit()
    return {
        "reassessment_id": event_row.id,
        "plan_id": plan.id,
        "previous_version_number": current.number,
        "new_version_number": new_ver.number,
        "followup_task": {
            "id": followup.id,
            "title": followup.title,
            "phase": followup.phase,
            "owner_role": followup.owner_role,
            "status": followup.status,
            "reassessed_from_task_id": followup.reassessed_from_task_id,
        },
    }


def review_plan_demo(db: Session, clinic_id: str, plan_id: str, actor: str):
    plan, version = get_plan_version(db, clinic_id, plan_id)
    if version.status != "draft":
        raise HTTPException(409, "Already reviewed")
    tasks = db.scalars(select(m.PlanTask).where(m.PlanTask.plan_version_id == version.id)).all()
    if not tasks:
        raise HTTPException(422, "A plan must have tasks")
    version.status = "demo_reviewed"
    version.reviewer_demo = actor
    audit(
        db,
        clinic_id,
        actor,
        "plan.demo_reviewed_NOT_clinical_approval",
        "plan_version",
        version.id,
    )
    db.commit()
    return version


def _task_blocked_reasons(db: Session, task: m.PlanTask) -> list[str]:
    reasons: list[str] = []
    prereq_ids: set[str] = set()
    if task.depends_on_task_id:
        prereq_ids.add(task.depends_on_task_id)
    for edge in db.scalars(
        select(m.PlanTaskDependency).where(m.PlanTaskDependency.task_id == task.id)
    ).all():
        prereq_ids.add(edge.depends_on_task_id)

    for pid in prereq_ids:
        dep = db.get(m.PlanTask, pid)
        if dep is None or dep.status != "completed":
            reasons.append(f"prerequisite_incomplete:{pid}")

    lab_links = db.scalars(
        select(m.TreatmentCoordinationLink).where(
            m.TreatmentCoordinationLink.task_id == task.id,
            m.TreatmentCoordinationLink.target_type == "lab_case",
            m.TreatmentCoordinationLink.requires_verified_lab.is_(True),
        )
    ).all()
    for lnk in lab_links:
        lab = db.get(m.LabCase, lnk.target_id)
        if lab is None or lab.status != "verified":
            reasons.append("lab_not_verified")
    return reasons


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
    blockers = _task_blocked_reasons(db, task)
    if blockers:
        raise HTTPException(409, f"Task blocked: {', '.join(blockers)}")
    task.status = "completed"
    task.completed_at = m.utcnow()
    task.completion_evidence_note = f"Demo administrative completion by {actor}"
    audit(db, clinic_id, actor, "plan.task_demo_completed_NOT_procedure", "plan_task", task.id)
    db.commit()
    return task


def get_plan_timeline(db: Session, clinic_id: str, plan_id: str) -> dict:
    plan, version = get_plan_version(db, clinic_id, plan_id)
    tasks = db.scalars(select(m.PlanTask).where(m.PlanTask.plan_version_id == version.id)).all()
    now = m.utcnow()
    tasks_out = []
    for t in tasks:
        dep_ids = [
            e.depends_on_task_id
            for e in db.scalars(
                select(m.PlanTaskDependency).where(m.PlanTaskDependency.task_id == t.id)
            ).all()
        ]
        if t.depends_on_task_id and t.depends_on_task_id not in dep_ids:
            dep_ids.insert(0, t.depends_on_task_id)
        links = db.scalars(
            select(m.TreatmentCoordinationLink).where(m.TreatmentCoordinationLink.task_id == t.id)
        ).all()
        blockers = [] if t.status == "completed" else _task_blocked_reasons(db, t)
        overdue = bool(t.due_at and t.status != "completed" and t.due_at < now)
        tasks_out.append(
            {
                "id": t.id,
                "title": t.title,
                "phase": t.phase,
                "owner_role": t.owner_role,
                "status": t.status,
                "due_at": t.due_at.isoformat() + "Z" if t.due_at else None,
                "is_overdue": overdue,
                "depends_on_task_ids": dep_ids,
                "reassessed_from_task_id": t.reassessed_from_task_id,
                "blocked_reasons": blockers,
                "links": [
                    {
                        "target_type": lnk.target_type,
                        "target_id": lnk.target_id,
                        "requires_verified_lab": lnk.requires_verified_lab,
                    }
                    for lnk in links
                ],
                "completed_at": t.completed_at.isoformat() + "Z" if t.completed_at else None,
                "completion_evidence_note": t.completion_evidence_note,
            }
        )

    charges_sum = db.scalar(
        select(func.coalesce(func.sum(m.Charge.amount_vnd), 0)).where(
            m.Charge.clinic_id == clinic_id, m.Charge.patient_id == plan.patient_id
        )
    )
    payments_sum = db.scalar(
        select(func.coalesce(func.sum(m.Payment.amount_vnd), 0)).where(
            m.Payment.clinic_id == clinic_id, m.Payment.patient_id == plan.patient_id
        )
    )
    refunds_sum = db.scalar(
        select(func.coalesce(func.sum(m.PaymentRefund.amount_vnd), 0)).where(
            m.PaymentRefund.clinic_id == clinic_id, m.PaymentRefund.patient_id == plan.patient_id
        )
    )
    reassessments = db.scalars(
        select(m.PlanReassessment)
        .where(m.PlanReassessment.plan_id == plan.id)
        .order_by(m.PlanReassessment.created_at)
    ).all()
    return {
        "plan": {
            "id": plan.id,
            "patient_id": plan.patient_id,
            "title": plan.title,
            "current_version": plan.current_version,
        },
        "version": {
            "id": version.id,
            "number": version.number,
            "status": version.status,
            "reviewer_demo": version.reviewer_demo,
        },
        "tasks": tasks_out,
        "reassessments": [
            {
                "id": r.id,
                "from_version_number": r.from_version_number,
                "to_version_number": r.to_version_number,
                "source_task_id": r.source_task_id,
                "followup_task_id": r.followup_task_id,
                "reason": r.reason,
            }
            for r in reassessments
        ],
        "financial_summary": {
            "charged_vnd": int(charges_sum or 0),
            "paid_gross_vnd": int(payments_sum or 0),
            "refunded_vnd": int(refunds_sum or 0),
            "net_collected_vnd": int((payments_sum or 0) - (refunds_sum or 0)),
            "implies_clinical_completion": False,
        },
        "synthetic_only": True,
    }


def create_consent(db: Session, clinic_id: str, data: ConsentCreate, actor: str) -> m.ConsentRecord:
    ensure(db, m.Patient, data.patient_id, clinic_id)
    rec = m.ConsentRecord(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        purpose=data.purpose,
        template_version=data.template_version.strip(),
        disclosure_summary=data.disclosure_summary.strip(),
        signer_name=data.signer_name.strip(),
        signer_relationship=data.signer_relationship,
        guardian_authority_verified=data.guardian_authority_verified,
        status="granted",
        actor_demo=actor,
    )
    db.add(rec)
    db.flush()
    audit(
        db,
        clinic_id,
        actor,
        f"consent.granted.{data.purpose}",
        "consent_record",
        rec.id,
        {"purpose": data.purpose, "signer_relationship": data.signer_relationship},
    )
    db.commit()
    return rec


def withdraw_consent(
    db: Session,
    clinic_id: str,
    consent_id: str,
    data: ConsentWithdrawRequest,
    actor: str,
) -> m.ConsentRecord:
    rec = ensure(db, m.ConsentRecord, consent_id, clinic_id)
    if rec.status == "withdrawn":
        raise HTTPException(409, "Consent record is already withdrawn")
    rec.status = "withdrawn"
    rec.withdrawn_reason = data.reason.strip()
    rec.withdrawn_at = m.utcnow()
    audit(
        db,
        clinic_id,
        actor,
        f"consent.withdrawn.{rec.purpose}",
        "consent_record",
        rec.id,
        {"purpose": rec.purpose, "reason": rec.withdrawn_reason},
    )
    db.commit()
    return rec


def create_lab_case(db: Session, clinic_id: str, data: LabCaseCreate, actor: str) -> m.LabCase:
    ensure(db, m.Patient, data.patient_id, clinic_id)
    due_naive = dt_utc_naive(data.due_on) if data.due_on else None
    item = m.LabCase(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        title=data.title.strip(),
        specification_demo=data.specification_demo.strip(),
        file_manifest_json=json.dumps(data.file_references, ensure_ascii=False),
        due_on=due_naive,
    )
    db.add(item)
    db.flush()
    audit(db, clinic_id, actor, "lab.case_demo_created", "lab_case", item.id)
    db.commit()
    return item


def get_lab_alerts(db: Session, clinic_id: str, lab_id: str) -> dict:
    lab = ensure(db, m.LabCase, lab_id, clinic_id)
    alerts = []
    if lab.due_on and lab.status != "verified":
        lab_links = db.scalars(
            select(m.TreatmentCoordinationLink).where(
                m.TreatmentCoordinationLink.clinic_id == clinic_id,
                m.TreatmentCoordinationLink.target_type == "lab_case",
                m.TreatmentCoordinationLink.target_id == lab.id,
            )
        ).all()
        for l_link in lab_links:
            appt_links = db.scalars(
                select(m.TreatmentCoordinationLink).where(
                    m.TreatmentCoordinationLink.clinic_id == clinic_id,
                    m.TreatmentCoordinationLink.task_id == l_link.task_id,
                    m.TreatmentCoordinationLink.target_type == "appointment",
                )
            ).all()
            for a_link in appt_links:
                appt = db.get(m.Appointment, a_link.target_id)
                if appt and appt.status == "confirmed" and lab.due_on > appt.start_at:
                    alerts.append(
                        {
                            "alert_code": "lab_due_after_appointment",
                            "lab_case_id": lab.id,
                            "appointment_id": appt.id,
                            "task_id": l_link.task_id,
                            "lab_due_on": lab.due_on.isoformat() + "Z",
                            "appointment_start_at": appt.start_at.isoformat() + "Z",
                            "owner_role": "treatment_coordinator",
                            "auto_rescheduled": False,
                        }
                    )
    return {"lab_case_id": lab.id, "status": lab.status, "alerts": alerts}


def create_lab_partner_grant(
    db: Session,
    clinic_id: str,
    lab_id: str,
    staff_id: str,
    actor: str,
    secret: str,
    data: LabPartnerGrantCreate,
) -> dict:
    lab = ensure(db, m.LabCase, lab_id, clinic_id)
    expires_at = m.utcnow() + timedelta(seconds=data.ttl_seconds)
    grant = m.LabPartnerGrant(
        clinic_id=clinic_id,
        lab_case_id=lab.id,
        partner_name=data.partner_name.strip(),
        expires_at=expires_at,
        created_by_staff_id=staff_id,
    )
    db.add(grant)
    db.flush()
    exp_ts = int(expires_at.replace(tzinfo=timezone.utc).timestamp())
    msg = f"labgrant:{grant.id}:{clinic_id}:{lab.id}:{exp_ts}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    token = f"{grant.id}.{sig}"
    audit(
        db,
        clinic_id,
        actor,
        "lab.partner_grant_created",
        "lab_case",
        lab.id,
        {"grant_id": grant.id, "partner_name": grant.partner_name},
    )
    db.commit()
    return {
        "grant_id": grant.id,
        "grant_token": token,
        "lab_case_id": lab.id,
        "partner_name": grant.partner_name,
        "expires_at": expires_at.isoformat() + "Z",
    }


def _resolve_lab_partner_grant(
    db: Session,
    grant_token: str,
    secret: str,
    header_clinic_id: str | None = None,
) -> tuple[m.LabPartnerGrant, m.LabCase]:
    if "." not in grant_token:
        raise HTTPException(403, "Invalid lab partner grant token")
    grant_id, provided_sig = grant_token.split(".", 1)
    grant = db.get(m.LabPartnerGrant, grant_id)
    if grant is None or grant.revoked:
        raise HTTPException(403, "Lab partner grant not found or revoked")
    if header_clinic_id and header_clinic_id != grant.clinic_id:
        raise HTTPException(403, "Cross-clinic lab partner token access denied")
    exp_ts = int(grant.expires_at.replace(tzinfo=timezone.utc).timestamp())
    msg = f"labgrant:{grant.id}:{grant.clinic_id}:{grant.lab_case_id}:{exp_ts}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(403, "Lab partner grant signature mismatch")
    if m.utcnow() >= grant.expires_at:
        raise HTTPException(403, "Lab partner grant token expired")
    lab = ensure(db, m.LabCase, grant.lab_case_id, grant.clinic_id)
    return grant, lab


def get_lab_portal_case(
    db: Session,
    grant_token: str,
    secret: str,
    header_clinic_id: str | None = None,
) -> dict:
    grant, lab = _resolve_lab_partner_grant(db, grant_token, secret, header_clinic_id)
    audit(
        db,
        grant.clinic_id,
        f"lab_partner:{grant.partner_name}",
        "lab.partner_portal_viewed",
        "lab_case",
        lab.id,
    )
    db.commit()
    return {
        "lab_case_id": lab.id,
        "title": lab.title,
        "specification_demo": lab.specification_demo,
        "status": lab.status,
        "revision_number": lab.revision_number,
        "due_on": lab.due_on.isoformat() + "Z" if lab.due_on else None,
        "files": json.loads(lab.file_manifest_json or "[]"),
        "partner_name": grant.partner_name,
        "synthetic_only": True,
    }


def update_lab_portal_milestone(
    db: Session,
    grant_token: str,
    secret: str,
    data: LabPartnerMilestoneUpdate,
    header_clinic_id: str | None = None,
) -> dict:
    grant, lab = _resolve_lab_partner_grant(db, grant_token, secret, header_clinic_id)
    if data.next_status not in {"accepted", "in_progress", "ready"}:
        raise HTTPException(
            403, "Lab partner may only update manufacturing milestones (accepted/in_progress/ready)"
        )
    updated = set_lab_status(
        db,
        grant.clinic_id,
        lab.id,
        data.next_status,
        actor=f"lab_partner:{grant.partner_name}",
    )
    return {
        "lab_case_id": updated.id,
        "status": updated.status,
        "partner_name": grant.partner_name,
    }


def receive_lab_case(
    db: Session,
    clinic_id: str,
    lab_id: str,
    data: LabReceiveRequest,
    actor: str,
) -> m.LabCase:
    lab = ensure(db, m.LabCase, lab_id, clinic_id)
    if lab.status != "ready":
        raise HTTPException(409, f"Cannot record receipt from state '{lab.status}'")
    lab.status = "received"
    lab.delivery_condition = data.condition.strip()
    lab.delivered_at = m.utcnow()
    audit(
        db,
        clinic_id,
        actor,
        "lab.received_not_verified",
        "lab_case",
        lab.id,
        {"condition": lab.delivery_condition},
    )
    outbox(db, clinic_id, "lab.received", "lab_case", lab.id)
    db.commit()
    return lab


def remake_lab_case(
    db: Session,
    clinic_id: str,
    lab_id: str,
    data: LabRemakeCreate,
    actor: str,
) -> m.LabCase:
    parent = ensure(db, m.LabCase, lab_id, clinic_id)
    if parent.status in {"in_progress", "ready", "received"}:
        parent.status = "revision_requested"
    due_naive = dt_utc_naive(data.due_on) if data.due_on else parent.due_on
    child = m.LabCase(
        clinic_id=clinic_id,
        patient_id=parent.patient_id,
        title=f"{parent.title} (Remake v{parent.revision_number + 1})",
        specification_demo=data.specification_demo.strip(),
        file_manifest_json=parent.file_manifest_json,
        parent_lab_case_id=parent.id,
        revision_number=parent.revision_number + 1,
        status="requested",
        due_on=due_naive,
    )
    db.add(child)
    db.flush()
    audit(
        db,
        clinic_id,
        actor,
        "lab.remake_created",
        "lab_case",
        child.id,
        {"parent_lab_case_id": parent.id, "reason": data.reason.strip()},
    )
    outbox(db, clinic_id, "lab.remake_requested", "lab_case", child.id)
    db.commit()
    return child


LAB_TRANSITIONS = {
    "requested": {"accepted", "cancelled"},
    "accepted": {"in_progress", "cancelled"},
    "in_progress": {"ready", "revision_requested"},
    "ready": {"received", "revision_requested"},
    "received": {"verified", "revision_requested"},
    "revision_requested": {"in_progress", "cancelled"},
    "verified": set(),
    "cancelled": set(),
}


def set_lab_status(db: Session, clinic_id: str, lab_id: str, next_status: str, actor: str):
    item = ensure(db, m.LabCase, lab_id, clinic_id)
    if next_status not in LAB_TRANSITIONS.get(item.status, set()):
        raise HTTPException(409, f"Invalid lab state transition: {item.status} -> {next_status}")
    before = item.status
    item.status = next_status
    if next_status == "verified":
        item.verified_at = m.utcnow()
        item.verified_by_staff_id = actor[:36]
    audit(
        db,
        clinic_id,
        actor,
        "lab.status_changed",
        "lab_case",
        item.id,
        {"from": before, "to": next_status},
    )
    outbox(db, clinic_id, f"lab.{next_status}", "lab_case", item.id)
    db.commit()
    return item


def create_estimate(
    db: Session, clinic_id: str, data: EstimateCreate, actor: str
) -> m.EstimateVersion:
    ensure(db, m.Patient, data.patient_id, clinic_id)
    plan = ensure(db, m.TreatmentPlan, data.plan_id, clinic_id)
    if plan.patient_id != data.patient_id:
        raise HTTPException(422, "Treatment plan does not belong to patient")
    existing = db.scalar(
        select(m.EstimateVersion).where(
            m.EstimateVersion.plan_id == plan.id,
            m.EstimateVersion.version_number == data.version_number,
        )
    )
    if existing is not None:
        raise HTTPException(409, "Estimate version already exists and is immutable")
    est = m.EstimateVersion(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        plan_id=plan.id,
        version_number=data.version_number,
        amount_vnd=data.amount_vnd,
        items_summary=data.items_summary.strip(),
        status="draft",
    )
    db.add(est)
    db.flush()
    audit(
        db,
        clinic_id,
        actor,
        "finance.estimate_version_created",
        "estimate_version",
        est.id,
        {"version_number": est.version_number, "amount_vnd": est.amount_vnd},
    )
    db.commit()
    return est


def accept_estimate(
    db: Session,
    clinic_id: str,
    estimate_id: str,
    data: EstimateAcceptRequest,
    actor: str,
) -> m.EstimateVersion:
    est = ensure(db, m.EstimateVersion, estimate_id, clinic_id)
    if est.status != "draft":
        raise HTTPException(409, f"Estimate in status '{est.status}' cannot be accepted")
    prior_accepted = db.scalars(
        select(m.EstimateVersion).where(
            m.EstimateVersion.plan_id == est.plan_id,
            m.EstimateVersion.status == "accepted",
        )
    ).all()
    for old in prior_accepted:
        old.status = "superseded"
    est.status = "accepted"
    est.accepted_by = data.accepted_by.strip()
    est.accepted_at = m.utcnow()
    audit(
        db,
        clinic_id,
        actor,
        "finance.estimate_version_accepted",
        "estimate_version",
        est.id,
        {"accepted_by": est.accepted_by, "amount_vnd": est.amount_vnd},
    )
    db.commit()
    return est


def create_charge(db: Session, clinic_id: str, data: ChargeCreate, actor: str) -> m.Charge:
    if data.idempotency_key:
        existing = db.scalar(
            select(m.Charge).where(
                m.Charge.clinic_id == clinic_id,
                m.Charge.idempotency_key == data.idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.patient_id == data.patient_id
                and existing.label == data.label
                and existing.amount_vnd == data.amount_vnd
            ):
                return existing
            raise HTTPException(409, "Charge idempotency_key reused with different parameters")
    ensure(db, m.Patient, data.patient_id, clinic_id)
    item = m.Charge(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        label=data.label,
        amount_vnd=data.amount_vnd,
        idempotency_key=data.idempotency_key,
    )
    db.add(item)
    db.flush()
    ledger(
        db,
        clinic_id,
        data.patient_id,
        "charge_posted",
        "debit",
        item.amount_vnd,
        "charge",
        item.id,
        actor,
    )
    audit(db, clinic_id, actor, "finance.charge_demo_created", "charge", item.id)
    db.commit()
    return item


def create_payment(db: Session, clinic_id: str, data: PaymentCreate, actor: str) -> m.Payment:
    if data.idempotency_key:
        existing = db.scalar(
            select(m.Payment).where(
                m.Payment.clinic_id == clinic_id,
                m.Payment.idempotency_key == data.idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.patient_id == data.patient_id
                and existing.amount_vnd == data.amount_vnd
                and existing.payment_method == data.payment_method
            ):
                return existing
            raise HTTPException(409, "Payment idempotency_key reused with different parameters")
    ensure(db, m.Patient, data.patient_id, clinic_id)
    item = m.Payment(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        amount_vnd=data.amount_vnd,
        payment_method=data.payment_method,
        external_reference=data.external_reference,
        idempotency_key=data.idempotency_key,
    )
    db.add(item)
    db.flush()
    ledger(
        db,
        clinic_id,
        data.patient_id,
        "payment_received",
        "credit",
        item.amount_vnd,
        "payment",
        item.id,
        actor,
        payment_method=item.payment_method,
    )
    audit(db, clinic_id, actor, "finance.payment_demo_recorded", "payment", item.id)
    db.commit()
    return item


def allocate(
    db: Session,
    clinic_id: str,
    charge_id: str,
    payment_id: str,
    amount_vnd: int,
    actor: str,
    idempotency_key: str | None = None,
):
    if idempotency_key:
        existing = db.scalar(
            select(m.PaymentAllocation).where(
                m.PaymentAllocation.clinic_id == clinic_id,
                m.PaymentAllocation.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.charge_id == charge_id
                and existing.payment_id == payment_id
                and existing.amount_vnd == amount_vnd
            ):
                return existing
            raise HTTPException(409, "Allocation idempotency_key reused with different parameters")

    charge = db.scalar(
        select(m.Charge)
        .where(m.Charge.id == charge_id, m.Charge.clinic_id == clinic_id)
        .with_for_update()
    )
    payment = db.scalar(
        select(m.Payment)
        .where(m.Payment.id == payment_id, m.Payment.clinic_id == clinic_id)
        .with_for_update()
    )
    if not charge or not payment or charge.patient_id != payment.patient_id:
        raise HTTPException(422, "Charge and payment must belong to same demo patient and clinic")
    a = db.scalar(
        select(func.coalesce(func.sum(m.PaymentAllocation.amount_vnd), 0)).where(
            m.PaymentAllocation.charge_id == charge.id
        )
    )
    b = db.scalar(
        select(func.coalesce(func.sum(m.PaymentAllocation.amount_vnd), 0)).where(
            m.PaymentAllocation.payment_id == payment.id
        )
    )
    r = db.scalar(
        select(func.coalesce(func.sum(m.PaymentRefund.amount_vnd), 0)).where(
            m.PaymentRefund.payment_id == payment.id
        )
    )
    if a + amount_vnd > charge.amount_vnd or b + r + amount_vnd > payment.amount_vnd:
        raise HTTPException(409, "Allocation exceeds charge or available payment")
    try:
        item = m.PaymentAllocation(
            clinic_id=clinic_id,
            charge_id=charge.id,
            payment_id=payment.id,
            amount_vnd=amount_vnd,
            idempotency_key=idempotency_key,
        )
        db.add(item)
        db.flush()
        ledger(
            db,
            clinic_id,
            charge.patient_id,
            "payment_allocated",
            "credit",
            amount_vnd,
            "payment_allocation",
            item.id,
            actor,
            payment_method=payment.payment_method,
        )
        audit(db, clinic_id, actor, "payment.demo_allocated", "payment_allocation", item.id)
        db.commit()
        return item
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Allocation exceeds charge or available payment") from exc


def refund_payment(
    db: Session,
    clinic_id: str,
    payment_id: str,
    data: RefundCreate,
    actor: str,
) -> m.PaymentRefund:
    if data.idempotency_key:
        existing = db.scalar(
            select(m.PaymentRefund).where(
                m.PaymentRefund.clinic_id == clinic_id,
                m.PaymentRefund.idempotency_key == data.idempotency_key,
            )
        )
        if existing is not None:
            if existing.payment_id == payment_id and existing.amount_vnd == data.amount_vnd:
                return existing
            raise HTTPException(409, "Refund idempotency_key reused with different parameters")

    payment = db.scalar(
        select(m.Payment)
        .where(m.Payment.id == payment_id, m.Payment.clinic_id == clinic_id)
        .with_for_update()
    )
    if payment is None:
        raise HTTPException(404, "Payment not found in this clinic")
    allocated = db.scalar(
        select(func.coalesce(func.sum(m.PaymentAllocation.amount_vnd), 0)).where(
            m.PaymentAllocation.payment_id == payment.id
        )
    )
    refunded = db.scalar(
        select(func.coalesce(func.sum(m.PaymentRefund.amount_vnd), 0)).where(
            m.PaymentRefund.payment_id == payment.id
        )
    )
    if allocated + refunded + data.amount_vnd > payment.amount_vnd:
        raise HTTPException(409, "Refund exceeds unallocated available payment balance")
    item = m.PaymentRefund(
        clinic_id=clinic_id,
        payment_id=payment.id,
        patient_id=payment.patient_id,
        amount_vnd=data.amount_vnd,
        reason=data.reason.strip(),
        actor_demo=actor,
        idempotency_key=data.idempotency_key,
    )
    db.add(item)
    db.flush()
    ledger(
        db,
        clinic_id,
        payment.patient_id,
        "payment_refunded",
        "debit",
        item.amount_vnd,
        "payment_refund",
        item.id,
        actor,
        payment_method=payment.payment_method,
    )
    audit(
        db,
        clinic_id,
        actor,
        "finance.payment_refunded_demo",
        "payment_refund",
        item.id,
        {"payment_id": payment.id, "amount_vnd": data.amount_vnd},
    )
    outbox(
        db,
        clinic_id,
        "finance.payment_refunded",
        "payment_refund",
        item.id,
        {"payment_id": payment.id, "amount_vnd": data.amount_vnd},
    )
    db.commit()
    return item


def get_patient_revenue_account(db: Session, clinic_id: str, patient_id: str) -> dict:
    ensure(db, m.Patient, patient_id, clinic_id)
    estimates = db.scalars(
        select(m.EstimateVersion)
        .where(
            m.EstimateVersion.clinic_id == clinic_id,
            m.EstimateVersion.patient_id == patient_id,
        )
        .order_by(m.EstimateVersion.version_number.desc())
    ).all()
    latest_by_plan: dict[str, int] = {}
    for est in estimates:
        if est.plan_id not in latest_by_plan:
            latest_by_plan[est.plan_id] = est.amount_vnd
    proposed_vnd = sum(latest_by_plan.values())

    charged_vnd = int(
        db.scalar(
            select(func.coalesce(func.sum(m.Charge.amount_vnd), 0)).where(
                m.Charge.clinic_id == clinic_id, m.Charge.patient_id == patient_id
            )
        )
        or 0
    )
    collected_gross_vnd = int(
        db.scalar(
            select(func.coalesce(func.sum(m.Payment.amount_vnd), 0)).where(
                m.Payment.clinic_id == clinic_id, m.Payment.patient_id == patient_id
            )
        )
        or 0
    )
    refunded_vnd = int(
        db.scalar(
            select(func.coalesce(func.sum(m.PaymentRefund.amount_vnd), 0)).where(
                m.PaymentRefund.clinic_id == clinic_id,
                m.PaymentRefund.patient_id == patient_id,
            )
        )
        or 0
    )
    allocated_vnd = int(
        db.scalar(
            select(func.coalesce(func.sum(m.PaymentAllocation.amount_vnd), 0))
            .join(m.Charge, m.PaymentAllocation.charge_id == m.Charge.id)
            .where(m.Charge.clinic_id == clinic_id, m.Charge.patient_id == patient_id)
        )
        or 0
    )
    net_collected_vnd = collected_gross_vnd - refunded_vnd
    entries = db.scalars(
        select(m.LedgerEntry)
        .where(
            m.LedgerEntry.clinic_id == clinic_id,
            m.LedgerEntry.patient_id == patient_id,
        )
        .order_by(m.LedgerEntry.created_at)
    ).all()
    return {
        "patient_id": patient_id,
        "proposed_estimate_vnd": proposed_vnd,
        "charged_vnd": charged_vnd,
        "collected_gross_vnd": collected_gross_vnd,
        "refunded_vnd": refunded_vnd,
        "net_collected_vnd": net_collected_vnd,
        "allocated_vnd": allocated_vnd,
        "unallocated_credit_vnd": net_collected_vnd - allocated_vnd,
        "outstanding_balance_vnd": charged_vnd - allocated_vnd,
        "implies_clinical_completion": False,
        "ledger_entries": [
            {
                "id": e.id,
                "entry_type": e.entry_type,
                "direction": e.direction,
                "amount_vnd": e.amount_vnd,
                "payment_method": e.payment_method,
                "reference_type": e.reference_type,
                "reference_id": e.reference_id,
                "created_at": e.created_at.isoformat() + "Z",
            }
            for e in entries
        ],
    }


def reconcile_cashier_daily(
    db: Session,
    clinic_id: str,
    data: CashierReconciliationCreate,
    actor: str,
) -> m.CashierReconciliation:
    def net_by_method(method: str) -> int:
        gross = int(
            db.scalar(
                select(func.coalesce(func.sum(m.Payment.amount_vnd), 0)).where(
                    m.Payment.clinic_id == clinic_id,
                    m.Payment.payment_method == method,
                )
            )
            or 0
        )
        ref = int(
            db.scalar(
                select(func.coalesce(func.sum(m.PaymentRefund.amount_vnd), 0))
                .join(m.Payment, m.PaymentRefund.payment_id == m.Payment.id)
                .where(
                    m.Payment.clinic_id == clinic_id,
                    m.Payment.payment_method == method,
                )
            )
            or 0
        )
        return gross - ref

    exp_cash = net_by_method("cash")
    exp_transfer = net_by_method("bank_transfer")
    exp_card = net_by_method("card")
    diff_cash = data.counted_cash_vnd - exp_cash
    diff_transfer = data.counted_transfer_vnd - exp_transfer
    diff_card = data.counted_card_vnd - exp_card
    status = (
        "balanced"
        if diff_cash == 0 and diff_transfer == 0 and diff_card == 0
        else "discrepancy_flagged"
    )
    rec = m.CashierReconciliation(
        clinic_id=clinic_id,
        expected_cash_vnd=exp_cash,
        counted_cash_vnd=data.counted_cash_vnd,
        discrepancy_cash_vnd=diff_cash,
        expected_transfer_vnd=exp_transfer,
        counted_transfer_vnd=data.counted_transfer_vnd,
        discrepancy_transfer_vnd=diff_transfer,
        expected_card_vnd=exp_card,
        counted_card_vnd=data.counted_card_vnd,
        discrepancy_card_vnd=diff_card,
        status=status,
        notes=data.notes.strip(),
        actor_demo=actor,
    )
    db.add(rec)
    db.flush()
    audit(
        db,
        clinic_id,
        actor,
        "finance.cashier_reconciled",
        "cashier_reconciliation",
        rec.id,
        {"status": status},
    )
    db.commit()
    return rec


def create_paper_batch(
    db: Session, clinic_id: str, data: PaperBatchCreate, actor: str
) -> m.MigrationBatch:
    batch = m.MigrationBatch(
        clinic_id=clinic_id,
        source_cabinet=data.source_cabinet.strip(),
        expected_item_count=data.expected_item_count,
        status="quarantined_open",
        operator_actor=actor,
    )
    db.add(batch)
    db.flush()
    audit(
        db,
        clinic_id,
        actor,
        "migration.paper_batch_created",
        "migration_batch",
        batch.id,
    )
    db.commit()
    return batch


def ingest_paper_item(
    db: Session,
    clinic_id: str,
    batch_id: str,
    data: PaperItemCreate,
    actor: str,
) -> dict:
    batch = ensure(db, m.MigrationBatch, batch_id, clinic_id)
    if batch.status != "quarantined_open":
        raise HTTPException(409, f"Cannot ingest into batch in status '{batch.status}'")

    present_nums = {p.page_number for p in data.pages}
    expected_nums = set(range(1, data.expected_page_count + 1))
    missing = sorted(expected_nums - present_nums)
    any_illegible = any(not p.legible for p in data.pages)
    if missing:
        comp_status = "incomplete_missing_pages"
    elif any_illegible:
        comp_status = "illegible_quarantined"
    else:
        comp_status = "complete"

    name_clean = data.patient_display_name.strip()
    conds = [m.Patient.display_name == name_clean]
    if data.phone_demo:
        conds.append(m.Patient.phone_demo == data.phone_demo)
    candidates = db.scalars(
        select(m.Patient).where(m.Patient.clinic_id == clinic_id, or_(*conds))
    ).all()
    cand_ids = [c.id for c in candidates]
    match_status = "needs_human_identity_review" if cand_ids else "no_collision"

    pages_serialized = [p.model_dump() for p in data.pages]
    item = m.MigrationItem(
        clinic_id=clinic_id,
        batch_id=batch.id,
        legacy_folder_id=data.legacy_folder_id.strip(),
        patient_display_name=name_clean,
        birth_year=data.birth_year,
        phone_demo=data.phone_demo,
        expected_page_count=data.expected_page_count,
        pages_json=json.dumps(pages_serialized, ensure_ascii=False),
        missing_pages_json=json.dumps(missing),
        completeness_status=comp_status,
        match_status=match_status,
        candidate_patient_ids_json=json.dumps(cand_ids),
        status="quarantined",
        provenance_source="legacy_scan",
        digital_signature_status="not_digitally_signed_legacy_paper",
    )
    db.add(item)
    db.flush()
    audit(
        db,
        clinic_id,
        actor,
        "migration.paper_item_quarantined",
        "migration_item",
        item.id,
        {"completeness_status": comp_status, "match_status": match_status},
    )
    db.commit()
    return _serialize_migration_item(item)


def verify_and_link_paper_item(
    db: Session,
    clinic_id: str,
    item_id: str,
    data: PaperItemVerifyLinkRequest,
    actor: str,
) -> dict:
    item = ensure(db, m.MigrationItem, item_id, clinic_id)
    if data.claim_digitally_signed:
        audit(
            db,
            clinic_id,
            actor,
            "migration.digital_signature_forgery_blocked",
            "migration_item",
            item.id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Historical paper scan cannot be marked digitally signed (DR-03 / MIG-007)",
        )
    if item.completeness_status != "complete":
        raise HTTPException(
            409,
            f"Paper item incomplete ({item.completeness_status}); cannot mark verified complete (NEG-10 / DR-01)",
        )
    if item.status != "quarantined":
        raise HTTPException(409, f"Paper item in status '{item.status}' cannot be verified")

    if data.resolution_mode == "link_existing_patient":
        if not data.target_patient_id:
            raise HTTPException(422, "target_patient_id required for link_existing_patient")
        pat = ensure(db, m.Patient, data.target_patient_id, clinic_id)
        item.linked_patient_id = pat.id
        item.created_new_patient = False
    else:
        new_pat = m.Patient(
            clinic_id=clinic_id,
            display_name=item.patient_display_name,
            birth_year=item.birth_year,
            phone_demo=item.phone_demo,
            source="legacy_scan",
        )
        db.add(new_pat)
        db.flush()
        item.linked_patient_id = new_pat.id
        item.created_new_patient = True

    item.match_status = "resolved"
    item.status = "verified_legacy_archive"
    item.reviewer_note = data.reviewer_note.strip()
    item.reviewed_by = actor
    audit(
        db,
        clinic_id,
        actor,
        "migration.paper_item_verified_legacy_archive",
        "migration_item",
        item.id,
        {"linked_patient_id": item.linked_patient_id, "resolution_mode": data.resolution_mode},
    )
    db.commit()
    return _serialize_migration_item(item)


def get_paper_batch_reconciliation(db: Session, clinic_id: str, batch_id: str) -> dict:
    batch = ensure(db, m.MigrationBatch, batch_id, clinic_id)
    items = db.scalars(
        select(m.MigrationItem).where(m.MigrationItem.batch_id == batch.id)
    ).all()
    return {
        "batch_id": batch.id,
        "source_cabinet": batch.source_cabinet,
        "status": batch.status,
        "expected_item_count": batch.expected_item_count,
        "submitted_count": len(items),
        "incomplete_quarantined_count": sum(1 for x in items if x.completeness_status != "complete"),
        "needs_identity_review_count": sum(
            1 for x in items if x.match_status == "needs_human_identity_review"
        ),
        "verified_legacy_archive_count": sum(
            1 for x in items if x.status == "verified_legacy_archive"
        ),
        "rolled_back_count": sum(1 for x in items if x.status == "rolled_back"),
    }


def rollback_paper_batch(
    db: Session,
    clinic_id: str,
    batch_id: str,
    data: PaperBatchRollbackRequest,
    actor: str,
) -> dict:
    batch = ensure(db, m.MigrationBatch, batch_id, clinic_id)
    if batch.status == "rolled_back":
        raise HTTPException(409, "Migration batch already rolled back")
    items = db.scalars(
        select(m.MigrationItem).where(m.MigrationItem.batch_id == batch.id)
    ).all()
    for item in items:
        item.status = "rolled_back"
        item.linked_patient_id = None
    batch.status = "rolled_back"
    batch.rollback_reason = data.reason.strip()
    audit(
        db,
        clinic_id,
        actor,
        "migration.paper_batch_rolled_back",
        "migration_batch",
        batch.id,
        {"reason": batch.rollback_reason, "item_count": len(items)},
    )
    db.commit()
    return get_paper_batch_reconciliation(db, clinic_id, batch.id)


def _serialize_migration_item(item: m.MigrationItem) -> dict:
    return {
        "id": item.id,
        "clinic_id": item.clinic_id,
        "batch_id": item.batch_id,
        "legacy_folder_id": item.legacy_folder_id,
        "patient_display_name": item.patient_display_name,
        "birth_year": item.birth_year,
        "phone_demo": item.phone_demo,
        "expected_page_count": item.expected_page_count,
        "missing_pages": json.loads(item.missing_pages_json or "[]"),
        "completeness_status": item.completeness_status,
        "match_status": item.match_status,
        "candidate_patient_ids": json.loads(item.candidate_patient_ids_json or "[]"),
        "linked_patient_id": item.linked_patient_id,
        "created_new_patient": item.created_new_patient,
        "status": item.status,
        "provenance_source": item.provenance_source,
        "digital_signature_status": item.digital_signature_status,
        "reviewer_note": item.reviewer_note,
        "reviewed_by": item.reviewed_by,
        "created_at": item.created_at.isoformat() + "Z",
    }


def create_document_snapshot(
    db: Session,
    clinic_id: str,
    data: DocumentSnapshotCreate,
    actor: str,
    parent_snapshot_id: str | None = None,
    amendment_reason: str | None = None,
) -> m.ClinicalDocumentSnapshot:
    note = ensure(db, m.ClinicalNote, data.note_id, clinic_id)
    if note.latest_revision != data.expected_revision:
        raise HTTPException(409, "Stale note revision: cannot create document snapshot")
    rev = db.scalar(
        select(m.NoteRevision).where(
            m.NoteRevision.note_id == note.id,
            m.NoteRevision.revision_no == data.expected_revision,
        )
    )
    if rev is None:
        raise HTTPException(404, "Note revision not found")
    if data.template_id:
        ensure(db, m.FormTemplateVersion, data.template_id, clinic_id)

    payload = {
        "clinic_id": clinic_id,
        "encounter_id": note.encounter_id,
        "note_id": note.id,
        "note_revision_no": rev.revision_no,
        "content": rev.content,
        "template_id": data.template_id,
        "parent_snapshot_id": parent_snapshot_id,
        "amendment_reason": amendment_reason,
    }
    canonical_json, _, canonical_sha256 = signing.canonicalize_document_payload(payload)
    manifest_input = json.dumps(
        {
            "canonical_sha256": canonical_sha256,
            "encounter_id": note.encounter_id,
            "note_id": note.id,
            "revision": rev.revision_no,
            "attachments": [],
        },
        sort_keys=True,
    ).encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_input).hexdigest()

    snap = m.ClinicalDocumentSnapshot(
        clinic_id=clinic_id,
        encounter_id=note.encounter_id,
        note_id=note.id,
        note_revision_no=rev.revision_no,
        parent_snapshot_id=parent_snapshot_id,
        amendment_reason=amendment_reason,
        status="ready_for_signature",
        canonical_json=canonical_json,
        canonical_sha256=canonical_sha256,
        manifest_sha256=manifest_sha256,
    )
    db.add(snap)
    db.flush()
    audit(
        db,
        clinic_id,
        actor,
        "clinical_doc.snapshot_prepared",
        "clinical_document_snapshot",
        snap.id,
        {"canonical_sha256": canonical_sha256},
    )
    db.commit()
    return snap


def sign_document_snapshot_synthetic(
    db: Session,
    clinic_id: str,
    snapshot_id: str,
    signer_staff_id: str,
    actor: str,
    secret: str,
    data: DocumentSyntheticSignRequest,
) -> dict:
    snap = ensure(db, m.ClinicalDocumentSnapshot, snapshot_id, clinic_id)
    if data.mode == "legal_authenticated":
        audit(
            db,
            clinic_id,
            actor,
            "clinical_doc.legal_sign_blocked",
            "clinical_document_snapshot",
            snap.id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Real legal e-signature ('authenticated') is blocked until NEEDS_CLINICAL_REVIEW.md gates pass",
        )
    if snap.status != "ready_for_signature":
        raise HTTPException(409, f"Snapshot in status '{snap.status}' cannot be signed")

    note = ensure(db, m.ClinicalNote, snap.note_id, clinic_id)
    if note.latest_revision != snap.note_revision_no:
        raise HTTPException(
            409, "Underlying clinical note changed concurrently; prepare a fresh snapshot"
        )
    if not hmac.compare_digest(snap.canonical_sha256, data.expected_sha256):
        raise HTTPException(409, "Canonical content SHA256 mismatch (NEG-03)")

    provider = signing.FakeSyntheticSignatureProvider(secret)
    receipt = provider.sign_snapshot(
        canonical_bytes=snap.canonical_json.encode("utf-8"),
        signer_staff_id=signer_staff_id,
        clinic_id=clinic_id,
        simulate_failure=data.simulate_failure,
    )
    snap.signer_staff_id = signer_staff_id
    snap.provider_receipt_json = json.dumps(receipt.__dict__, ensure_ascii=False, sort_keys=True)
    snap.status = "synthetic_signed_NOT_legal"
    if note.status == "draft":
        note.status = "demo_locked"
        note.locked_digest = snap.canonical_sha256
    audit(
        db,
        clinic_id,
        actor,
        "clinical_doc.synthetic_sealed_NOT_legal",
        "clinical_document_snapshot",
        snap.id,
        {"canonical_sha256": snap.canonical_sha256, "provider": receipt.provider_id},
    )
    db.commit()
    return _serialize_snapshot(snap)


def verify_document_snapshot(
    db: Session, clinic_id: str, snapshot_id: str, secret: str
) -> dict:
    snap = ensure(db, m.ClinicalDocumentSnapshot, snapshot_id, clinic_id)
    if not snap.provider_receipt_json:
        return {
            "snapshot_id": snap.id,
            "status": snap.status,
            "integrity_verified": False,
            "legal_signature_valid": False,
        }
    receipt_dict = json.loads(snap.provider_receipt_json)
    receipt = signing.SignatureReceipt(**receipt_dict)
    provider = signing.FakeSyntheticSignatureProvider(secret)
    ok = provider.verify_receipt(snap.canonical_json.encode("utf-8"), receipt, clinic_id)
    return {
        "snapshot_id": snap.id,
        "status": snap.status,
        "canonical_sha256": snap.canonical_sha256,
        "manifest_sha256": snap.manifest_sha256,
        "integrity_verified": ok,
        "legal_signature_valid": False,
        "synthetic_only": True,
    }


def create_document_addendum(
    db: Session,
    clinic_id: str,
    parent_snapshot_id: str,
    data: DocumentAddendumCreate,
    actor: str,
) -> dict:
    parent = ensure(db, m.ClinicalDocumentSnapshot, parent_snapshot_id, clinic_id)
    if parent.status != "synthetic_signed_NOT_legal":
        raise HTTPException(409, "Addendum requires a sealed parent document snapshot")
    addendum_note = create_note(
        db=db,
        clinic_id=clinic_id,
        encounter_id=parent.encounter_id,
        content=data.content,
        actor=actor,
        parent_note_id=parent.note_id,
    )
    snap = create_document_snapshot(
        db=db,
        clinic_id=clinic_id,
        data=DocumentSnapshotCreate(note_id=addendum_note.id, expected_revision=1),
        actor=actor,
        parent_snapshot_id=parent.id,
        amendment_reason=data.amendment_reason.strip(),
    )
    return _serialize_snapshot(snap)


def enter_document_in_error(
    db: Session,
    clinic_id: str,
    snapshot_id: str,
    data: DocumentEnterInErrorRequest,
    actor: str,
) -> dict:
    snap = ensure(db, m.ClinicalDocumentSnapshot, snapshot_id, clinic_id)
    if snap.status == "entered_in_error":
        raise HTTPException(409, "Document snapshot already marked entered_in_error")
    snap.status = "entered_in_error"
    snap.entered_in_error_reason = data.reason.strip()
    snap.entered_in_error_by = actor
    audit(
        db,
        clinic_id,
        actor,
        "clinical_doc.entered_in_error",
        "clinical_document_snapshot",
        snap.id,
        {"reason": snap.entered_in_error_reason},
    )
    db.commit()
    return _serialize_snapshot(snap)


def _serialize_snapshot(snap: m.ClinicalDocumentSnapshot) -> dict:
    return {
        "id": snap.id,
        "clinic_id": snap.clinic_id,
        "encounter_id": snap.encounter_id,
        "note_id": snap.note_id,
        "note_revision_no": snap.note_revision_no,
        "parent_snapshot_id": snap.parent_snapshot_id,
        "amendment_reason": snap.amendment_reason,
        "status": snap.status,
        "canonical_json": snap.canonical_json,
        "canonical_sha256": snap.canonical_sha256,
        "manifest_sha256": snap.manifest_sha256,
        "signer_staff_id": snap.signer_staff_id,
        "entered_in_error_reason": snap.entered_in_error_reason,
        "entered_in_error_by": snap.entered_in_error_by,
        "legal_signature_valid": False,
        "synthetic_only": True,
        "created_at": snap.created_at.isoformat() + "Z",
    }


def register_form_template(
    db: Session, clinic_id: str, data: FormTemplateCreate, actor: str
) -> dict:
    existing = db.scalar(
        select(m.FormTemplateVersion).where(
            m.FormTemplateVersion.clinic_id == clinic_id,
            m.FormTemplateVersion.official_code == data.official_code,
            m.FormTemplateVersion.schema_version == data.schema_version,
        )
    )
    if existing is not None:
        raise HTTPException(
            409,
            "Form template version already exists and cannot be overwritten (NEG-16)",
        )
    seen_codes: set[str] = set()
    for field in data.fields:
        if field.field_code in seen_codes:
            raise HTTPException(422, f"Duplicate field_code in template: {field.field_code}")
        seen_codes.add(field.field_code)
    tpl = m.FormTemplateVersion(
        clinic_id=clinic_id,
        official_code=data.official_code,
        title=data.title,
        schema_version=data.schema_version,
        source_citation=data.source_citation,
        source_sha256=data.source_sha256,
        approval_status="quarantined_synthetic_draft",
    )
    db.add(tpl)
    db.flush()
    fields_out = []
    for field in data.fields:
        row = m.FormFieldMap(
            template_id=tpl.id,
            field_code=field.field_code,
            label_vi=field.label_vi,
            field_type=field.field_type,
            required_when=field.required_when,
            allow_unknown=field.allow_unknown,
        )
        db.add(row)
        db.flush()
        fields_out.append(
            {
                "id": row.id,
                "field_code": row.field_code,
                "label_vi": row.label_vi,
                "field_type": row.field_type,
                "required_when": row.required_when,
                "allow_unknown": row.allow_unknown,
            }
        )
    audit(
        db,
        clinic_id,
        actor,
        "clinical_form.template_registered_quarantined",
        "form_template_version",
        tpl.id,
        {"official_code": tpl.official_code, "schema_version": tpl.schema_version},
    )
    db.commit()
    return {
        "id": tpl.id,
        "clinic_id": tpl.clinic_id,
        "official_code": tpl.official_code,
        "title": tpl.title,
        "schema_version": tpl.schema_version,
        "source_citation": tpl.source_citation,
        "source_sha256": tpl.source_sha256,
        "approval_status": tpl.approval_status,
        "clinical_review_blocked": True,
        "fields": fields_out,
    }


def list_form_templates(db: Session, clinic_id: str) -> list[dict]:
    rows = db.scalars(
        select(m.FormTemplateVersion)
        .where(m.FormTemplateVersion.clinic_id == clinic_id)
        .order_by(m.FormTemplateVersion.official_code, m.FormTemplateVersion.schema_version)
    ).all()
    out = []
    for tpl in rows:
        fields = db.scalars(
            select(m.FormFieldMap).where(m.FormFieldMap.template_id == tpl.id)
        ).all()
        out.append(
            {
                "id": tpl.id,
                "clinic_id": tpl.clinic_id,
                "official_code": tpl.official_code,
                "title": tpl.title,
                "schema_version": tpl.schema_version,
                "approval_status": tpl.approval_status,
                "clinical_review_blocked": tpl.approval_status != "approved_for_clinical_use",
                "fields": [
                    {
                        "field_code": f.field_code,
                        "label_vi": f.label_vi,
                        "field_type": f.field_type,
                        "required_when": f.required_when,
                        "allow_unknown": f.allow_unknown,
                    }
                    for f in fields
                ],
            }
        )
    return out


def approve_form_template_blocked(
    db: Session, clinic_id: str, template_id: str, actor: str
) -> None:
    tpl = ensure(db, m.FormTemplateVersion, template_id, clinic_id)
    audit(
        db,
        clinic_id,
        actor,
        "clinical_form.self_approval_blocked",
        "form_template_version",
        tpl.id,
    )
    db.commit()
    raise HTTPException(
        409,
        "Clinical/legal approval cannot be self-asserted in synthetic mode; see docs/clinical/NEEDS_CLINICAL_REVIEW.md",
    )


def validate_form_preview(
    db: Session,
    clinic_id: str,
    data: FormValidatePreviewRequest,
    actor: str,
) -> dict:
    tpl = ensure(db, m.FormTemplateVersion, data.template_id, clinic_id)
    enc = ensure(db, m.Encounter, data.encounter_id, clinic_id)
    fields = db.scalars(
        select(m.FormFieldMap).where(m.FormFieldMap.template_id == tpl.id)
    ).all()
    normalized: dict[str, dict] = {}
    missing_required: list[str] = []

    for f in fields:
        entry = data.values.get(f.field_code)
        if entry is None or entry.state == "missing":
            normalized[f.field_code] = {"state": "missing", "value": None}
            if f.required_when == "always":
                missing_required.append(f.field_code)
        elif entry.state == "unknown":
            normalized[f.field_code] = {"state": "unknown", "value": None}
            if not f.allow_unknown and f.required_when == "always":
                missing_required.append(f.field_code)
        elif entry.state == "present":
            val_empty = entry.value is None or str(entry.value).strip() == ""
            normalized[f.field_code] = {"state": "present", "value": entry.value}
            if val_empty and f.required_when == "always":
                missing_required.append(f.field_code)
        else:
            normalized[f.field_code] = {"state": entry.state, "value": entry.value}

    audit(
        db,
        clinic_id,
        actor,
        "clinical_form.synthetic_preview_validated",
        "encounter",
        enc.id,
        {"template_id": tpl.id, "complete": len(missing_required) == 0},
    )
    db.commit()
    return {
        "template_id": tpl.id,
        "official_code": tpl.official_code,
        "schema_version": tpl.schema_version,
        "encounter_id": enc.id,
        "complete": len(missing_required) == 0,
        "missing_required_fields": missing_required,
        "normalized_values": normalized,
        "template_approval_status": tpl.approval_status,
        "clinical_approval": False,
        "synthetic_only": True,
        "warning": "Synthetic form preview only; not an approved 16/BV-01 medical record.",
    }


def export_official_form_blocked(
    db: Session,
    clinic_id: str,
    data: FormOfficialExportRequest,
    actor: str,
) -> None:
    tpl = ensure(db, m.FormTemplateVersion, data.template_id, clinic_id)
    ensure(db, m.Encounter, data.encounter_id, clinic_id)
    audit(
        db,
        clinic_id,
        actor,
        "clinical_form.official_export_blocked",
        "form_template_version",
        tpl.id,
    )
    db.commit()
    raise HTTPException(
        409,
        "Official EMR export blocked: template lacks named dentist and legal counsel approval (NEEDS_CLINICAL_REVIEW.md)",
    )
