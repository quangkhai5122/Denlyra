"""T023 PHI-redacted structured telemetry (OPS-005), isolated per-clinic onboarding
configuration (OPS-010), owner-consent-gated support diagnostics (OPS-012), forensic
security incident & breach workflow (SEC-012), and exact-pinning SBOM supply-chain
verifier (SEC-013).

Written BEFORE T023 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"
CLINIC_B = "22222222-2222-4222-8222-222222222222"


def _headers(client: TestClient, role: str, clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_phi_redacted_telemetry_never_records_notes_or_patient_identifiers(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'telemetry_ops.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        receptionist = _headers(client, "receptionist")

        secret_patient_name = "Nguyễn Thị Tuyệt Mật Không Ghi Log"
        secret_note_text = "Bệnh nhân đau tủy răng 36 cấp tính không được lộ vào telemetry"
        client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": secret_patient_name, "birth_year": 1991},
        )

        # OPS-005: Emit telemetry carrying sensitive keys, raw phone, patient name, and JWT
        emitted = client.post(
            "/api/v1/ops/telemetry-events",
            headers=receptionist,
            json={
                "trace_id": "trace-ops-005-redaction-0001",
                "span_name": "encounter.save_draft",
                "severity": "warn",
                "attributes": {
                    "note_content": secret_note_text,
                    "patient_name": secret_patient_name,
                    "free_debug_msg": f"Liên hệ {secret_patient_name} qua 0909888777 hoặc token eyJhbGciOiJIUzI1NiJ9.payload.sig",
                    "http_status": 409,
                    "module": "clinical",
                },
            },
        )
        assert emitted.status_code == 201, emitted.text
        eb = emitted.json()
        assert eb["contains_phi_or_note_text"] is False
        assert eb["redacted_field_count"] >= 3
        assert secret_patient_name not in emitted.text
        assert secret_note_text not in emitted.text
        assert "0909888777" not in emitted.text
        assert "eyJhbGciOiJIUzI1NiJ9" not in emitted.text

        listed = client.get("/api/v1/ops/telemetry-events", headers=owner)
        assert listed.status_code == 200
        assert secret_patient_name not in listed.text
        assert secret_note_text not in listed.text
        assert "0909888777" not in listed.text


def test_isolated_clinic_onboarding_and_consent_gated_support_diagnostics(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'onboard_sup.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner_a = _headers(client, "clinic_owner", clinic_id=CLINIC_A)
        owner_b = _headers(client, "clinic_owner", clinic_id=CLINIC_B)
        receptionist_a = _headers(client, "receptionist", clinic_id=CLINIC_A)

        secret_pat_a = "BN_KHONG_XUAT_TRONG_SUPPORT_BUNDLE"
        client.post(
            "/api/v1/patients",
            headers=receptionist_a,
            json={"display_name": secret_pat_a, "birth_year": 1987},
        )

        # Negative 1 (OPS-010): Receptionist cannot modify clinic onboarding config -> 403
        assert (
            client.post(
                "/api/v1/ops/onboarding-config",
                headers=receptionist_a,
                json={
                    "configured_roles": ["dentist", "receptionist"],
                    "legacy_field_mapping": {"legacy_code": "patient_code"},
                    "mark_ready": False,
                },
            ).status_code
            == 403
        )

        # Seed price catalog & quarantined form in Clinic A ONLY
        assert (
            client.post(
                "/api/v1/finance/price-catalog",
                headers=owner_a,
                json={
                    "service_code": "EXAM-GEN-01",
                    "name_vi": "Khám tổng quát RHM",
                    "category": "general",
                    "unit_price_vnd": 200000,
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/clinical-forms/templates",
                headers=owner_a,
                json={
                    "official_code": "16/BV-01-ONB",
                    "title": "Phiếu khám RHM ngoại trú giả lập",
                    "source_citation": "Circular 32/2023/TT-BYT synthetic draft",
                    "source_sha256": "a" * 64,
                    "fields": [
                        {
                            "field_code": "drug_allergy",
                            "label_vi": "Tiền sử dị ứng thuốc",
                            "field_type": "tri_state",
                            "required_when": "always",
                            "allow_unknown": True,
                        }
                    ],
                },
            ).status_code
            == 201
        )

        # Clinic A succeeds with mark_ready=True
        onb_a = client.post(
            "/api/v1/ops/onboarding-config",
            headers=owner_a,
            json={
                "configured_roles": ["clinic_owner", "dentist", "receptionist", "finance"],
                "legacy_field_mapping": {"ma_bn_cu": "legacy_patient_id"},
                "mark_ready": True,
            },
        )
        assert onb_a.status_code == 201, onb_a.text
        assert onb_a.json()["readiness_status"] == "configured_synthetic_ready"

        # Negative 2 (OPS-010): Clinic B has NOT configured its own catalog/forms -> mark_ready=True fails 409!
        assert (
            client.post(
                "/api/v1/ops/onboarding-config",
                headers=owner_b,
                json={
                    "configured_roles": ["clinic_owner", "dentist"],
                    "legacy_field_mapping": {"ma_bn_cu": "legacy_patient_id"},
                    "mark_ready": True,
                },
            ).status_code
            == 409
        )

        # Negative 3 (OPS-012): Support diagnostic export WITHOUT customer consent grant -> 403
        assert (
            client.post(
                "/api/v1/ops/support/diagnostic-export",
                headers=owner_a,
                json={"grant_id": "missing-grant", "include_patient_records": False},
            ).status_code
            == 403
        )

        # Negative 4 (OPS-012): Requesting live patient records in support grant -> 409
        assert (
            client.post(
                "/api/v1/ops/support/grants",
                headers=owner_a,
                json={
                    "ticket_reference": "SUP-2026-001",
                    "ttl_seconds": 600,
                    "allow_live_patient_records": True,
                },
            ).status_code
            == 409
        )

        # Valid owner-consented redacted diagnostic grant -> export succeeds without PHI -> revoking blocks reuse (403)
        gr = client.post(
            "/api/v1/ops/support/grants",
            headers=owner_a,
            json={
                "ticket_reference": "SUP-2026-002",
                "ttl_seconds": 600,
                "allow_live_patient_records": False,
            },
        )
        assert gr.status_code == 201, gr.text
        grant_id = gr.json()["id"]

        # Negative 5 (OPS-012): Even with valid grant, include_patient_records=True on export -> 409
        assert (
            client.post(
                "/api/v1/ops/support/diagnostic-export",
                headers=owner_a,
                json={"grant_id": grant_id, "include_patient_records": True},
            ).status_code
            == 409
        )

        diag = client.post(
            "/api/v1/ops/support/diagnostic-export",
            headers=owner_a,
            json={"grant_id": grant_id, "include_patient_records": False},
        )
        assert diag.status_code == 201, diag.text
        assert secret_pat_a not in diag.text
        assert len(diag.json()["bundle_sha256"]) == 64

        assert (
            client.post(f"/api/v1/ops/support/grants/{grant_id}/revoke", headers=owner_a).status_code
            == 200
        )
        assert (
            client.post(
                "/api/v1/ops/support/diagnostic-export",
                headers=owner_a,
                json={"grant_id": grant_id, "include_patient_records": False},
            ).status_code
            == 403
        )


def test_security_incident_breach_workflow_and_sbom_supply_chain_verifier(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'sec_sbom.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        receptionist = _headers(client, "receptionist")

        # SEC-012: Open critical potential breach -> preserves current audit chain head hash
        inc = client.post(
            "/api/v1/security/incidents",
            headers=owner,
            json={
                "severity": "critical_potential_breach",
                "incident_type": "token_compromise",
                "summary": "Phát hiện phiên truy cập bất thường từ thiết bị trạm giả lập",
            },
        )
        assert inc.status_code == 201, inc.text
        ib = inc.json()
        inc_id = ib["id"]
        assert ib["containment_status"] == "triaged_evidence_preserved"
        assert len(ib["preserved_audit_head_hash"]) == 64

        # Negative 1 (SEC-012): Receptionist denied reading security incident cases -> 403
        assert client.get("/api/v1/security/incidents", headers=receptionist).status_code == 403

        # Negative 2 (SEC-012): Cannot close critical breach without counsel guidance & notification decision -> 409
        assert (
            client.post(
                f"/api/v1/security/incidents/{inc_id}/transition",
                headers=owner,
                json={
                    "next_status": "closed",
                    "detail_note": "Thử đóng vội chưa có ý kiến pháp chế",
                },
            ).status_code
            == 409
        )

        # Record containment + counsel guidance -> then close succeeds while preserved_audit_head_hash stays immutable
        assert (
            client.post(
                f"/api/v1/security/incidents/{inc_id}/transition",
                headers=owner,
                json={
                    "next_status": "counsel_reviewed",
                    "detail_note": "Đã thu hồi token JTI và cô lập máy trạm",
                    "counsel_guidance_note": "Luật sư đánh giá dữ liệu giả lập không chứa dữ liệu cá nhân thật",
                    "notification_decision": "internal_postmortem_only_synthetic_env",
                },
            ).status_code
            == 200
        )
        closed = client.post(
            f"/api/v1/security/incidents/{inc_id}/transition",
            headers=owner,
            json={
                "next_status": "closed",
                "detail_note": "Hoàn tất biên bản sự cố và cập nhật khóa phiên",
            },
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()["containment_status"] == "closed"
        assert closed.json()["preserved_audit_head_hash"] == ib["preserved_audit_head_hash"]

        # Negative 3 (SEC-013): Unpinned dependency line in constraints override rejected -> 409
        assert (
            client.post(
                "/api/v1/security/supply-chain/verify",
                headers=owner,
                json={"constraints_override_text": "fastapi==0.115.6\nrogue-pkg>=1.0.0\n"},
            ).status_code
            == 409
        )

        # Valid live repository lockfile + constraints SBOM verification
        sbom = client.post(
            "/api/v1/security/supply-chain/verify",
            headers=owner,
            json={},
        )
        assert sbom.status_code == 201, sbom.text
        sb = sbom.json()
        assert sb["status"] == "verified_pinned"
        assert sb["unpinned_dependency_count"] == 0
        assert sb["sbom_component_count"] >= 5
        assert len(sb["sbom_canonical_sha256"]) == 64
        assert len(sb["attestation_hmac_sha256"]) == 64
