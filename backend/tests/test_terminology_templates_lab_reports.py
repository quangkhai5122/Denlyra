"""T025 versioned medical code sets without guessed mappings (EMR-016), clinic-reviewed
specialty plan templates (TRT-015), PHI-free lab price list & invoice reconciliation
(LAB-010), labeled non-diagnostic longitudinal imaging overlays (ODN-009), and
multi-branch aggregate governance + DLY1-encrypted PHI-free scheduled report exports
(RPT-009, RPT-010).

Written BEFORE T025 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

import base64
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


def test_versioned_terminology_no_guessed_mapping_and_reviewed_specialty_templates(
    tmp_path: Path,
):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'term_tpl.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        coordinator = _headers(client, "treatment_coordinator")
        receptionist = _headers(client, "receptionist")

        pat = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Thuật Ngữ & Mẫu Chuyên Khoa", "birth_year": 1991},
        ).json()["id"]

        # Negative 1 (EMR-016): Receptionist cannot publish authoritative terminology codes -> 403
        assert (
            client.post(
                "/api/v1/terminology/codes",
                headers=receptionist,
                json={
                    "code_system": "ICD-10-VN-DEMO",
                    "system_version": "2026.1",
                    "code": "K02.1",
                    "display_vi": "Sâu ngà răng (mô phỏng)",
                },
            ).status_code
            == 403
        )

        assert (
            client.post(
                "/api/v1/terminology/codes",
                headers=dentist,
                json={
                    "code_system": "ICD-10-VN-DEMO",
                    "system_version": "2026.1",
                    "code": "K02.1",
                    "display_vi": "Sâu ngà răng (mô phỏng)",
                },
            ).status_code
            == 201
        )

        # Negative 2 (EMR-016): Guessed/fuzzy mapping method rejected -> 422
        assert (
            client.post(
                "/api/v1/terminology/mappings",
                headers=dentist,
                json={
                    "source_code": "LOCAL-CARIES-DENTIN",
                    "target_code_system": "ICD-10-VN-DEMO",
                    "target_system_version": "2026.1",
                    "target_code": "K02.1",
                    "equivalence": "exact",
                    "mapping_method": "ai_guessed",
                },
            ).status_code
            == 422
        )

        # Unmapped lookup abstains without guessing
        unmapped = client.get(
            "/api/v1/terminology/resolve?source_code=UNMAPPED-999&target_code_system=ICD-10-VN-DEMO",
            headers=dentist,
        ).json()
        assert unmapped["mapped"] is False
        assert unmapped["guessed_fallback_used"] is False

        assert (
            client.post(
                "/api/v1/terminology/mappings",
                headers=dentist,
                json={
                    "source_code": "LOCAL-CARIES-DENTIN",
                    "target_code_system": "ICD-10-VN-DEMO",
                    "target_system_version": "2026.1",
                    "target_code": "K02.1",
                    "equivalence": "exact",
                    "mapping_method": "clinician_verified_exact",
                },
            ).status_code
            == 201
        )
        resolved = client.get(
            "/api/v1/terminology/resolve?source_code=LOCAL-CARIES-DENTIN&target_code_system=ICD-10-VN-DEMO",
            headers=dentist,
        ).json()
        assert resolved["mapped"] is True
        assert resolved["target_code"] == "K02.1"

        # Negative 3 (TRT-015): Generic internet protocol rejected -> 422
        assert (
            client.post(
                "/api/v1/treatment-plans/specialty-templates",
                headers=coordinator,
                json={
                    "template_code": "IMP-2STAGE-01",
                    "specialty": "implant",
                    "title_vi": "Mẫu cấy ghép 2 giai đoạn giả lập",
                    "source_kind": "generic_internet_protocol",
                    "tasks_blueprint": [
                        {"phase": "Phẫu thuật", "title": "Đặt trụ Implant"},
                        {"phase": "Phục hình", "title": "Gắn mão sứ trên trụ"},
                    ],
                },
            ).status_code
            == 422
        )

        tpl_res = client.post(
            "/api/v1/treatment-plans/specialty-templates",
            headers=coordinator,
            json={
                "template_code": "IMP-2STAGE-01",
                "specialty": "implant",
                "title_vi": "Mẫu cấy ghép 2 giai đoạn phòng khám duyệt",
                "source_kind": "clinic_clinician_authored",
                "tasks_blueprint": [
                    {"phase": "Phẫu thuật", "title": "Đặt trụ Implant giai đoạn 1"},
                    {"phase": "Phục hình", "title": "Lấy dấu & gắn mão sứ giai đoạn 2"},
                ],
            },
        )
        assert tpl_res.status_code == 201, tpl_res.text
        tpl_id = tpl_res.json()["id"]

        # Negative 4 (TRT-015): Cannot instantiate patient plan before clinic clinician reviews template -> 409
        assert (
            client.post(
                "/api/v1/treatment-plans/from-specialty-template",
                headers=coordinator,
                json={"patient_id": pat, "template_id": tpl_id},
            ).status_code
            == 409
        )
        # Coordinator cannot review clinical specialty template -> 403
        assert (
            client.post(
                f"/api/v1/treatment-plans/specialty-templates/{tpl_id}/review",
                headers=coordinator,
                json={},
            ).status_code
            == 403
        )

        # Dentist reviews template -> coordinator instantiates draft plan with sequential task dependency
        assert (
            client.post(
                f"/api/v1/treatment-plans/specialty-templates/{tpl_id}/review",
                headers=dentist,
                json={},
            ).status_code
            == 200
        )
        inst = client.post(
            "/api/v1/treatment-plans/from-specialty-template",
            headers=coordinator,
            json={"patient_id": pat, "template_id": tpl_id},
        )
        assert inst.status_code == 201, inst.text
        assert inst.json()["version_status"] == "draft"
        assert inst.json()["created_task_count"] == 2


def test_phi_free_lab_invoicing_and_labeled_non_diagnostic_imaging_overlay(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'lab_odn.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        coordinator = _headers(client, "treatment_coordinator")
        receptionist = _headers(client, "receptionist")

        secret_patient_name = "BN_BI_MAT_KHONG_LO_CHO_XUONG_LAB"
        pat = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": secret_patient_name, "birth_year": 1986},
        ).json()["id"]
        pat_other = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Khác", "birth_year": 1994},
        ).json()["id"]

        lc = client.post(
            "/api/v1/lab-cases",
            headers=coordinator,
            json={"patient_id": pat, "title": "Mão sứ Zirconia R26"},
        ).json()["id"]

        assert (
            client.post(
                "/api/v1/lab/price-list",
                headers=coordinator,
                json={
                    "vendor_code": "LAB-SAIGON-01",
                    "prosthesis_code": "ZIRC-CROWN-STD",
                    "unit_price_vnd": 1800000,
                    "remake_surcharge_vnd": 400000,
                },
            ).status_code
            == 201
        )

        # Negative 1 (LAB-010): Vendor invoice reference containing patient name/phone PII rejected -> 422
        assert (
            client.post(
                f"/api/v1/lab-cases/{lc}/invoice-reconciliations",
                headers=coordinator,
                json={
                    "vendor_code": "LAB-SAIGON-01",
                    "prosthesis_code": "ZIRC-CROWN-STD",
                    "billed_amount_vnd": 1800000,
                    "vendor_invoice_ref": f"INV-{secret_patient_name}-0909111222",
                },
            ).status_code
            == 422
        )

        # Overbilled vendor invoice flags discrepancy_flagged and emits ZERO patient identifiers
        rec = client.post(
            f"/api/v1/lab-cases/{lc}/invoice-reconciliations",
            headers=coordinator,
            json={
                "vendor_code": "LAB-SAIGON-01",
                "prosthesis_code": "ZIRC-CROWN-STD",
                "billed_amount_vnd": 2100000,
                "vendor_invoice_ref": "LAB-INV-2026-0088",
            },
        )
        assert rec.status_code == 201, rec.text
        assert secret_patient_name not in rec.text
        assert pat not in rec.text
        rb = rec.json()
        assert rb["contains_phi"] is False
        assert rb["contracted_amount_vnd"] == 1800000
        assert rb["variance_vnd"] == 300000
        assert rb["reconciliation_status"] == "discrepancy_flagged"

        # ODN-009: Upload two encrypted imaging archive objects for pat and one for pat_other
        obj_base = client.post(
            "/api/v1/archive/objects",
            headers=dentist,
            json={
                "patient_id": pat,
                "object_kind": "clinical_attachment",
                "media_type": "image/png",
                "original_filename": "xray-r26-t0.png",
                "content_b64": base64.b64encode(b"FAKE-PNG-T0").decode("ascii"),
            },
        ).json()["id"]
        obj_follow = client.post(
            "/api/v1/archive/objects",
            headers=dentist,
            json={
                "patient_id": pat,
                "object_kind": "clinical_attachment",
                "media_type": "image/png",
                "original_filename": "xray-r26-t6m.png",
                "content_b64": base64.b64encode(b"FAKE-PNG-T6M").decode("ascii"),
            },
        ).json()["id"]
        obj_wrong_pat = client.post(
            "/api/v1/archive/objects",
            headers=dentist,
            json={
                "patient_id": pat_other,
                "object_kind": "clinical_attachment",
                "media_type": "image/png",
                "original_filename": "other.png",
                "content_b64": base64.b64encode(b"OTHER").decode("ascii"),
            },
        ).json()["id"]

        # Negative 2 (ODN-009): Claiming auto-diagnosis or cross-patient image rejected -> 409 / 422
        assert (
            client.post(
                f"/api/v1/patients/{pat}/odontogram/imaging-overlays",
                headers=dentist,
                json={
                    "tooth_code": "26",
                    "baseline_archive_object_id": obj_base,
                    "followup_archive_object_id": obj_follow,
                    "alignment_label_vi": "Đối chiếu 6 tháng sau điều trị nội nha",
                    "claim_auto_diagnosis": True,
                },
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/patients/{pat}/odontogram/imaging-overlays",
                headers=dentist,
                json={
                    "tooth_code": "26",
                    "baseline_archive_object_id": obj_base,
                    "followup_archive_object_id": obj_wrong_pat,
                    "alignment_label_vi": "Nhầm phim bệnh nhân khác",
                },
            ).status_code
            == 422
        )

        ov = client.post(
            f"/api/v1/patients/{pat}/odontogram/imaging-overlays",
            headers=dentist,
            json={
                "tooth_code": "26",
                "baseline_archive_object_id": obj_base,
                "followup_archive_object_id": obj_follow,
                "alignment_label_vi": "Đối chiếu 6 tháng sau điều trị nội nha (chỉ hiển thị trực quan)",
            },
        )
        assert ov.status_code == 201, ov.text
        assert ov.json()["auto_diagnosis_generated"] is False
        assert (
            ov.json()["visualization_provenance_label"]
            == "SYNTHETIC_VISUAL_COMPARISON_NOT_DIAGNOSTIC"
        )


def test_multibranch_report_governance_and_encrypted_phi_free_scheduled_exports(
    tmp_path: Path,
):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'rpt_exp.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner_a = _headers(client, "clinic_owner", clinic_id=CLINIC_A)
        owner_b = _headers(client, "clinic_owner", clinic_id=CLINIC_B)

        secret_b = "BN_CHI_NHANH_B_KHONG_XUAT_BAO_CAO"
        client.post(
            "/api/v1/patients",
            headers=owner_b,
            json={"display_name": secret_b, "birth_year": 1990},
        )

        # Negative 1 (RPT-010): include_phi=True rejected -> 409
        assert (
            client.post(
                "/api/v1/reports/scheduled-exports",
                headers=owner_a,
                json={
                    "report_kind": "single_clinic_kpi",
                    "recipient_email": "owner@denlyra-clinic.local",
                    "include_phi": True,
                },
            ).status_code
            == 409
        )

        # Negative 2 (RPT-010): Unallowlisted external email domain rejected -> 403
        assert (
            client.post(
                "/api/v1/reports/scheduled-exports",
                headers=owner_a,
                json={
                    "report_kind": "single_clinic_kpi",
                    "recipient_email": "leak@gmail.com",
                    "include_phi": False,
                },
            ).status_code
            == 403
        )

        # Negative 3 (RPT-009): Multi-branch report export without OwnerBranchScopeGrant -> 403
        assert (
            client.post(
                "/api/v1/reports/scheduled-exports",
                headers=owner_a,
                json={
                    "report_kind": "multi_branch_aggregate",
                    "owner_group_key": "holding-rpt-009",
                    "recipient_email": "board@denlyra-clinic.local",
                    "include_phi": False,
                },
            ).status_code
            == 403
        )

        # Enroll Clinic A & Clinic B in holding-rpt-009 -> encrypted PHI-free export succeeds
        client.post(
            "/api/v1/org/branch-scope-grants",
            headers=owner_a,
            json={"owner_group_key": "holding-rpt-009", "branch_id": "branch-main"},
        )
        client.post(
            "/api/v1/org/branch-scope-grants",
            headers=owner_b,
            json={"owner_group_key": "holding-rpt-009", "branch_id": "branch-main"},
        )
        exp = client.post(
            "/api/v1/reports/scheduled-exports",
            headers=owner_a,
            json={
                "report_kind": "multi_branch_aggregate",
                "owner_group_key": "holding-rpt-009",
                "recipient_email": "board@denlyra-clinic.local",
                "include_phi": False,
            },
        )
        assert exp.status_code == 201, exp.text
        assert secret_b not in exp.text
        eb = exp.json()
        assert eb["include_phi"] is False
        raw_cipher = base64.b64decode(eb["encrypted_envelope_b64"])
        assert raw_cipher.startswith(b"DLY1")
