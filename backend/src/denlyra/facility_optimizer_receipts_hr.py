"""T021 domain services: licensed facility metadata without display-name inference
(ORG-001), clinician-approved procedure duration templates & safe fallback (SCH-011),
non-mutating constraint slot optimizer requiring explicit human acceptance (SCH-012),
HMAC-traceable non-bank financial receipt exports (FIN-013), and Asia/Ho_Chi_Minh
timezone-correct attendance & overtime isolated from clinical authorship (HR-001, HR-010).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .schemas import (
    AppointmentCreate,
    FacilityLicenseProfileCreate,
    FinancialReceiptExportCreate,
    ProcedureDurationTemplateCreate,
    ScheduleOptimizerAcceptRequest,
    ScheduleOptimizerProposeRequest,
    StaffAttendanceCreate,
)

TZ_HCM = timezone(timedelta(hours=7))


def _to_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def publish_facility_license_profile(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: FacilityLicenseProfileCreate,
) -> m.FacilityLicenseProfile:
    max_ver = int(
        db.scalar(
            select(func.coalesce(func.max(m.FacilityLicenseProfile.version_number), 0)).where(
                m.FacilityLicenseProfile.clinic_id == clinic_id
            )
        )
        or 0
    )
    scopes_sorted = sorted(set(data.permitted_scopes))
    row = m.FacilityLicenseProfile(
        clinic_id=clinic_id,
        version_number=max_ver + 1,
        legal_entity_name_demo=data.legal_entity_name_demo.strip(),
        license_number_demo=data.license_number_demo.strip(),
        license_type=data.license_type,
        permitted_scopes_json=json.dumps(scopes_sorted),
        regulating_authority_demo=data.regulating_authority_demo.strip(),
        verification_status=data.verification_status,
        updated_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "org.facility_profile_published",
        "facility_license_profile",
        row.id,
        {
            "version_number": row.version_number,
            "verification_status": row.verification_status,
            "scopes": scopes_sorted,
        },
    )
    db.commit()
    return row


def evaluate_facility_scope(
    db: Session,
    clinic_id: str,
    requested_scope: str,
) -> dict:
    clinic = db.get(m.Clinic, clinic_id)
    latest = db.scalars(
        select(m.FacilityLicenseProfile)
        .where(m.FacilityLicenseProfile.clinic_id == clinic_id)
        .order_by(m.FacilityLicenseProfile.version_number.desc())
    ).first()
    if latest is None:
        return {
            "clinic_id": clinic_id,
            "clinic_display_name": clinic.name if clinic else clinic_id,
            "requested_scope": requested_scope,
            "allowed_in_demo_scope": False,
            "verification_status": "missing_profile",
            "permitted_scopes": [],
            "never_inferred_from_display_name": True,
        }
    scopes = json.loads(latest.permitted_scopes_json)
    allowed = (
        latest.verification_status == "verified_demo_only"
        and requested_scope.strip() in scopes
    )
    return {
        "clinic_id": clinic_id,
        "clinic_display_name": clinic.name if clinic else clinic_id,
        "requested_scope": requested_scope.strip(),
        "allowed_in_demo_scope": allowed,
        "verification_status": latest.verification_status,
        "permitted_scopes": scopes,
        "profile_version_number": latest.version_number,
        "never_inferred_from_display_name": True,
    }


def publish_procedure_duration_template(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: ProcedureDurationTemplateCreate,
) -> m.ProcedureDurationTemplate:
    code = data.procedure_code.strip().upper()
    max_ver = int(
        db.scalar(
            select(func.coalesce(func.max(m.ProcedureDurationTemplate.version_number), 0)).where(
                m.ProcedureDurationTemplate.clinic_id == clinic_id,
                m.ProcedureDurationTemplate.procedure_code == code,
            )
        )
        or 0
    )
    row = m.ProcedureDurationTemplate(
        clinic_id=clinic_id,
        procedure_code=code,
        version_number=max_ver + 1,
        title_vi=data.title_vi.strip(),
        recommended_minutes=data.recommended_minutes,
        buffer_minutes=data.buffer_minutes,
        fallback_minutes=data.fallback_minutes,
        approved_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "scheduling.duration_template_published",
        "procedure_duration_template",
        row.id,
        {"procedure_code": code, "version_number": row.version_number},
    )
    db.commit()
    return row


def estimate_procedure_duration(
    db: Session,
    clinic_id: str,
    procedure_code: str,
) -> dict:
    code = procedure_code.strip().upper()
    tpl = db.scalars(
        select(m.ProcedureDurationTemplate)
        .where(
            m.ProcedureDurationTemplate.clinic_id == clinic_id,
            m.ProcedureDurationTemplate.procedure_code == code,
        )
        .order_by(m.ProcedureDurationTemplate.version_number.desc())
    ).first()
    if tpl is None:
        return {
            "procedure_code": code,
            "recommended_minutes": 30,
            "buffer_minutes": 0,
            "suggested_total_minutes": 30,
            "used_safe_fallback": True,
            "staff_decides": True,
            "template_version_number": None,
        }
    total = tpl.recommended_minutes + tpl.buffer_minutes
    return {
        "procedure_code": code,
        "recommended_minutes": tpl.recommended_minutes,
        "buffer_minutes": tpl.buffer_minutes,
        "suggested_total_minutes": total,
        "used_safe_fallback": False,
        "staff_decides": True,
        "template_version_number": tpl.version_number,
    }


def propose_optimized_slots(
    db: Session,
    clinic_id: str,
    actor: str,
    data: ScheduleOptimizerProposeRequest,
) -> dict:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    doc_staff = svc.ensure(db, m.Staff, data.practitioner_id, clinic_id)
    if doc_staff.role not in {"dentist", "medical_director"} or not doc_staff.active:
        raise HTTPException(422, "Selected practitioner is not an active clinician")
    chair = svc.ensure(db, m.Resource, data.chair_id, clinic_id)
    if chair.kind != "chair":
        raise HTTPException(422, "Selected resource is not a dental chair")

    if data.override_duration_minutes is not None:
        dur_mins = data.override_duration_minutes
    else:
        dur_mins = estimate_procedure_duration(db, clinic_id, data.procedure_code)[
            "suggested_total_minutes"
        ]

    win_start = _to_utc_naive(data.window_start_at)
    win_end = _to_utc_naive(data.window_end_at)
    dur_delta = timedelta(minutes=dur_mins)
    if win_start + dur_delta > win_end:
        raise HTTPException(422, "Requested window is shorter than procedure duration")

    keys = {f"dentist:{doc_staff.id}", f"chair:{chair.id}"}
    busy_bookings = db.scalars(
        select(m.ResourceBooking).where(
            m.ResourceBooking.clinic_id == clinic_id,
            m.ResourceBooking.state == "active",
            m.ResourceBooking.resource_key.in_(keys),
            m.ResourceBooking.start_at < win_end,
            m.ResourceBooking.end_at > win_start,
        )
    ).all()
    downtimes = db.scalars(
        select(m.ResourceDowntime).where(
            m.ResourceDowntime.clinic_id == clinic_id,
            m.ResourceDowntime.status == "active",
            m.ResourceDowntime.resource_key.in_(keys),
            m.ResourceDowntime.start_at < win_end,
            m.ResourceDowntime.end_at > win_start,
        )
    ).all()
    shifts = db.scalars(
        select(m.StaffShift).where(
            m.StaffShift.clinic_id == clinic_id,
            m.StaffShift.staff_id == doc_staff.id,
            m.StaffShift.active.is_(True),
            m.StaffShift.start_at < win_end,
            m.StaffShift.end_at > win_start,
        )
    ).all()

    candidates: list[dict] = []
    step = timedelta(minutes=15)
    cursor = win_start
    max_candidates = 8
    while cursor + dur_delta <= win_end and len(candidates) < max_candidates:
        cand_end = cursor + dur_delta
        conflict = any(
            b.start_at < cand_end and b.end_at > cursor for b in busy_bookings
        ) or any(d.start_at < cand_end and d.end_at > cursor for d in downtimes)
        if not conflict and shifts:
            in_shift = any(s.start_at <= cursor and s.end_at >= cand_end for s in shifts)
            if not in_shift:
                conflict = True
        if not conflict:
            candidates.append(
                {
                    "slot_index": len(candidates),
                    "start_at": cursor.isoformat() + "Z",
                    "end_at": cand_end.isoformat() + "Z",
                }
            )
        cursor += step

    prop = m.ScheduleOptimizerProposal(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        practitioner_id=doc_staff.id,
        chair_id=chair.id,
        procedure_code=data.procedure_code.strip().upper(),
        window_start_at=win_start,
        window_end_at=win_end,
        duration_minutes=dur_mins,
        proposed_slots_json=json.dumps(candidates),
        solver_engine="deterministic_constraint_grid_v1",
        status="proposed_pending_human",
        actor_demo=actor,
    )
    db.add(prop)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "scheduling.optimizer_proposed",
        "schedule_optimizer_proposal",
        prop.id,
        {"candidate_count": len(candidates), "altered_confirmed_appointments": 0},
    )
    db.commit()
    return {
        "id": prop.id,
        "clinic_id": clinic_id,
        "patient_id": prop.patient_id,
        "procedure_code": prop.procedure_code,
        "duration_minutes": dur_mins,
        "proposed_slots": candidates,
        "solver_engine": prop.solver_engine,
        "altered_confirmed_appointments": 0,
        "status": prop.status,
    }


def accept_optimized_slot(
    db: Session,
    clinic_id: str,
    proposal_id: str,
    actor: str,
    data: ScheduleOptimizerAcceptRequest,
) -> dict:
    prop = svc.ensure(db, m.ScheduleOptimizerProposal, proposal_id, clinic_id)
    if prop.status != "proposed_pending_human":
        raise HTTPException(
            409,
            f"Optimizer proposal is already '{prop.status}' and cannot be re-booked (SCH-012)",
        )
    slots = json.loads(prop.proposed_slots_json)
    if data.slot_index >= len(slots):
        raise HTTPException(422, "Requested slot_index is out of bounds for this proposal")
    chosen = slots[data.slot_index]
    start_dt = datetime.fromisoformat(chosen["start_at"].replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(chosen["end_at"].replace("Z", "+00:00"))

    appt = svc.schedule(
        db,
        clinic_id,
        AppointmentCreate(
            patient_id=prop.patient_id,
            practitioner_id=prop.practitioner_id,
            chair_id=prop.chair_id,
            start_at=start_dt,
            end_at=end_dt,
            reason_demo=data.reason_demo,
            idempotency_key=f"opt-accept-{prop.id}",
        ),
        actor,
    )
    prop.status = "accepted_booked"
    prop.accepted_appointment_id = appt.id
    svc.audit(
        db,
        clinic_id,
        actor,
        "scheduling.optimizer_accepted",
        "schedule_optimizer_proposal",
        prop.id,
        {"appointment_id": appt.id, "slot_index": data.slot_index},
    )
    db.commit()
    return {
        "proposal_id": prop.id,
        "status": prop.status,
        "appointment_id": appt.id,
        "booked_slot": chosen,
    }


def export_financial_receipt(
    db: Session,
    clinic_id: str,
    payment_id: str,
    staff_id: str,
    actor: str,
    auth_secret: str,
    data: FinancialReceiptExportCreate,
) -> m.FinancialReceiptExport:
    pmt = svc.ensure(db, m.Payment, payment_id, clinic_id)
    if data.claim_verified_bank_settlement:
        svc.audit(
            db,
            clinic_id,
            actor,
            "finance.fabricated_bank_receipt_blocked",
            "payment",
            pmt.id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Cannot fabricate verified bank receipt without licensed payment provider settlement proof (FIN-013)",
        )

    allocs = db.scalars(
        select(m.PaymentAllocation)
        .where(m.PaymentAllocation.payment_id == pmt.id)
        .order_by(m.PaymentAllocation.id.asc())
    ).all()
    alloc_items = []
    for al in allocs:
        chg = db.get(m.Charge, al.charge_id)
        alloc_items.append(
            {
                "allocation_id": al.id,
                "charge_id": al.charge_id,
                "charge_label": chg.label if chg else "",
                "allocated_amount_vnd": al.amount_vnd,
            }
        )
    ledger_ids = [
        le.id
        for le in db.scalars(
            select(m.LedgerEntry)
            .where(
                m.LedgerEntry.clinic_id == clinic_id,
                m.LedgerEntry.reference_id == pmt.id,
            )
            .order_by(m.LedgerEntry.id.asc())
        ).all()
    ]
    seq_count = int(
        db.scalar(
            select(func.count())
            .select_from(m.FinancialReceiptExport)
            .where(m.FinancialReceiptExport.clinic_id == clinic_id)
        )
        or 0
    )
    receipt_number = f"SYN-RCPT-{seq_count + 1:05d}-{pmt.id[:8]}"
    canonical_payload = {
        "clinic_id": clinic_id,
        "receipt_number": receipt_number,
        "patient_id": pmt.patient_id,
        "payment_id": pmt.id,
        "amount_vnd": pmt.amount_vnd,
        "payment_method": pmt.payment_method,
        "allocations": alloc_items,
        "ledger_entry_ids": ledger_ids,
        "synthetic_non_bank_receipt": True,
        "fabricated_bank_confirmation": False,
    }
    raw_bytes = json.dumps(
        canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    payload_sha = hashlib.sha256(raw_bytes).hexdigest()
    sig_hmac = hmac.new(
        f"{auth_secret}:{clinic_id}:receipt".encode("utf-8"),
        raw_bytes,
        hashlib.sha256,
    ).hexdigest()

    row = m.FinancialReceiptExport(
        clinic_id=clinic_id,
        patient_id=pmt.patient_id,
        payment_id=pmt.id,
        receipt_number=receipt_number,
        amount_vnd=pmt.amount_vnd,
        payment_method=pmt.payment_method,
        allocated_charges_json=json.dumps(alloc_items, ensure_ascii=False),
        ledger_entry_ids_json=json.dumps(ledger_ids),
        export_note=data.export_note.strip(),
        payload_sha256=payload_sha,
        signature_hmac_sha256=sig_hmac,
        synthetic_non_bank_receipt=True,
        exported_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.receipt_exported",
        "financial_receipt_export",
        row.id,
        {"receipt_number": receipt_number, "payload_sha256": payload_sha},
    )
    db.commit()
    return row


def record_staff_attendance(
    db: Session,
    clinic_id: str,
    recorder_staff_id: str,
    actor: str,
    data: StaffAttendanceCreate,
) -> m.StaffAttendanceLog:
    staff = svc.ensure(db, m.Staff, data.staff_id, clinic_id)
    local_in = data.check_in_at.astimezone(TZ_HCM)
    local_date_hcm = local_in.strftime("%Y-%m-%d")

    in_utc = _to_utc_naive(data.check_in_at)
    out_utc = _to_utc_naive(data.check_out_at)
    worked_mins = int((out_utc - in_utc).total_seconds() // 60)
    if worked_mins <= 0 or worked_mins > 24 * 60:
        raise HTTPException(422, "Attendance shift must be between 1 and 1440 minutes")

    daily_limit = 480
    prior_mins = int(
        db.scalar(
            select(func.coalesce(func.sum(m.StaffAttendanceLog.worked_minutes), 0)).where(
                m.StaffAttendanceLog.clinic_id == clinic_id,
                m.StaffAttendanceLog.staff_id == staff.id,
                m.StaffAttendanceLog.local_date_hcm == local_date_hcm,
            )
        )
        or 0
    )
    remaining_regular = max(0, daily_limit - prior_mins)
    regular_mins = min(worked_mins, remaining_regular)
    overtime_mins = worked_mins - regular_mins

    row = m.StaffAttendanceLog(
        clinic_id=clinic_id,
        staff_id=staff.id,
        check_in_at=in_utc,
        check_out_at=out_utc,
        local_date_hcm=local_date_hcm,
        worked_minutes=worked_mins,
        regular_minutes=regular_mins,
        overtime_minutes=overtime_mins,
        standard_daily_limit_minutes=daily_limit,
        note=data.note.strip(),
        recorded_by_staff_id=recorder_staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "hr.attendance_recorded",
        "staff_attendance_log",
        row.id,
        {
            "local_date_hcm": local_date_hcm,
            "worked_minutes": worked_mins,
            "overtime_minutes": overtime_mins,
        },
    )
    db.commit()
    return row


def get_overtime_summary(
    db: Session,
    clinic_id: str,
    local_date_hcm: str,
) -> dict:
    logs = db.scalars(
        select(m.StaffAttendanceLog)
        .where(
            m.StaffAttendanceLog.clinic_id == clinic_id,
            m.StaffAttendanceLog.local_date_hcm == local_date_hcm.strip(),
        )
        .order_by(m.StaffAttendanceLog.created_at.asc())
    ).all()
    grouped: dict[str, dict] = {}
    for lg in logs:
        if lg.staff_id not in grouped:
            st = db.get(m.Staff, lg.staff_id)
            grouped[lg.staff_id] = {
                "staff_id": lg.staff_id,
                "display_name": st.display_name if st else lg.staff_id,
                "role": st.role if st else "unknown",
                "worked_minutes": 0,
                "regular_minutes": 0,
                "overtime_minutes": 0,
            }
        grouped[lg.staff_id]["worked_minutes"] += lg.worked_minutes
        grouped[lg.staff_id]["regular_minutes"] += lg.regular_minutes
        grouped[lg.staff_id]["overtime_minutes"] += lg.overtime_minutes

    return {
        "clinic_id": clinic_id,
        "local_date_hcm": local_date_hcm.strip(),
        "timezone": "Asia/Ho_Chi_Minh",
        "standard_daily_limit_minutes": 480,
        "affects_clinical_credentials_or_authorship": False,
        "staff_summaries": list(grouped.values()),
    }
