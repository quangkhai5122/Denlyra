"""T029 negative-first & integration tests: Vietnam-region IaC blueprint & secret guard (OPS-003),
partner-scoped private dental insurance claim sandbox blocking BHYT & auto-settlement (FIN-012),
licensed de-identified LoRA measurable lift gate (AI-012), and simulation-only clinician
treatment plan version attestation (TRT-004).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"
AUTH_SECRET = "t029-synthetic-secret-key-for-tests-32b"


def _make_client(tmp_path) -> TestClient:
    app = create_app(
        Settings(
            demo_mode=True,
            require_auth=True,
            auth_secret=AUTH_SECRET,
            db_url=f"sqlite+pysqlite:///{tmp_path / 't029.db'}",
            archive_dir=str(tmp_path / "archive"),
        )
    )
    return TestClient(app)


def _issue_headers(client: TestClient, role: str, clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_ops003_iac_region_and_secret_guard_blocks_foreign_region_inline_secrets_and_live_apply(tmp_path):
    with _make_client(tmp_path) as client:
        owner_h = _issue_headers(client, "clinic_owner")

        # Foreign region rejected with 409
        bad_region = client.post(
            "/api/v1/ops/iac-blueprints/validate",
            headers=owner_h,
            json={
                "blueprint_name": "prod-foreign-attempt",
                "primary_region": "us-east-1",
                "dpa_contract_reference": "DPA-SYN-2026-01",
                "environment_variables": {"DB_URL": "secret_ref://kms/vn/db-url"},
            },
        )
        assert bad_region.status_code == 409

        # Inline plaintext secret rejected with 422
        inline_sec = client.post(
            "/api/v1/ops/iac-blueprints/validate",
            headers=owner_h,
            json={
                "blueprint_name": "vn-inline-secret",
                "primary_region": "vn-ho-chi-minh-1",
                "dpa_contract_reference": "DPA-SYN-2026-01",
                "environment_variables": {"DB_URL": "postgresql://admin:SuperSecret123@10.0.0.5/db"},
            },
        )
        assert inline_sec.status_code == 422

        # Live cloud provisioning blocked with 409
        live_apply = client.post(
            "/api/v1/ops/iac-blueprints/validate",
            headers=owner_h,
            json={
                "blueprint_name": "vn-live-apply",
                "primary_region": "vn-ho-chi-minh-1",
                "dpa_contract_reference": "DPA-SYN-2026-01",
                "environment_variables": {"DB_URL": "secret_ref://kms/vn/db-url"},
                "apply_live_cloud_provisioning": True,
            },
        )
        assert live_apply.status_code == 409

        ok = client.post(
            "/api/v1/ops/iac-blueprints/validate",
            headers=owner_h,
            json={
                "blueprint_name": "vn-hcm-single-clinic-blueprint",
                "primary_region": "vn-ho-chi-minh-1",
                "dpa_contract_reference": "DPA-SYN-2026-01",
                "environment_variables": {
                    "DENLYRA_DB_DSN": "secret_ref://vault/vn-hcm/db-dsn",
                    "DENLYRA_KEK_ID": "secret_ref://kms/vn-hcm/tenant-kek",
                },
            },
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["live_cloud_provisioned"] is False
        assert ok.json()["secrets_externalized"] is True


def test_fin012_insurance_claim_blocks_bhyt_and_autosettle_and_ai012_lora_requires_license_and_lift(tmp_path):
    with _make_client(tmp_path) as client:
        owner_h = _issue_headers(client, "clinic_owner")
        fin_h = _issue_headers(client, "finance")
        doc_h = _issue_headers(client, "dentist")

        # FIN-012: block unverified government BHYT portal
        bhyt = client.post(
            "/api/v1/finance/insurance-partners",
            headers=owner_h,
            json={
                "partner_code": "GOV-BHYT",
                "partner_name": "Cổng BHYT chưa cấp phép",
                "integration_kind": "government_bhyt_portal",
            },
        )
        assert bhyt.status_code == 409

        tpa = client.post(
            "/api/v1/finance/insurance-partners",
            headers=owner_h,
            json={
                "partner_code": "TPA-DENTAL-SYN-01",
                "partner_name": "Đối tác Bảo hiểm Nha khoa Tư nhân (Sandbox)",
                "integration_kind": "private_dental_tpa_sandbox",
            },
        )
        assert tpa.status_code == 201, tpa.text
        partner_id = tpa.json()["id"]

        pat_id = client.post("/api/v1/patients", headers=owner_h, json={"display_name": "BN Bảo Hiểm"}).json()["id"]
        chg_id = client.post(
            "/api/v1/finance/charges",
            headers=fin_h,
            json={"patient_id": pat_id, "label": "Trám răng sâu ngà", "amount_vnd": 800_000, "idempotency_key": "ins-c1"},
        ).json()["id"]

        # Without financial + data_processing consents -> 403
        no_consent = client.post(
            "/api/v1/finance/insurance-claims",
            headers=fin_h,
            json={
                "patient_id": pat_id,
                "partner_id": partner_id,
                "charge_id": chg_id,
                "claimed_amount_vnd": 500_000,
            },
        )
        assert no_consent.status_code == 403

        for purpose in ("financial", "data_processing"):
            client.post(
                "/api/v1/consents",
                headers=owner_h,
                json={
                    "patient_id": pat_id,
                    "purpose": purpose,
                    "template_version": "v1",
                    "disclosure_summary": f"Đồng thuận {purpose}",
                    "signer_name": "BN Bảo Hiểm",
                },
            )

        # Auto-settlement forbidden -> 409
        assert (
            client.post(
                "/api/v1/finance/insurance-claims",
                headers=fin_h,
                json={
                    "patient_id": pat_id,
                    "partner_id": partner_id,
                    "charge_id": chg_id,
                    "claimed_amount_vnd": 500_000,
                    "auto_settle_as_paid": True,
                },
            ).status_code
            == 409
        )

        claim = client.post(
            "/api/v1/finance/insurance-claims",
            headers=fin_h,
            json={
                "patient_id": pat_id,
                "partner_id": partner_id,
                "charge_id": chg_id,
                "claimed_amount_vnd": 500_000,
            },
        )
        assert claim.status_code == 201, claim.text
        assert claim.json()["auto_settled_payment"] is False
        assert claim.json()["called_government_bhyt_api"] is False

        # AI-012: block scraped/unlicensed data (403), PII leak (422), and negative lift (409)
        assert (
            client.post(
                "/api/v1/ai/adaptation-runs/evaluate",
                headers=doc_h,
                json={
                    "adapter_code": "lora-scraped",
                    "base_model_digest": "sha256:" + "a" * 64,
                    "dataset_license_id": "scraped_web",
                    "deidentification_verified": True,
                    "dataset_sample_texts": ["răng 36 sâu ngà"],
                    "baseline_f1_bp": 8000,
                    "candidate_f1_bp": 8500,
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/ai/adaptation-runs/evaluate",
                headers=doc_h,
                json={
                    "adapter_code": "lora-pii",
                    "base_model_digest": "sha256:" + "a" * 64,
                    "dataset_license_id": "CC-BY-4.0-SYNTHETIC",
                    "deidentification_verified": True,
                    "dataset_sample_texts": ["Bệnh nhân SĐT 0901234567 khám răng 16"],
                    "baseline_f1_bp": 8000,
                    "candidate_f1_bp": 8500,
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/ai/adaptation-runs/evaluate",
                headers=doc_h,
                json={
                    "adapter_code": "lora-no-lift",
                    "base_model_digest": "sha256:" + "a" * 64,
                    "dataset_license_id": "CC-BY-4.0-SYNTHETIC",
                    "deidentification_verified": True,
                    "dataset_sample_texts": ["răng 36 mặt nhai sâu ngà nông"],
                    "baseline_f1_bp": 8400,
                    "candidate_f1_bp": 8450,
                    "min_required_lift_bp": 150,
                },
            ).status_code
            == 409
        )

        lora_ok = client.post(
            "/api/v1/ai/adaptation-runs/evaluate",
            headers=doc_h,
            json={
                "adapter_code": "lora-vn-dental-syn-v1",
                "base_model_digest": "sha256:" + "b" * 64,
                "dataset_license_id": "CC-BY-4.0-SYNTHETIC",
                "deidentification_verified": True,
                "dataset_sample_texts": ["răng 36 mặt nhai sâu ngà nông", "mão sứ zirconia răng 16"],
                "baseline_f1_bp": 8100,
                "candidate_f1_bp": 8420,
                "min_required_lift_bp": 150,
            },
        )
        assert lora_ok.status_code == 201, lora_ok.text
        assert lora_ok.json()["measured_lift_bp"] == 320
        assert lora_ok.json()["deployed_to_clinical_production"] is False
        assert lora_ok.json()["wrote_to_emr"] is False


def test_trt004_plan_review_attestation_binds_exact_version_and_blocks_legal_approval_claim(tmp_path):
    with _make_client(tmp_path) as client:
        doc_h = _issue_headers(client, "dentist")
        pat_id = client.post("/api/v1/patients", headers=doc_h, json={"display_name": "BN Phác Đồ"}).json()["id"]
        plan_id = client.post(
            "/api/v1/treatment-plans",
            headers=doc_h,
            json={"patient_id": pat_id, "title": "Phác đồ phục hình răng 46"},
        ).json()["id"]
        client.post(
            f"/api/v1/treatment-plans/{plan_id}/tasks",
            headers=doc_h,
            json={"title": "Sửa soạn cùi răng 46", "phase": "phase_1", "owner_role": "dentist"},
        )

        # Claiming legal clinical approval must fail closed with 409
        legal_claim = client.post(
            f"/api/v1/treatment-plans/{plan_id}/review-attestations",
            headers=doc_h,
            json={
                "expected_version_number": 1,
                "approval_mode": "legal_clinical_approval",
                "review_note_vi": "Thử tuyên bố duyệt pháp lý",
            },
        )
        assert legal_claim.status_code == 409

        # Wrong version number -> 409
        wrong_ver = client.post(
            f"/api/v1/treatment-plans/{plan_id}/review-attestations",
            headers=doc_h,
            json={
                "expected_version_number": 2,
                "approval_mode": "demo_simulation_only",
                "review_note_vi": "Sai phiên bản",
            },
        )
        assert wrong_ver.status_code == 409

        ok = client.post(
            f"/api/v1/treatment-plans/{plan_id}/review-attestations",
            headers=doc_h,
            json={
                "expected_version_number": 1,
                "approval_mode": "demo_simulation_only",
                "review_note_vi": "Xác nhận mô phỏng phiên bản v1 phục vụ kiểm thử",
            },
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["is_legal_clinical_approval"] is False
        assert ok.json()["simulation_label"] == "demo_reviewed_simulation_NOT_dentist_approval"
        assert len(ok.json()["version_canonical_sha256"]) == 64
