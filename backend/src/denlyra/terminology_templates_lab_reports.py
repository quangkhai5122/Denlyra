"""T025 domain services: versioned medical code sets & exact mappings without guessing
(EMR-016), clinic-reviewed specialty plan templates (TRT-015), PHI-free lab vendor
price list & invoice reconciliation (LAB-010), labeled non-diagnostic longitudinal
imaging overlays (ODN-009), and scope-checked DLY1-encrypted PHI-free scheduled
report exports (RPT-009, RPT-010).
"""
from __future__ import annotations

import base64
import hashlib
import json
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import archive_dr, governance_analytics, models as m, org_crm_ops_assistant, services as svc
from .schemas import (
    InstantiateSpecialtyTemplateRequest,
    LabInvoiceReconcileCreate,
    LabVendorPriceCreate,
    LongitudinalOverlayCreate,
    ScheduledReportExportCreate,
    SpecialtyPlanTemplateCreate,
    TerminologyCodeCreate,
    TerminologyMappingCreate,
)

PHONE_RE = re.compile(r"(?:\+?84|0)\d{8,10}\b")
ALLOWLISTED_REPORT_DOMAINS = ("@denlyra-clinic.local", "@owner-verified.local")


def publish_terminology_code(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: TerminologyCodeCreate,
) -> m.TerminologyCodeEntry:
    code_norm = data.code.strip().upper()
    ver_norm = data.system_version.strip()
    existing = db.scalar(
        select(m.TerminologyCodeEntry).where(
            m.TerminologyCodeEntry.clinic_id == clinic_id,
            m.TerminologyCodeEntry.code_system == data.code_system,
            m.TerminologyCodeEntry.system_version == ver_norm,
            m.TerminologyCodeEntry.code == code_norm,
        )
    )
    if existing is not None:
        return existing

    row = m.TerminologyCodeEntry(
        clinic_id=clinic_id,
        code_system=data.code_system,
        system_version=ver_norm,
        code=code_norm,
        display_vi=data.display_vi.strip(),
        approved_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "terminology.code_published",
        "terminology_code_entry",
        row.id,
        {"code_system": row.code_system, "version": row.system_version, "code": row.code},
    )
    db.commit()
    return row


def publish_terminology_mapping(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: TerminologyMappingCreate,
) -> m.TerminologyMappingRule:
    src = data.source_code.strip().upper()
    tgt_code = data.target_code.strip().upper()
    tgt_ver = data.target_system_version.strip()

    target_entry = db.scalar(
        select(m.TerminologyCodeEntry).where(
            m.TerminologyCodeEntry.clinic_id == clinic_id,
            m.TerminologyCodeEntry.code_system == data.target_code_system,
            m.TerminologyCodeEntry.system_version == tgt_ver,
            m.TerminologyCodeEntry.code == tgt_code,
        )
    )
    if target_entry is None:
        raise HTTPException(
            404,
            f"Target terminology code {data.target_code_system}:{tgt_ver}:{tgt_code} not registered in clinic (EMR-016)",
        )

    row = m.TerminologyMappingRule(
        clinic_id=clinic_id,
        source_code=src,
        target_code_system=data.target_code_system,
        target_system_version=tgt_ver,
        target_code=tgt_code,
        equivalence=data.equivalence,
        mapping_method="clinician_verified_exact",
        reviewed_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "terminology.mapping_published",
        "terminology_mapping_rule",
        row.id,
        {"source_code": src, "target_code": tgt_code},
    )
    db.commit()
    return row


def resolve_terminology_mapping(
    db: Session,
    clinic_id: str,
    source_code: str,
    target_code_system: str,
) -> dict:
    src = source_code.strip().upper()
    sys_norm = target_code_system.strip()
    rule = db.scalar(
        select(m.TerminologyMappingRule).where(
            m.TerminologyMappingRule.clinic_id == clinic_id,
            m.TerminologyMappingRule.source_code == src,
            m.TerminologyMappingRule.target_code_system == sys_norm,
        )
    )
    if rule is None:
        return {
            "source_code": src,
            "target_code_system": sys_norm,
            "mapped": False,
            "target_code": None,
            "target_system_version": None,
            "guessed_fallback_used": False,
        }
    return {
        "source_code": src,
        "target_code_system": rule.target_code_system,
        "mapped": True,
        "target_code": rule.target_code,
        "target_system_version": rule.target_system_version,
        "equivalence": rule.equivalence,
        "mapping_method": rule.mapping_method,
        "guessed_fallback_used": False,
    }


def create_specialty_plan_template(
    db: Session,
    clinic_id: str,
    actor: str,
    data: SpecialtyPlanTemplateCreate,
) -> m.SpecialtyPlanTemplate:
    code = data.template_code.strip().upper()
    max_ver = int(
        db.scalar(
            select(func.coalesce(func.max(m.SpecialtyPlanTemplate.version_number), 0)).where(
                m.SpecialtyPlanTemplate.clinic_id == clinic_id,
                m.SpecialtyPlanTemplate.template_code == code,
            )
        )
        or 0
    )
    blueprint = [b.model_dump() for b in data.tasks_blueprint]
    row = m.SpecialtyPlanTemplate(
        clinic_id=clinic_id,
        template_code=code,
        version_number=max_ver + 1,
        specialty=data.specialty,
        title_vi=data.title_vi.strip(),
        tasks_blueprint_json=json.dumps(blueprint, ensure_ascii=False),
        source_kind="clinic_clinician_authored",
        review_status="draft_unreviewed",
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "treatment.specialty_template_created",
        "specialty_plan_template",
        row.id,
        {"template_code": code, "version_number": row.version_number},
    )
    db.commit()
    return row


def review_specialty_plan_template(
    db: Session,
    clinic_id: str,
    template_id: str,
    staff_id: str,
    actor: str,
) -> m.SpecialtyPlanTemplate:
    tpl = svc.ensure(db, m.SpecialtyPlanTemplate, template_id, clinic_id)
    tpl.review_status = "clinic_reviewed_active"
    tpl.reviewed_by_staff_id = staff_id
    tpl.reviewed_at = m.utcnow()
    svc.audit(
        db,
        clinic_id,
        actor,
        "treatment.specialty_template_reviewed",
        "specialty_plan_template",
        tpl.id,
        {"reviewed_by_staff_id": staff_id},
    )
    db.commit()
    return tpl


def instantiate_plan_from_specialty_template(
    db: Session,
    clinic_id: str,
    actor: str,
    data: InstantiateSpecialtyTemplateRequest,
) -> dict:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    tpl = svc.ensure(db, m.SpecialtyPlanTemplate, data.template_id, clinic_id)
    if tpl.review_status != "clinic_reviewed_active":
        raise HTTPException(
            409,
            "Specialty template must be reviewed by a clinic dentist/medical director before instantiating patient plans (TRT-015)",
        )

    plan = m.TreatmentPlan(
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        title=tpl.title_vi,
        current_version=1,
    )
    db.add(plan)
    db.flush()
    pv = m.PlanVersion(
        plan_id=plan.id,
        number=1,
        status="draft",
    )
    db.add(pv)
    db.flush()

    blueprint = json.loads(tpl.tasks_blueprint_json)
    prev_task_id: str | None = None
    created_ids: list[str] = []
    for item in blueprint:
        task = m.PlanTask(
            plan_version_id=pv.id,
            title=item["title"],
            phase=item["phase"],
            owner_role="dentist",
            depends_on_task_id=prev_task_id,
            status="pending",
        )
        db.add(task)
        db.flush()
        if prev_task_id is not None:
            db.add(
                m.PlanTaskDependency(
                    plan_version_id=pv.id,
                    task_id=task.id,
                    depends_on_task_id=prev_task_id,
                )
            )
        prev_task_id = task.id
        created_ids.append(task.id)

    svc.audit(
        db,
        clinic_id,
        actor,
        "treatment.plan_instantiated_from_specialty_template",
        "treatment_plan",
        plan.id,
        {"template_id": tpl.id, "task_count": len(created_ids)},
    )
    db.commit()
    return {
        "plan_id": plan.id,
        "template_id": tpl.id,
        "template_version_number": tpl.version_number,
        "version_status": pv.status,
        "created_task_count": len(created_ids),
        "task_ids": created_ids,
    }


def publish_lab_vendor_price_item(
    db: Session,
    clinic_id: str,
    actor: str,
    data: LabVendorPriceCreate,
) -> m.LabVendorPriceItem:
    vendor = data.vendor_code.strip().upper()
    pcode = data.prosthesis_code.strip().upper()
    max_ver = int(
        db.scalar(
            select(func.coalesce(func.max(m.LabVendorPriceItem.version_number), 0)).where(
                m.LabVendorPriceItem.clinic_id == clinic_id,
                m.LabVendorPriceItem.vendor_code == vendor,
                m.LabVendorPriceItem.prosthesis_code == pcode,
            )
        )
        or 0
    )
    row = m.LabVendorPriceItem(
        clinic_id=clinic_id,
        vendor_code=vendor,
        prosthesis_code=pcode,
        version_number=max_ver + 1,
        unit_price_vnd=data.unit_price_vnd,
        remake_surcharge_vnd=data.remake_surcharge_vnd,
        actor_demo=actor,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "lab.vendor_price_published",
        "lab_vendor_price_item",
        row.id,
        {"vendor_code": vendor, "prosthesis_code": pcode, "version": row.version_number},
    )
    db.commit()
    return row


def reconcile_lab_vendor_invoice(
    db: Session,
    clinic_id: str,
    lab_case_id: str,
    actor: str,
    data: LabInvoiceReconcileCreate,
) -> m.LabInvoiceReconciliation:
    lc = svc.ensure(db, m.LabCase, lab_case_id, clinic_id)
    pat = svc.ensure(db, m.Patient, lc.patient_id, clinic_id)

    ref = data.vendor_invoice_ref.strip()
    if (
        (pat.display_name and pat.display_name.lower() in ref.lower())
        or pat.id in ref
        or PHONE_RE.search(ref)
    ):
        raise HTTPException(
            422,
            "Lab vendor invoice reference must not contain patient name, ID, or phone PII (LAB-010)",
        )

    vendor = data.vendor_code.strip().upper()
    pcode = data.prosthesis_code.strip().upper()
    price_item = db.scalars(
        select(m.LabVendorPriceItem)
        .where(
            m.LabVendorPriceItem.clinic_id == clinic_id,
            m.LabVendorPriceItem.vendor_code == vendor,
            m.LabVendorPriceItem.prosthesis_code == pcode,
        )
        .order_by(m.LabVendorPriceItem.version_number.desc())
    ).first()
    if price_item is None:
        raise HTTPException(
            404,
            f"Contracted lab price not found for vendor={vendor}, prosthesis={pcode} (LAB-010)",
        )

    contracted = price_item.unit_price_vnd + (
        price_item.remake_surcharge_vnd if lc.revision_number > 1 else 0
    )
    variance = data.billed_amount_vnd - contracted
    rec_status = "matched" if variance == 0 else "discrepancy_flagged"
    sanitized_payload = {
        "lab_case_id": lc.id,
        "case_revision_number": lc.revision_number,
        "vendor_code": vendor,
        "prosthesis_code": pcode,
        "price_version_number": price_item.version_number,
        "contracted_amount_vnd": contracted,
        "billed_amount_vnd": data.billed_amount_vnd,
        "variance_vnd": variance,
        "contains_phi": False,
    }
    row = m.LabInvoiceReconciliation(
        clinic_id=clinic_id,
        lab_case_id=lc.id,
        vendor_code=vendor,
        prosthesis_code=pcode,
        vendor_invoice_ref=ref,
        price_version_number=price_item.version_number,
        contracted_amount_vnd=contracted,
        billed_amount_vnd=data.billed_amount_vnd,
        variance_vnd=variance,
        reconciliation_status=rec_status,
        sanitized_vendor_payload_json=json.dumps(sanitized_payload, sort_keys=True),
        contains_phi=False,
        actor_demo=actor,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "lab.invoice_reconciled_phi_free",
        "lab_invoice_reconciliation",
        row.id,
        {"reconciliation_status": rec_status, "variance_vnd": variance},
    )
    db.commit()
    return row


def create_longitudinal_imaging_overlay(
    db: Session,
    clinic_id: str,
    patient_id: str,
    staff_id: str,
    actor: str,
    data: LongitudinalOverlayCreate,
) -> m.LongitudinalImagingOverlay:
    if data.claim_auto_diagnosis:
        raise HTTPException(
            409,
            "Automated clinical diagnosis is prohibited on longitudinal imaging overlays (ODN-009)",
        )
    svc.ensure(db, m.Patient, patient_id, clinic_id)
    base_obj = svc.ensure(db, m.ArchiveObject, data.baseline_archive_object_id, clinic_id)
    foll_obj = svc.ensure(db, m.ArchiveObject, data.followup_archive_object_id, clinic_id)
    if base_obj.patient_id != patient_id or foll_obj.patient_id != patient_id:
        raise HTTPException(
            422,
            "Both baseline and follow-up ArchiveObjects must belong to the specified patient (ODN-009)",
        )

    row = m.LongitudinalImagingOverlay(
        clinic_id=clinic_id,
        patient_id=patient_id,
        tooth_code=data.tooth_code,
        baseline_archive_object_id=base_obj.id,
        followup_archive_object_id=foll_obj.id,
        alignment_label_vi=data.alignment_label_vi.strip(),
        visualization_provenance_label="SYNTHETIC_VISUAL_COMPARISON_NOT_DIAGNOSTIC",
        auto_diagnosis_generated=False,
        created_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "odontogram.longitudinal_overlay_created",
        "longitudinal_imaging_overlay",
        row.id,
        {"tooth_code": row.tooth_code, "auto_diagnosis_generated": False},
    )
    db.commit()
    return row


def create_encrypted_scheduled_report_export(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    auth_secret: str,
    data: ScheduledReportExportCreate,
) -> m.ScheduledReportExport:
    if data.include_phi:
        raise HTTPException(
            409,
            "Scheduled report exports exclude PHI by default; raw patient data export prohibited (RPT-010)",
        )
    email = data.recipient_email.strip().lower()
    if not any(email.endswith(dom) for dom in ALLOWLISTED_REPORT_DOMAINS):
        raise HTTPException(
            403,
            "Recipient email domain is not in clinic-approved report allowlist (RPT-010)",
        )

    if data.report_kind == "multi_branch_aggregate":
        if not data.owner_group_key:
            raise HTTPException(422, "owner_group_key required for multi_branch_aggregate")
        report_payload = org_crm_ops_assistant.get_multi_branch_aggregates(
            db, clinic_id, actor, data.owner_group_key
        )
    else:
        kpi = governance_analytics.compute_kpi_lineage(db, clinic_id)
        report_payload = {
            "clinic_id": clinic_id,
            "metrics": [
                {"metric_code": item["metric_code"], "values": item["values"]}
                for item in kpi["metrics"]
            ],
            "contains_patient_charts_or_pii": False,
        }

    plain_bytes = json.dumps(
        report_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    plain_sha = hashlib.sha256(plain_bytes).hexdigest()

    key_row = archive_dr.ensure_active_tenant_key(db, clinic_id, auth_secret, actor)
    kek_enc, kek_mac = archive_dr.derive_kek(auth_secret, clinic_id, key_row.key_version)
    aad_wrap = f"wrap-dek:{clinic_id}:v{key_row.key_version}".encode("utf-8")
    raw_dek = archive_dr.decrypt_envelope(
        kek_enc, kek_mac, base64.b64decode(key_row.wrapped_dek_b64), aad_wrap
    )
    dek_enc, dek_mac = archive_dr.derive_dek_subkeys(
        raw_dek, clinic_id, key_row.key_version
    )
    aad_rpt = f"report-export:{clinic_id}:v{key_row.key_version}".encode("utf-8")
    cipher_bytes = archive_dr.encrypt_envelope(dek_enc, dek_mac, plain_bytes, aad_rpt)
    cipher_sha = hashlib.sha256(cipher_bytes).hexdigest()

    row = m.ScheduledReportExport(
        clinic_id=clinic_id,
        owner_group_key=data.owner_group_key,
        report_kind=data.report_kind,
        recipient_email=email,
        include_phi=False,
        key_id=key_row.id,
        key_version=key_row.key_version,
        encrypted_envelope_b64=base64.b64encode(cipher_bytes).decode("ascii"),
        plaintext_sha256=plain_sha,
        ciphertext_sha256=cipher_sha,
        exported_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "reports.scheduled_encrypted_export_created",
        "scheduled_report_export",
        row.id,
        {"report_kind": row.report_kind, "key_version": row.key_version},
    )
    db.commit()
    return row
