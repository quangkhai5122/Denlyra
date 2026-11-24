"""T022 domain services: reviewed reminder templates & consent-gated communication
drafting (CRM-002, AI-006), decoupled anonymous non-manipulative patient satisfaction
survey (CRM-011), and hash-verified incumbent software export adapter + parallel-run
cutover guard (INT-012, MIG-009, MIG-010).
"""
from __future__ import annotations

from datetime import timedelta, timezone
import hashlib
import hmac
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai_harness, models as m, services as svc
from .schemas import (
    CommunicationDraftCreate,
    IncumbentExportApproveRequest,
    IncumbentExportIngestCreate,
    MigrationCutoverPlanCreate,
    ReminderTemplateCreate,
    SatisfactionSurveySubmit,
    SatisfactionTokenIssueRequest,
)

TZ_HCM = timezone(timedelta(hours=7))

URGENT_SYMPTOM_KEYWORDS = (
    "chảy máu",
    "khó thở",
    "sưng to",
    "sốt cao",
    "đau dữ dội",
    "phản vệ",
)


def publish_reminder_template(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: ReminderTemplateCreate,
) -> m.ReminderTemplateVersion:
    code = data.template_code.strip().upper()
    max_ver = int(
        db.scalar(
            select(func.coalesce(func.max(m.ReminderTemplateVersion.version_number), 0)).where(
                m.ReminderTemplateVersion.clinic_id == clinic_id,
                m.ReminderTemplateVersion.template_code == code,
            )
        )
        or 0
    )
    row = m.ReminderTemplateVersion(
        clinic_id=clinic_id,
        template_code=code,
        version_number=max_ver + 1,
        channel=data.channel,
        purpose_category=data.purpose_category,
        body_template_vi=data.body_template_vi.strip(),
        window_start_hour_hcm=data.window_start_hour_hcm,
        window_end_hour_hcm=data.window_end_hour_hcm,
        reviewed_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.reminder_template_published",
        "reminder_template_version",
        row.id,
        {"template_code": code, "version_number": row.version_number},
    )
    db.commit()
    return row


def create_communication_draft(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    ai_enabled: bool,
    data: CommunicationDraftCreate,
) -> m.CommunicationDraftRecord:
    if not ai_enabled:
        raise HTTPException(
            503,
            "AI communication drafting is disabled by clinic feature switch (AI-014)",
        )
    inj_hits = ai_harness.detect_prompt_injection(data.custom_context_note)
    if inj_hits:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ai.comm_draft_injection_blocked",
            "patient",
            data.patient_id,
            {"matched_rules": inj_hits},
        )
        db.commit()
        raise HTTPException(
            409,
            f"Prompt injection pattern blocked in communication context ({', '.join(inj_hits)}) (AI-010)",
        )

    pat = svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    clinic = db.get(m.Clinic, clinic_id)
    code = data.template_code.strip().upper()
    tpl = db.scalars(
        select(m.ReminderTemplateVersion)
        .where(
            m.ReminderTemplateVersion.clinic_id == clinic_id,
            m.ReminderTemplateVersion.template_code == code,
        )
        .order_by(m.ReminderTemplateVersion.version_number.desc())
    ).first()
    if tpl is None:
        raise HTTPException(404, f"Reviewed reminder template '{code}' not found")

    local_send = data.proposed_send_at.astimezone(TZ_HCM)
    send_hour = local_send.hour
    if not (tpl.window_start_hour_hcm <= send_hour < tpl.window_end_hour_hcm):
        raise HTTPException(
            409,
            f"Proposed Ho Chi Minh City send hour ({send_hour}:00) is outside approved window "
            f"[{tpl.window_start_hour_hcm}:00, {tpl.window_end_hour_hcm}:00) (CRM-002)",
        )

    if tpl.purpose_category == "marketing_promo":
        mkt_consent = db.scalars(
            select(m.ConsentRecord)
            .where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == pat.id,
                m.ConsentRecord.purpose == "marketing",
            )
            .order_by(m.ConsentRecord.created_at.desc())
        ).first()
        if mkt_consent is None or mkt_consent.status != "granted":
            svc.audit(
                db,
                clinic_id,
                actor,
                "crm.comm_draft_blocked_no_marketing_consent",
                "patient",
                pat.id,
            )
            db.commit()
            raise HTTPException(
                409,
                "Marketing communication draft blocked: patient lacks active granted 'marketing' consent (CRM-002 / AI-006)",
            )
    else:
        dp_consent = db.scalars(
            select(m.ConsentRecord)
            .where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == pat.id,
                m.ConsentRecord.purpose == "data_processing",
            )
            .order_by(m.ConsentRecord.created_at.desc())
        ).first()
        if dp_consent is not None and dp_consent.status == "withdrawn":
            raise HTTPException(
                409,
                "Communication draft blocked: patient has withdrawn data_processing notice consent (CRM-002)",
            )

    note_lower = data.custom_context_note.lower()
    escalation_needed = any(kw in note_lower for kw in URGENT_SYMPTOM_KEYWORDS)
    if escalation_needed and tpl.purpose_category == "marketing_promo":
        raise HTTPException(
            409,
            "Marketing draft prohibited when urgent post-op clinical symptoms are reported; escalate to clinician (AI-006)",
        )

    rendered = (
        tpl.body_template_vi.replace("{{patient_name}}", pat.display_name)
        .replace("{{clinic_name}}", clinic.name if clinic else clinic_id)
        .replace("{{slot_local}}", local_send.strftime("%Y-%m-%d %H:%M"))
    )
    if escalation_needed:
        rendered = (
            "[CẦN BÁC SĨ PHÂN LOẠI KHẨN - KHÔNG GỬI TỰ ĐỘNG] " + rendered
        )

    row = m.CommunicationDraftRecord(
        clinic_id=clinic_id,
        patient_id=pat.id,
        appointment_id=data.appointment_id,
        template_id=tpl.id,
        template_version_number=tpl.version_number,
        purpose_category=tpl.purpose_category,
        proposed_send_hour_hcm=send_hour,
        rendered_draft_text=rendered,
        escalation_required=escalation_needed,
        auto_sent=False,
        status="draft_pending_staff_review",
        drafted_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ai.communication_draft_created",
        "communication_draft_record",
        row.id,
        {"escalation_required": escalation_needed, "auto_sent": False},
    )
    db.commit()
    return row


def issue_satisfaction_survey_token(
    db: Session,
    clinic_id: str,
    actor: str,
    auth_secret: str,
    data: SatisfactionTokenIssueRequest,
) -> dict:
    svc.ensure(db, m.Appointment, data.appointment_id, clinic_id)
    nonce = str(uuid4())
    msg = f"{clinic_id}:{nonce}".encode("utf-8")
    sig = hmac.new(
        f"{auth_secret}:satisfaction-survey".encode("utf-8"), msg, hashlib.sha256
    ).hexdigest()
    survey_token = f"{nonce}.{sig}"
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.satisfaction_token_issued",
        "clinic",
        clinic_id,
        {"deidentified_token_issued": True},
    )
    db.commit()
    return {
        "clinic_id": clinic_id,
        "survey_token": survey_token,
        "deidentified_storage": True,
    }


def submit_anonymous_satisfaction_survey(
    db: Session,
    auth_secret: str,
    data: SatisfactionSurveySubmit,
) -> dict:
    clinic = db.get(m.Clinic, data.clinic_id)
    if clinic is None:
        raise HTTPException(404, "Clinic not found")
    parts = data.survey_token.strip().split(".")
    if len(parts) != 2:
        raise HTTPException(401, "Malformed satisfaction survey token")
    nonce, provided_sig = parts
    expected_sig = hmac.new(
        f"{auth_secret}:satisfaction-survey".encode("utf-8"),
        f"{data.clinic_id}:{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(
            401, "Invalid or cross-clinic satisfaction survey token (CRM-011)"
        )

    token_sha = hashlib.sha256(data.survey_token.strip().encode("utf-8")).hexdigest()
    existing = db.scalar(
        select(m.SatisfactionTokenReceipt).where(
            m.SatisfactionTokenReceipt.clinic_id == data.clinic_id,
            m.SatisfactionTokenReceipt.token_sha256 == token_sha,
        )
    )
    if existing is not None:
        raise HTTPException(
            409, "Satisfaction survey token has already been used (CRM-011)"
        )

    db.add(
        m.SatisfactionTokenReceipt(
            clinic_id=data.clinic_id,
            token_sha256=token_sha,
        )
    )
    resp = m.PatientSatisfactionResponse(
        clinic_id=data.clinic_id,
        service_month=data.service_month,
        overall_rating=data.overall_rating,
        wait_time_rating=data.wait_time_rating,
        clarity_rating=data.clarity_rating,
        sanitized_comment=data.comment.strip(),
    )
    db.add(resp)
    db.commit()
    return {
        "id": resp.id,
        "clinic_id": resp.clinic_id,
        "service_month": resp.service_month,
        "overall_rating": resp.overall_rating,
        "wait_time_rating": resp.wait_time_rating,
        "clarity_rating": resp.clarity_rating,
        "deidentified": True,
    }


def get_satisfaction_summary(db: Session, clinic_id: str) -> dict:
    rows = db.scalars(
        select(m.PatientSatisfactionResponse)
        .where(m.PatientSatisfactionResponse.clinic_id == clinic_id)
        .order_by(m.PatientSatisfactionResponse.created_at.desc())
    ).all()
    dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    total = len(rows)
    sum_overall = 0
    for r in rows:
        dist[str(r.overall_rating)] += 1
        sum_overall += r.overall_rating
    avg_bp = int(round((sum_overall / total) * 100)) if total > 0 else 0
    return {
        "clinic_id": clinic_id,
        "total_responses": total,
        "average_overall_x100": avg_bp,
        "rating_distribution": dist,
        "contains_patient_identifiers": False,
        "scale_symmetric_1_to_5": True,
    }


def ingest_incumbent_export_package(
    db: Session,
    clinic_id: str,
    uploader_staff_id: str,
    actor: str,
    data: IncumbentExportIngestCreate,
) -> m.IncumbentExportPackage:
    if not data.export_license_confirmed:
        raise HTTPException(
            409,
            "Clinic data export rights must be confirmed before ingesting incumbent software archive (INT-012 / MIG-009)",
        )
    vendor = data.source_vendor_code.strip().lower()
    declared = data.declared_sha256.strip().lower()

    dup = db.scalar(
        select(m.IncumbentExportPackage).where(
            m.IncumbentExportPackage.clinic_id == clinic_id,
            m.IncumbentExportPackage.source_vendor_code == vendor,
            m.IncumbentExportPackage.declared_sha256 == declared,
        )
    )
    if dup is not None:
        raise HTTPException(
            409,
            "Duplicate incumbent export package blocked by double-entry guard (MIG-010)",
        )

    records_dumped = [r.model_dump() for r in data.records]
    canonical_json = json.dumps(
        records_dumped, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    computed = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    if computed != declared:
        svc.audit(
            db,
            clinic_id,
            actor,
            "migration.incumbent_sha256_mismatch_blocked",
            "clinic",
            clinic_id,
            {"declared": declared, "computed": computed},
        )
        db.commit()
        raise HTTPException(
            409,
            "Incumbent export SHA-256 mismatch; historical integrity check failed (INT-012 / MIG-009)",
        )

    total_bal = sum(r.historical_balance_vnd for r in data.records)
    pkg = m.IncumbentExportPackage(
        clinic_id=clinic_id,
        source_vendor_code=vendor,
        schema_version=data.schema_version.strip(),
        export_license_note=data.export_license_note.strip(),
        declared_sha256=declared,
        computed_sha256=computed,
        record_count=len(data.records),
        total_balance_vnd=total_bal,
        payload_json=canonical_json,
        validation_status="quarantined_verified",
        review_status="pending_reviewer_signoff",
        uploader_staff_id=uploader_staff_id,
    )
    db.add(pkg)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "migration.incumbent_package_quarantined",
        "incumbent_export_package",
        pkg.id,
        {"record_count": pkg.record_count, "total_balance_vnd": total_bal},
    )
    db.commit()
    return pkg


def approve_incumbent_export_quarantine(
    db: Session,
    clinic_id: str,
    package_id: str,
    reviewer_staff_id: str,
    actor: str,
    data: IncumbentExportApproveRequest,
) -> m.IncumbentExportPackage:
    pkg = svc.ensure(db, m.IncumbentExportPackage, package_id, clinic_id)
    if pkg.uploader_staff_id == reviewer_staff_id:
        raise HTTPException(
            409,
            "Independent reviewer sign-off required for incumbent system import (uploader != reviewer) (INT-012)",
        )
    if pkg.review_status == "reviewer_approved_quarantine":
        raise HTTPException(409, "Incumbent export package is already approved")
    pkg.review_status = "reviewer_approved_quarantine"
    pkg.reviewer_staff_id = reviewer_staff_id
    pkg.review_note = data.review_note.strip()
    pkg.reviewed_at = m.utcnow()
    svc.audit(
        db,
        clinic_id,
        actor,
        "migration.incumbent_package_approved",
        "incumbent_export_package",
        pkg.id,
        {"reviewer_staff_id": reviewer_staff_id},
    )
    db.commit()
    return pkg


def create_migration_cutover_plan(
    db: Session,
    clinic_id: str,
    approver_staff_id: str,
    actor: str,
    data: MigrationCutoverPlanCreate,
) -> m.MigrationCutoverPlan:
    pkg = svc.ensure(db, m.IncumbentExportPackage, data.incumbent_package_id, clinic_id)
    if pkg.review_status != "reviewer_approved_quarantine":
        raise HTTPException(
            409,
            "Cannot execute cutover plan before independent reviewer approves incumbent package (INT-012 / MIG-010)",
        )
    if (
        data.cutover_mode == "cutover_locked_legacy"
        and not data.legacy_write_freeze_confirmed
    ):
        raise HTTPException(
            409,
            "Cannot finalize cutover while legacy system still permits writes; uncontrolled double-entry risk (MIG-010)",
        )
    if (
        data.reconciled_patient_count != pkg.record_count
        or data.reconciled_total_balance_vnd != pkg.total_balance_vnd
    ):
        raise HTTPException(
            409,
            "Parallel-run reconciliation mismatch against verified incumbent package totals (MIG-010)",
        )

    plan = m.MigrationCutoverPlan(
        clinic_id=clinic_id,
        incumbent_package_id=pkg.id,
        cutover_mode=data.cutover_mode,
        legacy_write_freeze_confirmed=data.legacy_write_freeze_confirmed,
        reconciled_patient_count=data.reconciled_patient_count,
        reconciled_total_balance_vnd=data.reconciled_total_balance_vnd,
        double_entry_guard_active=True,
        rollback_runbook_note=data.rollback_runbook_note.strip(),
        approved_by_staff_id=approver_staff_id,
    )
    db.add(plan)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "migration.cutover_plan_activated",
        "migration_cutover_plan",
        plan.id,
        {
            "cutover_mode": plan.cutover_mode,
            "reconciled_patient_count": plan.reconciled_patient_count,
        },
    )
    db.commit()
    return plan
