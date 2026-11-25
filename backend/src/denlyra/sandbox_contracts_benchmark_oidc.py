"""T027 domain services: clinic-policy-governed cancellation slot outreach (CRM-012),
reproducible local latency & throughput benchmark without invented SLAs (OPS-008),
OIDC enterprise directory group mapping & immediate token_version revocation (ORG-010),
consent/opt-out messaging sandbox contract (INT-007), and HMAC-SHA256 signed payment
webhook sandbox with replay protection & bounded reversals (INT-008).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .schemas import (
    CancellationOutreachExecuteRequest,
    CancellationOutreachPolicyCreate,
    LoadBenchmarkRunRequest,
    MessagingOptOutWebhookRequest,
    MessagingSandboxSendRequest,
    OidcDirectorySyncRequest,
    OidcGroupMappingCreate,
    PaymentCreate,
    PaymentSandboxWebhookRequest,
    RefundCreate,
)

FORBIDDEN_MESSAGING_CLINICAL_TERMS = (
    "icd-",
    "chẩn đoán:",
    "kháng sinh",
    "viêm tủy",
    "đơn thuốc",
    "hiv",
    "viêm gan",
)

OPT_OUT_KEYWORDS = {"STOP", "HUY", "HỦY", "UNSUBSCRIBE", "TC"}


def create_cancellation_outreach_policy(
    db: Session,
    clinic_id: str,
    staff_id: str,
    role: str,
    actor: str,
    data: CancellationOutreachPolicyCreate,
) -> m.CancellationOutreachPolicy:
    if data.approve_immediately and role not in {"clinic_owner", "medical_director"}:
        raise HTTPException(
            403, "Only clinic_owner or medical_director can approve outreach policies (CRM-012)"
        )
    row = m.CancellationOutreachPolicy(
        clinic_id=clinic_id,
        policy_code=data.policy_code.strip().upper(),
        max_candidates_per_slot=data.max_candidates_per_slot,
        require_marketing_consent=data.require_marketing_consent,
        prioritization_mode="fifo_waitlist_only",
        clinical_triage_inferred=False,
        auto_book_without_confirmation=False,
        status="approved_by_leadership" if data.approve_immediately else "draft_unapproved",
        approved_by_staff_id=staff_id if data.approve_immediately else None,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Cancellation outreach policy_code already exists") from exc
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.cancellation_outreach_policy_created",
        "cancellation_outreach_policy",
        row.id,
        {"policy_code": row.policy_code, "status": row.status},
    )
    db.commit()
    return row


def execute_cancellation_outreach(
    db: Session,
    clinic_id: str,
    appointment_id: str,
    actor: str,
    data: CancellationOutreachExecuteRequest,
) -> m.CancellationOutreachBatch:
    appt = svc.ensure(db, m.Appointment, appointment_id, clinic_id)
    pol = svc.ensure(db, m.CancellationOutreachPolicy, data.policy_id, clinic_id)
    if appt.status != "cancelled":
        raise HTTPException(
            409, "Target appointment must be cancelled before slot recovery outreach (CRM-012)"
        )
    if pol.status != "approved_by_leadership":
        svc.audit(
            db,
            clinic_id,
            actor,
            "crm.cancellation_outreach_blocked_unapproved_policy",
            "cancellation_outreach_policy",
            pol.id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Approved clinic cancellation outreach policy is mandatory before automated outreach (CRM-012)",
        )

    req_purpose = "marketing" if pol.require_marketing_consent else "data_processing"
    waitlist_rows = db.scalars(
        select(m.ScheduleWaitlistEntry)
        .where(
            m.ScheduleWaitlistEntry.clinic_id == clinic_id,
            m.ScheduleWaitlistEntry.status == "waiting",
        )
        .order_by(m.ScheduleWaitlistEntry.created_at.asc(), m.ScheduleWaitlistEntry.id.asc())
    ).all()

    selected: list[dict[str, str]] = []
    for entry in waitlist_rows:
        has_consent = db.scalar(
            select(m.ConsentRecord).where(
                m.ConsentRecord.clinic_id == clinic_id,
                m.ConsentRecord.patient_id == entry.patient_id,
                m.ConsentRecord.purpose == req_purpose,
                m.ConsentRecord.status == "granted",
            )
        )
        if has_consent is None:
            continue
        opted_out = db.scalar(
            select(m.MessagingChannelPreference).where(
                m.MessagingChannelPreference.clinic_id == clinic_id,
                m.MessagingChannelPreference.patient_id == entry.patient_id,
                m.MessagingChannelPreference.opted_out.is_(True),
            )
        )
        if opted_out is not None:
            continue
        selected.append(
            {
                "waitlist_entry_id": entry.id,
                "patient_id": entry.patient_id,
                "preferred_date_window": entry.preferred_date_window,
            }
        )
        if len(selected) >= pol.max_candidates_per_slot:
            break

    batch = m.CancellationOutreachBatch(
        clinic_id=clinic_id,
        appointment_id=appt.id,
        policy_id=pol.id,
        queued_count=len(selected),
        candidates_json=json.dumps(selected, ensure_ascii=False),
        clinical_triage_inferred=False,
        auto_booked=False,
        actor_demo=actor[:100],
    )
    db.add(batch)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "crm.cancellation_outreach_prepared_fifo",
        "cancellation_outreach_batch",
        batch.id,
        {"queued_count": batch.queued_count, "policy_code": pol.policy_code},
    )
    db.commit()
    return batch


def run_local_load_benchmark(
    db: Session,
    clinic_id: str,
    actor: str,
    data: LoadBenchmarkRunRequest,
) -> m.LoadBenchmarkRun:
    if data.claim_production_sla:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ops.benchmark_blocked_fabricated_sla",
            "clinic",
            clinic_id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Fabricated production or cloud SLA claims are forbidden on local synthetic benchmarks (OPS-008)",
        )

    samples_us: list[int] = []
    t_suite_start = time.perf_counter_ns()
    for _ in range(data.iterations):
        t0 = time.perf_counter_ns()
        if data.workload_profile == "clinic_read_mix":
            _ = db.scalar(
                select(func.count()).select_from(m.Patient).where(m.Patient.clinic_id == clinic_id)
            )
            _ = db.scalar(
                select(func.count())
                .select_from(m.Appointment)
                .where(m.Appointment.clinic_id == clinic_id)
            )
        else:
            _ = db.scalars(
                select(m.ResourceBooking)
                .where(
                    m.ResourceBooking.clinic_id == clinic_id,
                    m.ResourceBooking.state == "active",
                )
                .limit(25)
            ).all()
        elapsed_us = max(0, (time.perf_counter_ns() - t0) // 1_000)
        samples_us.append(int(elapsed_us))
    total_ns = max(1_000, time.perf_counter_ns() - t_suite_start)

    samples_us.sort()
    n = len(samples_us)
    p50_us = samples_us[int((n - 1) * 0.50)]
    p95_us = samples_us[int((n - 1) * 0.95)]
    max_us = samples_us[-1]
    ops_per_sec = max(1, int((data.iterations * 1_000_000_000) // total_ns))

    row = m.LoadBenchmarkRun(
        clinic_id=clinic_id,
        workload_profile=data.workload_profile,
        iterations=data.iterations,
        p50_latency_us=p50_us,
        p95_latency_us=p95_us,
        max_latency_us=max_us,
        throughput_ops_per_sec=ops_per_sec,
        environment_label="local_synthetic_non_sla",
        claims_production_sla=False,
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ops.local_load_benchmark_recorded",
        "load_benchmark_run",
        row.id,
        {"p50_us": p50_us, "p95_us": p95_us, "iterations": data.iterations},
    )
    db.commit()
    return row


def create_oidc_group_mapping(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: OidcGroupMappingCreate,
) -> m.OidcGroupMappingRule:
    row = m.OidcGroupMappingRule(
        clinic_id=clinic_id,
        idp_issuer=data.idp_issuer.strip(),
        external_group_id=data.external_group_id.strip(),
        branch_id=data.branch_id.strip(),
        mapped_role=data.mapped_role,
        created_by_staff_id=staff_id,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "OIDC group mapping already exists for issuer and group") from exc
    svc.audit(
        db,
        clinic_id,
        actor,
        "auth.oidc_group_mapping_created",
        "oidc_group_mapping_rule",
        row.id,
        {"external_group_id": row.external_group_id, "mapped_role": row.mapped_role},
    )
    db.commit()
    return row


def sync_oidc_directory_membership(
    db: Session,
    clinic_id: str,
    actor: str,
    data: OidcDirectorySyncRequest,
) -> m.OidcDirectorySyncEvent:
    staff = svc.ensure(db, m.Staff, data.staff_id, clinic_id)
    group_set = {g.strip() for g in data.external_groups if g.strip()}
    matched_rules = (
        db.scalars(
            select(m.OidcGroupMappingRule).where(
                m.OidcGroupMappingRule.clinic_id == clinic_id,
                m.OidcGroupMappingRule.idp_issuer == data.idp_issuer.strip(),
                m.OidcGroupMappingRule.external_group_id.in_(group_set),
            )
        ).all()
        if group_set
        else []
    )

    if not data.active_in_directory or not matched_rules:
        staff.active = False
        staff.token_version = (staff.token_version or 1) + 1
        outcome = "revoked_access_immediately"
    else:
        targets = {(r.mapped_role, r.branch_id) for r in matched_rules}
        if len(targets) > 1:
            raise HTTPException(
                409,
                "Conflicting OIDC directory group-to-role mappings detected; refusing ambiguous privilege grant (ORG-010)",
            )
        target_role, target_branch = next(iter(targets))
        changed = (
            (not staff.active)
            or (staff.role != target_role)
            or (staff.branch_id != target_branch)
        )
        staff.active = True
        staff.role = target_role
        staff.branch_id = target_branch
        if changed:
            staff.token_version = (staff.token_version or 1) + 1
        outcome = "provisioned_or_updated"

    evt = m.OidcDirectorySyncEvent(
        clinic_id=clinic_id,
        idp_issuer=data.idp_issuer.strip(),
        staff_id=staff.id,
        external_subject=data.external_subject.strip(),
        sync_outcome=outcome,
        resulting_token_version=staff.token_version,
        actor_demo=actor[:100],
    )
    db.add(evt)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        f"auth.oidc_directory_sync.{outcome}",
        "staff",
        staff.id,
        {"token_version": staff.token_version, "external_subject": evt.external_subject},
    )
    db.commit()
    return evt


def record_messaging_opt_out_webhook(
    db: Session,
    clinic_id: str,
    actor: str,
    data: MessagingOptOutWebhookRequest,
) -> m.MessagingChannelPreference:
    pat = svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    kw = data.keyword.strip().upper()
    if kw not in OPT_OUT_KEYWORDS:
        raise HTTPException(422, f"Unsupported opt-out keyword '{kw}'")
    pref = db.scalar(
        select(m.MessagingChannelPreference).where(
            m.MessagingChannelPreference.clinic_id == clinic_id,
            m.MessagingChannelPreference.patient_id == pat.id,
            m.MessagingChannelPreference.channel == data.channel,
        )
    )
    if pref is None:
        pref = m.MessagingChannelPreference(
            clinic_id=clinic_id,
            patient_id=pat.id,
            channel=data.channel,
            opted_out=True,
            last_keyword=kw,
            provider_event_id=data.provider_event_id.strip(),
        )
        db.add(pref)
    else:
        pref.opted_out = True
        pref.last_keyword = kw
        pref.provider_event_id = data.provider_event_id.strip()
        pref.updated_at = m.utcnow()
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "integrations.messaging_opt_out_recorded",
        "patient",
        pat.id,
        {"channel": data.channel, "keyword": kw},
    )
    db.commit()
    return pref


def send_sandbox_message(
    db: Session,
    clinic_id: str,
    actor: str,
    data: MessagingSandboxSendRequest,
) -> m.MessagingSandboxDispatch:
    lower_body = data.rendered_body_minimized.lower()
    for term in FORBIDDEN_MESSAGING_CLINICAL_TERMS:
        if term in lower_body:
            raise HTTPException(
                422,
                f"Clinical diagnosis/PHI term '{term}' is forbidden in external messaging payloads (INT-007)",
            )

    existing = db.scalar(
        select(m.MessagingSandboxDispatch).where(
            m.MessagingSandboxDispatch.clinic_id == clinic_id,
            m.MessagingSandboxDispatch.idempotency_key == data.idempotency_key,
        )
    )
    if existing is not None:
        return existing

    pat = svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    pref = db.scalar(
        select(m.MessagingChannelPreference).where(
            m.MessagingChannelPreference.clinic_id == clinic_id,
            m.MessagingChannelPreference.patient_id == pat.id,
            m.MessagingChannelPreference.channel == data.channel,
        )
    )
    if pref is not None and pref.opted_out:
        svc.audit(
            db,
            clinic_id,
            actor,
            "integrations.messaging_blocked_opted_out",
            "patient",
            pat.id,
            {"channel": data.channel},
        )
        db.commit()
        raise HTTPException(403, "Patient has opted out of this messaging channel (INT-007)")

    req_consent = "marketing" if data.purpose == "marketing_recall" else "data_processing"
    consent = db.scalar(
        select(m.ConsentRecord).where(
            m.ConsentRecord.clinic_id == clinic_id,
            m.ConsentRecord.patient_id == pat.id,
            m.ConsentRecord.purpose == req_consent,
            m.ConsentRecord.status == "granted",
        )
    )
    if consent is None:
        raise HTTPException(
            403, f"Active '{req_consent}' consent is required before messaging dispatch (INT-007)"
        )

    row = m.MessagingSandboxDispatch(
        clinic_id=clinic_id,
        patient_id=pat.id,
        channel=data.channel,
        purpose=data.purpose,
        template_code=data.template_code.strip(),
        rendered_body_minimized=data.rendered_body_minimized.strip(),
        delivery_state="delivered_sandbox_no_confirmation_implied",
        patient_confirmed_appointment=False,
        zero_external_egress=True,
        idempotency_key=data.idempotency_key.strip(),
        actor_demo=actor[:100],
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "integrations.messaging_sandbox_dispatched",
        "messaging_sandbox_dispatch",
        row.id,
        {"channel": row.channel, "purpose": row.purpose},
    )
    db.commit()
    return row


def process_signed_payment_webhook(
    db: Session,
    clinic_id: str,
    auth_secret: str,
    actor: str,
    data: PaymentSandboxWebhookRequest,
) -> dict[str, object]:
    now_ts = int(time.time())
    if abs(now_ts - data.timestamp_unix) > 300:
        raise HTTPException(401, "Payment webhook timestamp outside 300s replay window (INT-008)")

    key = f"{auth_secret}:payment-webhook:{clinic_id}".encode("utf-8")
    msg = (
        f"{clinic_id}|{data.provider_code}|{data.provider_event_id}|"
        f"{data.event_type}|{data.patient_id}|{data.amount_vnd}|{data.timestamp_unix}"
    ).encode("utf-8")
    expected_sig = hmac.new(key, msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, data.hmac_signature_hex.lower()):
        raise HTTPException(401, "Invalid payment webhook HMAC-SHA256 signature (INT-008)")

    canonical_payload = json.dumps(
        {
            "clinic_id": clinic_id,
            "provider_code": data.provider_code,
            "provider_event_id": data.provider_event_id,
            "event_type": data.event_type,
            "patient_id": data.patient_id,
            "amount_vnd": data.amount_vnd,
            "payment_reference": data.payment_reference,
            "original_payment_id": data.original_payment_id or "",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload_sha = hashlib.sha256(canonical_payload).hexdigest()

    existing = db.scalar(
        select(m.PaymentWebhookInbox).where(
            m.PaymentWebhookInbox.clinic_id == clinic_id,
            m.PaymentWebhookInbox.provider_code == data.provider_code,
            m.PaymentWebhookInbox.provider_event_id == data.provider_event_id,
        )
    )
    if existing is not None:
        if existing.payload_sha256 == payload_sha:
            return {
                "id": existing.id,
                "provider_code": existing.provider_code,
                "provider_event_id": existing.provider_event_id,
                "event_type": existing.event_type,
                "amount_vnd": existing.amount_vnd,
                "payment_id": existing.payment_id,
                "refund_id": existing.refund_id,
                "implies_clinical_completion": False,
                "replayed_duplicate_ignored": True,
            }
        svc.audit(
            db,
            clinic_id,
            actor,
            "integrations.payment_webhook_mutated_replay_blocked",
            "payment_webhook_inbox",
            existing.id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Payment webhook provider_event_id replayed with mutated payload parameters (INT-008)",
        )

    payment_id: str | None = None
    refund_id: str | None = None
    if data.event_type == "payment.succeeded":
        pay = svc.create_payment(
            db,
            clinic_id,
            PaymentCreate(
                patient_id=data.patient_id,
                amount_vnd=data.amount_vnd,
                payment_method="bank_transfer",
                external_reference=data.payment_reference,
                idempotency_key=f"wh:{data.provider_code}:{data.provider_event_id}"[:120],
            ),
            actor,
        )
        payment_id = pay.id
    else:
        if not data.original_payment_id:
            raise HTTPException(422, "original_payment_id is required for payment.reversed")
        ref = svc.refund_payment(
            db,
            clinic_id,
            data.original_payment_id,
            RefundCreate(
                amount_vnd=data.amount_vnd,
                reason=f"Provider webhook reversal ({data.payment_reference})",
                idempotency_key=f"wh-rev:{data.provider_code}:{data.provider_event_id}"[:120],
            ),
            actor,
        )
        payment_id = data.original_payment_id
        refund_id = ref.id

    inbox = m.PaymentWebhookInbox(
        clinic_id=clinic_id,
        provider_code=data.provider_code,
        provider_event_id=data.provider_event_id,
        event_type=data.event_type,
        patient_id=data.patient_id,
        amount_vnd=data.amount_vnd,
        payload_sha256=payload_sha,
        payment_id=payment_id,
        refund_id=refund_id,
        implies_clinical_completion=False,
    )
    db.add(inbox)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        f"integrations.payment_webhook.{data.event_type}",
        "payment_webhook_inbox",
        inbox.id,
        {"amount_vnd": data.amount_vnd, "provider_event_id": data.provider_event_id},
    )
    db.commit()
    return {
        "id": inbox.id,
        "provider_code": inbox.provider_code,
        "provider_event_id": inbox.provider_event_id,
        "event_type": inbox.event_type,
        "amount_vnd": inbox.amount_vnd,
        "payment_id": inbox.payment_id,
        "refund_id": inbox.refund_id,
        "implies_clinical_completion": False,
        "replayed_duplicate_ignored": False,
    }
