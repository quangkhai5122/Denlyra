"""T020 domain services: aggregate-only multi-branch owner view (ORG-007),
auto-expiring temporary delegation (ORG-009), staff operational task escalations
and patient/task-tied internal handoffs (HR-005, HR-006), differentiated contact
timeline & restricted complaint notes (CRM-001, CRM-009), and allowlisted
read-only operations assistant (AI-005).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai_harness, auth, governance_analytics, inventory, models as m, services as svc
from .schemas import (
    BranchScopeGrantCreate,
    InternalHandoffCreate,
    OpsAssistantQueryRequest,
    PatientContactLogCreate,
    ServiceComplaintCreate,
    StaffOperationalTaskCreate,
    TemporaryDelegationCreate,
)

OPS_TOOL_PERMISSIONS = {
    "chair_utilization_summary": "dashboard.read",
    "low_stock_alerts": "inventory.read",
    "overdue_staff_tasks": "operations.read",
    "waitlist_count": "appointment.read",
}


def _ser(item) -> dict:
    out = {}
    for col in item.__table__.columns:
        val = getattr(item, col.name)
        out[col.name] = val.isoformat() + "Z" if isinstance(val, datetime) else val
    return out


def grant_owner_branch_scope(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: BranchScopeGrantCreate,
) -> m.OwnerBranchScopeGrant:
    key = data.owner_group_key.strip()
    branch = data.branch_id.strip()
    existing = db.scalar(
        select(m.OwnerBranchScopeGrant).where(
            m.OwnerBranchScopeGrant.owner_group_key == key,
            m.OwnerBranchScopeGrant.clinic_id == clinic_id,
            m.OwnerBranchScopeGrant.branch_id == branch,
        )
    )
    if existing is not None:
        existing.active = True
        db.commit()
        return existing
    grant = m.OwnerBranchScopeGrant(
        owner_group_key=key,
        clinic_id=clinic_id,
        branch_id=branch,
        granted_by_staff_id=staff_id,
        active=True,
    )
    db.add(grant)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "org.branch_scope_granted",
        "owner_branch_scope_grant",
        grant.id,
        {"owner_group_key": key, "branch_id": branch},
    )
    db.commit()
    return grant


def get_multi_branch_aggregates(
    db: Session,
    caller_clinic_id: str,
    actor: str,
    owner_group_key: str,
) -> dict:
    key = owner_group_key.strip()
    caller_authorized = db.scalar(
        select(m.OwnerBranchScopeGrant).where(
            m.OwnerBranchScopeGrant.owner_group_key == key,
            m.OwnerBranchScopeGrant.clinic_id == caller_clinic_id,
            m.OwnerBranchScopeGrant.active.is_(True),
        )
    )
    if caller_authorized is None:
        raise HTTPException(
            403,
            "Caller clinic is not enrolled in the requested multi-branch owner_group_key (ORG-007)",
        )

    grants = db.scalars(
        select(m.OwnerBranchScopeGrant)
        .where(
            m.OwnerBranchScopeGrant.owner_group_key == key,
            m.OwnerBranchScopeGrant.active.is_(True),
        )
        .order_by(m.OwnerBranchScopeGrant.clinic_id.asc())
    ).all()

    branches_out = []
    total_billed = 0
    total_net_cash = 0
    for gr in grants:
        cid = gr.clinic_id
        clinic_row = db.get(m.Clinic, cid)
        appt_cnt = int(
            db.scalar(
                select(func.count())
                .select_from(m.Appointment)
                .where(m.Appointment.clinic_id == cid)
            )
            or 0
        )
        billed = int(
            db.scalar(
                select(func.coalesce(func.sum(m.Charge.amount_vnd), 0)).where(
                    m.Charge.clinic_id == cid
                )
            )
            or 0
        )
        paid = int(
            db.scalar(
                select(func.coalesce(func.sum(m.Payment.amount_vnd), 0)).where(
                    m.Payment.clinic_id == cid
                )
            )
            or 0
        )
        refunded = int(
            db.scalar(
                select(func.coalesce(func.sum(m.PaymentRefund.amount_vnd), 0)).where(
                    m.PaymentRefund.clinic_id == cid
                )
            )
            or 0
        )
        open_inc = int(
            db.scalar(
                select(func.count())
                .select_from(m.QualityIncidentReport)
                .where(m.QualityIncidentReport.clinic_id == cid)
            )
            or 0
        )
        net_cash = paid - refunded
        total_billed += billed
        total_net_cash += net_cash
        branches_out.append(
            {
                "clinic_id": cid,
                "clinic_name": clinic_row.name if clinic_row else cid,
                "branch_id": gr.branch_id,
                "appointment_count": appt_cnt,
                "billed_charges_vnd": billed,
                "net_collected_cash_vnd": net_cash,
                "quality_incident_count": open_inc,
            }
        )

    svc.audit(
        db,
        caller_clinic_id,
        actor,
        "org.multi_branch_aggregates_viewed",
        "owner_branch_scope_grant",
        caller_authorized.id,
        {"owner_group_key": key, "branch_count": len(branches_out)},
    )
    db.commit()
    return {
        "owner_group_key": key,
        "branches": branches_out,
        "total_billed_charges_vnd": total_billed,
        "total_net_collected_cash_vnd": total_net_cash,
        "contains_patient_charts_or_pii": False,
    }


def create_temporary_delegation(
    db: Session,
    clinic_id: str,
    granter_staff_id: str,
    actor: str,
    data: TemporaryDelegationCreate,
) -> m.TemporaryDelegationGrant:
    delegate = svc.ensure(db, m.Staff, data.delegate_staff_id, clinic_id)
    if not delegate.active:
        raise HTTPException(409, "Cannot delegate permissions to an inactive staff member")
    expires_at = m.utcnow() + timedelta(seconds=int(data.ttl_seconds))
    grant = m.TemporaryDelegationGrant(
        clinic_id=clinic_id,
        granter_staff_id=granter_staff_id,
        delegate_staff_id=delegate.id,
        permission=data.permission,
        reason=data.reason.strip(),
        expires_at=expires_at,
        revoked=False,
    )
    db.add(grant)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "auth.delegation_granted",
        "temporary_delegation_grant",
        grant.id,
        {
            "delegate_staff_id": delegate.id,
            "permission": grant.permission,
            "expires_at": expires_at.isoformat() + "Z",
            "reason": grant.reason,
        },
    )
    db.commit()
    return grant


def revoke_temporary_delegation(
    db: Session, clinic_id: str, grant_id: str, actor: str
) -> m.TemporaryDelegationGrant:
    grant = svc.ensure(db, m.TemporaryDelegationGrant, grant_id, clinic_id)
    grant.revoked = True
    svc.audit(
        db,
        clinic_id,
        actor,
        "auth.delegation_revoked",
        "temporary_delegation_grant",
        grant.id,
    )
    db.commit()
    return grant


def create_staff_operational_task(
    db: Session,
    clinic_id: str,
    actor: str,
    data: StaffOperationalTaskCreate,
) -> m.StaffOperationalTask:
    svc.ensure(db, m.Staff, data.assignee_staff_id, clinic_id)
    if data.patient_id:
        svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    due_naive = data.due_at.astimezone(timezone.utc).replace(tzinfo=None)
    task = m.StaffOperationalTask(
        clinic_id=clinic_id,
        assignee_staff_id=data.assignee_staff_id,
        patient_id=data.patient_id,
        title=data.title.strip(),
        due_at=due_naive,
        escalation_owner_role=data.escalation_owner_role,
        status="open",
        actor_demo=actor,
    )
    db.add(task)
    db.flush()
    db.add(
        m.StaffOperationalTaskEvent(
            clinic_id=clinic_id,
            task_id=task.id,
            action="created",
            note=f"Assigned to {data.assignee_staff_id}",
            actor_demo=actor,
        )
    )
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.staff_task_created",
        "staff_operational_task",
        task.id,
    )
    db.commit()
    return task


def escalate_overdue_staff_tasks(
    db: Session, clinic_id: str, actor: str
) -> dict:
    now = m.utcnow()
    overdue = db.scalars(
        select(m.StaffOperationalTask).where(
            m.StaffOperationalTask.clinic_id == clinic_id,
            m.StaffOperationalTask.status == "open",
            m.StaffOperationalTask.due_at < now,
        )
    ).all()
    escalated_ids: list[str] = []
    for t in overdue:
        t.status = "escalated"
        escalated_ids.append(t.id)
        db.add(
            m.StaffOperationalTaskEvent(
                clinic_id=clinic_id,
                task_id=t.id,
                action="escalated",
                note=f"Overdue past {t.due_at.isoformat()}Z -> escalated to {t.escalation_owner_role}",
                actor_demo=actor,
            )
        )
        db.add(
            m.OutboxEvent(
                clinic_id=clinic_id,
                event_type="StaffTaskOverdueEscalated",
                aggregate_type="staff_operational_task",
                aggregate_id=t.id,
                payload_json=json.dumps(
                    {"escalation_owner_role": t.escalation_owner_role}, ensure_ascii=False
                ),
            )
        )
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.staff_tasks_escalated",
        "clinic",
        clinic_id,
        {"count": len(escalated_ids)},
    )
    db.commit()
    return {"escalated_count": len(escalated_ids), "escalated_task_ids": escalated_ids}


def create_internal_handoff_note(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: InternalHandoffCreate,
) -> m.InternalHandoffNote:
    if data.patient_id:
        svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    if data.task_id:
        svc.ensure(db, m.StaffOperationalTask, data.task_id, clinic_id)
    item = m.InternalHandoffNote(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        task_id=data.task_id,
        message_vi=data.message_vi.strip(),
        author_staff_id=staff_id,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "operations.handoff_note_created",
        "internal_handoff_note",
        item.id,
        {"patient_id": data.patient_id, "task_id": data.task_id},
    )
    db.commit()
    return item


def create_patient_contact_log(
    db: Session,
    clinic_id: str,
    patient_id: str,
    actor: str,
    data: PatientContactLogCreate,
) -> m.PatientContactLog:
    svc.ensure(db, m.Patient, patient_id, clinic_id)
    item = m.PatientContactLog(
        clinic_id=clinic_id,
        patient_id=patient_id,
        channel=data.channel,
        visibility=data.visibility,
        summary_text=data.summary_text.strip(),
        actor_demo=actor,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.contact_logged",
        "patient_contact_log",
        item.id,
        {"visibility": item.visibility, "channel": item.channel},
    )
    db.commit()
    return item


def create_service_complaint(
    db: Session,
    clinic_id: str,
    actor: str,
    data: ServiceComplaintCreate,
) -> m.ServiceComplaintCase:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    item = m.ServiceComplaintCase(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        severity=data.severity,
        public_intake_summary=data.public_intake_summary.strip(),
        private_investigation_notes=data.private_investigation_notes.strip(),
        status="open",
        actor_demo=actor,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.complaint_created",
        "service_complaint_case",
        item.id,
        {"severity": item.severity},
    )
    db.commit()
    return item


def list_service_complaints_scoped(
    db: Session, principal: auth.Principal
) -> list[dict]:
    can_view_private = principal.role in auth.ROLE_PERMISSIONS["complaint.read_private"]
    rows = db.scalars(
        select(m.ServiceComplaintCase)
        .where(m.ServiceComplaintCase.clinic_id == principal.clinic_id)
        .order_by(m.ServiceComplaintCase.created_at.desc())
    ).all()
    out = []
    for r in rows:
        d = _ser(r)
        if not can_view_private:
            d["private_investigation_notes"] = "[REDACTED_AUTHORIZED_LEADERSHIP_ONLY]"
        out.append(d)
    return out


def query_policy_aware_ops_assistant(
    db: Session,
    principal: auth.Principal,
    ai_enabled: bool,
    data: OpsAssistantQueryRequest,
) -> dict:
    if not ai_enabled:
        raise HTTPException(
            503, "AI operations assistant disabled by clinic safety switch (AI-014)"
        )
    triggers = ai_harness.detect_prompt_injection(data.prompt_note)
    if triggers:
        svc.audit(
            db,
            principal.clinic_id,
            principal.actor_label,
            "ai.ops_assistant_injection_blocked",
            "ai_ops_assistant",
            principal.clinic_id,
            {"triggers": triggers},
        )
        db.commit()
        raise HTTPException(
            409,
            f"Prompt injection or unsafe command blocked in ops assistant: {', '.join(triggers)} (AI-010)",
        )

    needed_perm = OPS_TOOL_PERMISSIONS[data.tool_name]
    auth.check_permission(
        db,
        principal,
        needed_perm,
        subject_type="ai_ops_tool",
        subject_id=data.tool_name,
    )

    cid = principal.clinic_id
    if data.tool_name == "chair_utilization_summary":
        kpi = governance_analytics.compute_kpi_lineage_report(db, cid)
        rpt2 = next(x for x in kpi["metrics"] if x["metric_code"] == "RPT-002")
        result_data = rpt2["values"]
        proposal = "Review unseated scheduled appointments with front-desk check-in queue."
    elif data.tool_name == "low_stock_alerts":
        alerts = inventory.get_inventory_alerts(db, cid)
        result_data = {
            "low_stock_sku_count": len(alerts["low_stock_skus"]),
            "expired_lot_count": len(alerts["expired_lots"]),
        }
        proposal = "Human coordinator may open a draft PurchaseOrder if reorder needed."
    elif data.tool_name == "overdue_staff_tasks":
        now = m.utcnow()
        cnt = int(
            db.scalar(
                select(func.count())
                .select_from(m.StaffOperationalTask)
                .where(
                    m.StaffOperationalTask.clinic_id == cid,
                    m.StaffOperationalTask.status == "open",
                    m.StaffOperationalTask.due_at < now,
                )
            )
            or 0
        )
        result_data = {"overdue_open_staff_tasks": cnt}
        proposal = "Authorized manager may trigger POST /api/v1/operations/staff-tasks/escalate-overdue."
    else:
        wl_cnt = int(
            db.scalar(
                select(func.count())
                .select_from(m.ScheduleWaitlistEntry)
                .where(
                    m.ScheduleWaitlistEntry.clinic_id == cid,
                    m.ScheduleWaitlistEntry.status == "waiting",
                )
            )
            or 0
        )
        result_data = {"waiting_entries": wl_cnt}
        proposal = "Staff may prepare consent-verified outreach on waiting list entries."

    svc.audit(
        db,
        cid,
        principal.actor_label,
        "ai.ops_assistant_read_queried",
        "ai_ops_tool",
        data.tool_name,
    )
    db.commit()
    return {
        "tool_name": data.tool_name,
        "checked_permission": needed_perm,
        "read_only_result": result_data,
        "proposed_human_action": proposal,
        "executed_any_write": False,
        "requires_human_confirmation": True,
        "external_network_egress": False,
    }
