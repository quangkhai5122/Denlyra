"""T018 domain services: clinical milestone checklists (TRT-012), lossless treatment
pause/cancel/terminate governance (TRT-014), consent-safe schedule waiting list (SCH-008),
reviewed installment schedules without auto-charge (FIN-008), and protected quality
incident escalation queue (HR-008).
"""
from __future__ import annotations

from datetime import datetime
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .schemas import (
    AppointmentCreate,
    InstallmentScheduleCreate,
    MilestoneChecklistCreate,
    MilestoneEvaluateRequest,
    PlanLifecycleTransitionCreate,
    QualityIncidentCreate,
    WaitlistCreate,
)


def _ser(item) -> dict:
    out = {}
    for col in item.__table__.columns:
        val = getattr(item, col.name)
        out[col.name] = val.isoformat() + "Z" if isinstance(val, datetime) else val
    return out


def create_milestone_checklist(
    db: Session,
    clinic_id: str,
    task_id: str,
    actor: str,
    data: MilestoneChecklistCreate,
) -> m.PlanMilestoneChecklist:
    task = db.get(m.PlanTask, task_id)
    if task is None:
        raise HTTPException(404, "Plan task not found")
    pv = db.get(m.PlanVersion, task.plan_version_id)
    plan = svc.ensure(db, m.TreatmentPlan, pv.plan_id, clinic_id)

    cleaned = [c.strip() for c in data.criteria_items if c.strip()]
    if not cleaned:
        raise HTTPException(422, "criteria_items must contain at least one non-empty item")

    item = m.PlanMilestoneChecklist(
        clinic_id=clinic_id,
        plan_id=plan.id,
        task_id=task.id,
        title_vi=data.title_vi.strip(),
        criteria_items_json=json.dumps(cleaned, ensure_ascii=False),
        status="pending",
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "treatment.milestone_checklist_created",
        "plan_milestone_checklist",
        item.id,
        {"task_id": task.id},
    )
    db.commit()
    return item


def evaluate_milestone_checklist(
    db: Session,
    clinic_id: str,
    milestone_id: str,
    staff_id: str,
    actor: str,
    data: MilestoneEvaluateRequest,
) -> m.PlanMilestoneChecklist:
    ms = svc.ensure(db, m.PlanMilestoneChecklist, milestone_id, clinic_id)
    if data.all_criteria_met:
        ms.status = "passed"
        ms.clinician_override_reason = None
    else:
        reason = (data.clinician_override_reason or "").strip()
        if len(reason) < 5:
            raise HTTPException(
                409,
                "clinician_override_reason is required when milestone criteria are not fully met (TRT-012)",
            )
        ms.status = "overridden_with_reason"
        ms.clinician_override_reason = reason

    ms.evaluated_by_staff_id = staff_id
    ms.evaluated_at = m.utcnow()
    svc.audit(
        db,
        clinic_id,
        actor,
        "treatment.milestone_evaluated",
        "plan_milestone_checklist",
        ms.id,
        {"status": ms.status, "override_reason": ms.clinician_override_reason},
    )
    db.commit()
    return ms


def get_plan_active_lifecycle_state(db: Session, clinic_id: str, plan_id: str) -> str:
    events = db.scalars(
        select(m.TreatmentPlanLifecycleEvent)
        .where(
            m.TreatmentPlanLifecycleEvent.clinic_id == clinic_id,
            m.TreatmentPlanLifecycleEvent.plan_id == plan_id,
        )
        .order_by(m.TreatmentPlanLifecycleEvent.created_at.asc())
    ).all()
    return events[-1].resulting_state if events else "active"


def transition_plan_lifecycle(
    db: Session,
    clinic_id: str,
    plan_id: str,
    staff_id: str,
    actor: str,
    data: PlanLifecycleTransitionCreate,
) -> m.TreatmentPlanLifecycleEvent:
    plan = svc.ensure(db, m.TreatmentPlan, plan_id, clinic_id)
    current_state = get_plan_active_lifecycle_state(db, clinic_id, plan.id)
    if current_state in {"cancelled", "terminated"}:
        raise HTTPException(
            409, f"Treatment plan is already '{current_state}'; create a new plan instead"
        )
    if data.action == "resume" and current_state != "paused":
        raise HTTPException(409, "Only a 'paused' treatment plan can be resumed")
    if data.action == "pause" and current_state != "active":
        raise HTTPException(409, "Only an 'active' treatment plan can be paused")

    state_map = {
        "pause": "paused",
        "resume": "active",
        "cancel": "cancelled",
        "terminate": "terminated",
    }
    resulting = state_map[data.action]
    ev = m.TreatmentPlanLifecycleEvent(
        clinic_id=clinic_id,
        plan_id=plan.id,
        action=data.action,
        resulting_state=resulting,
        reason=data.reason.strip(),
        clinical_handoff_note=data.clinical_handoff_note.strip(),
        actor_staff_id=staff_id,
    )
    db.add(ev)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        f"treatment.plan_{data.action}",
        "treatment_plan_lifecycle_event",
        ev.id,
        {"plan_id": plan.id, "resulting_state": resulting},
    )
    db.commit()
    return ev


def create_waitlist_entry(
    db: Session,
    clinic_id: str,
    actor: str,
    data: WaitlistCreate,
) -> m.ScheduleWaitlistEntry:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    svc._assert_not_merged_secondary(db, clinic_id, data.patient_id)
    if data.preferred_practitioner_id:
        svc.doctor(db, data.preferred_practitioner_id, clinic_id)
    item = m.ScheduleWaitlistEntry(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        preferred_practitioner_id=data.preferred_practitioner_id,
        preferred_date_window=data.preferred_date_window.strip(),
        service_note_minimized=data.service_note_minimized.strip(),
        status="waiting",
        actor_demo=actor,
    )
    db.add(item)
    db.flush()
    svc.audit(db, clinic_id, actor, "scheduling.waitlist_added", "schedule_waitlist_entry", item.id)
    db.commit()
    return item


def prepare_waitlist_outreach(
    db: Session,
    clinic_id: str,
    entry_id: str,
    actor: str,
) -> m.ScheduleWaitlistEntry:
    entry = svc.ensure(db, m.ScheduleWaitlistEntry, entry_id, clinic_id)
    if entry.status != "waiting":
        raise HTTPException(409, f"Waitlist entry is in state '{entry.status}'")
    active_consent = db.scalar(
        select(m.ConsentRecord).where(
            m.ConsentRecord.clinic_id == clinic_id,
            m.ConsentRecord.patient_id == entry.patient_id,
            m.ConsentRecord.purpose == "treatment",
            m.ConsentRecord.status == "granted",
        )
    )
    if active_consent is None:
        raise HTTPException(
            409,
            "Active 'treatment' consent required before waitlist outreach preparation (SCH-008)",
        )
    entry.status = "outreach_prepared"
    svc.audit(
        db,
        clinic_id,
        actor,
        "scheduling.waitlist_outreach_prepared",
        "schedule_waitlist_entry",
        entry.id,
        {"consent_id": active_consent.id},
    )
    db.commit()
    return entry


def confirm_waitlist_booking(
    db: Session,
    clinic_id: str,
    entry_id: str,
    actor: str,
    booking_data: AppointmentCreate,
) -> m.ScheduleWaitlistEntry:
    entry = svc.ensure(db, m.ScheduleWaitlistEntry, entry_id, clinic_id)
    if entry.status not in {"waiting", "outreach_prepared"}:
        raise HTTPException(409, f"Waitlist entry already resolved ('{entry.status}')")
    if booking_data.patient_id != entry.patient_id:
        raise HTTPException(422, "Booking patient_id must match waitlist entry patient_id")
    appt = svc.schedule(db, clinic_id, booking_data, actor)
    entry.status = "booked_by_staff"
    entry.booked_appointment_id = appt.id
    svc.audit(
        db,
        clinic_id,
        actor,
        "scheduling.waitlist_confirmed_booked",
        "schedule_waitlist_entry",
        entry.id,
        {"booked_appointment_id": appt.id},
    )
    db.commit()
    return entry


def create_installment_schedule(
    db: Session,
    clinic_id: str,
    actor: str,
    data: InstallmentScheduleCreate,
) -> dict:
    est = svc.ensure(db, m.EstimateVersion, data.estimate_id, clinic_id)
    consent = svc.ensure(db, m.ConsentRecord, data.consent_id, clinic_id)
    if (
        consent.patient_id != est.patient_id
        or consent.purpose != "financial"
        or consent.status != "granted"
    ):
        raise HTTPException(
            409,
            "Active granted 'financial' ConsentRecord for the patient is required for installment schedule (FIN-008)",
        )

    tranche_sum = sum(int(t.amount_vnd) for t in data.tranches)
    if tranche_sum != int(est.amount_vnd):
        raise HTTPException(
            422,
            f"Installment tranches sum ({tranche_sum} VND) must equal estimate amount_vnd ({est.amount_vnd} VND)",
        )

    sched = m.InstallmentSchedule(
        clinic_id=clinic_id,
        patient_id=est.patient_id,
        estimate_id=est.id,
        consent_id=consent.id,
        total_amount_vnd=int(est.amount_vnd),
        auto_charge_enabled=False,
        status="active",
        actor_demo=actor,
    )
    db.add(sched)
    db.flush()

    tranche_rows: list[m.InstallmentTranche] = []
    for idx, tr in enumerate(data.tranches, start=1):
        row = m.InstallmentTranche(
            clinic_id=clinic_id,
            schedule_id=sched.id,
            sequence_no=idx,
            due_date=tr.due_date,
            amount_vnd=int(tr.amount_vnd),
            reminder_status="none",
            status="scheduled",
        )
        db.add(row)
        tranche_rows.append(row)
    db.flush()

    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.installment_schedule_created",
        "installment_schedule",
        sched.id,
        {"total_amount_vnd": sched.total_amount_vnd, "auto_charge_enabled": False},
    )
    db.commit()
    return {"schedule": _ser(sched), "tranches": [_ser(r) for r in tranche_rows]}


def log_installment_tranche_reminder(
    db: Session,
    clinic_id: str,
    schedule_id: str,
    tranche_id: str,
    actor: str,
) -> m.InstallmentTranche:
    sched = svc.ensure(db, m.InstallmentSchedule, schedule_id, clinic_id)
    tranche = svc.ensure(db, m.InstallmentTranche, tranche_id, clinic_id)
    if tranche.schedule_id != sched.id:
        raise HTTPException(422, "Tranche does not belong to specified installment schedule")
    tranche.reminder_status = "reminder_logged"
    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.installment_reminder_logged_no_autocharge",
        "installment_tranche",
        tranche.id,
        {"schedule_id": sched.id, "amount_vnd": tranche.amount_vnd},
    )
    db.commit()
    return tranche


def create_quality_incident_report(
    db: Session,
    clinic_id: str,
    reporter_staff_id: str,
    actor: str,
    data: QualityIncidentCreate,
) -> m.QualityIncidentReport:
    if data.encounter_id:
        svc.ensure(db, m.Encounter, data.encounter_id, clinic_id)
    escalate = data.severity in {"high", "critical"}
    status = "escalated_to_director" if escalate else "open"

    item = m.QualityIncidentReport(
        clinic_id=clinic_id,
        encounter_id=data.encounter_id,
        category=data.category,
        severity=data.severity,
        summary=data.summary.strip(),
        evidence_note=data.evidence_note.strip(),
        status=status,
        reporter_staff_id=reporter_staff_id,
    )
    db.add(item)
    db.flush()
    if escalate:
        db.add(
            m.OutboxEvent(
                clinic_id=clinic_id,
                event_type="QualityIncidentEscalated",
                aggregate_type="quality_incident_report",
                aggregate_id=item.id,
                payload_json=json.dumps(
                    {"category": item.category, "severity": item.severity},
                    ensure_ascii=False,
                ),
            )
        )
    svc.audit(
        db,
        clinic_id,
        actor,
        "quality.incident_reported",
        "quality_incident_report",
        item.id,
        {"category": item.category, "severity": item.severity, "status": item.status},
    )
    db.commit()
    return item
