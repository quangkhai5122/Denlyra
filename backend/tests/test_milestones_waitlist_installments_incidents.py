"""T018 clinical milestone checklists (TRT-012), lossless treatment pause/cancel/terminate
governance (TRT-014), consent-safe schedule waiting list (SCH-008), reviewed installment
schedule without auto-charge (FIN-008), and protected quality incident queue (HR-008).

Written BEFORE T018 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"


def _headers(client: TestClient, role: str, clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_clinical_milestone_gate_and_lossless_treatment_pause_terminate(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'trt_milestones.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        finance = _headers(client, "finance")

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Cột mốc Implant & Tạm dừng Phác đồ", "birth_year": 1982},
        ).json()["id"]
        plan_id = client.post(
            "/api/v1/treatment-plans",
            headers=dentist,
            json={"patient_id": pat_id, "title": "Phục hình trên Implant răng 46"},
        ).json()["id"]
        task_id = client.post(
            f"/api/v1/treatment-plans/{plan_id}/tasks",
            headers=dentist,
            json={"title": "Lấy dấu phục hình sau tích hợp xương", "phase": "Phục hình"},
        ).json()["id"]
        client.post(f"/api/v1/treatment-plans/{plan_id}/demo-review", headers=dentist)

        # Record historical charge & payment prior to pause/termination
        chg_id = client.post(
            "/api/v1/finance/charges",
            headers=finance,
            json={"patient_id": pat_id, "label": "Đặt trụ giai đoạn 1", "amount_vnd": 15000000},
        ).json()["id"]
        pay_id = client.post(
            "/api/v1/finance/payments",
            headers=finance,
            json={"patient_id": pat_id, "amount_vnd": 15000000, "payment_method": "bank_transfer"},
        ).json()["id"]

        # Attach clinical milestone checklist (TRT-012)
        ms = client.post(
            f"/api/v1/treatment-tasks/{task_id}/milestones",
            headers=dentist,
            json={
                "title_vi": "Đánh giá tích hợp xương trước lấy dấu",
                "criteria_items": ["ISQ >= 70", "Không viêm quanh trụ"],
            },
        )
        assert ms.status_code == 201, ms.text
        ms_id = ms.json()["id"]

        # Negative 1: Completing task while milestone is pending -> 409
        assert client.post(f"/api/v1/treatment-tasks/{task_id}/demo-complete", headers=dentist).status_code == 409

        # Negative 2: Overriding unmet milestone without override reason -> 409
        assert (
            client.post(
                f"/api/v1/treatment-milestones/{ms_id}/evaluate",
                headers=dentist,
                json={"all_criteria_met": False},
            ).status_code
            == 409
        )

        # Clinician evaluates milestone with documented override reason -> unblocks milestone
        ev_ok = client.post(
            f"/api/v1/treatment-milestones/{ms_id}/evaluate",
            headers=dentist,
            json={
                "all_criteria_met": False,
                "clinician_override_reason": "Lấy dấu phục hình tạm tải lực nhẹ có kiểm soát của bác sĩ",
            },
        )
        assert ev_ok.status_code == 200
        assert ev_ok.json()["status"] == "overridden_with_reason"

        # TRT-014: Pause plan -> completing task while paused fails closed (409)
        paused = client.post(
            f"/api/v1/treatment-plans/{plan_id}/lifecycle",
            headers=dentist,
            json={
                "action": "pause",
                "reason": "Bệnh nhân đi công tác nước ngoài 3 tháng",
                "clinical_handoff_note": "Đã gắn healing abutment ổn định",
            },
        )
        assert paused.status_code == 201
        assert client.post(f"/api/v1/treatment-tasks/{task_id}/demo-complete", headers=dentist).status_code == 409

        # Resume plan -> task completion succeeds; then terminate remaining plan and verify zero history loss
        client.post(
            f"/api/v1/treatment-plans/{plan_id}/lifecycle",
            headers=dentist,
            json={"action": "resume", "reason": "Bệnh nhân quay lại tiếp tục điều trị"},
        )
        assert client.post(f"/api/v1/treatment-tasks/{task_id}/demo-complete", headers=dentist).status_code == 200

        term = client.post(
            f"/api/v1/treatment-plans/{plan_id}/lifecycle",
            headers=dentist,
            json={
                "action": "terminate",
                "reason": "Chuyển cơ sở điều trị theo nguyện vọng gia đình",
                "clinical_handoff_note": "Bảo toàn nguyên vẹn hồ sơ và lịch sử thanh toán",
            },
        )
        assert term.status_code == 201
        assert term.json()["resulting_state"] == "terminated"

        # Historical charges, payments, and tasks remain 100% intact
        assert any(c["id"] == chg_id for c in client.get("/api/v1/finance/charges", headers=finance).json())
        assert any(p["id"] == pay_id for p in client.get("/api/v1/finance/payments", headers=finance).json())
        assert len(client.get(f"/api/v1/treatment-plans/{plan_id}", headers=dentist).json()["tasks"]) == 1


def test_consent_safe_waitlist_and_installment_schedule_without_autocharge(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'waitlist_inst.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        finance = _headers(client, "finance")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Danh sách chờ & Lịch Trả góp", "birth_year": 1993},
        ).json()["id"]

        # SCH-008: Enqueue waitlist item; preparing outreach without treatment consent -> 409
        wl = client.post(
            "/api/v1/operations/waitlist",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "preferred_practitioner_id": doc_id,
                "preferred_date_window": "2026-12-28..2026-12-30",
                "service_note_minimized": "Khám tư vấn chỉnh nha",
            },
        )
        assert wl.status_code == 201, wl.text
        wl_id = wl.json()["id"]

        assert (
            client.post(
                f"/api/v1/operations/waitlist/{wl_id}/prepare-outreach", headers=receptionist
            ).status_code
            == 409
        )

        # Grant treatment consent -> prepare-outreach succeeds WITHOUT auto-creating an appointment!
        trt_consent = client.post(
            "/api/v1/consents",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "purpose": "treatment",
                "template_version": "CONSENT-2026-V1",
                "disclosure_summary": "Đồng thuận liên hệ điều phối lịch khám",
                "signer_name": "BN Danh sách chờ",
                "signer_relationship": "self",
            },
        ).json()["id"]

        outreach = client.post(
            f"/api/v1/operations/waitlist/{wl_id}/prepare-outreach", headers=receptionist
        )
        assert outreach.status_code == 200
        assert outreach.json()["status"] == "outreach_prepared"
        assert client.get("/api/v1/appointments", headers=receptionist).json() == []

        # Explicit staff confirmation books slot atomically
        confirmed_wl = client.post(
            f"/api/v1/operations/waitlist/{wl_id}/confirm-booking",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-28T09:00:00+07:00",
                "end_at": "2026-12-28T09:45:00+07:00",
                "reason_demo": "Xác nhận chỗ trống từ danh sách chờ",
            },
        )
        assert confirmed_wl.status_code == 201
        assert confirmed_wl.json()["status"] == "booked_by_staff"
        assert confirmed_wl.json()["booked_appointment_id"] is not None

        # FIN-008: Installment schedule requires financial consent (treatment consent rejected -> 409)
        plan_id = client.post(
            "/api/v1/treatment-plans",
            headers=dentist,
            json={"patient_id": pat_id, "title": "Chỉnh nha mắc cài 30 triệu"},
        ).json()["id"]
        est_id = client.post(
            "/api/v1/finance/estimates",
            headers=finance,
            json={
                "patient_id": pat_id,
                "plan_id": plan_id,
                "version_number": 1,
                "amount_vnd": 30000000,
                "items_summary": "Trọn gói chỉnh nha mắc cài kim loại",
            },
        ).json()["id"]

        wrong_consent = client.post(
            "/api/v1/finance/installments",
            headers=finance,
            json={
                "estimate_id": est_id,
                "consent_id": trt_consent,
                "tranches": [
                    {"due_date": "2027-01-10", "amount_vnd": 15000000},
                    {"due_date": "2027-02-10", "amount_vnd": 15000000},
                ],
            },
        )
        assert wrong_consent.status_code == 409

        fin_consent = client.post(
            "/api/v1/consents",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "purpose": "financial",
                "template_version": "FIN-CONSENT-2026-V1",
                "disclosure_summary": "Đồng thuận lịch thanh toán theo đợt không tự động trừ tiền",
                "signer_name": "BN Danh sách chờ",
                "signer_relationship": "self",
            },
        ).json()["id"]

        # Mismatched tranche total (25M != 30M) -> 422
        assert (
            client.post(
                "/api/v1/finance/installments",
                headers=finance,
                json={
                    "estimate_id": est_id,
                    "consent_id": fin_consent,
                    "tranches": [
                        {"due_date": "2027-01-10", "amount_vnd": 15000000},
                        {"due_date": "2027-02-10", "amount_vnd": 10000000},
                    ],
                },
            ).status_code
            == 422
        )

        # Valid installment schedule -> auto_charge_enabled is False and ZERO Charge rows auto-created
        sched = client.post(
            "/api/v1/finance/installments",
            headers=finance,
            json={
                "estimate_id": est_id,
                "consent_id": fin_consent,
                "tranches": [
                    {"due_date": "2027-01-10", "amount_vnd": 15000000},
                    {"due_date": "2027-02-10", "amount_vnd": 15000000},
                ],
            },
        )
        assert sched.status_code == 201, sched.text
        sched_body = sched.json()
        assert sched_body["schedule"]["auto_charge_enabled"] is False
        tranche_1_id = sched_body["tranches"][0]["id"]

        rem = client.post(
            f"/api/v1/finance/installments/{sched_body['schedule']['id']}/tranches/{tranche_1_id}/log-reminder",
            headers=finance,
        )
        assert rem.status_code == 200
        assert client.get("/api/v1/finance/charges", headers=finance).json() == []


def test_protected_quality_incident_escalation_and_ai_prohibition(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'incidents.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        assistant = _headers(client, "assistant")
        receptionist = _headers(client, "receptionist")

        # Negative 1: AI diagnosis / root-cause source rejected -> 422 (HR-008)
        assert (
            client.post(
                "/api/v1/operations/incidents",
                headers=assistant,
                json={
                    "category": "sterilization_breach",
                    "severity": "high",
                    "summary": "AI tự suy đoán nguyên nhân sự cố",
                    "evidence_note": "Không hợp lệ",
                    "source_kind": "ai_diagnosis",
                },
            ).status_code
            == 422
        )

        # Assistant files high-severity quality incident -> 201 and auto-escalates
        inc = client.post(
            "/api/v1/operations/incidents",
            headers=assistant,
            json={
                "category": "sterilization_breach",
                "severity": "high",
                "summary": "Phát hiện chỉ thị nhiệt lô hấp số 04 chưa chuyển màu đạt chuẩn",
                "evidence_note": "Đã cô lập toàn bộ khay dụng cụ lô 04 trước khi sử dụng",
            },
        )
        assert inc.status_code == 201, inc.text
        assert inc.json()["status"] == "escalated_to_director"

        # Negative 2: Protected queue — receptionist and assistant cannot list incidents -> 403
        assert client.get("/api/v1/operations/incidents", headers=receptionist).status_code == 403
        assert client.get("/api/v1/operations/incidents", headers=assistant).status_code == 403

        # Clinic owner can review protected incident queue -> 200
        queue = client.get("/api/v1/operations/incidents", headers=owner)
        assert queue.status_code == 200
        assert len(queue.json()) == 1
        assert queue.json()[0]["id"] == inc.json()["id"]
