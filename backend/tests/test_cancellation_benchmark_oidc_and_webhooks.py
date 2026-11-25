"""T027 negative-first & integration tests: policy-governed cancellation outreach (CRM-012),
reproducible local load benchmark without invented SLA (OPS-008), OIDC directory group
mapping & immediate revocation (ORG-010), consent/opt-out messaging sandbox (INT-007),
and HMAC-signed payment webhook replay protection & reversals (INT-008).
"""
from __future__ import annotations

import hashlib
import hmac
import time

from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"
AUTH_SECRET = "t027-synthetic-secret-key-for-tests-32b"


def _make_client(tmp_path) -> TestClient:
    app = create_app(
        Settings(
            demo_mode=True,
            require_auth=True,
            auth_secret=AUTH_SECRET,
            db_url=f"sqlite+pysqlite:///{tmp_path / 't027.db'}",
            archive_dir=str(tmp_path / "archive"),
        )
    )
    return TestClient(app)


def _issue_headers(client: TestClient, role: str, clinic_id: str = CLINIC_A, staff_id: str | None = None) -> dict[str, str]:
    payload: dict[str, object] = {"clinic_id": clinic_id, "role": role}
    if staff_id:
        payload["staff_id"] = staff_id
    resp = client.post("/api/v1/auth/token", json=payload)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Demo-Clinic": clinic_id}


def _sign_payment_webhook(
    clinic_id: str,
    provider_code: str,
    provider_event_id: str,
    event_type: str,
    patient_id: str,
    amount_vnd: int,
    timestamp_unix: int,
) -> str:
    key = f"{AUTH_SECRET}:payment-webhook:{clinic_id}".encode("utf-8")
    msg = f"{clinic_id}|{provider_code}|{provider_event_id}|{event_type}|{patient_id}|{amount_vnd}|{timestamp_unix}".encode(
        "utf-8"
    )
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def test_crm012_cancellation_outreach_requires_approved_policy_and_blocks_clinical_triage(tmp_path):
    with _make_client(tmp_path) as client:
        owner_h = _issue_headers(client, "clinic_owner")
        rec_h = _issue_headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=owner_h).json()
        dentist_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        p1 = client.post("/api/v1/patients", headers=rec_h, json={"display_name": "BN Hủy Lịch"}).json()["id"]
        p2 = client.post("/api/v1/patients", headers=rec_h, json={"display_name": "BN Chờ Có Consent"}).json()["id"]
        p3 = client.post("/api/v1/patients", headers=rec_h, json={"display_name": "BN Chờ Không Consent"}).json()["id"]

        client.post(
            "/api/v1/consents",
            headers=rec_h,
            json={
                "patient_id": p2,
                "purpose": "marketing",
                "template_version": "v1",
                "disclosure_summary": "Đồng ý nhận thông báo lịch trống",
                "signer_name": "BN Chờ Có Consent",
            },
        )

        client.post(
            "/api/v1/operations/waitlist",
            headers=rec_h,
            json={
                "patient_id": p2,
                "preferred_date_window": "2026-12-10",
                "service_note_minimized": "Khám định kỳ",
            },
        )
        client.post(
            "/api/v1/operations/waitlist",
            headers=rec_h,
            json={
                "patient_id": p3,
                "preferred_date_window": "2026-12-10",
                "service_note_minimized": "Tư vấn chung",
            },
        )

        appt = client.post(
            "/api/v1/appointments",
            headers=rec_h,
            json={
                "patient_id": p1,
                "practitioner_id": dentist_id,
                "chair_id": chair_id,
                "start_at": "2026-12-10T09:00:00+07:00",
                "end_at": "2026-12-10T10:00:00+07:00",
                "reason_demo": "Khám tổng quát",
            },
        )
        assert appt.status_code == 201, appt.text
        appt_id = appt.json()["id"]

        # Reject clinical triage inference policy
        bad_pol = client.post(
            "/api/v1/crm/cancellation-outreach-policies",
            headers=owner_h,
            json={
                "policy_code": "POL-BAD",
                "clinical_triage_inferred": True,
                "approve_immediately": True,
            },
        )
        assert bad_pol.status_code == 422

        # Unapproved draft policy must block outreach with 409
        draft_pol = client.post(
            "/api/v1/crm/cancellation-outreach-policies",
            headers=owner_h,
            json={
                "policy_code": "POL-DRAFT-01",
                "max_candidates_per_slot": 2,
                "approve_immediately": False,
            },
        )
        assert draft_pol.status_code == 201, draft_pol.text
        client.post(f"/api/v1/appointments/{appt_id}/cancel", headers=rec_h)

        blocked = client.post(
            f"/api/v1/crm/appointments/{appt_id}/cancellation-outreach",
            headers=rec_h,
            json={"policy_id": draft_pol.json()["id"]},
        )
        assert blocked.status_code == 409

        # Approved policy queues only consented FIFO candidate without auto-booking
        ok_pol = client.post(
            "/api/v1/crm/cancellation-outreach-policies",
            headers=owner_h,
            json={
                "policy_code": "POL-FIFO-01",
                "max_candidates_per_slot": 3,
                "require_marketing_consent": True,
                "approve_immediately": True,
            },
        )
        assert ok_pol.status_code == 201, ok_pol.text
        run = client.post(
            f"/api/v1/crm/appointments/{appt_id}/cancellation-outreach",
            headers=rec_h,
            json={"policy_id": ok_pol.json()["id"]},
        )
        assert run.status_code == 201, run.text
        body = run.json()
        assert body["queued_count"] == 1
        assert body["clinical_triage_inferred"] is False
        assert body["auto_booked"] is False


def test_ops008_benchmark_blocks_sla_claim_and_org010_oidc_revokes_session_immediately(tmp_path):
    with _make_client(tmp_path) as client:
        owner_h = _issue_headers(client, "clinic_owner")

        # OPS-008: claiming production SLA must fail closed with 409
        sla_claim = client.post(
            "/api/v1/ops/load-benchmarks/run",
            headers=owner_h,
            json={"workload_profile": "clinic_read_mix", "iterations": 10, "claim_production_sla": True},
        )
        assert sla_claim.status_code == 409

        bench = client.post(
            "/api/v1/ops/load-benchmarks/run",
            headers=owner_h,
            json={"workload_profile": "clinic_read_mix", "iterations": 12, "claim_production_sla": False},
        )
        assert bench.status_code == 201, bench.text
        b_data = bench.json()
        assert b_data["iterations"] == 12
        assert b_data["p95_latency_us"] >= b_data["p50_latency_us"] >= 0
        assert b_data["claims_production_sla"] is False

        # ORG-010: wildcard OIDC group rejected; directory revocation immediately invalidates active JWT
        wild = client.post(
            "/api/v1/auth/oidc/group-mappings",
            headers=owner_h,
            json={
                "idp_issuer": "https://idp.denlyra-synthetic.example",
                "external_group_id": "*",
                "mapped_role": "dentist",
            },
        )
        assert wild.status_code == 422

        mp = client.post(
            "/api/v1/auth/oidc/group-mappings",
            headers=owner_h,
            json={
                "idp_issuer": "https://idp.denlyra-synthetic.example",
                "external_group_id": "grp-reception-hcm",
                "branch_id": "branch-q1",
                "mapped_role": "receptionist",
            },
        )
        assert mp.status_code == 201, mp.text

        staff_res = client.post(
            "/api/v1/staff",
            headers=owner_h,
            json={"display_name": "Nhân sự OIDC", "role": "receptionist", "branch_id": "branch-q1"},
        )
        assert staff_res.status_code == 201
        staff_id = staff_res.json()["id"]
        staff_headers = _issue_headers(client, "receptionist", staff_id=staff_id)
        assert client.get("/api/v1/patients", headers=staff_headers).status_code == 200

        # Revoke group membership in directory -> token must fail with 401 immediately
        rev = client.post(
            "/api/v1/auth/oidc/directory-sync",
            headers=owner_h,
            json={
                "idp_issuer": "https://idp.denlyra-synthetic.example",
                "staff_id": staff_id,
                "external_subject": "oidc-sub-0091",
                "active_in_directory": True,
                "external_groups": [],
            },
        )
        assert rev.status_code == 201, rev.text
        assert rev.json()["sync_outcome"] == "revoked_access_immediately"
        denied = client.get("/api/v1/patients", headers=staff_headers)
        assert denied.status_code == 401


def test_int007_messaging_opt_out_and_int008_signed_payment_webhook_replay_and_reversal(tmp_path):
    with _make_client(tmp_path) as client:
        fin_h = _issue_headers(client, "finance")
        rec_h = _issue_headers(client, "receptionist")

        pat_id = client.post(
            "/api/v1/patients",
            headers=rec_h,
            json={"display_name": "BN Sandbox Webhook"},
        ).json()["id"]
        client.post(
            "/api/v1/consents",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "purpose": "data_processing",
                "template_version": "v1",
                "disclosure_summary": "Nhận tin nhắn nhắc lịch",
                "signer_name": "BN Sandbox Webhook",
            },
        )

        # INT-007: reject diagnosis leakage in message body
        phi_leak = client.post(
            "/api/v1/integrations/messaging-sandbox/send",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "channel": "zalo_zns_sandbox",
                "purpose": "appointment_reminder",
                "template_code": "TPL-REM-01",
                "rendered_body_minimized": "Nhắc hẹn điều trị chẩn đoán: viêm tủy cấp ICD-K04",
                "idempotency_key": "msg-leak-1",
            },
        )
        assert phi_leak.status_code == 422

        ok_msg = client.post(
            "/api/v1/integrations/messaging-sandbox/send",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "channel": "zalo_zns_sandbox",
                "purpose": "appointment_reminder",
                "template_code": "TPL-REM-01",
                "rendered_body_minimized": "Xin chào, nhắc lịch hẹn lúc 09:00 tại Phòng khám Demo A.",
                "idempotency_key": "msg-ok-1",
            },
        )
        assert ok_msg.status_code == 201, ok_msg.text
        assert ok_msg.json()["patient_confirmed_appointment"] is False
        assert ok_msg.json()["zero_external_egress"] is True

        # Opt-out webhook blocks subsequent messages with 403
        opt_out = client.post(
            "/api/v1/integrations/messaging-sandbox/opt-out-webhook",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "channel": "zalo_zns_sandbox",
                "keyword": "STOP",
                "provider_event_id": "zns-stop-001",
            },
        )
        assert opt_out.status_code == 201, opt_out.text

        blocked_after_stop = client.post(
            "/api/v1/integrations/messaging-sandbox/send",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "channel": "zalo_zns_sandbox",
                "purpose": "appointment_reminder",
                "template_code": "TPL-REM-01",
                "rendered_body_minimized": "Xin chào, nhắc lịch hẹn tiếp theo.",
                "idempotency_key": "msg-after-stop",
            },
        )
        assert blocked_after_stop.status_code == 403

        # INT-008: payment webhook signature verification, idempotent duplicate, tampered replay, and reversal
        now_ts = int(time.time())
        bad_sig = client.post(
            "/api/v1/integrations/payment-sandbox/webhook",
            headers=fin_h,
            json={
                "provider_code": "SYNTHETIC-VN-PAY-SANDBOX",
                "provider_event_id": "evt-pay-001",
                "event_type": "payment.succeeded",
                "patient_id": pat_id,
                "amount_vnd": 1_500_000,
                "payment_reference": "REF-001",
                "timestamp_unix": now_ts,
                "hmac_signature_hex": "0" * 64,
            },
        )
        assert bad_sig.status_code == 401

        good_sig = _sign_payment_webhook(
            CLINIC_A,
            "SYNTHETIC-VN-PAY-SANDBOX",
            "evt-pay-001",
            "payment.succeeded",
            pat_id,
            1_500_000,
            now_ts,
        )
        wh1 = client.post(
            "/api/v1/integrations/payment-sandbox/webhook",
            headers=fin_h,
            json={
                "provider_code": "SYNTHETIC-VN-PAY-SANDBOX",
                "provider_event_id": "evt-pay-001",
                "event_type": "payment.succeeded",
                "patient_id": pat_id,
                "amount_vnd": 1_500_000,
                "payment_reference": "REF-001",
                "timestamp_unix": now_ts,
                "hmac_signature_hex": good_sig,
            },
        )
        assert wh1.status_code == 201, wh1.text
        pay_id = wh1.json()["payment_id"]
        assert wh1.json()["implies_clinical_completion"] is False

        # Exact duplicate delivery is idempotent (no double ledger credit)
        wh_dup = client.post(
            "/api/v1/integrations/payment-sandbox/webhook",
            headers=fin_h,
            json={
                "provider_code": "SYNTHETIC-VN-PAY-SANDBOX",
                "provider_event_id": "evt-pay-001",
                "event_type": "payment.succeeded",
                "patient_id": pat_id,
                "amount_vnd": 1_500_000,
                "payment_reference": "REF-001",
                "timestamp_unix": now_ts,
                "hmac_signature_hex": good_sig,
            },
        )
        assert wh_dup.status_code == 201
        assert wh_dup.json()["replayed_duplicate_ignored"] is True

        # Mutated amount with same provider_event_id (even re-signed) must fail closed with 409
        mut_sig = _sign_payment_webhook(
            CLINIC_A,
            "SYNTHETIC-VN-PAY-SANDBOX",
            "evt-pay-001",
            "payment.succeeded",
            pat_id,
            9_000_000,
            now_ts,
        )
        wh_mut = client.post(
            "/api/v1/integrations/payment-sandbox/webhook",
            headers=fin_h,
            json={
                "provider_code": "SYNTHETIC-VN-PAY-SANDBOX",
                "provider_event_id": "evt-pay-001",
                "event_type": "payment.succeeded",
                "patient_id": pat_id,
                "amount_vnd": 9_000_000,
                "payment_reference": "REF-001",
                "timestamp_unix": now_ts,
                "hmac_signature_hex": mut_sig,
            },
        )
        assert wh_mut.status_code == 409

        # Bounded reversal appends debit without deleting original payment
        rev_sig = _sign_payment_webhook(
            CLINIC_A,
            "SYNTHETIC-VN-PAY-SANDBOX",
            "evt-rev-001",
            "payment.reversed",
            pat_id,
            500_000,
            now_ts,
        )
        wh_rev = client.post(
            "/api/v1/integrations/payment-sandbox/webhook",
            headers=fin_h,
            json={
                "provider_code": "SYNTHETIC-VN-PAY-SANDBOX",
                "provider_event_id": "evt-rev-001",
                "event_type": "payment.reversed",
                "patient_id": pat_id,
                "amount_vnd": 500_000,
                "payment_reference": "REF-REV-001",
                "original_payment_id": pay_id,
                "timestamp_unix": now_ts,
                "hmac_signature_hex": rev_sig,
            },
        )
        assert wh_rev.status_code == 201, wh_rev.text

        acct = client.get(f"/api/v1/patients/{pat_id}/revenue-account", headers=fin_h).json()
        assert acct["collected_gross_vnd"] == 1_500_000
        assert acct["refunded_vnd"] == 500_000
        assert acct["net_collected_vnd"] == 1_000_000
