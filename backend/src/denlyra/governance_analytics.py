"""T016 domain services: versioned clinic service price catalog (FIN-001),
dual-control discount & override approval without hidden treatment changes (FIN-014),
and attributable owner KPI lineage & metric dictionary (RPT-002, RPT-004..007, RPT-011).

All money values are integer VND; all percentage rates use integer basis points (0..10000).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .schemas import (
    DiscountDecisionRequest,
    DiscountRequestCreate,
    EstimateFromCatalogCreate,
    PriceCatalogCreate,
)

METRIC_DICTIONARY = [
    {
        "metric_code": "RPT-002",
        "title_vi": "Hiệu suất sử dụng ghế nha thực tế so với lịch đặt",
        "formula_expression": (
            "utilized_chair_minutes = SUM(duration_min(appt) WHERE checkin.status IN "
            "('in_chair','checked_out')); scheduled_chair_minutes = SUM(duration_min(appt) "
            "WHERE appt.status='confirmed')"
        ),
        "numerator_definition": "Tổng số phút lịch hẹn thực tế đã qua cổng vô khuẩn vào ghế (in_chair/checked_out)",
        "denominator_definition": "Tổng số phút lịch hẹn đã đặt (scheduled_chair_minutes) và thời gian bảo trì (maintenance_downtime_minutes)",
        "exclusions_definition": "Các lịch hẹn đã hủy (cancelled) hoặc chỉ đặt giữ chỗ nhưng bệnh nhân chưa vào ghế",
        "source_tables": ["appointment", "checkin_queue_item", "resource_downtime"],
        "review_owner_role": "clinic_owner",
    },
    {
        "metric_code": "RPT-004",
        "title_vi": "Tỷ lệ hoàn tất chăm sóc tái khám & theo dõi điều phối",
        "formula_expression": (
            "followup_rate_bp = ROUND_INT(completed_followup_numerator_count * 10000 / "
            "MAX(due_recall_denominator_count, 1))"
        ),
        "numerator_definition": "Số phiếu recall/follow-up đã đóng kèm bằng chứng (status='closed' AND closure_evidence IS NOT NULL)",
        "denominator_definition": "Tổng số phiếu recall/follow-up đến hạn của bệnh nhân chưa rút đồng thuận liên hệ tương ứng",
        "exclusions_definition": "Bệnh nhân đã rút đồng thuận mục đích tương ứng (withdrawn consent / opt-out) được tách riêng vào excluded_opt_out_count",
        "source_tables": ["recall_followup_item", "consent_record"],
        "review_owner_role": "treatment_coordinator",
    },
    {
        "metric_code": "RPT-005",
        "title_vi": "Phễu kế hoạch điều trị theo trạng thái độc lập",
        "formula_expression": (
            "DISTINCT COUNTS(draft_count, clinician_reviewed_count, estimate_accepted_count, "
            "in_progress_count, all_tasks_completed_admin_count)"
        ),
        "numerator_definition": "Số lượng kế hoạch điều trị ở từng nấc trạng thái hành chính/tài chính riêng biệt",
        "denominator_definition": "Tổng số TreatmentPlan thuộc phòng khám",
        "exclusions_definition": "Không đồng nhất trạng thái hành chính hoàn tất task với xác nhận khỏi bệnh lâm sàng",
        "source_tables": ["treatment_plan", "plan_version", "plan_task", "estimate_version"],
        "review_owner_role": "medical_director",
    },
    {
        "metric_code": "RPT-006",
        "title_vi": "Đối chiếu phát sinh dịch vụ (Accrual) so với thực thu tiền mặt/chuyển khoản (Cash)",
        "formula_expression": (
            "net_collected_cash_vnd = gross_collected_cash_vnd - refunded_vnd; "
            "unallocated_deposit_liability_vnd = net_collected_cash_vnd - allocated_to_charges_vnd; "
            "outstanding_receivable_vnd = billed_charges_vnd - allocated_to_charges_vnd"
        ),
        "numerator_definition": "Tách riêng công nợ phát sinh (Charge), tiền thực thu ròng (Payment - PaymentRefund), và phân bổ (PaymentAllocation)",
        "denominator_definition": "Toàn bộ bút toán sổ cái doanh thu VND nguyên của phòng khám",
        "exclusions_definition": "Báo giá nháp (EstimateVersion) chưa phát sinh Charge không được tính vào doanh thu hay công nợ",
        "source_tables": ["charge", "payment", "payment_refund", "payment_allocation"],
        "review_owner_role": "finance",
    },
    {
        "metric_code": "RPT-007",
        "title_vi": "Ngoại lệ tiến độ Labo & Chờ bác sĩ nghiệm thu lâm sàng",
        "formula_expression": (
            "overdue_unreceived_count = COUNT(due_on < now AND delivered_at IS NULL); "
            "delivered_awaiting_clinical_verification_count = COUNT(status='received' AND verified_at IS NULL)"
        ),
        "numerator_definition": "Số ca labo trễ hạn giao thực tế và số ca đã nhận vật lý nhưng chờ bác sĩ nghiệm thu (LAB-009)",
        "denominator_definition": "Tổng số hồ sơ LabCase thuộc phòng khám",
        "exclusions_definition": "Không suy diễn ngày giao dự kiến thành đã nghiệm thu lâm sàng",
        "source_tables": ["lab_case"],
        "review_owner_role": "dentist",
    },
]


def _ser(item) -> dict:
    out = {}
    for col in item.__table__.columns:
        val = getattr(item, col.name)
        out[col.name] = val.isoformat() + "Z" if isinstance(val, datetime) else val
    return out


def publish_price_catalog_version(
    db: Session,
    clinic_id: str,
    actor: str,
    data: PriceCatalogCreate,
) -> m.ServicePriceCatalogItem:
    code = data.service_code.strip().upper()
    existing = db.scalars(
        select(m.ServicePriceCatalogItem)
        .where(
            m.ServicePriceCatalogItem.clinic_id == clinic_id,
            m.ServicePriceCatalogItem.service_code == code,
        )
        .order_by(m.ServicePriceCatalogItem.version_number.desc())
    ).all()
    next_version = (existing[0].version_number + 1) if existing else 1
    for prev in existing:
        if prev.status == "active":
            prev.status = "superseded"

    item = m.ServicePriceCatalogItem(
        clinic_id=clinic_id,
        service_code=code,
        version_number=next_version,
        name_vi=data.name_vi.strip(),
        category=data.category.strip(),
        unit_price_vnd=int(data.unit_price_vnd),
        max_auto_discount_pct=int(data.max_auto_discount_pct),
        status="active",
        actor_demo=actor,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.price_catalog_version_published",
        "service_price_catalog_item",
        item.id,
        {
            "service_code": item.service_code,
            "version_number": item.version_number,
            "unit_price_vnd": item.unit_price_vnd,
        },
    )
    db.commit()
    return item


def create_estimate_from_catalog(
    db: Session,
    clinic_id: str,
    actor: str,
    data: EstimateFromCatalogCreate,
) -> dict:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    plan = svc.ensure(db, m.TreatmentPlan, data.plan_id, clinic_id)
    if plan.patient_id != data.patient_id:
        raise HTTPException(422, "TreatmentPlan does not belong to specified patient")

    latest_ver = int(
        db.scalar(
            select(func.coalesce(func.max(m.EstimateVersion.version_number), 0)).where(
                m.EstimateVersion.plan_id == plan.id
            )
        )
        or 0
    )

    line_rows: list[m.EstimatePriceSnapshot] = []
    summary_parts: list[str] = []
    total_vnd = 0
    for line_in in data.lines:
        cat = svc.ensure(db, m.ServicePriceCatalogItem, line_in.catalog_item_id, clinic_id)
        line_total = int(cat.unit_price_vnd) * int(line_in.quantity)
        total_vnd += line_total
        summary_parts.append(f"{cat.service_code}@v{cat.version_number}x{line_in.quantity}")
        line_rows.append(
            m.EstimatePriceSnapshot(
                clinic_id=clinic_id,
                estimate_id="",
                catalog_item_id=cat.id,
                service_code=cat.service_code,
                catalog_version_number=cat.version_number,
                quantity=int(line_in.quantity),
                locked_unit_price_vnd=int(cat.unit_price_vnd),
                line_total_vnd=line_total,
            )
        )

    est = m.EstimateVersion(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        plan_id=plan.id,
        version_number=latest_ver + 1,
        amount_vnd=total_vnd,
        items_summary=", ".join(summary_parts)[:400],
        status="draft",
    )
    db.add(est)
    db.flush()
    for snap in line_rows:
        snap.estimate_id = est.id
        db.add(snap)
    db.flush()

    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.estimate_created_from_catalog",
        "estimate_version",
        est.id,
        {"version_number": est.version_number, "amount_vnd": est.amount_vnd},
    )
    db.commit()
    return {"estimate": _ser(est), "lines": [_ser(s) for s in line_rows]}


def get_estimate_with_lines(db: Session, clinic_id: str, estimate_id: str) -> dict:
    est = svc.ensure(db, m.EstimateVersion, estimate_id, clinic_id)
    lines = db.scalars(
        select(m.EstimatePriceSnapshot)
        .where(
            m.EstimatePriceSnapshot.clinic_id == clinic_id,
            m.EstimatePriceSnapshot.estimate_id == est.id,
        )
        .order_by(m.EstimatePriceSnapshot.created_at.asc())
    ).all()
    return {"estimate": _ser(est), "lines": [_ser(s) for s in lines]}


def _spawn_discounted_estimate_version(
    db: Session,
    est: m.EstimateVersion,
    discount_amount_vnd: int,
    reason: str,
) -> m.EstimateVersion:
    latest_ver = int(
        db.scalar(
            select(func.coalesce(func.max(m.EstimateVersion.version_number), 0)).where(
                m.EstimateVersion.plan_id == est.plan_id
            )
        )
        or 0
    )
    new_amount = int(est.amount_vnd) - int(discount_amount_vnd)
    new_est = m.EstimateVersion(
        clinic_id=est.clinic_id,
        patient_id=est.patient_id,
        plan_id=est.plan_id,
        version_number=latest_ver + 1,
        amount_vnd=new_amount,
        items_summary=f"{est.items_summary} | discount=-{discount_amount_vnd} ({reason.strip()})"[:400],
        status="draft",
    )
    db.add(new_est)
    db.flush()

    orig_lines = db.scalars(
        select(m.EstimatePriceSnapshot).where(
            m.EstimatePriceSnapshot.clinic_id == est.clinic_id,
            m.EstimatePriceSnapshot.estimate_id == est.id,
        )
    ).all()
    for ol in orig_lines:
        db.add(
            m.EstimatePriceSnapshot(
                clinic_id=ol.clinic_id,
                estimate_id=new_est.id,
                catalog_item_id=ol.catalog_item_id,
                service_code=ol.service_code,
                catalog_version_number=ol.catalog_version_number,
                quantity=ol.quantity,
                locked_unit_price_vnd=ol.locked_unit_price_vnd,
                line_total_vnd=ol.line_total_vnd,
            )
        )
    db.flush()
    return new_est


def request_estimate_discount(
    db: Session,
    clinic_id: str,
    estimate_id: str,
    requester_staff_id: str,
    actor: str,
    data: DiscountRequestCreate,
) -> m.DiscountApprovalRequest:
    est = svc.ensure(db, m.EstimateVersion, estimate_id, clinic_id)
    if data.discount_amount_vnd >= est.amount_vnd:
        raise HTTPException(422, "discount_amount_vnd must be strictly less than estimate amount_vnd")

    lines = db.scalars(
        select(m.EstimatePriceSnapshot).where(
            m.EstimatePriceSnapshot.clinic_id == clinic_id,
            m.EstimatePriceSnapshot.estimate_id == est.id,
        )
    ).all()
    if lines:
        cat_items = [db.get(m.ServicePriceCatalogItem, ln.catalog_item_id) for ln in lines]
        policy_pct = min((c.max_auto_discount_pct for c in cat_items if c is not None), default=5)
    else:
        policy_pct = 5

    discount_pct_bp = (int(data.discount_amount_vnd) * 10000) // int(est.amount_vnd)
    within_auto = int(data.discount_amount_vnd) * 100 <= int(est.amount_vnd) * int(policy_pct)

    resulting_id: str | None = None
    if within_auto:
        new_est = _spawn_discounted_estimate_version(
            db, est, int(data.discount_amount_vnd), data.reason
        )
        resulting_id = new_est.id
        status = "auto_approved_within_policy"
    else:
        status = "pending_owner_approval"

    req = m.DiscountApprovalRequest(
        clinic_id=clinic_id,
        patient_id=est.patient_id,
        estimate_id=est.id,
        original_amount_vnd=est.amount_vnd,
        discount_amount_vnd=int(data.discount_amount_vnd),
        discount_pct_bp=discount_pct_bp,
        reason=data.reason.strip(),
        status=status,
        requester_staff_id=requester_staff_id,
        resulting_estimate_id=resulting_id,
    )
    db.add(req)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.discount_requested",
        "discount_approval_request",
        req.id,
        {
            "estimate_id": est.id,
            "discount_amount_vnd": req.discount_amount_vnd,
            "status": req.status,
        },
    )
    db.commit()
    return req


def decide_discount_request(
    db: Session,
    clinic_id: str,
    request_id: str,
    approver_staff_id: str,
    actor: str,
    data: DiscountDecisionRequest,
) -> m.DiscountApprovalRequest:
    req = svc.ensure(db, m.DiscountApprovalRequest, request_id, clinic_id)
    if req.status != "pending_owner_approval":
        raise HTTPException(409, f"Discount request is already in state '{req.status}'")
    if req.requester_staff_id == approver_staff_id:
        raise HTTPException(
            409,
            "Dual-control violation: requester cannot approve their own discount override (FIN-014)",
        )

    est = svc.ensure(db, m.EstimateVersion, req.estimate_id, clinic_id)
    if data.approve:
        new_est = _spawn_discounted_estimate_version(
            db, est, req.discount_amount_vnd, req.reason
        )
        req.status = "approved"
        req.resulting_estimate_id = new_est.id
    else:
        req.status = "rejected"

    req.approver_staff_id = approver_staff_id
    req.decision_note = data.decision_note.strip()
    req.decided_at = m.utcnow()
    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.discount_decided",
        "discount_approval_request",
        req.id,
        {
            "status": req.status,
            "approver_staff_id": approver_staff_id,
            "resulting_estimate_id": req.resulting_estimate_id,
        },
    )
    db.commit()
    return req


def get_metric_dictionary() -> list[dict]:
    return [dict(entry) for entry in METRIC_DICTIONARY]


def compute_kpi_lineage_report(db: Session, clinic_id: str) -> dict:
    now = m.utcnow()
    refreshed_iso = now.isoformat() + "Z"

    # RPT-002: Chair utilization vs scheduled vs maintenance downtime
    confirmed_appts = db.scalars(
        select(m.Appointment).where(
            m.Appointment.clinic_id == clinic_id,
            m.Appointment.status == "confirmed",
        )
    ).all()
    seated_appt_ids = set(
        db.scalars(
            select(m.CheckinQueueItem.appointment_id).where(
                m.CheckinQueueItem.clinic_id == clinic_id,
                m.CheckinQueueItem.status.in_(["in_chair", "checked_out"]),
            )
        ).all()
    )
    downtimes = db.scalars(
        select(m.ResourceDowntime).where(
            m.ResourceDowntime.clinic_id == clinic_id,
            m.ResourceDowntime.status == "active",
        )
    ).all()

    scheduled_min = sum(
        max(0, int((a.end_at - a.start_at).total_seconds() // 60)) for a in confirmed_appts
    )
    utilized_min = sum(
        max(0, int((a.end_at - a.start_at).total_seconds() // 60))
        for a in confirmed_appts
        if a.id in seated_appt_ids
    )
    downtime_min = sum(
        max(0, int((d.end_at - d.start_at).total_seconds() // 60)) for d in downtimes
    )
    utilization_bp = (utilized_min * 10000) // scheduled_min if scheduled_min > 0 else 0

    # RPT-004: Patient retention & recall follow-up rate with opt-out exclusions
    recalls = db.scalars(
        select(m.RecallFollowupItem).where(m.RecallFollowupItem.clinic_id == clinic_id)
    ).all()
    withdrawn_consents = db.scalars(
        select(m.ConsentRecord).where(
            m.ConsentRecord.clinic_id == clinic_id,
            m.ConsentRecord.status == "withdrawn",
        )
    ).all()
    withdrawn_pairs = {(c.patient_id, c.purpose) for c in withdrawn_consents}
    excluded_opt_out = 0
    eligible_recalls: list[m.RecallFollowupItem] = []
    for rec in recalls:
        needed_purpose = "marketing" if rec.kind == "marketing_outreach" else "treatment"
        if (rec.patient_id, needed_purpose) in withdrawn_pairs and rec.status != "closed":
            excluded_opt_out += 1
        else:
            eligible_recalls.append(rec)
    completed_recalls = [
        r for r in eligible_recalls if r.status == "closed" and bool(r.closure_evidence)
    ]
    denom_recalls = len(eligible_recalls)
    followup_bp = (len(completed_recalls) * 10000) // denom_recalls if denom_recalls > 0 else 0

    # RPT-005: Treatment plan pipeline
    plans = db.scalars(
        select(m.TreatmentPlan).where(m.TreatmentPlan.clinic_id == clinic_id)
    ).all()
    draft_plans = 0
    reviewed_plans = 0
    accepted_est_plans = 0
    in_progress_plans = 0
    completed_admin_plans = 0
    for pl in plans:
        pv = db.scalar(
            select(m.PlanVersion).where(
                m.PlanVersion.plan_id == pl.id,
                m.PlanVersion.number == pl.current_version,
            )
        )
        tasks = (
            db.scalars(select(m.PlanTask).where(m.PlanTask.plan_version_id == pv.id)).all()
            if pv
            else []
        )
        has_accepted_est = (
            db.scalar(
                select(m.EstimateVersion.id).where(
                    m.EstimateVersion.clinic_id == clinic_id,
                    m.EstimateVersion.plan_id == pl.id,
                    m.EstimateVersion.status == "accepted",
                )
            )
            is not None
        )
        if has_accepted_est:
            accepted_est_plans += 1
        if pv and pv.status == "demo_reviewed":
            reviewed_plans += 1
        else:
            draft_plans += 1
        if tasks:
            done_cnt = sum(1 for t in tasks if t.status == "demo_completed")
            if done_cnt == len(tasks):
                completed_admin_plans += 1
            elif done_cnt > 0:
                in_progress_plans += 1

    # RPT-006: Billing (Accrual) vs Collection (Cash)
    charges = db.scalars(select(m.Charge).where(m.Charge.clinic_id == clinic_id)).all()
    payments = db.scalars(select(m.Payment).where(m.Payment.clinic_id == clinic_id)).all()
    refunds = db.scalars(
        select(m.PaymentRefund).where(m.PaymentRefund.clinic_id == clinic_id)
    ).all()
    allocations = db.scalars(
        select(m.PaymentAllocation)
        .join(m.Charge, m.PaymentAllocation.charge_id == m.Charge.id)
        .where(m.Charge.clinic_id == clinic_id)
    ).all()
    billed_vnd = sum(int(c.amount_vnd) for c in charges)
    gross_cash_vnd = sum(int(p.amount_vnd) for p in payments)
    refunded_vnd = sum(int(r.amount_vnd) for r in refunds)
    net_cash_vnd = gross_cash_vnd - refunded_vnd
    allocated_vnd = sum(int(a.amount_vnd) for a in allocations)

    # RPT-007: Laboratory turnaround exceptions
    labs = db.scalars(select(m.LabCase).where(m.LabCase.clinic_id == clinic_id)).all()
    overdue_unreceived = [
        lb for lb in labs if lb.due_on is not None and lb.due_on < now and lb.delivered_at is None
    ]
    awaiting_verification = [
        lb for lb in labs if lb.status == "received" and lb.verified_at is None
    ]
    verified_labs = [lb for lb in labs if lb.status == "verified"]
    remakes = [lb for lb in labs if lb.revision_number > 1]

    by_code = {d["metric_code"]: d for d in METRIC_DICTIONARY}
    metrics = [
        {
            **by_code["RPT-002"],
            "refreshed_at": refreshed_iso,
            "values": {
                "scheduled_chair_minutes": scheduled_min,
                "utilized_chair_minutes": utilized_min,
                "idle_scheduled_gap_minutes": max(0, scheduled_min - utilized_min),
                "maintenance_downtime_minutes": downtime_min,
                "scheduled_to_utilized_rate_bp": utilization_bp,
            },
            "source_record_ids": [a.id for a in confirmed_appts] + [d.id for d in downtimes],
        },
        {
            **by_code["RPT-004"],
            "refreshed_at": refreshed_iso,
            "values": {
                "total_recall_items": len(recalls),
                "excluded_opt_out_count": excluded_opt_out,
                "due_recall_denominator_count": denom_recalls,
                "completed_followup_numerator_count": len(completed_recalls),
                "followup_rate_bp": followup_bp,
            },
            "source_record_ids": [r.id for r in recalls],
        },
        {
            **by_code["RPT-005"],
            "refreshed_at": refreshed_iso,
            "values": {
                "total_plans": len(plans),
                "draft_count": draft_plans,
                "clinician_reviewed_count": reviewed_plans,
                "estimate_accepted_count": accepted_est_plans,
                "in_progress_count": in_progress_plans,
                "all_tasks_completed_admin_count": completed_admin_plans,
            },
            "source_record_ids": [p.id for p in plans],
        },
        {
            **by_code["RPT-006"],
            "refreshed_at": refreshed_iso,
            "values": {
                "billed_charges_vnd": billed_vnd,
                "gross_collected_cash_vnd": gross_cash_vnd,
                "refunded_vnd": refunded_vnd,
                "net_collected_cash_vnd": net_cash_vnd,
                "allocated_to_charges_vnd": allocated_vnd,
                "unallocated_deposit_liability_vnd": net_cash_vnd - allocated_vnd,
                "outstanding_receivable_vnd": billed_vnd - allocated_vnd,
            },
            "source_record_ids": [c.id for c in charges] + [p.id for p in payments],
        },
        {
            **by_code["RPT-007"],
            "refreshed_at": refreshed_iso,
            "values": {
                "total_lab_cases": len(labs),
                "overdue_unreceived_count": len(overdue_unreceived),
                "delivered_awaiting_clinical_verification_count": len(awaiting_verification),
                "verified_count": len(verified_labs),
                "remake_count": len(remakes),
            },
            "source_record_ids": [lb.id for lb in labs],
        },
    ]
    return {
        "clinic_id": clinic_id,
        "refreshed_at": refreshed_iso,
        "metrics": metrics,
        "synthetic_only": True,
    }
