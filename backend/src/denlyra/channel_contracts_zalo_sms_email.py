"""T030 domain services: channel-specific sandbox messaging contracts — official Zalo OA/ZNS
pricing & parameter allowlist gate (CRM-006), SMS brandname carrier DLR evidence & opt-out
propagation (CRM-007), and SPF/DKIM/DMARC verified Email sender with safe-template & rolling
hourly 429 rate limiting (CRM-008). Zero live external egress in synthetic demonstrator.
"""
from __future__ import annotations

from datetime import timedelta
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models as m, sandbox_contracts_benchmark_oidc as sbx, services as svc
from .schemas import (
    EmailSandboxSendCreate,
    EmailVerifiedSenderCreate,
    SmsDeliveryReceiptCreate,
    SmsSandboxDispatchCreate,
    ZaloZnsContractCreate,
    ZaloZnsPreviewDispatchRequest,
)

UNSAFE_EMAIL_PATTERNS = (
    "<script",
    "<iframe",
    "javascript:",
    "onerror=",
    "onload=",
    "<img",
)


def _assert_consent_and_not_opted_out(
    db: Session,
    clinic_id: str,
    patient_id: str,
    channel: str,
    purpose: str,
) -> None:
    pref = db.scalar(
        select(m.MessagingChannelPreference).where(
            m.MessagingChannelPreference.clinic_id == clinic_id,
            m.MessagingChannelPreference.patient_id == patient_id,
            m.MessagingChannelPreference.channel == channel,
            m.MessagingChannelPreference.opted_out.is_(True),
        )
    )
    if pref is not None:
        raise HTTPException(403, f"Patient has opted out on channel '{channel}'")

    consent = db.scalar(
        select(m.ConsentRecord).where(
            m.ConsentRecord.clinic_id == clinic_id,
            m.ConsentRecord.patient_id == patient_id,
            m.ConsentRecord.purpose == purpose,
            m.ConsentRecord.status == "granted",
        )
    )
    if consent is None:
        raise HTTPException(403, f"Active '{purpose}' consent is required for channel '{channel}'")


def _assert_no_clinical_phi(text_val: str) -> None:
    lower = text_val.lower()
    for term in sbx.FORBIDDEN_MESSAGING_CLINICAL_TERMS:
        if term in lower:
            raise HTTPException(
                422,
                f"Clinical diagnosis/prescription term '{term}' is forbidden in external channel payload",
            )


def create_zalo_zns_contract(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: ZaloZnsContractCreate,
) -> m.ZaloZnsContract:
    clean_keys = sorted({k.strip() for k in data.allowed_param_keys if k.strip()})
    if not clean_keys:
        raise HTTPException(422, "allowed_param_keys cannot be empty")
    row = m.ZaloZnsContract(
        clinic_id=clinic_id,
        oa_id_demo=data.oa_id_demo.strip(),
        zns_template_id=data.zns_template_id.strip(),
        official_api_only=True,
        legal_basis_purpose=data.legal_basis_purpose,
        price_per_message_vnd=data.price_per_message_vnd,
        pricing_confirmed=data.pricing_confirmed,
        allowed_param_keys_json=json.dumps(clean_keys, ensure_ascii=False),
        created_by_staff_id=staff_id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "ZNS template_id already registered in clinic") from exc
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.zalo_zns_contract_registered",
        "zalo_zns_contract",
        row.id,
        {"zns_template_id": row.zns_template_id, "pricing_confirmed": row.pricing_confirmed},
    )
    db.commit()
    return row


def preview_zalo_zns_dispatch(
    db: Session,
    clinic_id: str,
    actor: str,
    data: ZaloZnsPreviewDispatchRequest,
) -> m.ZaloZnsDispatchPreview:
    pat = svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    contract = svc.ensure(db, m.ZaloZnsContract, data.contract_id, clinic_id)
    if not contract.pricing_confirmed:
        raise HTTPException(
            409,
            "Zalo OA/ZNS contract pricing and legal basis must be confirmed before dispatch (CRM-006)",
        )
    allowed_keys = set(json.loads(contract.allowed_param_keys_json))
    extra_keys = set(data.template_params.keys()) - allowed_keys
    if extra_keys:
        raise HTTPException(
            422,
            f"Undeclared ZNS template parameter keys rejected: {sorted(extra_keys)} (CRM-006)",
        )
    for val in data.template_params.values():
        _assert_no_clinical_phi(val)

    _assert_consent_and_not_opted_out(
        db, clinic_id, pat.id, "zalo_zns_sandbox", contract.legal_basis_purpose
    )

    row = m.ZaloZnsDispatchPreview(
        clinic_id=clinic_id,
        patient_id=pat.id,
        contract_id=contract.id,
        params_json=json.dumps(data.template_params, sort_keys=True, ensure_ascii=False),
        quoted_cost_vnd=contract.price_per_message_vnd,
        live_external_egress=False,
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.zalo_zns_preview_dispatched_sandbox",
        "zalo_zns_dispatch_preview",
        row.id,
        {"quoted_cost_vnd": row.quoted_cost_vnd},
    )
    db.commit()
    return row


def send_sms_sandbox(
    db: Session,
    clinic_id: str,
    actor: str,
    data: SmsSandboxDispatchCreate,
) -> m.SmsSandboxDispatch:
    _assert_no_clinical_phi(data.message_ascii_or_ucs2)
    existing = db.scalar(
        select(m.SmsSandboxDispatch).where(
            m.SmsSandboxDispatch.clinic_id == clinic_id,
            m.SmsSandboxDispatch.idempotency_key == data.idempotency_key.strip(),
        )
    )
    if existing is not None:
        return existing

    pat = svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    _assert_consent_and_not_opted_out(db, clinic_id, pat.id, "sms_sandbox", data.purpose)

    row = m.SmsSandboxDispatch(
        clinic_id=clinic_id,
        patient_id=pat.id,
        brandname_sender=data.brandname_sender.strip().upper(),
        purpose=data.purpose,
        message_ascii_or_ucs2=data.message_ascii_or_ucs2.strip(),
        carrier_delivery_status="queued_sandbox",
        dlr_evidence_sha256=None,
        patient_confirmed_appointment=False,
        live_external_egress=False,
        idempotency_key=data.idempotency_key.strip(),
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.sms_sandbox_queued",
        "sms_sandbox_dispatch",
        row.id,
        {"brandname_sender": row.brandname_sender},
    )
    db.commit()
    return row


def record_sms_dlr_receipt(
    db: Session,
    clinic_id: str,
    dispatch_id: str,
    actor: str,
    data: SmsDeliveryReceiptCreate,
) -> m.SmsSandboxDispatch:
    disp = svc.ensure(db, m.SmsSandboxDispatch, dispatch_id, clinic_id)
    evidence = json.dumps(
        {
            "clinic_id": clinic_id,
            "dispatch_id": disp.id,
            "provider_dlr_code": data.provider_dlr_code.strip(),
            "carrier_status": data.carrier_status,
            "opt_out_triggered": data.opt_out_triggered,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    disp.carrier_delivery_status = data.carrier_status
    disp.dlr_evidence_sha256 = hashlib.sha256(evidence).hexdigest()

    if data.opt_out_triggered:
        pref = db.scalar(
            select(m.MessagingChannelPreference).where(
                m.MessagingChannelPreference.clinic_id == clinic_id,
                m.MessagingChannelPreference.patient_id == disp.patient_id,
                m.MessagingChannelPreference.channel == "sms_sandbox",
            )
        )
        if pref is None:
            db.add(
                m.MessagingChannelPreference(
                    clinic_id=clinic_id,
                    patient_id=disp.patient_id,
                    channel="sms_sandbox",
                    opted_out=True,
                    last_keyword="DLR_STOP",
                    provider_event_id=data.provider_dlr_code.strip(),
                )
            )
        else:
            pref.opted_out = True
            pref.last_keyword = "DLR_STOP"
            pref.provider_event_id = data.provider_dlr_code.strip()
            pref.updated_at = m.utcnow()

    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.sms_dlr_recorded",
        "sms_sandbox_dispatch",
        disp.id,
        {"carrier_status": disp.carrier_delivery_status, "opt_out": data.opt_out_triggered},
    )
    db.commit()
    return disp


def register_email_sender(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: EmailVerifiedSenderCreate,
) -> m.EmailVerifiedSender:
    addr = data.sender_address.strip().lower()
    if "@" not in addr or "\r" in addr or "\n" in addr:
        raise HTTPException(422, "Invalid sender email address")
    row = m.EmailVerifiedSender(
        clinic_id=clinic_id,
        sender_address=addr,
        spf_verified=data.spf_verified,
        dkim_verified=data.dkim_verified,
        dmarc_verified=data.dmarc_verified,
        hourly_rate_limit=data.hourly_rate_limit,
        created_by_staff_id=staff_id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Sender email already registered in clinic") from exc
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.email_sender_registered",
        "email_verified_sender",
        row.id,
        {"sender_address": addr},
    )
    db.commit()
    return row


def send_email_sandbox(
    db: Session,
    clinic_id: str,
    actor: str,
    data: EmailSandboxSendCreate,
) -> m.EmailSandboxDispatch:
    if "\r" in data.subject_minimized or "\n" in data.subject_minimized:
        raise HTTPException(422, "CRLF header injection blocked in email subject (CRM-008)")
    combined_lower = f"{data.subject_minimized}\n{data.body_safe_text}".lower()
    for bad in UNSAFE_EMAIL_PATTERNS:
        if bad in combined_lower:
            raise HTTPException(
                422,
                f"Unsafe HTML/script/tracking pattern '{bad}' blocked in email template (CRM-008)",
            )
    _assert_no_clinical_phi(combined_lower)

    pat = svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    sender = svc.ensure(db, m.EmailVerifiedSender, data.sender_id, clinic_id)
    if not (sender.spf_verified and sender.dkim_verified and sender.dmarc_verified):
        raise HTTPException(
            409,
            "Clinic email sender must have SPF, DKIM, and DMARC verified before sending (CRM-008)",
        )

    _assert_consent_and_not_opted_out(db, clinic_id, pat.id, "email_sandbox", data.purpose)

    window_start = m.utcnow() - timedelta(hours=1)
    sent_in_window = int(
        db.scalar(
            select(func.count())
            .select_from(m.EmailSandboxDispatch)
            .where(
                m.EmailSandboxDispatch.clinic_id == clinic_id,
                m.EmailSandboxDispatch.sender_id == sender.id,
                m.EmailSandboxDispatch.created_at >= window_start,
            )
        )
        or 0
    )
    if sent_in_window >= sender.hourly_rate_limit:
        svc.audit(
            db,
            clinic_id,
            actor,
            "crm.email_rate_limit_exceeded",
            "email_verified_sender",
            sender.id,
            {"hourly_rate_limit": sender.hourly_rate_limit},
        )
        db.commit()
        raise HTTPException(
            429,
            f"Hourly email rate limit ({sender.hourly_rate_limit}/hr) exceeded for sender (CRM-008)",
        )

    row = m.EmailSandboxDispatch(
        clinic_id=clinic_id,
        patient_id=pat.id,
        sender_id=sender.id,
        purpose=data.purpose,
        subject_minimized=data.subject_minimized.strip(),
        body_safe_text=data.body_safe_text.strip(),
        live_external_egress=False,
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.email_sandbox_dispatched",
        "email_sandbox_dispatch",
        row.id,
        {"sender_address": sender.sender_address},
    )
    db.commit()
    return row
