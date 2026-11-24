"""T013 Clinic Operations: Shifts, Resource Downtime, Confirmations, Check-In, Chair Turnover & Recalls.

Enforces:
- SCH-001 / ORG-008: Clinician shift definitions.
- SCH-015 / HR-004: Chair/device maintenance downtime blocks.
- SCH-009 / CRM-003: Transport ('sent'/'delivered') != patient intent ('patient_confirmed').
- PAT-009 / SCH-010: Identity verification required at check-in; accessible waiting-room queue.
- HR-002 / HR-003: Chair sanitation & assistant preparation checklist blocks 'in_chair' until 'sanitized_ready'.
- CRM-004 / CRM-005 / CRM-010: Clinical recall requires clinician_approved=True; marketing outreach requires
  active granted 'marketing' ConsentRecord (respecting withdrawals).
"""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .schemas import (
    AppointmentConfirmationCreate,
    ChairTurnoverCompleteRequest,
    ChairTurnoverCreate,
    CheckinCreate,
    CheckinStatusUpdate,
    RecallCloseRequest,
    RecallCreate,
    ResourceDowntimeCreate,
    StaffShiftCreate,
)


def create_staff_shift(
    db: Session, clinic_id: str, data: StaffShiftCreate, actor: str
) -> m.StaffShift:
    svc.doctor(db, data.staff_id, clinic_id)
    start, end = svc.dt_utc_naive(data.start_at), svc.dt_utc_naive(data.end_at)
    shift = m.StaffShift(
        clinic_id=clinic_id,
        staff_id=data.staff_id,
        start_at=start,
        end_at=end,
        active=True,
        actor_demo=actor,
    )
    db.add(shift)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.shift_defined",
        "staff_shift",
        shift.id,
        {"staff_id": data.staff_id},
    )
    db.commit()
    return shift


def create_resource_downtime(
    db: Session, clinic_id: str, data: ResourceDowntimeCreate, actor: str
) -> m.ResourceDowntime:
    res = svc.ensure(db, m.Resource, data.resource_id, clinic_id)
    start, end = svc.dt_utc_naive(data.start_at), svc.dt_utc_naive(data.end_at)
    rkey = f"{res.kind}:{res.id}"

    existing_booking = db.scalars(
        select(m.ResourceBooking).where(
            m.ResourceBooking.clinic_id == clinic_id,
            m.ResourceBooking.resource_key == rkey,
            m.ResourceBooking.state == "active",
            m.ResourceBooking.start_at < end,
            m.ResourceBooking.end_at > start,
        )
    ).first()
    if existing_booking is not None:
        raise HTTPException(
            409,
            "Active confirmed appointment exists in downtime window; reschedule appointment explicitly first",
        )

    dt_row = m.ResourceDowntime(
        clinic_id=clinic_id,
        resource_id=res.id,
        resource_key=rkey,
        start_at=start,
        end_at=end,
        reason=data.reason.strip(),
        status="active",
        actor_demo=actor,
    )
    db.add(dt_row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.downtime_opened",
        "resource_downtime",
        dt_row.id,
        {"resource_key": rkey, "reason": dt_row.reason},
    )
    db.commit()
    return dt_row


def resolve_resource_downtime(
    db: Session, clinic_id: str, downtime_id: str, actor: str
) -> m.ResourceDowntime:
    dt_row = svc.ensure(db, m.ResourceDowntime, downtime_id, clinic_id)
    if dt_row.status == "resolved":
        raise HTTPException(409, "Downtime window is already resolved")
    dt_row.status = "resolved"
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.downtime_resolved",
        "resource_downtime",
        dt_row.id,
    )
    db.commit()
    return dt_row


def record_appointment_confirmation(
    db: Session,
    clinic_id: str,
    appointment_id: str,
    data: AppointmentConfirmationCreate,
    actor: str,
) -> m.AppointmentConfirmation:
    svc.ensure(db, m.Appointment, appointment_id, clinic_id)
    ev = m.AppointmentConfirmation(
        clinic_id=clinic_id,
        appointment_id=appointment_id,
        event_type=data.event_type,
        channel=data.channel,
        evidence_note=data.evidence_note.strip(),
        actor_demo=actor,
    )
    db.add(ev)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        f"appointment.confirmation_{data.event_type}",
        "appointment_confirmation",
        ev.id,
        {"appointment_id": appointment_id, "channel": data.channel},
    )
    db.commit()
    return ev


def get_appointment_confirmation_summary(
    db: Session, clinic_id: str, appointment_id: str
) -> dict:
    svc.ensure(db, m.Appointment, appointment_id, clinic_id)
    events = db.scalars(
        select(m.AppointmentConfirmation)
        .where(
            m.AppointmentConfirmation.clinic_id == clinic_id,
            m.AppointmentConfirmation.appointment_id == appointment_id,
        )
        .order_by(m.AppointmentConfirmation.created_at)
    ).all()
    latest_status = events[-1].event_type if events else "not_sent"
    # SCH-009 / CRM-003: ONLY explicit 'patient_confirmed' counts as confirmed!
    is_confirmed = latest_status == "patient_confirmed"
    return {
        "appointment_id": appointment_id,
        "confirmation_status": latest_status,
        "is_patient_confirmed": is_confirmed,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "channel": e.channel,
                "evidence_note": e.evidence_note,
                "created_at": e.created_at.isoformat() + "Z",
            }
            for e in events
        ],
    }


def create_chair_turnover(
    db: Session, clinic_id: str, data: ChairTurnoverCreate, actor: str
) -> m.ChairTurnoverChecklist:
    svc.chair(db, data.chair_id, clinic_id)
    appt = svc.ensure(db, m.Appointment, data.appointment_id, clinic_id)
    if appt.chair_id != data.chair_id:
        raise HTTPException(422, "Turnover chair_id does not match appointment chair_id")
    row = m.ChairTurnoverChecklist(
        clinic_id=clinic_id,
        chair_id=data.chair_id,
        appointment_id=appt.id,
        status="pending",
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.turnover_checklist_opened",
        "chair_turnover_checklist",
        row.id,
    )
    db.commit()
    return row


def complete_chair_turnover(
    db: Session,
    clinic_id: str,
    checklist_id: str,
    data: ChairTurnoverCompleteRequest,
    actor: str,
) -> m.ChairTurnoverChecklist:
    row = svc.ensure(db, m.ChairTurnoverChecklist, checklist_id, clinic_id)
    if not (
        data.surface_disinfected
        and data.sterile_kit_verified
        and data.waterline_flushed
        and data.assistant_prep_ready
    ):
        raise HTTPException(
            409,
            "All sanitation and assistant preparation steps must be verified before marking chair ready (HR-002 / HR-003)",
        )
    row.surface_disinfected = True
    row.sterile_kit_verified = True
    row.waterline_flushed = True
    row.assistant_prep_ready = True
    row.status = "sanitized_ready"
    row.notes = data.notes.strip()
    row.completed_by = actor
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.turnover_sanitized_ready",
        "chair_turnover_checklist",
        row.id,
    )
    db.commit()
    return row


def create_checkin(
    db: Session, clinic_id: str, data: CheckinCreate, actor: str
) -> m.CheckinQueueItem:
    appt = svc.ensure(db, m.Appointment, data.appointment_id, clinic_id)
    if appt.status != "confirmed":
        raise HTTPException(409, "Cannot check in a cancelled appointment")
    if not data.identity_verified:
        svc.audit(
            db,
            clinic_id,
            actor,
            "operations.checkin_unverified_identity_blocked",
            "appointment",
            appt.id,
        )
        db.commit()
        raise HTTPException(
            409, "Patient identity verification is mandatory at check-in (PAT-009)"
        )

    item = m.CheckinQueueItem(
        clinic_id=clinic_id,
        appointment_id=appt.id,
        patient_id=appt.patient_id,
        identity_verified=True,
        verification_method=data.verification_method,
        status="waiting",
        notes=data.notes.strip(),
        actor_demo=actor,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.patient_checked_in",
        "checkin_queue_item",
        item.id,
        {"method": data.verification_method},
    )
    db.commit()
    return item


def transition_checkin_status(
    db: Session,
    clinic_id: str,
    checkin_id: str,
    data: CheckinStatusUpdate,
    actor: str,
) -> m.CheckinQueueItem:
    item = svc.ensure(db, m.CheckinQueueItem, checkin_id, clinic_id)
    if data.next_status == "in_chair":
        pending_turnover = db.scalars(
            select(m.ChairTurnoverChecklist).where(
                m.ChairTurnoverChecklist.clinic_id == clinic_id,
                m.ChairTurnoverChecklist.appointment_id == item.appointment_id,
                m.ChairTurnoverChecklist.status != "sanitized_ready",
            )
        ).first()
        if pending_turnover is not None:
            raise HTTPException(
                409,
                "Chair sanitation & assistant preparation checklist is incomplete; cannot seat patient (HR-002 / HR-003)",
            )
    before = item.status
    item.status = data.next_status
    if data.notes.strip():
        item.notes = data.notes.strip()
    svc.audit(
        db,
        clinic_id,
        actor,
        f"operations.checkin_{data.next_status}",
        "checkin_queue_item",
        item.id,
        {"from": before, "to": data.next_status},
    )
    db.commit()
    return item


def create_recall_item(
    db: Session, clinic_id: str, data: RecallCreate, actor: str
) -> m.RecallFollowupItem:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    date.fromisoformat(data.due_date)

    if data.kind == "clinical_recall" and not data.clinician_approved:
        raise HTTPException(
            409,
            "Clinical recall program requires explicit clinician_approved=True timing sign-off (CRM-005)",
        )
    if data.kind == "marketing_outreach":
        mkt = db.scalars(
            select(m.ConsentRecord)
            .where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == data.patient_id,
                m.ConsentRecord.purpose == "marketing",
            )
            .order_by(m.ConsentRecord.created_at.desc())
        ).first()
        if mkt is None or mkt.status != "granted":
            svc.audit(
                db,
                clinic_id,
                actor,
                "crm.marketing_outreach_blocked_no_consent",
                "patient",
                data.patient_id,
            )
            db.commit()
            raise HTTPException(
                409,
                "Marketing outreach blocked: patient lacks active granted 'marketing' consent or has opted out (CRM-010 / PAT-008)",
            )

    row = m.RecallFollowupItem(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        kind=data.kind,
        due_date=data.due_date,
        reason=data.reason.strip(),
        clinician_approved=data.clinician_approved,
        status="open",
        owner_role=data.owner_role,
        actor_demo=actor,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        f"crm.recall_opened.{data.kind}",
        "recall_followup_item",
        row.id,
    )
    db.commit()
    return row


def close_recall_item(
    db: Session,
    clinic_id: str,
    recall_id: str,
    data: RecallCloseRequest,
    actor: str,
) -> m.RecallFollowupItem:
    row = svc.ensure(db, m.RecallFollowupItem, recall_id, clinic_id)
    if row.status == "closed":
        raise HTTPException(409, "Recall item is already closed")
    row.status = "closed"
    row.closure_evidence = data.closure_evidence.strip()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.recall_closed",
        "recall_followup_item",
        row.id,
        {"closure_evidence": row.closure_evidence},
    )
    db.commit()
    return row
