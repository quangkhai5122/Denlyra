"""T019 domain services: clinician-reviewed odontogram legend without silent history
remapping (ODN-006), optimistic tooth restoration/prosthesis revisions & structured
print/export (ODN-007, ODN-008, ODN-010), reviewed external referrals (EMR-013),
non-destructive document eligibility evaluator (PAT-010), and structured clinical
export with attachment digests (EMR-014).
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m, schemas, services as svc
from .schemas import (
    ExternalReferralCreate,
    ExternalReferralReviewRequest,
    OdontogramLegendCreate,
    OdontogramRestorationUpsert,
)

CONSENT_MAX_AGE_DAYS = 365


def _ser(item) -> dict:
    out = {}
    for col in item.__table__.columns:
        val = getattr(item, col.name)
        out[col.name] = val.isoformat() + "Z" if isinstance(val, datetime) else val
    return out


def publish_odontogram_legend_version(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: OdontogramLegendCreate,
) -> m.OdontogramLegendEntry:
    code = data.code.strip().upper()
    existing = db.scalars(
        select(m.OdontogramLegendEntry)
        .where(
            m.OdontogramLegendEntry.clinic_id == clinic_id,
            m.OdontogramLegendEntry.code == code,
        )
        .order_by(m.OdontogramLegendEntry.version_number.desc())
    ).all()
    next_ver = (existing[0].version_number + 1) if existing else 1
    for prev in existing:
        if prev.status == "active":
            prev.status = "superseded"

    entry = m.OdontogramLegendEntry(
        clinic_id=clinic_id,
        code=code,
        version_number=next_ver,
        label_vi=data.label_vi.strip(),
        symbol_code=data.symbol_code.strip().upper(),
        category=data.category,
        clinician_reviewed=True,
        reviewed_by_staff_id=staff_id,
        status="active",
    )
    db.add(entry)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "odontogram.legend_version_published",
        "odontogram_legend_entry",
        entry.id,
        {"code": entry.code, "version_number": entry.version_number},
    )
    db.commit()
    return entry


def upsert_tooth_restoration_optimistic(
    db: Session,
    clinic_id: str,
    patient_id: str,
    tooth_code: str,
    staff_id: str,
    actor: str,
    data: OdontogramRestorationUpsert,
) -> m.OdontogramRestorationState:
    try:
        schemas._check_fdi_code(tooth_code)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    svc.ensure(db, m.Patient, patient_id, clinic_id)
    if data.encounter_id:
        enc = svc.ensure(db, m.Encounter, data.encounter_id, clinic_id)
        if enc.patient_id != patient_id:
            raise HTTPException(422, "Encounter does not belong to specified patient")

    code = data.legend_code.strip().upper()
    active_legend = db.scalar(
        select(m.OdontogramLegendEntry)
        .where(
            m.OdontogramLegendEntry.clinic_id == clinic_id,
            m.OdontogramLegendEntry.code == code,
            m.OdontogramLegendEntry.status == "active",
        )
        .order_by(m.OdontogramLegendEntry.version_number.desc())
    )
    if active_legend is None:
        raise HTTPException(
            404,
            f"Active clinician-reviewed odontogram legend '{code}' not found in clinic (ODN-006)",
        )

    state = db.scalar(
        select(m.OdontogramRestorationState).where(
            m.OdontogramRestorationState.clinic_id == clinic_id,
            m.OdontogramRestorationState.patient_id == patient_id,
            m.OdontogramRestorationState.tooth_code == tooth_code,
        )
    )
    if state is None:
        if data.expected_revision != 0:
            raise HTTPException(
                409,
                f"Optimistic concurrency conflict on tooth {tooth_code}: expected_revision={data.expected_revision} but current=0 (ODN-010)",
            )
        next_rev = 1
        state = m.OdontogramRestorationState(
            clinic_id=clinic_id,
            patient_id=patient_id,
            tooth_code=tooth_code,
            current_revision_no=next_rev,
            latest_legend_code=active_legend.code,
            latest_legend_version_number=active_legend.version_number,
            latest_surface=data.surface.strip().upper(),
            latest_material_note=data.material_note.strip(),
            latest_source_kind=data.source_kind,
            latest_documented_date=data.documented_date,
            updated_at=m.utcnow(),
        )
        db.add(state)
        db.flush()
    else:
        if data.expected_revision != state.current_revision_no:
            raise HTTPException(
                409,
                f"Optimistic concurrency conflict on tooth {tooth_code}: "
                f"expected_revision={data.expected_revision} != current={state.current_revision_no} (ODN-010)",
            )
        next_rev = state.current_revision_no + 1
        state.current_revision_no = next_rev
        state.latest_legend_code = active_legend.code
        state.latest_legend_version_number = active_legend.version_number
        state.latest_surface = data.surface.strip().upper()
        state.latest_material_note = data.material_note.strip()
        state.latest_source_kind = data.source_kind
        state.latest_documented_date = data.documented_date
        state.updated_at = m.utcnow()
        db.flush()

    rev = m.OdontogramRestorationRevision(
        clinic_id=clinic_id,
        state_id=state.id,
        patient_id=patient_id,
        tooth_code=tooth_code,
        revision_no=next_rev,
        legend_code=active_legend.code,
        legend_version_number=active_legend.version_number,
        surface=state.latest_surface,
        material_note=state.latest_material_note,
        source_kind=data.source_kind,
        documented_date=data.documented_date,
        evidence_note=data.evidence_note.strip(),
        encounter_id=data.encounter_id,
        author_staff_id=staff_id,
    )
    db.add(rev)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "odontogram.restoration_revision_recorded",
        "odontogram_restoration_state",
        state.id,
        {
            "tooth_code": tooth_code,
            "revision_no": next_rev,
            "legend_code": active_legend.code,
            "legend_version_number": active_legend.version_number,
        },
    )
    db.commit()
    return state


def export_patient_odontogram(
    db: Session, clinic_id: str, patient_id: str, actor: str
) -> dict:
    patient = svc.ensure(db, m.Patient, patient_id, clinic_id)
    findings = db.scalars(
        select(m.DentalFinding)
        .join(m.Encounter, m.DentalFinding.encounter_id == m.Encounter.id)
        .where(
            m.Encounter.clinic_id == clinic_id,
            m.Encounter.patient_id == patient_id,
        )
        .order_by(m.DentalFinding.created_at.asc())
    ).all()
    procs = db.scalars(
        select(m.PerformedProcedureEvidence)
        .where(
            m.PerformedProcedureEvidence.clinic_id == clinic_id,
            m.PerformedProcedureEvidence.patient_id == patient_id,
        )
        .order_by(m.PerformedProcedureEvidence.created_at.asc())
    ).all()
    states = db.scalars(
        select(m.OdontogramRestorationState)
        .where(
            m.OdontogramRestorationState.clinic_id == clinic_id,
            m.OdontogramRestorationState.patient_id == patient_id,
        )
        .order_by(m.OdontogramRestorationState.tooth_code.asc())
    ).all()
    legend_lookup = {
        (lg.code, lg.version_number): lg
        for lg in db.scalars(
            select(m.OdontogramLegendEntry).where(
                m.OdontogramLegendEntry.clinic_id == clinic_id
            )
        ).all()
    }

    restorations_out = []
    for st in states:
        revs = db.scalars(
            select(m.OdontogramRestorationRevision)
            .where(m.OdontogramRestorationRevision.state_id == st.id)
            .order_by(m.OdontogramRestorationRevision.revision_no.asc())
        ).all()
        restorations_out.append(
            {
                **_ser(st),
                "revisions": [
                    {
                        **_ser(rv),
                        "legend_label_vi": (
                            legend_lookup[(rv.legend_code, rv.legend_version_number)].label_vi
                            if (rv.legend_code, rv.legend_version_number) in legend_lookup
                            else rv.legend_code
                        ),
                    }
                    for rv in revs
                ],
            }
        )

    canonical_body = {
        "clinic_id": clinic_id,
        "patient_id": patient.id,
        "template_code": "ODN-FDI-PRINT-SYNTHETIC-V1",
        "findings": [_ser(f) for f in findings],
        "performed_procedures": [_ser(p) for p in procs],
        "restorations": restorations_out,
    }
    digest = hashlib.sha256(
        json.dumps(canonical_body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    svc.audit(
        db,
        clinic_id,
        actor,
        "odontogram.structured_export_generated",
        "patient",
        patient.id,
        {"export_sha256": digest},
    )
    db.commit()
    return {
        **canonical_body,
        "export_sha256": digest,
        "certified_clinical_print": False,
        "synthetic_only": True,
    }


def create_external_referral(
    db: Session,
    clinic_id: str,
    patient_id: str,
    actor: str,
    data: ExternalReferralCreate,
) -> m.ExternalReferralDocument:
    svc.ensure(db, m.Patient, patient_id, clinic_id)
    if data.encounter_id:
        enc = svc.ensure(db, m.Encounter, data.encounter_id, clinic_id)
        if enc.patient_id != patient_id:
            raise HTTPException(422, "Encounter does not belong to specified patient")
    if data.archive_object_id:
        obj = svc.ensure(db, m.ArchiveObject, data.archive_object_id, clinic_id)
        if obj.patient_id != patient_id:
            raise HTTPException(422, "ArchiveObject does not belong to specified patient")

    item = m.ExternalReferralDocument(
        clinic_id=clinic_id,
        patient_id=patient_id,
        encounter_id=data.encounter_id,
        origin_facility_name=data.origin_facility_name.strip(),
        referring_clinician_name=data.referring_clinician_name.strip(),
        referral_date=data.referral_date,
        document_summary_vi=data.document_summary_vi.strip(),
        content_sha256=data.content_sha256.lower(),
        archive_object_id=data.archive_object_id,
        review_status="quarantined_unreviewed",
        actor_demo=actor,
    )
    db.add(item)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "emr.external_referral_ingested",
        "external_referral_document",
        item.id,
        {"patient_id": patient_id, "origin_facility_name": item.origin_facility_name},
    )
    db.commit()
    return item


def review_external_referral(
    db: Session,
    clinic_id: str,
    referral_id: str,
    staff_id: str,
    actor: str,
    data: ExternalReferralReviewRequest,
) -> m.ExternalReferralDocument:
    ref = svc.ensure(db, m.ExternalReferralDocument, referral_id, clinic_id)
    ref.review_status = "clinician_reviewed"
    ref.reviewed_by_staff_id = staff_id
    ref.review_note = data.review_note.strip()
    ref.reviewed_at = m.utcnow()
    svc.audit(
        db,
        clinic_id,
        actor,
        "emr.external_referral_clinician_reviewed",
        "external_referral_document",
        ref.id,
        {"reviewed_by_staff_id": staff_id},
    )
    db.commit()
    return ref


def evaluate_patient_document_eligibility(
    db: Session, clinic_id: str, patient_id: str
) -> dict:
    svc.ensure(db, m.Patient, patient_id, clinic_id)
    now = m.utcnow()
    cutoff = now - timedelta(days=CONSENT_MAX_AGE_DAYS)

    consents = db.scalars(
        select(m.ConsentRecord).where(
            m.ConsentRecord.clinic_id == clinic_id,
            m.ConsentRecord.patient_id == patient_id,
        )
    ).all()
    active_treatment_consents = [
        c for c in consents if c.purpose == "treatment" and c.status == "granted"
    ]
    fresh_treatment_consent = any(c.created_at >= cutoff for c in active_treatment_consents)

    latest_risk = db.scalar(
        select(m.PatientMedicalRiskReview)
        .where(
            m.PatientMedicalRiskReview.clinic_id == clinic_id,
            m.PatientMedicalRiskReview.patient_id == patient_id,
        )
        .order_by(m.PatientMedicalRiskReview.revision_number.desc())
    )
    risk_complete = bool(
        latest_risk is not None
        and latest_risk.drug_allergy_state != "unanswered"
        and latest_risk.bleeding_anticoagulant_state != "unanswered"
        and latest_risk.created_at >= cutoff
    )

    flags: list[str] = []
    if not active_treatment_consents:
        flags.append("missing_active_treatment_consent")
    elif not fresh_treatment_consent:
        flags.append("outdated_treatment_consent")
    if not risk_complete:
        flags.append("missing_or_unanswered_medical_risk_review")

    return {
        "patient_id": patient_id,
        "evaluated_at": now.isoformat() + "Z",
        "eligible_for_elective_procedure": len(flags) == 0,
        "flags": flags,
        "signed_documents_mutated": False,
    }


def export_structured_clinical_document(
    db: Session, clinic_id: str, snapshot_id: str, actor: str
) -> dict:
    snap = svc.ensure(db, m.ClinicalDocumentSnapshot, snapshot_id, clinic_id)
    if snap.status == "ready_for_signature":
        raise HTTPException(
            409,
            "Cannot export unsigned 'ready_for_signature' snapshot as finalized clinical package (EMR-014)",
        )
    enc = svc.ensure(db, m.Encounter, snap.encounter_id, clinic_id)
    attachments = db.scalars(
        select(m.ArchiveObject)
        .where(
            m.ArchiveObject.clinic_id == clinic_id,
            m.ArchiveObject.encounter_id == enc.id,
        )
        .order_by(m.ArchiveObject.created_at.asc())
    ).all()

    canonical_obj = json.loads(snap.canonical_json)
    attachment_manifest = [
        {
            "id": a.id,
            "snapshot_id": a.snapshot_id,
            "object_kind": a.object_kind,
            "media_type": a.media_type,
            "original_filename": a.original_filename,
            "byte_size": a.byte_size,
            "plaintext_sha256": a.plaintext_sha256,
            "ciphertext_sha256": a.ciphertext_sha256,
            "key_version": a.key_version,
        }
        for a in attachments
    ]
    pdf_stub_text = (
        f"[SYNTHETIC ARCHIVE EXPORT — NOT CERTIFIED EMR]\n"
        f"Snapshot: {snap.id} | Status: {snap.status}\n"
        f"Canonical SHA-256: {snap.canonical_sha256}\n"
        f"Note: {snap.note_id} v{snap.note_revision_no} | Attachments: {len(attachment_manifest)}"
    )
    package = {
        "snapshot": {
            "id": snap.id,
            "encounter_id": snap.encounter_id,
            "note_id": snap.note_id,
            "note_revision_no": snap.note_revision_no,
            "status": snap.status,
            "canonical_sha256": snap.canonical_sha256,
            "manifest_sha256": snap.manifest_sha256,
            "created_at": snap.created_at.isoformat() + "Z",
        },
        "canonical_payload": canonical_obj,
        "attachment_manifest": attachment_manifest,
        "pdf_layout_stub_text": pdf_stub_text,
        "legally_certified_pdf": False,
        "synthetic_only": True,
    }
    svc.audit(
        db,
        clinic_id,
        actor,
        "clinical_doc.structured_archive_exported",
        "clinical_document_snapshot",
        snap.id,
        {"attachments_count": len(attachment_manifest)},
    )
    db.commit()
    return package
