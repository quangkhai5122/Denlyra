"""T030 negative-first & integration tests: official Zalo OA/ZNS pricing & param allowlist
contract (CRM-006), SMS brandname DLR cryptographic evidence & opt-out propagation (CRM-007),
and SPF/DKIM/DMARC verified Email sender with safe template & rolling 429 rate limit (CRM-008).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"
AUTH_SECRET = "t030-synthetic-secret-key-for-tests-32b"


def _make_client(tmp_path) -> TestClient:
    app = create_app(
        Settings(
            demo_mode=True,
            require_auth=True,
            auth_secret=AUTH_SECRET,
            db_url=f"sqlite+pysqlite:///{tmp_path / 't030.db'}",
            archive_dir=str(tmp_path / "archive"),
        )
    )
    return TestClient(app)


def _issue_headers(client: TestClient, role: str, clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_crm006_zalo_zns_blocks_unofficial_api_unconfirmed_pricing_and_undeclared_params(tmp_path):
    with _make_client(tmp_path) as client:
        owner_h = _issue_headers(client, "clinic_owner")
        rec_h = _issue_headers(client, "receptionist")

        pat_id = client.post("/api/v1/patients", headers=rec_h, json={"display_name": "BN Zalo ZNS"}).json()["id"]
        client.post(
            "/api/v1/consents",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "purpose": "data_processing",
                "template_version": "v1",
                "disclosure_summary": "Đồng thuận nhận ZNS nhắc lịch",
                "signer_name": "BN Zalo ZNS",
            },
        )

        # Unofficial scraping/personal account rejected with 422
        assert (
            client.post(
                "/api/v1/crm/channels/zalo-zns/contracts",
                headers=owner_h,
                json={
                    "oa_id_demo": "OA-SYN-01",
                    "zns_template_id": "ZNS-UNOFFICIAL",
                    "official_api_only": False,
                    "legal_basis_purpose": "data_processing",
                    "price_per_message_vnd": 300,
                    "pricing_confirmed": True,
                    "allowed_param_keys": ["appointment_time"],
                },
            ).status_code
            == 422
        )

        unpriced = client.post(
            "/api/v1/crm/channels/zalo-zns/contracts",
            headers=owner_h,
            json={
                "oa_id_demo": "OA-SYN-01",
                "zns_template_id": "ZNS-UNPRICED",
                "official_api_only": True,
                "legal_basis_purpose": "data_processing",
                "price_per_message_vnd": 300,
                "pricing_confirmed": False,
                "allowed_param_keys": ["appointment_time"],
            },
        )
        assert unpriced.status_code == 201, unpriced.text

        # Unconfirmed pricing blocks dispatch with 409
        assert (
            client.post(
                "/api/v1/crm/channels/zalo-zns/preview-dispatch",
                headers=rec_h,
                json={
                    "patient_id": pat_id,
                    "contract_id": unpriced.json()["id"],
                    "template_params": {"appointment_time": "09:30 12/12/2026"},
                },
            ).status_code
            == 409
        )

        confirmed = client.post(
            "/api/v1/crm/channels/zalo-zns/contracts",
            headers=owner_h,
            json={
                "oa_id_demo": "OA-SYN-01",
                "zns_template_id": "ZNS-REM-001",
                "official_api_only": True,
                "legal_basis_purpose": "data_processing",
                "price_per_message_vnd": 300,
                "pricing_confirmed": True,
                "allowed_param_keys": ["appointment_time", "clinic_branch"],
            },
        )
        assert confirmed.status_code == 201
        cid = confirmed.json()["id"]

        # Undeclared param key rejected with 422
        assert (
            client.post(
                "/api/v1/crm/channels/zalo-zns/preview-dispatch",
                headers=rec_h,
                json={
                    "patient_id": pat_id,
                    "contract_id": cid,
                    "template_params": {"appointment_time": "09:30", "diagnosis_secret": "viêm tủy"},
                },
            ).status_code
            == 422
        )

        ok = client.post(
            "/api/v1/crm/channels/zalo-zns/preview-dispatch",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "contract_id": cid,
                "template_params": {"appointment_time": "09:30 12/12/2026", "clinic_branch": "Chi nhánh Q1"},
            },
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["live_external_egress"] is False
        assert ok.json()["quoted_cost_vnd"] == 300


def test_crm007_sms_dlr_evidence_and_opt_out_propagation(tmp_path):
    with _make_client(tmp_path) as client:
        rec_h = _issue_headers(client, "receptionist")
        pat_id = client.post("/api/v1/patients", headers=rec_h, json={"display_name": "BN SMS DLR"}).json()["id"]
        client.post(
            "/api/v1/consents",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "purpose": "data_processing",
                "template_version": "v1",
                "disclosure_summary": "Nhận SMS nhắc lịch",
                "signer_name": "BN SMS DLR",
            },
        )

        sms = client.post(
            "/api/v1/crm/channels/sms/send-sandbox",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "brandname_sender": "DENLYRA_DEMO",
                "purpose": "data_processing",
                "message_ascii_or_ucs2": "Denlyra Demo nhac lich hen luc 14:00 ngay mai.",
                "idempotency_key": "sms-dlr-1",
            },
        )
        assert sms.status_code == 201, sms.text
        disp_id = sms.json()["id"]
        assert sms.json()["patient_confirmed_appointment"] is False

        dlr = client.post(
            f"/api/v1/crm/channels/sms/dispatches/{disp_id}/dlr-receipt",
            headers=rec_h,
            json={
                "provider_dlr_code": "DLR-200-STOP",
                "carrier_status": "carrier_delivered",
                "opt_out_triggered": True,
            },
        )
        assert dlr.status_code == 201, dlr.text
        assert len(dlr.json()["dlr_evidence_sha256"]) == 64

        # Next SMS blocked with 403 because DLR propagated opt-out
        blocked = client.post(
            "/api/v1/crm/channels/sms/send-sandbox",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "brandname_sender": "DENLYRA_DEMO",
                "purpose": "data_processing",
                "message_ascii_or_ucs2": "Tin nhan tiep theo sau opt-out.",
                "idempotency_key": "sms-dlr-2",
            },
        )
        assert blocked.status_code == 403


def test_crm008_email_requires_verified_sender_safe_template_and_enforces_429_rate_limit(tmp_path):
    with _make_client(tmp_path) as client:
        owner_h = _issue_headers(client, "clinic_owner")
        rec_h = _issue_headers(client, "receptionist")

        pat_id = client.post("/api/v1/patients", headers=rec_h, json={"display_name": "BN Email"}).json()["id"]
        client.post(
            "/api/v1/consents",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "purpose": "data_processing",
                "template_version": "v1",
                "disclosure_summary": "Nhận email xác nhận lịch",
                "signer_name": "BN Email",
            },
        )

        unver = client.post(
            "/api/v1/crm/channels/email/senders",
            headers=owner_h,
            json={
                "sender_address": "unverified@denlyra-clinic.local",
                "spf_verified": True,
                "dkim_verified": False,
                "dmarc_verified": True,
                "hourly_rate_limit": 2,
            },
        )
        assert unver.status_code == 201
        assert (
            client.post(
                "/api/v1/crm/channels/email/send-sandbox",
                headers=rec_h,
                json={
                    "patient_id": pat_id,
                    "sender_id": unver.json()["id"],
                    "purpose": "data_processing",
                    "subject_minimized": "Nhắc lịch hẹn",
                    "body_safe_text": "Xin chào quý khách, hẹn gặp lúc 09:00.",
                },
            ).status_code
            == 409
        )

        ver = client.post(
            "/api/v1/crm/channels/email/senders",
            headers=owner_h,
            json={
                "sender_address": "notice@denlyra-clinic.local",
                "spf_verified": True,
                "dkim_verified": True,
                "dmarc_verified": True,
                "hourly_rate_limit": 2,
            },
        )
        assert ver.status_code == 201
        sid = ver.json()["id"]

        # Unsafe script/tracking pixel rejected with 422
        assert (
            client.post(
                "/api/v1/crm/channels/email/send-sandbox",
                headers=rec_h,
                json={
                    "patient_id": pat_id,
                    "sender_id": sid,
                    "purpose": "data_processing",
                    "subject_minimized": "Nhắc lịch hẹn",
                    "body_safe_text": "Xin chào <script>alert(1)</script>",
                },
            ).status_code
            == 422
        )

        # Rate limit = 2 per hour -> 1st and 2nd succeed (201), 3rd blocked with 429
        for i in range(2):
            r = client.post(
                "/api/v1/crm/channels/email/send-sandbox",
                headers=rec_h,
                json={
                    "patient_id": pat_id,
                    "sender_id": sid,
                    "purpose": "data_processing",
                    "subject_minimized": f"Nhắc lịch hẹn #{i + 1}",
                    "body_safe_text": "Xin chào quý khách, lịch hẹn tại phòng khám đã ghi nhận.",
                },
            )
            assert r.status_code == 201, r.text

        over = client.post(
            "/api/v1/crm/channels/email/send-sandbox",
            headers=rec_h,
            json={
                "patient_id": pat_id,
                "sender_id": sid,
                "purpose": "data_processing",
                "subject_minimized": "Nhắc lịch hẹn #3",
                "body_safe_text": "Xin chào quý khách, vượt ngưỡng giới hạn gửi.",
            },
        )
        assert over.status_code == 429
