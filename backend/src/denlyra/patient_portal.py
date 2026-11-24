"""T015 domain services: reversible dual-confirmed patient merge (PAT-006),
short-TTL emergency break-glass access with independent after-action review (ORG-011),
and clinician-published patient/guardian portal views (PORT-001..007, PORT-009, TRT-016).

Synthetic research demonstrator only — NOT a public patient portal or certified EMR.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import time

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import auth, models as m, operations, services as svc
from .schemas import (
    AppointmentConfirmationCreate,
    AppointmentReschedule,
    BreakGlassCreateRequest,
    BreakGlassReviewRequest,
    PatientMergeConfirmRequest,
    PatientMergeCreate,
    PatientMergeReverseRequest,
    PortalGrantCreate,
    PortalInstructionPublish,
    PortalIntakeCreate,
    PortalPlanSummaryPublish,
    PortalRescheduleCreate,
    PortalRescheduleDecisionRequest,
)

EMERGENCY_READ_SCOPES = [
    "encounter.read",
    "note.read",
    "clinical_doc.read",
    "odontogram.read",
]


@dataclass(frozen=True)
class PortalPrincipal:
    grant_id: str
    clinic_id: str
    patient_id: str
    actor_kind: str
    actor_display_name: str


def _ser(item) -> dict:
    out = {}
    for col in item.__table__.columns:
        val = getattr(item, col.name)
        out[col.name] = val.isoformat() + "Z" if isinstance(val, datetime) else val
    return out


def assert_patient_not_merged_secondary(
    db: Session, clinic_id: str, patient_id: str
) -> None:
    active_merge = db.scalar(
        select(m.PatientMergeRequest).where(
            m.PatientMergeRequest.clinic_id == clinic_id,
            m.PatientMergeRequest.secondary_patient_id == patient_id,
            m.PatientMergeRequest.status == "merged",
        )
    )
    if active_merge is not None:
        raise HTTPException(
            409,
            f"Patient '{patient_id}' is merged into canonical patient "
            f"'{active_merge.primary_patient_id}'; book or chart against canonical ID (PAT-006)",
        )


def create_patient_merge_request(
    db: Session,
    clinic_id: str,
    requester_staff_id: str,
    actor: str,
    data: PatientMergeCreate,
) -> m.PatientMergeRequest:
    if data.primary_patient_id == data.secondary_patient_id:
        raise HTTPException(422, "primary_patient_id and secondary_patient_id must differ")
    svc.ensure(db, m.Patient, data.primary_patient_id, clinic_id)
    svc.ensure(db, m.Patient, data.secondary_patient_id, clinic_id)

    chained = db.scalar(
        select(m.PatientMergeRequest).where(
            m.PatientMergeRequest.clinic_id == clinic_id,
            m.PatientMergeRequest.status == "merged",
            m.PatientMergeRequest.secondary_patient_id.in_(
                [data.primary_patient_id, data.secondary_patient_id]
            ),
        )
    )
    if chained is not None:
        raise HTTPException(
            409,
            "One of the specified patients is already a merged secondary record (PAT-006)",
        )

    req = m.PatientMergeRequest(
        clinic_id=clinic_id,
        primary_patient_id=data.primary_patient_id,
        secondary_patient_id=data.secondary_patient_id,
        rationale=data.rationale.strip(),
        contradictions_noted=data.contradictions_noted.strip(),
        status="pending_second_confirmation",
        requester_staff_id=requester_staff_id,
    )
    db.add(req)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "patient.merge_requested",
        "patient_merge_request",
        req.id,
        {
            "primary_patient_id": req.primary_patient_id,
            "secondary_patient_id": req.secondary_patient_id,
        },
    )
    db.commit()
    return req


def confirm_patient_merge_request(
    db: Session,
    clinic_id: str,
    merge_id: str,
    approver_staff_id: str,
    actor: str,
    data: PatientMergeConfirmRequest,
) -> m.PatientMergeRequest:
    req = svc.ensure(db, m.PatientMergeRequest, merge_id, clinic_id)
    if req.status != "pending_second_confirmation":
        raise HTTPException(409, f"Merge request is in state '{req.status}', cannot confirm")
    if req.requester_staff_id == approver_staff_id:
        raise HTTPException(
            409,
            "Independent second staff confirmation required; requester cannot self-confirm patient merge (PAT-006)",
        )
    already_merged = db.scalar(
        select(m.PatientMergeRequest).where(
            m.PatientMergeRequest.clinic_id == clinic_id,
            m.PatientMergeRequest.secondary_patient_id == req.secondary_patient_id,
            m.PatientMergeRequest.status == "merged",
        )
    )
    if already_merged is not None:
        raise HTTPException(409, "Secondary patient is already merged in another active link")

    req.status = "merged"
    req.approver_staff_id = approver_staff_id
    req.confirmation_note = data.confirmation_note.strip()
    req.approved_at = m.utcnow()
    db.add(
        m.OutboxEvent(
            clinic_id=clinic_id,
            event_type="PatientMerged",
            aggregate_type="patient_merge_request",
            aggregate_id=req.id,
            payload_json=json.dumps(
                {
                    "primary_patient_id": req.primary_patient_id,
                    "secondary_patient_id": req.secondary_patient_id,
                },
                ensure_ascii=False,
            ),
        )
    )
    svc.audit(
        db,
        clinic_id,
        actor,
        "patient.merge_confirmed",
        "patient_merge_request",
        req.id,
        {
            "primary_patient_id": req.primary_patient_id,
            "secondary_patient_id": req.secondary_patient_id,
            "approver_staff_id": approver_staff_id,
        },
    )
    db.commit()
    return req


def reverse_patient_merge_request(
    db: Session,
    clinic_id: str,
    merge_id: str,
    staff_id: str,
    actor: str,
    data: PatientMergeReverseRequest,
) -> m.PatientMergeRequest:
    req = svc.ensure(db, m.PatientMergeRequest, merge_id, clinic_id)
    if req.status != "merged":
        raise HTTPException(409, f"Only 'merged' records can be reversed (current='{req.status}')")
    req.status = "reversed"
    req.reversal_reason = data.reversal_reason.strip()
    req.reversed_by_staff_id = staff_id
    req.reversed_at = m.utcnow()
    svc.audit(
        db,
        clinic_id,
        actor,
        "patient.merge_reversed",
        "patient_merge_request",
        req.id,
        {"reversal_reason": req.reversal_reason},
    )
    db.commit()
    return req


def get_patient_unified_summary(
    db: Session, clinic_id: str, patient_id: str
) -> dict:
    svc.ensure(db, m.Patient, patient_id, clinic_id)
    as_secondary = db.scalar(
        select(m.PatientMergeRequest).where(
            m.PatientMergeRequest.clinic_id == clinic_id,
            m.PatientMergeRequest.secondary_patient_id == patient_id,
            m.PatientMergeRequest.status == "merged",
        )
    )
    canonical_id = as_secondary.primary_patient_id if as_secondary else patient_id
    canonical_patient = svc.ensure(db, m.Patient, canonical_id, clinic_id)

    merged_links = db.scalars(
        select(m.PatientMergeRequest).where(
            m.PatientMergeRequest.clinic_id == clinic_id,
            m.PatientMergeRequest.primary_patient_id == canonical_id,
            m.PatientMergeRequest.status == "merged",
        )
    ).all()
    secondary_ids = [r.secondary_patient_id for r in merged_links]
    family_ids = [canonical_id, *secondary_ids]

    def _collect(cls):
        rows = db.scalars(
            select(cls)
            .where(cls.clinic_id == clinic_id, cls.patient_id.in_(family_ids))
            .order_by(cls.created_at.asc())
        ).all()
        return [{**_ser(r), "source_patient_id": r.patient_id} for r in rows]

    return {
        "queried_patient_id": patient_id,
        "canonical_patient_id": canonical_id,
        "canonical_patient": _ser(canonical_patient),
        "merged_secondary_patient_ids": secondary_ids,
        "encounters": _collect(m.Encounter),
        "appointments": _collect(m.Appointment),
        "treatment_plans": _collect(m.TreatmentPlan),
        "charges": _collect(m.Charge),
        "payments": _collect(m.Payment),
    }


def create_break_glass_grant(
    db: Session,
    principal: auth.Principal,
    data: BreakGlassCreateRequest,
) -> m.BreakGlassGrant:
    svc.ensure(db, m.Patient, data.patient_id, principal.clinic_id)
    expires_at = m.utcnow() + timedelta(seconds=data.ttl_seconds)
    grant = m.BreakGlassGrant(
        clinic_id=principal.clinic_id,
        patient_id=data.patient_id,
        requester_staff_id=principal.staff_id,
        requester_role=principal.role,
        emergency_reason=data.emergency_reason.strip(),
        granted_permissions_json=json.dumps(EMERGENCY_READ_SCOPES),
        expires_at=expires_at,
        status="active",
        review_status="pending_independent_review",
    )
    db.add(grant)
    db.flush()
    db.add(
        m.OutboxEvent(
            clinic_id=principal.clinic_id,
            event_type="BreakGlassActivated",
            aggregate_type="break_glass_grant",
            aggregate_id=grant.id,
            payload_json=json.dumps(
                {
                    "patient_id": grant.patient_id,
                    "requester_staff_id": grant.requester_staff_id,
                    "expires_at": expires_at.isoformat() + "Z",
                },
                ensure_ascii=False,
            ),
        )
    )
    svc.audit(
        db,
        principal.clinic_id,
        principal.actor_label,
        "auth.break_glass_activated",
        "break_glass_grant",
        grant.id,
        {
            "patient_id": grant.patient_id,
            "ttl_seconds": data.ttl_seconds,
            "emergency_reason": grant.emergency_reason,
        },
    )
    db.commit()
    return grant


def read_break_glass_chart(
    db: Session,
    principal: auth.Principal,
    grant_id: str,
) -> dict:
    grant = db.get(m.BreakGlassGrant, grant_id)
    if grant is None:
        raise HTTPException(404, "Break-glass grant not found")
    if grant.clinic_id != principal.clinic_id or grant.requester_staff_id != principal.staff_id:
        svc.audit(
            db,
            principal.clinic_id,
            principal.actor_label,
            "auth.break_glass_access_denied",
            "break_glass_grant",
            grant.id,
        )
        db.commit()
        raise HTTPException(403, "Break-glass grant is bound to its original clinic and requester")

    now = m.utcnow()
    if grant.status != "active" or now >= grant.expires_at:
        if grant.status == "active" and now >= grant.expires_at:
            grant.status = "expired"
        svc.audit(
            db,
            principal.clinic_id,
            principal.actor_label,
            "auth.break_glass_expired_or_revoked_denied",
            "break_glass_grant",
            grant.id,
        )
        db.commit()
        raise HTTPException(403, "Break-glass grant is expired or revoked (ORG-011)")

    encounters = db.scalars(
        select(m.Encounter).where(
            m.Encounter.clinic_id == grant.clinic_id,
            m.Encounter.patient_id == grant.patient_id,
        )
    ).all()
    enc_ids = [e.id for e in encounters]
    notes_out = []
    findings_out = []
    if enc_ids:
        notes = db.scalars(
            select(m.ClinicalNote).where(
                m.ClinicalNote.clinic_id == grant.clinic_id,
                m.ClinicalNote.encounter_id.in_(enc_ids),
            )
        ).all()
        for n in notes:
            rev = db.scalar(
                select(m.NoteRevision)
                .where(
                    m.NoteRevision.note_id == n.id,
                    m.NoteRevision.revision_no == n.latest_revision,
                )
            )
            notes_out.append(
                {
                    "id": n.id,
                    "encounter_id": n.encounter_id,
                    "status": n.status,
                    "latest_revision": n.latest_revision,
                    "content": rev.content if rev else "",
                }
            )
        findings = db.scalars(
            select(m.DentalFinding).where(
                m.DentalFinding.clinic_id == grant.clinic_id,
                m.DentalFinding.encounter_id.in_(enc_ids),
            )
        ).all()
        findings_out = [_ser(f) for f in findings]

    svc.audit(
        db,
        principal.clinic_id,
        principal.actor_label,
        "auth.break_glass_chart_accessed",
        "break_glass_grant",
        grant.id,
        {"patient_id": grant.patient_id},
    )
    db.commit()
    return {
        "grant_id": grant.id,
        "patient_id": grant.patient_id,
        "expires_at": grant.expires_at.isoformat() + "Z",
        "read_only_emergency_view": True,
        "encounters": [_ser(e) for e in encounters],
        "notes": notes_out,
        "findings": findings_out,
    }


def revoke_break_glass_grant(
    db: Session,
    clinic_id: str,
    grant_id: str,
    actor: str,
) -> m.BreakGlassGrant:
    grant = svc.ensure(db, m.BreakGlassGrant, grant_id, clinic_id)
    grant.status = "revoked"
    svc.audit(db, clinic_id, actor, "auth.break_glass_revoked", "break_glass_grant", grant.id)
    db.commit()
    return grant


def review_break_glass_grant(
    db: Session,
    clinic_id: str,
    grant_id: str,
    reviewer_staff_id: str,
    actor: str,
    data: BreakGlassReviewRequest,
) -> m.BreakGlassGrant:
    grant = svc.ensure(db, m.BreakGlassGrant, grant_id, clinic_id)
    if grant.requester_staff_id == reviewer_staff_id:
        raise HTTPException(
            409,
            "Independent after-action review required; requester cannot review their own break-glass grant (ORG-011)",
        )
    grant.review_status = data.outcome
    grant.reviewer_staff_id = reviewer_staff_id
    grant.review_notes = data.review_notes.strip()
    grant.reviewed_at = m.utcnow()
    svc.audit(
        db,
        clinic_id,
        actor,
        "auth.break_glass_reviewed",
        "break_glass_grant",
        grant.id,
        {"outcome": data.outcome, "reviewer_staff_id": reviewer_staff_id},
    )
    db.commit()
    return grant


def issue_portal_session_grant(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    secret: str,
    data: PortalGrantCreate,
) -> dict:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    if data.actor_kind == "guardian":
        verified_guardian = db.scalar(
            select(m.ConsentRecord).where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == data.patient_id,
                m.ConsentRecord.signer_relationship == "guardian",
                m.ConsentRecord.guardian_authority_verified.is_(True),
                m.ConsentRecord.status == "granted",
            )
        )
        if verified_guardian is None:
            svc.audit(
                db,
                clinic_id,
                actor,
                "portal.guardian_unverified_denied",
                "patient",
                data.patient_id,
            )
            db.commit()
            raise HTTPException(
                403,
                "Verified guardian consent authority required before issuing guardian portal access (PORT-001 / PORT-009)",
            )

    now_ts = int(time.time())
    exp_ts = now_ts + int(data.ttl_seconds)
    expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc).replace(tzinfo=None)
    grant = m.PortalSessionGrant(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        actor_kind=data.actor_kind,
        actor_display_name=data.actor_display_name.strip(),
        expires_at=expires_at,
        revoked=False,
        created_by_staff_id=staff_id,
    )
    db.add(grant)
    db.flush()
    claims = {
        "iss": auth.ISSUER,
        "aud": "patient_portal",
        "sub": grant.id,
        "clinic_id": clinic_id,
        "patient_id": data.patient_id,
        "actor_kind": grant.actor_kind,
        "actor_display_name": grant.actor_display_name,
        "iat": now_ts,
        "exp": exp_ts,
    }
    token = auth.sign_token(claims, secret)
    svc.audit(
        db,
        clinic_id,
        actor,
        "portal.session_grant_issued",
        "portal_session_grant",
        grant.id,
        {"patient_id": data.patient_id, "actor_kind": grant.actor_kind},
    )
    db.commit()
    return {
        "grant_id": grant.id,
        "portal_token": token,
        "clinic_id": clinic_id,
        "patient_id": data.patient_id,
        "actor_kind": grant.actor_kind,
        "expires_at": expires_at.isoformat() + "Z",
        "synthetic_only": True,
    }


def resolve_portal_principal(
    db: Session,
    authorization: str | None,
    secret: str,
) -> PortalPrincipal:
    if not authorization:
        raise HTTPException(401, "Bearer portal token required")
    scheme, _, raw = authorization.partition(" ")
    if scheme.lower() != "bearer" or not raw.strip():
        raise HTTPException(401, "Bearer portal token required")
    claims = auth.decode_and_verify_token(raw.strip(), secret)
    if claims.get("aud") != "patient_portal":
        raise HTTPException(403, "Token is not scoped to patient_portal")
    grant_id = str(claims.get("sub") or "")
    grant = db.get(m.PortalSessionGrant, grant_id)
    if grant is None or grant.revoked or m.utcnow() >= grant.expires_at:
        raise HTTPException(401, "Portal session grant expired or revoked")
    return PortalPrincipal(
        grant_id=grant.id,
        clinic_id=grant.clinic_id,
        patient_id=grant.patient_id,
        actor_kind=grant.actor_kind,
        actor_display_name=grant.actor_display_name,
    )


def publish_portal_instruction(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: PortalInstructionPublish,
) -> m.PortalPublishedInstruction:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    if data.encounter_id:
        enc = svc.ensure(db, m.Encounter, data.encounter_id, clinic_id)
        if enc.patient_id != data.patient_id:
            raise HTTPException(422, "Encounter does not belong to specified patient")
    item = m.PortalPublishedInstruction(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        encounter_id=data.encounter_id,
        title_vi=data.title_vi.strip(),
        body_vi=data.body_vi.strip(),
        published_by_staff_id=staff_id,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "portal.instruction_published",
        "portal_published_instruction",
        item.id,
        {"patient_id": data.patient_id},
    )
    db.commit()
    return item


def publish_portal_plan_summary(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: PortalPlanSummaryPublish,
) -> m.PortalPublishedPlanSummary:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    plan = svc.ensure(db, m.TreatmentPlan, data.plan_id, clinic_id)
    if plan.patient_id != data.patient_id:
        raise HTTPException(422, "TreatmentPlan does not belong to specified patient")
    item = m.PortalPublishedPlanSummary(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        plan_id=plan.id,
        plan_version_number=plan.current_version,
        lay_summary_vi=data.lay_summary_vi.strip(),
        published_by_staff_id=staff_id,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "portal.plan_summary_published",
        "portal_published_plan_summary",
        item.id,
        {"patient_id": data.patient_id, "plan_id": plan.id},
    )
    db.commit()
    return item


def get_patient_portal_overview(db: Session, portal: PortalPrincipal) -> dict:
    patient = svc.ensure(db, m.Patient, portal.patient_id, portal.clinic_id)
    appts = db.scalars(
        select(m.Appointment)
        .where(
            m.Appointment.clinic_id == portal.clinic_id,
            m.Appointment.patient_id == portal.patient_id,
        )
        .order_by(m.Appointment.start_at.asc())
    ).all()
    staff_names = {
        s.id: s.display_name
        for s in db.scalars(select(m.Staff).where(m.Staff.clinic_id == portal.clinic_id)).all()
    }
    chair_names = {
        r.id: r.name
        for r in db.scalars(
            select(m.Resource).where(m.Resource.clinic_id == portal.clinic_id)
        ).all()
    }
    appointments_view = [
        {
            "id": a.id,
            "start_at": a.start_at.isoformat() + "Z",
            "end_at": a.end_at.isoformat() + "Z",
            "status": a.status,
            "practitioner_display_name": staff_names.get(a.practitioner_id, "Bác sĩ phòng khám"),
            "chair_name": chair_names.get(a.chair_id, "Ghế khám"),
            "reason_demo": a.reason_demo,
        }
        for a in appts
    ]

    instructions = db.scalars(
        select(m.PortalPublishedInstruction)
        .where(
            m.PortalPublishedInstruction.clinic_id == portal.clinic_id,
            m.PortalPublishedInstruction.patient_id == portal.patient_id,
        )
        .order_by(m.PortalPublishedInstruction.created_at.desc())
    ).all()
    plan_summaries = db.scalars(
        select(m.PortalPublishedPlanSummary)
        .where(
            m.PortalPublishedPlanSummary.clinic_id == portal.clinic_id,
            m.PortalPublishedPlanSummary.patient_id == portal.patient_id,
        )
        .order_by(m.PortalPublishedPlanSummary.created_at.desc())
    ).all()

    total_charges = int(
        db.scalar(
            select(func.coalesce(func.sum(m.Charge.amount_vnd), 0)).where(
                m.Charge.clinic_id == portal.clinic_id,
                m.Charge.patient_id == portal.patient_id,
            )
        )
        or 0
    )
    total_payments = int(
        db.scalar(
            select(func.coalesce(func.sum(m.Payment.amount_vnd), 0)).where(
                m.Payment.clinic_id == portal.clinic_id,
                m.Payment.patient_id == portal.patient_id,
            )
        )
        or 0
    )
    total_refunds = int(
        db.scalar(
            select(func.coalesce(func.sum(m.PaymentRefund.amount_vnd), 0)).where(
                m.PaymentRefund.clinic_id == portal.clinic_id,
                m.PaymentRefund.patient_id == portal.patient_id,
            )
        )
        or 0
    )
    total_allocated = int(
        db.scalar(
            select(func.coalesce(func.sum(m.PaymentAllocation.amount_vnd), 0))
            .join(m.Charge, m.PaymentAllocation.charge_id == m.Charge.id)
            .where(
                m.Charge.clinic_id == portal.clinic_id,
                m.Charge.patient_id == portal.patient_id,
            )
        )
        or 0
    )

    svc.audit(
        db,
        portal.clinic_id,
        f"portal:{portal.actor_kind}:{portal.grant_id[:18]}",
        "portal.overview_viewed",
        "patient",
        portal.patient_id,
    )
    db.commit()
    return {
        "patient": {
            "id": patient.id,
            "display_name": patient.display_name,
            "birth_year": patient.birth_year,
        },
        "actor_kind": portal.actor_kind,
        "actor_display_name": portal.actor_display_name,
        "appointments": appointments_view,
        "published_instructions": [
            {
                "id": i.id,
                "title_vi": i.title_vi,
                "body_vi": i.body_vi,
                "created_at": i.created_at.isoformat() + "Z",
            }
            for i in instructions
        ],
        "published_plan_summaries": [
            {
                "id": p.id,
                "plan_id": p.plan_id,
                "plan_version_number": p.plan_version_number,
                "lay_summary_vi": p.lay_summary_vi,
                "created_at": p.created_at.isoformat() + "Z",
            }
            for p in plan_summaries
        ],
        "financial_summary": {
            "total_charges_vnd": total_charges,
            "total_payments_vnd": total_payments,
            "total_refunds_vnd": total_refunds,
            "total_allocated_vnd": total_allocated,
            "outstanding_balance_vnd": total_charges - total_allocated,
        },
        "synthetic_only": True,
    }


def confirm_portal_appointment(
    db: Session,
    portal: PortalPrincipal,
    appointment_id: str,
) -> m.AppointmentConfirmation:
    appt = svc.ensure(db, m.Appointment, appointment_id, portal.clinic_id)
    if appt.patient_id != portal.patient_id:
        raise HTTPException(403, "Appointment does not belong to portal patient")
    return operations.record_appointment_confirmation(
        db=db,
        clinic_id=portal.clinic_id,
        appointment_id=appointment_id,
        data=AppointmentConfirmationCreate(
            event_type="patient_confirmed",
            channel="in_person",
            evidence_note=f"Confirmed via synthetic patient portal ({portal.actor_kind})",
        ),
        actor=f"portal:{portal.actor_kind}:{portal.grant_id[:18]}",
    )


def create_portal_reschedule_request(
    db: Session,
    portal: PortalPrincipal,
    appointment_id: str,
    data: PortalRescheduleCreate,
) -> m.PortalRescheduleRequest:
    appt = svc.ensure(db, m.Appointment, appointment_id, portal.clinic_id)
    if appt.patient_id != portal.patient_id:
        raise HTTPException(403, "Appointment does not belong to portal patient")
    if appt.status != "confirmed":
        raise HTTPException(409, "Only confirmed appointments can request reschedule")
    req_start = data.requested_start_at.astimezone(timezone.utc).replace(tzinfo=None)
    req_end = data.requested_end_at.astimezone(timezone.utc).replace(tzinfo=None)
    item = m.PortalRescheduleRequest(
        clinic_id=portal.clinic_id,
        patient_id=portal.patient_id,
        appointment_id=appt.id,
        requested_start_at=req_start,
        requested_end_at=req_end,
        reason=data.reason.strip(),
        status="pending_staff_validation",
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        portal.clinic_id,
        f"portal:{portal.actor_kind}:{portal.grant_id[:18]}",
        "portal.reschedule_requested",
        "portal_reschedule_request",
        item.id,
        {"appointment_id": appt.id},
    )
    db.commit()
    return item


def approve_portal_reschedule_request(
    db: Session,
    clinic_id: str,
    request_id: str,
    staff_id: str,
    actor: str,
    data: PortalRescheduleDecisionRequest,
) -> m.PortalRescheduleRequest:
    req = svc.ensure(db, m.PortalRescheduleRequest, request_id, clinic_id)
    if req.status != "pending_staff_validation":
        raise HTTPException(409, f"Reschedule request already resolved ({req.status})")
    new_appt = svc.reschedule_appointment(
        db=db,
        clinic_id=clinic_id,
        appointment_id=req.appointment_id,
        data=AppointmentReschedule(
            start_at=req.requested_start_at.replace(tzinfo=timezone.utc),
            end_at=req.requested_end_at.replace(tzinfo=timezone.utc),
            reason_demo=f"Portal reschedule validated: {req.reason}"[:260],
        ),
        actor=actor,
    )
    req.status = "approved_committed"
    req.resolved_appointment_id = new_appt.id
    req.resolved_by_staff_id = staff_id
    req.resolution_note = data.resolution_note.strip()
    svc.audit(
        db,
        clinic_id,
        actor,
        "portal.reschedule_approved_committed",
        "portal_reschedule_request",
        req.id,
        {"resolved_appointment_id": new_appt.id},
    )
    db.commit()
    return req


def submit_portal_intake_form(
    db: Session,
    portal: PortalPrincipal,
    data: PortalIntakeCreate,
) -> m.PortalIntakeSubmission:
    item = m.PortalIntakeSubmission(
        clinic_id=portal.clinic_id,
        patient_id=portal.patient_id,
        form_code=data.form_code.strip(),
        form_version=data.form_version.strip(),
        payload_json=json.dumps(data.answers, ensure_ascii=False, sort_keys=True),
        provenance="patient_portal_intake",
        legal_consent_granted=False,
        review_status="pending_staff_review",
        submitted_by_actor=f"{portal.actor_kind}:{portal.actor_display_name}"[:160],
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        portal.clinic_id,
        f"portal:{portal.actor_kind}:{portal.grant_id[:18]}",
        "portal.intake_submitted",
        "portal_intake_submission",
        item.id,
        {"form_code": item.form_code, "form_version": item.form_version},
    )
    db.commit()
    return item
