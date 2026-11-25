"""T028 domain services: per-clinic confirmed imaging modality & DICOM patient-ID
quarantine gateway (INT-004), zero-egress Vietnamese speech dictation audio-consent
and terminology benchmark draft (AI-001), PHI-free accounting journal export &
fail-closed official tax e-invoice gate (FIN-009, INT-009), and OWASP ASVS adversarial
security suite + fail-closed production PHI release gate (SEC-014, SEC-015).
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import ai_harness, models as m, services as svc
from .schemas import (
    AccountingExportCreate,
    AdversarialSecurityRunRequest,
    DicomModalityRegisterCreate,
    DicomStudyManifestIngestCreate,
    ProductionReleaseGateRequest,
    SpeechDictationTranscribeRequest,
)

VN_DENTAL_BENCHMARK_LEXICON = (
    "răng",
    "mặt nhai",
    "sâu ngà",
    "sâu men",
    "nướu",
    "tủy",
    "chóp",
    "nha chu",
    "mão sứ",
    "implant",
    "khớp cắn",
)

DANGEROUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".js", ".vbs", ".dll", ".scr"}


def register_dicom_modality(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: DicomModalityRegisterCreate,
) -> m.DicomModalityRegistration:
    row = m.DicomModalityRegistration(
        clinic_id=clinic_id,
        ae_title=data.ae_title.strip().upper(),
        modality_code=data.modality_code,
        device_label=data.device_label.strip(),
        confirmed_for_clinic=data.confirmed_for_clinic,
        registered_by_staff_id=staff_id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "DICOM AE Title already registered in clinic") from exc
    svc.audit(
        db,
        clinic_id,
        actor,
        "interop.dicom_modality_registered",
        "dicom_modality",
        row.id,
        {"ae_title": row.ae_title, "confirmed_for_clinic": row.confirmed_for_clinic},
    )
    db.commit()
    return row


def ingest_dicom_study_manifest(
    db: Session,
    clinic_id: str,
    actor: str,
    data: DicomStudyManifestIngestCreate,
) -> m.DicomStudyQuarantineManifest:
    if data.claim_diagnostic_samd:
        raise HTTPException(
            409,
            "Diagnostic SaMD radiology claims are blocked without regulatory certification (INT-004 / AI-013)",
        )
    pat = svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    mod = svc.ensure(db, m.DicomModalityRegistration, data.modality_id, clinic_id)
    if not mod.confirmed_for_clinic:
        svc.audit(
            db,
            clinic_id,
            actor,
            "interop.dicom_blocked_unconfirmed_modality",
            "dicom_modality",
            mod.id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Imaging modality is not confirmed for this clinic; study quarantined (INT-004)",
        )
    if data.dicom_patient_id_tag.strip() != pat.id:
        svc.audit(
            db,
            clinic_id,
            actor,
            "interop.dicom_blocked_patient_id_mismatch",
            "patient",
            pat.id,
            {"study_instance_uid": data.study_instance_uid},
        )
        db.commit()
        raise HTTPException(
            409,
            "DICOM PatientID tag does not match target clinic patient_id; wrong-patient attachment blocked (INT-004)",
        )

    row = m.DicomStudyQuarantineManifest(
        clinic_id=clinic_id,
        patient_id=pat.id,
        modality_id=mod.id,
        study_instance_uid=data.study_instance_uid.strip(),
        dicom_patient_id_tag=pat.id,
        series_count=data.series_count,
        instance_count=data.instance_count,
        study_sha256=data.study_sha256.lower(),
        viewer_mode="ohif_synthetic_htest_manifest",
        diagnostic_samd_certified=False,
        actor_demo=actor[:100],
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "StudyInstanceUID already registered in clinic") from exc
    svc.audit(
        db,
        clinic_id,
        actor,
        "interop.dicom_study_manifest_verified",
        "dicom_study",
        row.id,
        {"study_instance_uid": row.study_instance_uid, "study_sha256": row.study_sha256},
    )
    db.commit()
    return row


def transcribe_speech_dictation_draft(
    db: Session,
    clinic_id: str,
    actor: str,
    ai_enabled: bool,
    data: SpeechDictationTranscribeRequest,
) -> m.SpeechTranscriptionDraft:
    if not ai_enabled:
        raise HTTPException(503, "AI assistive workflows are disabled by clinic kill-switch (AI-014)")
    enc = svc.ensure(db, m.Encounter, data.encounter_id, clinic_id)
    has_dp_consent = db.scalar(
        select(m.ConsentRecord).where(
            m.ConsentRecord.clinic_id == clinic_id,
            m.ConsentRecord.patient_id == enc.patient_id,
            m.ConsentRecord.purpose == "data_processing",
            m.ConsentRecord.status == "granted",
        )
    )
    if not data.audio_recording_consent_verified or has_dp_consent is None:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ai.speech_blocked_missing_consent",
            "encounter",
            enc.id,
        )
        db.commit()
        raise HTTPException(
            403,
            "Verified audio recording consent and active data_processing consent are mandatory (AI-001)",
        )

    injection_hits = ai_harness.detect_prompt_injection(data.synthetic_transcript_vi)
    if injection_hits:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ai.speech_blocked_prompt_injection",
            "encounter",
            enc.id,
            {"hits": injection_hits},
        )
        db.commit()
        raise HTTPException(
            409,
            f"Prompt injection blocked in speech dictation transcript: {', '.join(injection_hits)} (AI-001 / AI-010)",
        )

    lower_txt = data.synthetic_transcript_vi.lower()
    matched = [term for term in VN_DENTAL_BENCHMARK_LEXICON if term in lower_txt]
    score_bp = min(10_000, int(round((len(matched) / max(1, len(VN_DENTAL_BENCHMARK_LEXICON))) * 10_000)))

    row = m.SpeechTranscriptionDraft(
        clinic_id=clinic_id,
        encounter_id=enc.id,
        patient_id=enc.patient_id,
        audio_sha256=data.audio_sha256.lower(),
        audio_consent_verified=True,
        transcript_draft_vi=data.synthetic_transcript_vi.strip(),
        matched_terms_json=json.dumps(matched, ensure_ascii=False),
        terminology_benchmark_score_bp=score_bp,
        wrote_to_emr=False,
        zero_external_egress=True,
        status="draft_for_clinician_review",
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ai.speech_draft_created_no_emr_write",
        "speech_draft",
        row.id,
        {"score_bp": score_bp, "matched_count": len(matched)},
    )
    db.commit()
    return row


def export_phi_free_accounting_batch(
    db: Session,
    clinic_id: str,
    actor: str,
    data: AccountingExportCreate,
) -> m.AccountingExportBatch:
    if data.issue_official_tax_einvoice or data.call_government_tax_api:
        svc.audit(
            db,
            clinic_id,
            actor,
            "finance.accounting_blocked_unauthorized_tax_api",
            "clinic",
            clinic_id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Official tax e-invoice issuance and government tax API calls are blocked until certified provider & legal sign-off (FIN-009 / INT-009)",
        )

    charged = int(
        db.scalar(
            select(func.coalesce(func.sum(m.Charge.amount_vnd), 0)).where(
                m.Charge.clinic_id == clinic_id
            )
        )
        or 0
    )
    collected = int(
        db.scalar(
            select(func.coalesce(func.sum(m.Payment.amount_vnd), 0)).where(
                m.Payment.clinic_id == clinic_id
            )
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
    entry_count = int(
        db.scalar(
            select(func.count())
            .select_from(m.LedgerEntry)
            .where(m.LedgerEntry.clinic_id == clinic_id)
        )
        or 0
    )

    canonical_obj = {
        "clinic_id": clinic_id,
        "period_label": data.period_label.strip(),
        "provider_profile": data.provider_profile.strip(),
        "total_charged_vnd": charged,
        "total_collected_vnd": collected,
        "total_refunded_vnd": refunded,
        "net_collected_vnd": collected - refunded,
        "ledger_entry_count": entry_count,
        "contains_phi": False,
        "official_tax_invoice_issued": False,
        "called_government_api": False,
    }
    canonical_bytes = json.dumps(
        canonical_obj, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()

    row = m.AccountingExportBatch(
        clinic_id=clinic_id,
        period_label=data.period_label.strip(),
        provider_profile=data.provider_profile.strip(),
        total_charged_vnd=charged,
        total_collected_vnd=collected,
        total_refunded_vnd=refunded,
        ledger_entry_count=entry_count,
        canonical_sha256=digest,
        contains_phi=False,
        official_tax_invoice_issued=False,
        called_government_api=False,
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "finance.accounting_export_created_phi_free",
        "accounting_export",
        row.id,
        {"canonical_sha256": digest, "period_label": row.period_label},
    )
    db.commit()
    return row


def _is_unsafe_outbound_url(raw_url: str) -> bool:
    parsed = urlparse(raw_url.strip())
    if parsed.scheme.lower() not in {"https"}:
        return True
    host = (parsed.hostname or "").strip().lower()
    if not host or host in {"localhost", "metadata.google.internal"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    except ValueError:
        pass
    return False


def _is_unsafe_filename(raw_name: str) -> bool:
    if ".." in raw_name or "/" in raw_name or "\\" in raw_name or "\x00" in raw_name:
        return True
    p_posix = PurePosixPath(raw_name)
    p_win = PureWindowsPath(raw_name)
    if p_posix.name != raw_name or p_win.name != raw_name:
        return True
    lower_suffixes = {s.lower() for s in p_posix.suffixes}
    return bool(lower_suffixes & DANGEROUS_EXTENSIONS)


def run_adversarial_security_suite(
    db: Session,
    clinic_id: str,
    actor: str,
    data: AdversarialSecurityRunRequest,
) -> m.AdversarialSecurityRun:
    ssrf_blocked = sum(1 for u in data.ssrf_probe_urls if _is_unsafe_outbound_url(u))
    trav_blocked = sum(1 for fn in data.traversal_filenames if _is_unsafe_filename(fn))
    all_blocked = ssrf_blocked == len(data.ssrf_probe_urls) and trav_blocked == len(
        data.traversal_filenames
    )
    if not all_blocked:
        raise HTTPException(
            409,
            "Adversarial probe bypassed SSRF or filename sanitizer guard (SEC-014)",
        )
    summary = {
        "clinic_id": clinic_id,
        "ssrf_probes_blocked": ssrf_blocked,
        "traversal_probes_blocked": trav_blocked,
        "all_vectors_blocked": True,
        "independent_external_pentest_complete": False,
    }
    digest = hashlib.sha256(
        json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    row = m.AdversarialSecurityRun(
        clinic_id=clinic_id,
        ssrf_probes_blocked=ssrf_blocked,
        traversal_probes_blocked=trav_blocked,
        all_vectors_blocked=True,
        independent_external_pentest_complete=False,
        report_sha256=digest,
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "security.adversarial_suite_verified",
        "adversarial_security_run",
        row.id,
        {"ssrf_blocked": ssrf_blocked, "traversal_blocked": trav_blocked},
    )
    db.commit()
    return row


def evaluate_production_release_gate(
    db: Session,
    clinic_id: str,
    actor: str,
    data: ProductionReleaseGateRequest,
) -> m.ReleaseGateEvaluation:
    open_blockers = [
        "NEEDS_CLINICAL_REVIEW: named dentist + Vietnamese healthcare counsel sign-off pending (T003/T004/T010)",
        "SEC-G1: live OIDC/MFA + external Cloud KMS/HSM + independent penetration test sign-off pending",
        "T002: live PostgreSQL 16 EXCLUDE USING gist execution receipt required before production booking",
    ]
    if data.target_environment == "production_phi" or data.enable_real_phi_processing:
        svc.audit(
            db,
            clinic_id,
            actor,
            "security.production_phi_gate_blocked",
            "clinic",
            clinic_id,
            {"open_blockers_count": len(open_blockers)},
        )
        db.commit()
        raise HTTPException(
            409,
            "Production PHI processing is strictly blocked in synthetic demonstrator until clinical, legal, live PostgreSQL, and SEC-G1 gates are signed off (SEC-015)",
        )

    row = m.ReleaseGateEvaluation(
        clinic_id=clinic_id,
        target_environment="synthetic_local",
        gate_status="synthetic_demo_permitted_phi_blocked",
        phi_processing_enabled=False,
        open_blockers_json=json.dumps(open_blockers, ensure_ascii=False),
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "security.release_gate_evaluated_synthetic_only",
        "release_gate_evaluation",
        row.id,
    )
    db.commit()
    return row
