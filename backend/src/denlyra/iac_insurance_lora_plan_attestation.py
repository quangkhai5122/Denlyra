"""T029 domain services: Vietnam-region IaC blueprint & secret externalization guard (OPS-003),
partner-scoped private dental insurance claim sandbox blocking BHYT & auto-settlement (FIN-012),
licensed de-identified LoRA measurable baseline-lift gate (AI-012), and canonical simulation-only
clinician treatment plan version attestation (TRT-004).
"""
from __future__ import annotations

import hashlib
import json
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .schemas import (
    AiAdaptationEvaluateRequest,
    IacBlueprintValidateRequest,
    InsuranceClaimDraftCreate,
    InsurancePartnerCreate,
    PlanReviewAttestationCreate,
)

ALLOWED_VN_REGIONS = {"vn-ho-chi-minh-1", "vn-ha-noi-1"}
INLINE_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|secret|api_key|private_key)\s*[:=]"),
    re.compile(r"postgresql(\+psycopg)?://[^/\s]+:[^@\s]+@"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
UNLICENSED_DATASET_TOKENS = {"unlicensed", "scraped_web", "unknown", "none", "proprietary_patient_raw"}
VN_PII_PATTERNS = (
    re.compile(r"\b0[35789]\d{8}\b"),
    re.compile(r"\b\d{12}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
)


def validate_iac_blueprint(
    db: Session,
    clinic_id: str,
    actor: str,
    data: IacBlueprintValidateRequest,
) -> m.IacBlueprintValidation:
    if data.apply_live_cloud_provisioning:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ops.iac_blocked_live_provisioning",
            "clinic",
            clinic_id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Live cloud provisioning is strictly forbidden from the synthetic demonstrator (OPS-003 / AGENTS.md)",
        )
    region = data.primary_region.strip().lower()
    if region not in ALLOWED_VN_REGIONS:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ops.iac_blocked_unverified_region",
            "clinic",
            clinic_id,
            {"primary_region": region},
        )
        db.commit()
        raise HTTPException(
            409,
            f"Primary region '{region}' is outside verified Vietnam hosting regions {sorted(ALLOWED_VN_REGIONS)} (OPS-003)",
        )
    dpa = data.dpa_contract_reference.strip()
    if not (dpa.startswith("DPA-SYN-") or dpa.startswith("DPA-DEMO-")):
        raise HTTPException(
            422,
            "dpa_contract_reference must carry explicit synthetic prefix DPA-SYN- or DPA-DEMO- (OPS-003)",
        )

    for k, v in data.environment_variables.items():
        val = v.strip()
        for pat in INLINE_SECRET_PATTERNS:
            if pat.search(f"{k}={val}") or pat.search(val):
                raise HTTPException(
                    422,
                    f"Inline secret detected in '{k}'; externalize credentials via secret_ref:// (OPS-003)",
                )
        if not val.startswith("secret_ref://"):
            raise HTTPException(
                422,
                f"Environment variable '{k}' must reference external secret vault via secret_ref:// (OPS-003)",
            )

    canonical = json.dumps(
        {
            "clinic_id": clinic_id,
            "blueprint_name": data.blueprint_name.strip(),
            "primary_region": region,
            "dpa_contract_reference": dpa,
            "env_keys": sorted(data.environment_variables.keys()),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    sha = hashlib.sha256(canonical).hexdigest()

    row = m.IacBlueprintValidation(
        clinic_id=clinic_id,
        blueprint_name=data.blueprint_name.strip(),
        primary_region=region,
        dpa_contract_reference=dpa,
        secrets_externalized=True,
        live_cloud_provisioned=False,
        blueprint_sha256=sha,
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ops.iac_blueprint_validated_offline",
        "iac_blueprint_validation",
        row.id,
        {"primary_region": region, "blueprint_sha256": sha},
    )
    db.commit()
    return row


def register_insurance_partner(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: InsurancePartnerCreate,
) -> m.InsurancePartnerContract:
    if data.integration_kind == "government_bhyt_portal":
        svc.audit(
            db,
            clinic_id,
            actor,
            "finance.insurance_blocked_government_bhyt",
            "clinic",
            clinic_id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Government BHYT health insurance integration is blocked without verified legal authorization (FIN-012 / INT-010)",
        )
    row = m.InsurancePartnerContract(
        clinic_id=clinic_id,
        partner_code=data.partner_code.strip().upper(),
        partner_name=data.partner_name.strip(),
        integration_kind="private_dental_tpa_sandbox",
        contract_active=data.contract_active,
        created_by_staff_id=staff_id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Insurance partner_code already registered in clinic") from exc
    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.insurance_partner_registered_sandbox",
        "insurance_partner_contract",
        row.id,
        {"partner_code": row.partner_code},
    )
    db.commit()
    return row


def create_insurance_claim_draft(
    db: Session,
    clinic_id: str,
    actor: str,
    data: InsuranceClaimDraftCreate,
) -> m.InsuranceClaimDraft:
    if data.auto_settle_as_paid:
        raise HTTPException(
            409,
            "Insurance claim drafts must never auto-settle as collected payments (FIN-012)",
        )
    pat = svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    partner = svc.ensure(db, m.InsurancePartnerContract, data.partner_id, clinic_id)
    if not partner.contract_active:
        raise HTTPException(409, "Insurance partner contract is inactive (FIN-012)")
    chg = svc.ensure(db, m.Charge, data.charge_id, clinic_id)
    if chg.patient_id != pat.id:
        raise HTTPException(422, "Charge does not belong to target patient")
    if data.claimed_amount_vnd > chg.amount_vnd:
        raise HTTPException(409, "Claimed VND exceeds posted charge amount (FIN-012)")

    for req_purpose in ("financial", "data_processing"):
        has_c = db.scalar(
            select(m.ConsentRecord).where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == pat.id,
                m.ConsentRecord.purpose == req_purpose,
                m.ConsentRecord.status == "granted",
            )
        )
        if has_c is None:
            raise HTTPException(
                403,
                f"Active '{req_purpose}' consent is required before submitting third-party insurance claim draft (FIN-012)",
            )

    row = m.InsuranceClaimDraft(
        clinic_id=clinic_id,
        patient_id=pat.id,
        partner_id=partner.id,
        charge_id=chg.id,
        claimed_amount_vnd=data.claimed_amount_vnd,
        claim_status="draft_submitted_sandbox_not_settled",
        auto_settled_payment=False,
        called_government_bhyt_api=False,
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.insurance_claim_draft_created",
        "insurance_claim_draft",
        row.id,
        {"claimed_amount_vnd": row.claimed_amount_vnd, "partner_code": partner.partner_code},
    )
    db.commit()
    return row


def evaluate_ai_adaptation_run(
    db: Session,
    clinic_id: str,
    actor: str,
    ai_enabled: bool,
    data: AiAdaptationEvaluateRequest,
) -> m.AiAdaptationRun:
    if not ai_enabled:
        raise HTTPException(503, "AI evaluation/adaptation disabled by clinic switch (AI-014)")
    lic = data.dataset_license_id.strip()
    if not data.deidentification_verified or lic.lower() in UNLICENSED_DATASET_TOKENS:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ai.adaptation_blocked_unlicensed_or_undeidentified",
            "clinic",
            clinic_id,
            {"dataset_license_id": lic},
        )
        db.commit()
        raise HTTPException(
            403,
            "LoRA/QLoRA adaptation requires a licensed, verified de-identified corpus (AI-012)",
        )

    for sample in data.dataset_sample_texts:
        for pii_pat in VN_PII_PATTERNS:
            if pii_pat.search(sample):
                raise HTTPException(
                    422,
                    "PII pattern detected in adaptation dataset sample; training/evaluation refused (AI-012)",
                )

    lift_bp = data.candidate_f1_bp - data.baseline_f1_bp
    if lift_bp < data.min_required_lift_bp:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ai.adaptation_blocked_insufficient_lift",
            "clinic",
            clinic_id,
            {"lift_bp": lift_bp, "required_bp": data.min_required_lift_bp},
        )
        db.commit()
        raise HTTPException(
            409,
            f"Candidate adapter lift ({lift_bp} bp) is below minimum threshold ({data.min_required_lift_bp} bp) over baseline (AI-012)",
        )

    row = m.AiAdaptationRun(
        clinic_id=clinic_id,
        adapter_code=data.adapter_code.strip(),
        base_model_digest=data.base_model_digest.strip(),
        dataset_license_id=lic,
        deidentification_verified=True,
        baseline_f1_bp=data.baseline_f1_bp,
        candidate_f1_bp=data.candidate_f1_bp,
        measured_lift_bp=lift_bp,
        status="benchmark_passed_offline_only",
        deployed_to_clinical_production=False,
        wrote_to_emr=False,
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ai.adaptation_benchmark_passed_offline",
        "ai_adaptation_run",
        row.id,
        {"adapter_code": row.adapter_code, "measured_lift_bp": lift_bp},
    )
    db.commit()
    return row


def attest_plan_version_simulation(
    db: Session,
    clinic_id: str,
    plan_id: str,
    staff_id: str,
    role: str,
    actor: str,
    data: PlanReviewAttestationCreate,
) -> m.PlanReviewAttestation:
    if data.approval_mode == "legal_clinical_approval":
        svc.audit(
            db,
            clinic_id,
            actor,
            "plan.review_blocked_legal_approval_claim",
            "treatment_plan",
            plan_id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Legal clinical treatment plan approval is gated on human clinical/legal sign-off; demo supports simulation only (TRT-004 / AGENTS.md)",
        )
    if role not in {"dentist", "medical_director"} or not data.credential_verified_in_demo:
        raise HTTPException(
            403,
            "Only credential-verified dentist or medical_director can review treatment plan versions (TRT-004)",
        )
    staff = svc.ensure(db, m.Staff, staff_id, clinic_id)
    if not staff.active:
        raise HTTPException(403, "Inactive clinician cannot attest plan version")

    plan, version = svc.get_plan_version(db, clinic_id, plan_id)
    if data.expected_version_number != version.number:
        raise HTTPException(
            409,
            f"Expected plan version v{data.expected_version_number} does not match current v{version.number} (TRT-004)",
        )
    tasks = db.scalars(
        select(m.PlanTask)
        .where(m.PlanTask.plan_version_id == version.id)
        .order_by(m.PlanTask.id.asc())
    ).all()
    if not tasks:
        raise HTTPException(409, "Cannot attest an empty treatment plan version (TRT-004)")

    edges = db.scalars(
        select(m.PlanTaskDependency)
        .where(m.PlanTaskDependency.plan_version_id == version.id)
        .order_by(m.PlanTaskDependency.task_id.asc(), m.PlanTaskDependency.depends_on_task_id.asc())
    ).all()
    canonical_doc = {
        "clinic_id": clinic_id,
        "plan_id": plan.id,
        "version_number": version.number,
        "tasks": [
            {"id": t.id, "title": t.title, "phase": t.phase, "owner_role": t.owner_role}
            for t in tasks
        ],
        "dependencies": [
            {"task_id": e.task_id, "depends_on_task_id": e.depends_on_task_id} for e in edges
        ],
        "simulation_only": True,
    }
    sha = hashlib.sha256(
        json.dumps(canonical_doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()

    version.status = "demo_reviewed"
    version.reviewer_demo = actor[:100]
    row = m.PlanReviewAttestation(
        clinic_id=clinic_id,
        plan_id=plan.id,
        version_number=version.number,
        reviewer_staff_id=staff.id,
        reviewer_role=role,
        version_canonical_sha256=sha,
        review_note_vi=data.review_note_vi.strip(),
        simulation_label="demo_reviewed_simulation_NOT_dentist_approval",
        is_legal_clinical_approval=False,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This plan version already has a review attestation") from exc
    svc.audit(
        db,
        clinic_id,
        actor,
        "plan.version_attested_simulation_NOT_legal",
        "plan_review_attestation",
        row.id,
        {"version_number": version.number, "version_canonical_sha256": sha},
    )
    db.commit()
    return row
