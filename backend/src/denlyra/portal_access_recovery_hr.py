"""T024 domain services: retention-aware patient subject access export (PAT-011),
FIFO consent-safe cancellation slot recovery without clinical priority inference
(SCH-014), malware/active-content-scanned quarantined portal uploads & human-triaged
support messaging (PORT-008, PORT-010), and staff competency expiry guard +
performed-vs-collected commission preview (HR-007, HR-009).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m, patient_portal, services as svc
from .schemas import (
    CancellationRecoveryRequest,
    PatientAccessRequestCreate,
    PortalSupportMessageCreate,
    PortalSupportReplyRequest,
    PortalUploadCreate,
    PortalUploadReviewRequest,
    StaffCompetencyUpsert,
    StaffCompetencyValidateRequest,
)

ALLOWED_PORTAL_UPLOADS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

EICAR_MARKER = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
DANGEROUS_UPLOAD_PATTERNS = (
    EICAR_MARKER,
    b"<script",
    b"/JavaScript",
    b"/Launch",
)

URGENT_PORTAL_KEYWORDS = (
    "chảy máu",
    "khó thở",
    "sưng to",
    "sốt cao",
    "đau dữ dội",
    "phản vệ",
    "dị ứng",
)


def handle_patient_access_request(
    db: Session,
    clinic_id: str,
    patient_id: str,
    staff_id: str,
    actor: str,
    data: PatientAccessRequestCreate,
) -> m.PatientAccessRequest:
    pat = svc.ensure(db, m.Patient, patient_id, clinic_id)
    if not data.authority_verified or data.requester_kind == "unverified_third_party":
        svc.audit(
            db,
            clinic_id,
            actor,
            "patient.access_request_denied_unverified",
            "patient",
            pat.id,
        )
        db.commit()
        raise HTTPException(
            403,
            "Verified requester authority is mandatory before fulfilling patient data access request (PAT-011)",
        )

    if data.requester_kind == "guardian":
        verified_guardian = db.scalar(
            select(m.ConsentRecord).where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == pat.id,
                m.ConsentRecord.signer_relationship == "guardian",
                m.ConsentRecord.guardian_authority_verified.is_(True),
                m.ConsentRecord.status == "granted",
            )
        )
        if verified_guardian is None:
            raise HTTPException(
                403,
                "Verified guardian ConsentRecord authority is required before guardian data export (PAT-011)",
            )

    if data.request_type == "erasure_request":
        enc_cnt = int(
            db.scalar(
                select(func.count())
                .select_from(m.Encounter)
                .where(m.Encounter.clinic_id == clinic_id, m.Encounter.patient_id == pat.id)
            )
            or 0
        )
        arch_cnt = int(
            db.scalar(
                select(func.count())
                .select_from(m.ArchiveObject)
                .where(
                    m.ArchiveObject.clinic_id == clinic_id,
                    m.ArchiveObject.patient_id == pat.id,
                )
            )
            or 0
        )
        if enc_cnt > 0 or arch_cnt > 0:
            svc.audit(
                db,
                clinic_id,
                actor,
                "patient.erasure_blocked_statutory_retention",
                "patient",
                pat.id,
                {"encounter_count": enc_cnt, "archive_object_count": arch_cnt},
            )
            db.commit()
            raise HTTPException(
                409,
                "Clinical records under statutory retention or legal hold cannot be erased via subject request (PAT-011 / SEC-010)",
            )

    appts = [
        {"id": a.id, "start_at": a.start_at.isoformat() + "Z", "status": a.status}
        for a in db.scalars(
            select(m.Appointment)
            .where(m.Appointment.clinic_id == clinic_id, m.Appointment.patient_id == pat.id)
            .order_by(m.Appointment.start_at.asc())
        ).all()
    ]
    visible_contacts = [
        {"id": c.id, "channel": c.channel, "summary_text": c.summary_text}
        for c in db.scalars(
            select(m.PatientContactLog)
            .where(
                m.PatientContactLog.clinic_id == clinic_id,
                m.PatientContactLog.patient_id == pat.id,
                m.PatientContactLog.visibility == "patient_visible",
            )
            .order_by(m.PatientContactLog.created_at.asc())
        ).all()
    ]
    consents = [
        {"id": c.id, "purpose": c.purpose, "status": c.status}
        for c in db.scalars(
            select(m.ConsentRecord)
            .where(m.ConsentRecord.clinic_id == clinic_id, m.ConsentRecord.patient_id == pat.id)
            .order_by(m.ConsentRecord.created_at.asc())
        ).all()
    ]
    export_bundle = {
        "patient": {
            "id": pat.id,
            "display_name": pat.display_name,
            "birth_year": pat.birth_year,
        },
        "appointments": appts,
        "patient_visible_contacts": visible_contacts,
        "consents": consents,
        "internal_staff_notes_excluded": True,
    }
    export_json = json.dumps(
        export_bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    export_sha = hashlib.sha256(export_json.encode("utf-8")).hexdigest()

    row = m.PatientAccessRequest(
        clinic_id=clinic_id,
        patient_id=pat.id,
        requester_kind=data.requester_kind,
        requester_name=data.requester_name.strip(),
        request_type=data.request_type,
        authority_verified=True,
        status="fulfilled_export_ready",
        export_sha256=export_sha,
        export_payload_json=export_json,
        decision_reason="Authority verified; internal staff notes excluded per privacy boundary",
        handled_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "patient.access_export_fulfilled",
        "patient_access_request",
        row.id,
        {"export_sha256": export_sha, "requester_kind": row.requester_kind},
    )
    db.commit()
    return row


def suggest_cancellation_slot_recovery(
    db: Session,
    clinic_id: str,
    appointment_id: str,
    actor: str,
    data: CancellationRecoveryRequest,
) -> dict:
    appt = svc.ensure(db, m.Appointment, appointment_id, clinic_id)
    if appt.status != "cancelled":
        raise HTTPException(
            409,
            "Cancellation recovery suggestions apply only to appointments in 'cancelled' status (SCH-014)",
        )
    if data.claim_clinical_urgency_ranking:
        raise HTTPException(
            409,
            "Automated clinical priority/urgency inference is prohibited without approved clinical policy (SCH-014 / CRM-012)",
        )

    waitlist_rows = db.scalars(
        select(m.ScheduleWaitlistEntry)
        .where(
            m.ScheduleWaitlistEntry.clinic_id == clinic_id,
            m.ScheduleWaitlistEntry.status.in_(("waiting", "outreach_prepared")),
        )
        .order_by(m.ScheduleWaitlistEntry.created_at.asc())
    ).all()

    candidates: list[dict] = []
    excluded_no_consent = 0
    for wl in waitlist_rows:
        if (
            wl.preferred_practitioner_id
            and wl.preferred_practitioner_id != appt.practitioner_id
        ):
            continue
        trt_consent = db.scalars(
            select(m.ConsentRecord)
            .where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == wl.patient_id,
                m.ConsentRecord.purpose == "treatment",
            )
            .order_by(m.ConsentRecord.created_at.desc())
        ).first()
        dp_consent = db.scalars(
            select(m.ConsentRecord)
            .where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == wl.patient_id,
                m.ConsentRecord.purpose == "data_processing",
            )
            .order_by(m.ConsentRecord.created_at.desc())
        ).first()
        if (
            trt_consent is None
            or trt_consent.status != "granted"
            or (dp_consent is not None and dp_consent.status == "withdrawn")
        ):
            excluded_no_consent += 1
            continue
        candidates.append(
            {
                "rank": len(candidates) + 1,
                "waitlist_entry_id": wl.id,
                "patient_id": wl.patient_id,
                "ranking_basis": "fifo_waitlist_arrival_only",
            }
        )

    row = m.CancellationRecoverySuggestion(
        clinic_id=clinic_id,
        cancelled_appointment_id=appt.id,
        ranked_candidates_json=json.dumps(candidates),
        excluded_no_consent_count=excluded_no_consent,
        clinical_priority_inferred=False,
        actor_demo=actor,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "scheduling.cancellation_recovery_suggested",
        "cancellation_recovery_suggestion",
        row.id,
        {
            "candidate_count": len(candidates),
            "excluded_no_consent_count": excluded_no_consent,
        },
    )
    db.commit()
    return {
        "id": row.id,
        "cancelled_appointment_id": appt.id,
        "freed_slot_start_at": appt.start_at.isoformat() + "Z",
        "freed_slot_end_at": appt.end_at.isoformat() + "Z",
        "ranked_candidates": candidates,
        "excluded_no_consent_count": excluded_no_consent,
        "clinical_priority_inferred": False,
        "auto_booked": False,
    }


def upload_portal_quarantined_file(
    db: Session,
    portal: patient_portal.PortalPrincipal,
    data: PortalUploadCreate,
) -> m.PortalQuarantinedUpload:
    fname = Path(data.original_filename.strip()).name
    ext = Path(fname).suffix.lower()
    expected_mime = ALLOWED_PORTAL_UPLOADS.get(ext)
    if expected_mime is None or data.declared_media_type.strip().lower() != expected_mime:
        raise HTTPException(
            422,
            "Unsupported file type; only PDF, JPEG, and PNG uploads are accepted into quarantine (PORT-008)",
        )
    try:
        raw = base64.b64decode(data.content_b64.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "Invalid base64 file content") from exc

    if len(raw) == 0 or len(raw) > 5_242_880:
        raise HTTPException(422, "Uploaded file size is outside permitted bounds (1B..5MB)")

    if raw.startswith(b"MZ") or raw.startswith(b"\x7fELF") or any(
        sig in raw for sig in DANGEROUS_UPLOAD_PATTERNS
    ):
        svc.audit(
            db,
            portal.clinic_id,
            f"portal:{portal.actor_kind}:{portal.grant_id[:8]}",
            "portal.upload_malware_or_script_blocked",
            "patient",
            portal.patient_id,
            {"filename": fname},
        )
        db.commit()
        raise HTTPException(
            422,
            "Upload blocked by malware and active-content scanner (PORT-008)",
        )

    sha_hex = hashlib.sha256(raw).hexdigest()
    row = m.PortalQuarantinedUpload(
        clinic_id=portal.clinic_id,
        patient_id=portal.patient_id,
        portal_grant_id=portal.grant_id,
        original_filename=fname,
        declared_media_type=expected_mime,
        byte_size=len(raw),
        sha256_hex=sha_hex,
        malware_scan_status="clean_quarantined",
        quarantine_status="quarantined_pending_review",
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        portal.clinic_id,
        f"portal:{portal.actor_kind}:{portal.grant_id[:8]}",
        "portal.upload_quarantined",
        "portal_quarantined_upload",
        row.id,
        {"sha256_hex": sha_hex, "byte_size": len(raw)},
    )
    db.commit()
    return row


def review_portal_quarantined_upload(
    db: Session,
    clinic_id: str,
    upload_id: str,
    staff_id: str,
    actor: str,
    data: PortalUploadReviewRequest,
) -> m.PortalQuarantinedUpload:
    row = svc.ensure(db, m.PortalQuarantinedUpload, upload_id, clinic_id)
    if row.quarantine_status != "quarantined_pending_review":
        raise HTTPException(409, f"Upload already reviewed ('{row.quarantine_status}')")
    row.quarantine_status = data.decision
    row.reviewed_by_staff_id = staff_id
    row.review_note = data.review_note.strip()
    row.reviewed_at = m.utcnow()
    svc.audit(
        db,
        clinic_id,
        actor,
        f"portal.upload_{data.decision}",
        "portal_quarantined_upload",
        row.id,
    )
    db.commit()
    return row


def create_portal_support_message(
    db: Session,
    portal: patient_portal.PortalPrincipal,
    data: PortalSupportMessageCreate,
) -> m.PortalSupportMessage:
    txt = data.message_text.strip()
    is_urgent = any(kw in txt.lower() for kw in URGENT_PORTAL_KEYWORDS)
    urgency = "urgent_human_triage" if is_urgent else "routine_human_queue"

    row = m.PortalSupportMessage(
        clinic_id=portal.clinic_id,
        patient_id=portal.patient_id,
        message_text=txt,
        urgency_flag=urgency,
        triage_status="queued_for_human",
        autonomous_medical_advice_sent=False,
    )
    db.add(row)
    db.flush()
    if is_urgent:
        db.add(
            m.OutboxEvent(
                clinic_id=portal.clinic_id,
                event_type="PortalUrgentSupportTriage",
                aggregate_type="portal_support_message",
                aggregate_id=row.id,
                payload_json=json.dumps(
                    {"patient_id": portal.patient_id, "urgency_flag": urgency},
                    ensure_ascii=False,
                ),
            )
        )
    svc.audit(
        db,
        portal.clinic_id,
        f"portal:{portal.actor_kind}:{portal.grant_id[:8]}",
        "portal.support_message_queued_for_human",
        "portal_support_message",
        row.id,
        {"urgency_flag": urgency, "autonomous_medical_advice_sent": False},
    )
    db.commit()
    return row


def reply_portal_support_message(
    db: Session,
    clinic_id: str,
    message_id: str,
    staff_id: str,
    actor: str,
    data: PortalSupportReplyRequest,
) -> m.PortalSupportMessage:
    row = svc.ensure(db, m.PortalSupportMessage, message_id, clinic_id)
    row.human_reply_text = data.reply_text.strip()
    row.responder_staff_id = staff_id
    row.responded_at = m.utcnow()
    row.triage_status = "responded_by_human"
    svc.audit(
        db,
        clinic_id,
        actor,
        "portal.support_message_responded_by_human",
        "portal_support_message",
        row.id,
    )
    db.commit()
    return row


def upsert_staff_competency(
    db: Session,
    clinic_id: str,
    verifier_staff_id: str,
    actor: str,
    data: StaffCompetencyUpsert,
) -> m.StaffCompetencyRecord:
    staff = svc.ensure(db, m.Staff, data.staff_id, clinic_id)
    code = data.competency_code.strip().upper()
    existing = db.scalar(
        select(m.StaffCompetencyRecord).where(
            m.StaffCompetencyRecord.clinic_id == clinic_id,
            m.StaffCompetencyRecord.staff_id == staff.id,
            m.StaffCompetencyRecord.competency_code == code,
        )
    )
    if existing is not None:
        existing.title_vi = data.title_vi.strip()
        existing.expires_on = data.expires_on
        existing.status = "active"
        existing.verified_by_staff_id = verifier_staff_id
        row = existing
    else:
        row = m.StaffCompetencyRecord(
            clinic_id=clinic_id,
            staff_id=staff.id,
            competency_code=code,
            title_vi=data.title_vi.strip(),
            expires_on=data.expires_on,
            status="active",
            verified_by_staff_id=verifier_staff_id,
        )
        db.add(row)
        db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "hr.competency_upserted",
        "staff_competency_record",
        row.id,
        {"staff_id": staff.id, "competency_code": code, "expires_on": data.expires_on},
    )
    db.commit()
    return row


def validate_staff_competency_assignment(
    db: Session,
    clinic_id: str,
    actor: str,
    data: StaffCompetencyValidateRequest,
) -> dict:
    staff = svc.ensure(db, m.Staff, data.staff_id, clinic_id)
    code = data.competency_code.strip().upper()
    rec = db.scalar(
        select(m.StaffCompetencyRecord).where(
            m.StaffCompetencyRecord.clinic_id == clinic_id,
            m.StaffCompetencyRecord.staff_id == staff.id,
            m.StaffCompetencyRecord.competency_code == code,
            m.StaffCompetencyRecord.status == "active",
        )
    )
    if rec is None or rec.expires_on < data.as_of_date:
        svc.audit(
            db,
            clinic_id,
            actor,
            "hr.competency_assignment_blocked",
            "staff",
            staff.id,
            {"competency_code": code, "as_of_date": data.as_of_date},
        )
        db.commit()
        raise HTTPException(
            409,
            f"Staff '{staff.id}' lacks valid non-expired competency '{code}' on {data.as_of_date} (HR-009)",
        )
    return {
        "staff_id": staff.id,
        "competency_code": code,
        "expires_on": rec.expires_on,
        "as_of_date": data.as_of_date,
        "assignment_permitted": True,
    }


def get_commission_payroll_preview(db: Session, clinic_id: str) -> dict:
    clinicians = db.scalars(
        select(m.Staff)
        .where(
            m.Staff.clinic_id == clinic_id,
            m.Staff.role.in_(("dentist", "medical_director")),
        )
        .order_by(m.Staff.display_name.asc())
    ).all()
    performed_ledger: list[dict] = []
    total_performed = 0
    for cl in clinicians:
        procs = db.scalars(
            select(m.PerformedProcedureEvidence)
            .where(
                m.PerformedProcedureEvidence.clinic_id == clinic_id,
                m.PerformedProcedureEvidence.performed_by_staff_id == cl.id,
            )
            .order_by(m.PerformedProcedureEvidence.created_at.asc())
        ).all()
        cnt = len(procs)
        total_performed += cnt
        performed_ledger.append(
            {
                "staff_id": cl.id,
                "display_name": cl.display_name,
                "performed_procedures_count": cnt,
                "performed_procedure_ids": [p.id for p in procs],
            }
        )

    gross_charges = int(
        db.scalar(
            select(func.coalesce(func.sum(m.Charge.amount_vnd), 0)).where(
                m.Charge.clinic_id == clinic_id
            )
        )
        or 0
    )
    allocated_collected = int(
        db.scalar(
            select(func.coalesce(func.sum(m.PaymentAllocation.amount_vnd), 0))
            .join(m.Charge, m.PaymentAllocation.charge_id == m.Charge.id)
            .where(m.Charge.clinic_id == clinic_id)
        )
        or 0
    )
    refunded = int(
        db.scalar(
            select(func.coalesce(func.sum(m.PaymentRefund.amount_vnd), 0)).where(
                m.PaymentRefund.clinic_id == clinic_id
            )
        )
        or 0
    )

    return {
        "clinic_id": clinic_id,
        "clinician_performed_ledger": performed_ledger,
        "clinic_totals": {
            "total_performed_procedures_count": total_performed,
            "total_billed_charges_vnd": gross_charges,
            "total_allocated_collected_vnd": allocated_collected,
            "total_refunded_vnd": refunded,
            "net_allocated_after_refunds_vnd": allocated_collected - refunded,
        },
        "performed_equated_to_collected": False,
        "payroll_legal_review_status": "synthetic_preview_requires_counsel_signoff",
    }
