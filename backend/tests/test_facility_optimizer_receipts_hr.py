"""T021 licensed facility metadata (ORG-001), approved procedure duration templates &
human-approved slot optimizer (SCH-011, SCH-012), traceable financial receipt exports
(FIN-013), and timezone-correct attendance & overtime isolated from clinical authorship
(HR-001, HR-010).

Written BEFORE T021 domain/API implementation per AGENTS.md negative-test-first rule.
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


def test_facility_licensing_never_infers_scope_from_display_name(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'facility_org.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        receptionist = _headers(client, "receptionist")

        # Negative 1 (ORG-001): Receptionist cannot configure facility license profile -> 403
        assert (
            client.post(
                "/api/v1/org/facility-profile",
                headers=receptionist,
                json={
                    "legal_entity_name_demo": "Công ty TNHH Nha Khoa Giả Lập A",
                    "license_number_demo": "DEMO-SYT-HCM-0001",
                    "license_type": "specialist_dental_clinic",
                    "permitted_scopes": ["general_dentistry"],
                    "regulating_authority_demo": "Sở Y tế TP.HCM (Demo)",
                    "verification_status": "verified_demo_only",
                },
            ).status_code
            == 403
        )

        # Negative 2 (AGENTS.md / ORG-001): Unprefixed real-looking license number rejected -> 422
        assert (
            client.post(
                "/api/v1/org/facility-profile",
                headers=owner,
                json={
                    "legal_entity_name_demo": "Công ty TNHH Nha Khoa Giả Lập A",
                    "license_number_demo": "04512/HCM-GPHD",
                    "license_type": "specialist_dental_clinic",
                    "permitted_scopes": ["general_dentistry"],
                    "regulating_authority_demo": "Sở Y tế TP.HCM (Demo)",
                },
            ).status_code
            == 422
        )

        # Before profile exists, scope check returns False even if staff has misleading title
        client.post(
            "/api/v1/staff",
            headers=owner,
            json={
                "display_name": "Bệnh Viện Chuyên Khoa Implant Phẫu Thuật Bộ Y Tế",
                "role": "receptionist",
            },
        )
        pre_chk = client.get(
            "/api/v1/org/facility-profile/scope-check?scope=implant_demo",
            headers=receptionist,
        )
        assert pre_chk.status_code == 200, pre_chk.text
        assert pre_chk.json()["allowed_in_demo_scope"] is False
        assert pre_chk.json()["never_inferred_from_display_name"] is True

        # Owner publishes v1 unverified_synthetic -> still not allowed until verified_demo_only
        v1 = client.post(
            "/api/v1/org/facility-profile",
            headers=owner,
            json={
                "legal_entity_name_demo": "Phòng Khám Chuyên Khoa RHM Demo Quận 1",
                "license_number_demo": "DEMO-SYT-HCM-2026-01",
                "license_type": "specialist_dental_clinic",
                "permitted_scopes": ["general_dentistry", "prosthodontics"],
                "regulating_authority_demo": "Sở Y tế TP.HCM (Synthetic)",
                "verification_status": "unverified_synthetic",
            },
        )
        assert v1.status_code == 201, v1.text
        assert v1.json()["version_number"] == 1
        assert (
            client.get(
                "/api/v1/org/facility-profile/scope-check?scope=general_dentistry",
                headers=receptionist,
            ).json()["allowed_in_demo_scope"]
            is False
        )

        # Publish v2 verified_demo_only with general_dentistry + prosthodontics (NOT implant_demo)
        v2 = client.post(
            "/api/v1/org/facility-profile",
            headers=owner,
            json={
                "legal_entity_name_demo": "Trung Tâm Implant Quốc Tế Tên Hiển Thị Demo",
                "license_number_demo": "DEMO-SYT-HCM-2026-02",
                "license_type": "specialist_dental_clinic",
                "permitted_scopes": ["general_dentistry", "prosthodontics"],
                "regulating_authority_demo": "Sở Y tế TP.HCM (Synthetic)",
                "verification_status": "verified_demo_only",
            },
        )
        assert v2.status_code == 201
        assert v2.json()["version_number"] == 2

        ok_gen = client.get(
            "/api/v1/org/facility-profile/scope-check?scope=general_dentistry",
            headers=receptionist,
        ).json()
        assert ok_gen["allowed_in_demo_scope"] is True

        # Even though legal_entity_name_demo contains "Implant", implant_demo is NOT in permitted_scopes -> False!
        deny_imp = client.get(
            "/api/v1/org/facility-profile/scope-check?scope=implant_demo",
            headers=receptionist,
        ).json()
        assert deny_imp["allowed_in_demo_scope"] is False


def test_duration_templates_and_non_mutating_slot_optimizer(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'sched_opt.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=dentist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        pat_1 = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Lịch Đã Chốt", "birth_year": 1989},
        ).json()["id"]
        pat_2 = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Cần Tối Ưu Slot", "birth_year": 1995},
        ).json()["id"]

        # Negative 1 (SCH-011): Receptionist cannot approve clinical procedure duration template -> 403
        assert (
            client.post(
                "/api/v1/scheduling/duration-templates",
                headers=receptionist,
                json={
                    "procedure_code": "ENDO-MOLAR-01",
                    "title_vi": "Nội nha răng cối lớn",
                    "recommended_minutes": 45,
                    "buffer_minutes": 15,
                    "fallback_minutes": 30,
                },
            ).status_code
            == 403
        )

        # Safe fallback when procedure_code unknown (SCH-011)
        fb = client.get(
            "/api/v1/scheduling/duration-estimate?procedure_code=UNKNOWN-PROC",
            headers=receptionist,
        )
        assert fb.status_code == 200
        assert fb.json()["used_safe_fallback"] is True
        assert fb.json()["suggested_total_minutes"] == 30
        assert fb.json()["staff_decides"] is True

        # Dentist publishes approved 45 + 15 = 60 min template
        tpl = client.post(
            "/api/v1/scheduling/duration-templates",
            headers=dentist,
            json={
                "procedure_code": "ENDO-MOLAR-01",
                "title_vi": "Nội nha răng cối lớn",
                "recommended_minutes": 45,
                "buffer_minutes": 15,
                "fallback_minutes": 30,
            },
        )
        assert tpl.status_code == 201, tpl.text
        est = client.get(
            "/api/v1/scheduling/duration-estimate?procedure_code=ENDO-MOLAR-01",
            headers=receptionist,
        ).json()
        assert est["used_safe_fallback"] is False
        assert est["suggested_total_minutes"] == 60

        # Existing confirmed appointment 09:00..10:00+07:00 & chair downtime 10:00..10:30+07:00
        existing_appt = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_1,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-10T09:00:00+07:00",
                "end_at": "2026-12-10T10:00:00+07:00",
                "reason_demo": "Ca đã xác nhận không được tự dời",
            },
        ).json()
        dt_res = client.post(
            "/api/v1/operations/downtimes",
            headers=dentist,
            json={
                "resource_id": chair_id,
                "start_at": "2026-12-10T10:00:00+07:00",
                "end_at": "2026-12-10T10:30:00+07:00",
                "reason": "Khử khuẩn định kỳ ghế 1",
            },
        )
        assert dt_res.status_code == 201, dt_res.text

        # SCH-012: Run optimizer across 09:00..12:00+07:00 -> must skip 09:00..10:30 and NEVER alter existing_appt
        prop = client.post(
            "/api/v1/scheduling/optimizer/propose",
            headers=receptionist,
            json={
                "patient_id": pat_2,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "procedure_code": "ENDO-MOLAR-01",
                "window_start_at": "2026-12-10T09:00:00+07:00",
                "window_end_at": "2026-12-10T12:00:00+07:00",
            },
        )
        assert prop.status_code == 201, prop.text
        pb = prop.json()
        assert pb["altered_confirmed_appointments"] == 0
        assert pb["duration_minutes"] == 60
        assert len(pb["proposed_slots"]) >= 1
        # Earliest valid 60-min slot starts at 10:30+07:00 = 03:30:00Z
        assert pb["proposed_slots"][0]["start_at"].startswith("2026-12-10T03:30:00")

        # Verify only 1 appointment exists so far and existing_appt is completely unchanged
        appts_before = client.get("/api/v1/appointments", headers=receptionist).json()
        assert len(appts_before) == 1
        assert appts_before[0]["id"] == existing_appt["id"]
        assert appts_before[0]["start_at"] == existing_appt["start_at"]

        # Human staff explicitly accepts slot 0 -> books second appointment; re-accepting fails 409
        acc = client.post(
            f"/api/v1/scheduling/optimizer/proposals/{pb['id']}/accept",
            headers=receptionist,
            json={"slot_index": 0, "reason_demo": "Lễ tân xác nhận slot 10:30"},
        )
        assert acc.status_code == 200, acc.text
        assert acc.json()["status"] == "accepted_booked"
        assert len(client.get("/api/v1/appointments", headers=receptionist).json()) == 2

        assert (
            client.post(
                f"/api/v1/scheduling/optimizer/proposals/{pb['id']}/accept",
                headers=receptionist,
                json={"slot_index": 0},
            ).status_code
            == 409
        )


def test_traceable_financial_receipts_and_timezone_attendance_overtime(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'fin_hr.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        finance = _headers(client, "finance")
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        finance_b = _headers(client, "finance", clinic_id=CLINIC_B)

        ctx = client.get("/api/v1/demo/context", headers=owner).json()
        rec_staff_id = next(s["id"] for s in ctx["staff"] if s["role"] == "receptionist")
        doc_staff_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")

        pat = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Biên Lai & Chấm Công", "birth_year": 1991},
        ).json()["id"]
        chg = client.post(
            "/api/v1/finance/charges",
            headers=finance,
            json={"patient_id": pat, "label": "Mão sứ răng 26 (Demo)", "amount_vnd": 6000000},
        ).json()["id"]
        pmt = client.post(
            "/api/v1/finance/payments",
            headers=finance,
            json={
                "patient_id": pat,
                "amount_vnd": 6000000,
                "payment_method": "bank_transfer",
            },
        ).json()["id"]
        client.post(
            "/api/v1/finance/allocations",
            headers=finance,
            json={"charge_id": chg, "payment_id": pmt, "amount_vnd": 6000000},
        )

        # Negative 1 (FIN-013): Dentist lacks finance.write -> 403; Clinic B finance -> 404
        assert (
            client.post(
                f"/api/v1/finance/payments/{pmt}/receipt-exports",
                headers=dentist,
                json={"export_note": "Bác sĩ thử xuất biên lai"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/finance/payments/{pmt}/receipt-exports",
                headers=finance_b,
                json={"export_note": "Cross clinic"},
            ).status_code
            == 404
        )

        # Negative 2 (FIN-013): Cannot fabricate verified bank settlement proof -> 409
        assert (
            client.post(
                f"/api/v1/finance/payments/{pmt}/receipt-exports",
                headers=finance,
                json={
                    "export_note": "Giả mạo xác nhận ngân hàng",
                    "claim_verified_bank_settlement": True,
                },
            ).status_code
            == 409
        )

        # Valid traceable synthetic receipt export
        rcpt = client.post(
            f"/api/v1/finance/payments/{pmt}/receipt-exports",
            headers=finance,
            json={"export_note": "Phiếu xác nhận thu tiền nội bộ giả lập"},
        )
        assert rcpt.status_code == 201, rcpt.text
        rb = rcpt.json()
        assert rb["amount_vnd"] == 6000000
        assert rb["synthetic_non_bank_receipt"] is True
        assert len(rb["payload_sha256"]) == 64
        assert len(rb["signature_hmac_sha256"]) == 64
        assert chg in rb["allocated_charges_json"]

        # HR-001 & HR-010: UTC rollover 2026-12-01T18:00:00Z -> 2026-12-02T04:00:00Z
        # In Ho Chi Minh City (+07:00), that is 2026-12-02 01:00 -> 11:00 (600 mins = 480 regular + 120 overtime)
        att = client.post(
            "/api/v1/hr/attendance",
            headers=receptionist,
            json={
                "staff_id": rec_staff_id,
                "check_in_at": "2026-12-01T18:00:00Z",
                "check_out_at": "2026-12-02T04:00:00Z",
                "note": "Ca trực kiểm kê đầu ngày giờ VN",
            },
        )
        assert att.status_code == 201, att.text
        ab = att.json()
        assert ab["local_date_hcm"] == "2026-12-02"
        assert ab["worked_minutes"] == 600
        assert ab["regular_minutes"] == 480
        assert ab["overtime_minutes"] == 120

        ot = client.get(
            "/api/v1/hr/overtime-summary?local_date_hcm=2026-12-02",
            headers=owner,
        )
        assert ot.status_code == 200, ot.text
        ot_body = ot.json()
        assert ot_body["timezone"] == "Asia/Ho_Chi_Minh"
        assert ot_body["affects_clinical_credentials_or_authorship"] is False
        rec_row = next(r for r in ot_body["staff_summaries"] if r["staff_id"] == rec_staff_id)
        assert rec_row["overtime_minutes"] == 120

        # Negative 3 (HR-001): Attendance never grants clinical authorship to receptionist -> 403,
        # while dentist clinical authorship remains intact
        assert (
            client.post(
                "/api/v1/encounters",
                headers=receptionist,
                json={"patient_id": pat, "practitioner_id": doc_staff_id},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/encounters",
                headers=dentist,
                json={"patient_id": pat, "practitioner_id": doc_staff_id},
            ).status_code
            == 201
        )
