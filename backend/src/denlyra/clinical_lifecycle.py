"""T017 domain services: tri-state medical/allergy risk review (EMR-003, PAT-003, INV-022),
encounter closure & missing-signature checklist gate (EMR-009, EMR-018), and clinician-authored
dental diagnosis & FDI tooth performed procedure evidence (EMR-010, EMR-011, ODN-005).

Synthetic research demonstrator only — NOT a certified EMR or real medical diagnosis system.
"""
from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .schemas import (
    EncounterDiagnosisCreate,
    MedicalRiskReviewCreate,
    PerformedProcedureCreate,
)


def create_medical_risk_review(
    db: Session,
    clinic_id: str,
    patient_id: str,
    staff_id: str,
    actor: str,
    data: MedicalRiskReviewCreate,
) -> m.PatientMedicalRiskReview:
    svc.ensure(db, m.Patient, patient_id, clinic_id)
    if data.encounter_id:
        enc = svc.ensure(db, m.Encounter, data.encounter_id, clinic_id)
        if enc.patient_id != patient_id:
            raise HTTPException(422, "Encounter does not belong to specified patient")

    latest_rev = int(
        db.scalar(
            select(func.coalesce(func.max(m.PatientMedicalRiskReview.revision_number), 0)).where(
                m.PatientMedicalRiskReview.clinic_id == clinic_id,
                m.PatientMedicalRiskReview.patient_id == patient_id,
            )
        )
        or 0
    )
    states = (
        data.drug_allergy_state,
        data.bleeding_anticoagulant_state,
        data.cardiovascular_hypertension_state,
        data.pregnancy_nursing_state,
    )
    high_risk = any(st in {"present", "unknown"} for st in states)

    item = m.PatientMedicalRiskReview(
        clinic_id=clinic_id,
        patient_id=patient_id,
        encounter_id=data.encounter_id,
        revision_number=latest_rev + 1,
        drug_allergy_state=data.drug_allergy_state,
        drug_allergy_detail=data.drug_allergy_detail.strip() if data.drug_allergy_detail else None,
        bleeding_anticoagulant_state=data.bleeding_anticoagulant_state,
        cardiovascular_hypertension_state=data.cardiovascular_hypertension_state,
        pregnancy_nursing_state=data.pregnancy_nursing_state,
        high_risk_banner_active=high_risk,
        source=data.source,
        reviewed_by_staff_id=staff_id,
        actor_demo=actor,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "emr.medical_risk_reviewed",
        "patient_medical_risk_review",
        item.id,
        {
            "patient_id": patient_id,
            "revision_number": item.revision_number,
            "drug_allergy_state": item.drug_allergy_state,
            "high_risk_banner_active": item.high_risk_banner_active,
        },
    )
    db.commit()
    return item


def get_encounter_closure_checklist(
    db: Session, clinic_id: str, encounter_id: str
) -> dict:
    enc = svc.ensure(db, m.Encounter, encounter_id, clinic_id)
    latest_risk = db.scalar(
        select(m.PatientMedicalRiskReview)
        .where(
            m.PatientMedicalRiskReview.clinic_id == clinic_id,
            m.PatientMedicalRiskReview.patient_id == enc.patient_id,
        )
        .order_by(m.PatientMedicalRiskReview.revision_number.desc())
    )
    allergy_ok = bool(
        latest_risk is not None
        and latest_risk.drug_allergy_state != "unanswered"
        and latest_risk.bleeding_anticoagulant_state != "unanswered"
    )

    notes = db.scalars(
        select(m.ClinicalNote).where(
            m.ClinicalNote.clinic_id == clinic_id,
            m.ClinicalNote.encounter_id == enc.id,
        )
    ).all()
    snapshots = db.scalars(
        select(m.ClinicalDocumentSnapshot).where(
            m.ClinicalDocumentSnapshot.clinic_id == clinic_id,
            m.ClinicalDocumentSnapshot.encounter_id == enc.id,
        )
    ).all()

    unlocked_draft_note_ids = [n.id for n in notes if n.status == "draft"]
    locked_or_signed_present = any(n.status == "demo_locked" for n in notes) or any(
        s.status == "synthetic_signed_NOT_legal" for s in snapshots
    )
    unsigned_snapshot_ids = [s.id for s in snapshots if s.status == "ready_for_signature"]

    blocking_reasons: list[str] = []
    if not allergy_ok:
        blocking_reasons.append("medical_allergy_risk_unanswered")
    if not locked_or_signed_present:
        blocking_reasons.append("missing_locked_or_signed_clinical_note")
    if unlocked_draft_note_ids:
        blocking_reasons.append("unlocked_draft_notes_remaining")
    if unsigned_snapshot_ids:
        blocking_reasons.append("unsigned_document_snapshots_pending")

    return {
        "encounter_id": enc.id,
        "status": enc.status,
        "responsible_practitioner_id": enc.practitioner_id,
        "medical_allergy_reviewed": allergy_ok,
        "locked_or_signed_note_present": locked_or_signed_present,
        "unlocked_draft_note_ids": unlocked_draft_note_ids,
        "unsigned_snapshot_ids": unsigned_snapshot_ids,
        "blocking_reasons": blocking_reasons,
        "ready_to_close": len(blocking_reasons) == 0 and enc.status == "in_progress",
        "certified_emr_closure": False,
    }


def notify_missing_signatures(
    db: Session, clinic_id: str, encounter_id: str, actor: str
) -> dict:
    checklist = get_encounter_closure_checklist(db, clinic_id, encounter_id)
    enc = svc.ensure(db, m.Encounter, encounter_id, clinic_id)
    payload = {
        "encounter_id": enc.id,
        "responsible_practitioner_id": enc.practitioner_id,
        "unsigned_snapshot_ids": checklist["unsigned_snapshot_ids"],
        "blocking_reasons": checklist["blocking_reasons"],
    }
    db.add(
        m.OutboxEvent(
            clinic_id=clinic_id,
            event_type="EncounterMissingSignatureAlert",
            aggregate_type="encounter",
            aggregate_id=enc.id,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
    )
    svc.audit(
        db,
        clinic_id,
        actor,
        "emr.missing_signature_checklist_notified",
        "encounter",
        enc.id,
        payload,
    )
    db.commit()
    return {
        **checklist,
        "notified_practitioner_id": enc.practitioner_id,
        "fabricated_signature": False,
    }


def close_encounter_demo(
    db: Session, clinic_id: str, encounter_id: str, actor: str
) -> m.Encounter:
    enc = svc.ensure(db, m.Encounter, encounter_id, clinic_id)
    if enc.status != "in_progress":
        raise HTTPException(409, f"Encounter is already in state '{enc.status}'")
    checklist = get_encounter_closure_checklist(db, clinic_id, encounter_id)
    if checklist["blocking_reasons"]:
        raise HTTPException(
            409,
            f"Encounter cannot be closed until checklist items pass: "
            f"{', '.join(checklist['blocking_reasons'])} (EMR-009 / EMR-018)",
        )
    enc.status = "demo_closed_not_certified"
    svc.audit(
        db,
        clinic_id,
        actor,
        "encounter.closed_demo_not_certified",
        "encounter",
        enc.id,
    )
    db.commit()
    return enc


def record_encounter_diagnosis_demo(
    db: Session,
    clinic_id: str,
    encounter_id: str,
    staff_id: str,
    actor: str,
    data: EncounterDiagnosisCreate,
) -> m.EncounterDiagnosisDemo:
    enc = svc.ensure(db, m.Encounter, encounter_id, clinic_id)
    if enc.status != "in_progress":
        raise HTTPException(
            409, "Cannot record new diagnosis directly on a closed encounter (EMR-009)"
        )
    item = m.EncounterDiagnosisDemo(
        clinic_id=clinic_id,
        encounter_id=enc.id,
        patient_id=enc.patient_id,
        tooth_code=data.tooth_code,
        diagnosis_code_demo=data.diagnosis_code_demo.strip().upper(),
        summary_vi=data.summary_vi.strip(),
        author_staff_id=staff_id,
        status="recorded_demo_not_certified",
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "emr.diagnosis_demo_recorded",
        "encounter_diagnosis_demo",
        item.id,
        {"tooth_code": item.tooth_code, "diagnosis_code_demo": item.diagnosis_code_demo},
    )
    db.commit()
    return item


def record_performed_procedure_evidence(
    db: Session,
    clinic_id: str,
    encounter_id: str,
    staff_id: str,
    actor: str,
    data: PerformedProcedureCreate,
) -> m.PerformedProcedureEvidence:
    enc = svc.ensure(db, m.Encounter, encounter_id, clinic_id)
    if enc.status != "in_progress":
        raise HTTPException(
            409, "Cannot record performed procedure directly on a closed encounter (EMR-009)"
        )
    if data.plan_task_id:
        task = db.get(m.PlanTask, data.plan_task_id)
        if task is None:
            raise HTTPException(404, "Linked plan_task_id not found")
        pv = db.get(m.PlanVersion, task.plan_version_id)
        plan = svc.ensure(db, m.TreatmentPlan, pv.plan_id, clinic_id)
        if plan.patient_id != enc.patient_id:
            raise HTTPException(422, "plan_task_id belongs to a different patient")

    item = m.PerformedProcedureEvidence(
        clinic_id=clinic_id,
        encounter_id=enc.id,
        patient_id=enc.patient_id,
        plan_task_id=data.plan_task_id,
        tooth_code=data.tooth_code,
        surface=data.surface.strip().upper(),
        procedure_code_demo=data.procedure_code_demo.strip().upper(),
        description_vi=data.description_vi.strip(),
        clinical_evidence_note=data.clinical_evidence_note.strip(),
        performed_by_staff_id=staff_id,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "emr.performed_procedure_recorded",
        "performed_procedure_evidence",
        item.id,
        {
            "tooth_code": item.tooth_code,
            "surface": item.surface,
            "procedure_code_demo": item.procedure_code_demo,
            "plan_task_id": item.plan_task_id,
        },
    )
    db.commit()
    return item
