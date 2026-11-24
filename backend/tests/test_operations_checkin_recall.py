"""T013 clinician shift windows (SCH-001), resource maintenance downtime (SCH-015/HR-004),
confirmation state separation (SCH-009/CRM-003), identity-verified check-in + chair turnover
sanitation gate (PAT-009/SCH-010/HR-002/HR-003), and consent-safe recall queue (CRM-004/005/010).

Written BEFORE T013 domain/API implementation per AGENTS.md negative-test-first rule.
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


def test_clinician_shift_window_and_chair_maintenance_downtime_guards(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'ops_shift.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Ca trực & Bảo trì Ghế", "birth_year": 1992},
        ).json()["id"]

        # Define approved morning shift 08:00-12:00 (+07:00) for dentist (SCH-001)
        sh = client.post(
            "/api/v1/operations/shifts",
            headers=owner,
            json={
                "staff_id": doc_id,
                "start_at": "2026-12-20T08:00:00+07:00",
                "end_at": "2026-12-20T12:00:00+07:00",
            },
        )
        assert sh.status_code == 201, sh.text

        # Negative 1: Booking outside shift (14:00-15:00) without override -> 409
        outside = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-20T14:00:00+07:00",
                "end_at": "2026-12-20T15:00:00+07:00",
                "reason_demo": "Ngoài ca trực",
            },
        )
        assert outside.status_code == 409

        # Reviewed override allows emergency outside-shift booking and audits reason
        overridden = client.post(
            "/api/v1/appointments",
            headers=owner,
            json={
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-20T14:00:00+07:00",
                "end_at": "2026-12-20T15:00:00+07:00",
                "reason_demo": "Cấp cứu đau tủy răng ngoài giờ",
                "override_shift_reason": "Giám đốc duyệt ca cấp cứu ngoài giờ",
            },
        )
        assert overridden.status_code == 201

        # Negative 2 (SCH-015 / HR-004): Register chair maintenance downtime 10:00-11:30 (+07:00)
        dt = client.post(
            "/api/v1/operations/downtimes",
            headers=owner,
            json={
                "resource_id": chair_id,
                "start_at": "2026-12-20T10:00:00+07:00",
                "end_at": "2026-12-20T11:30:00+07:00",
                "reason": "Bảo trì van nước vô khuẩn ghế nha",
            },
        )
        assert dt.status_code == 201
        dt_id = dt.json()["id"]

        # Booking inside clinician shift (10:15-11:00) on chair under maintenance -> 409
        during_maint = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-20T10:15:00+07:00",
                "end_at": "2026-12-20T11:00:00+07:00",
                "reason_demo": "Trùng giờ bảo trì ghế",
            },
        )
        assert during_maint.status_code == 409

        # Resolve downtime -> booking succeeds (201)
        res_dt = client.post(f"/api/v1/operations/downtimes/{dt_id}/resolve", headers=owner)
        assert res_dt.status_code == 200
        after_maint = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-20T10:15:00+07:00",
                "end_at": "2026-12-20T11:00:00+07:00",
                "reason_demo": "Sau khi hoàn tất bảo trì ghế",
            },
        )
        assert after_maint.status_code == 201


def test_confirmation_separation_identity_checkin_and_chair_turnover_gate(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'ops_checkin.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        receptionist = _headers(client, "receptionist")
        dentist = _headers(client, "dentist")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Check-in & Vô khuẩn Ghế", "birth_year": 1995},
        ).json()["id"]
        appt = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-21T09:00:00+07:00",
                "end_at": "2026-12-21T10:00:00+07:00",
                "reason_demo": "Khám tổng quát",
            },
        ).json()
        appt_id = appt["id"]

        # SCH-009 / CRM-003: Transport 'sent' and 'delivered' NEVER imply 'patient_confirmed'
        client.post(
            f"/api/v1/appointments/{appt_id}/confirmations",
            headers=receptionist,
            json={"event_type": "sent", "channel": "sms_stub", "evidence_note": "Gateway queued"},
        )
        client.post(
            f"/api/v1/appointments/{appt_id}/confirmations",
            headers=receptionist,
            json={"event_type": "delivered", "channel": "sms_stub", "evidence_note": "Handset receipt"},
        )
        conf_state = client.get(
            f"/api/v1/appointments/{appt_id}/confirmations", headers=receptionist
        ).json()
        assert conf_state["confirmation_status"] == "delivered"
        assert conf_state["is_patient_confirmed"] is False

        client.post(
            f"/api/v1/appointments/{appt_id}/confirmations",
            headers=receptionist,
            json={
                "event_type": "patient_confirmed",
                "channel": "phone",
                "evidence_note": "Bệnh nhân gọi điện xác nhận giữ lịch 09:00",
            },
        )
        conf_final = client.get(
            f"/api/v1/appointments/{appt_id}/confirmations", headers=receptionist
        ).json()
        assert conf_final["is_patient_confirmed"] is True

        # Open chair turnover checklist in 'pending' state (HR-002 / HR-003)
        turnover = client.post(
            "/api/v1/operations/turnovers",
            headers=dentist,
            json={"chair_id": chair_id, "appointment_id": appt_id},
        )
        assert turnover.status_code == 201
        turnover_id = turnover.json()["id"]

        # PAT-009: Check-in without identity verification fails closed -> 409
        bad_ci = client.post(
            "/api/v1/operations/checkins",
            headers=receptionist,
            json={
                "appointment_id": appt_id,
                "identity_verified": False,
                "verification_method": "photo_id_checked",
            },
        )
        assert bad_ci.status_code == 409

        ci = client.post(
            "/api/v1/operations/checkins",
            headers=receptionist,
            json={
                "appointment_id": appt_id,
                "identity_verified": True,
                "verification_method": "photo_id_checked",
            },
        )
        assert ci.status_code == 201
        ci_id = ci.json()["id"]
        assert ci.json()["status"] == "waiting"

        # Negative: Seating patient ('in_chair') while chair sanitation turnover is pending -> 409
        blocked_seat = client.post(
            f"/api/v1/operations/checkins/{ci_id}/status",
            headers=receptionist,
            json={"next_status": "in_chair"},
        )
        assert blocked_seat.status_code == 409

        # Incomplete turnover checklist (waterline_flushed=False) -> 409
        assert (
            client.post(
                f"/api/v1/operations/turnovers/{turnover_id}/complete",
                headers=dentist,
                json={
                    "surface_disinfected": True,
                    "sterile_kit_verified": True,
                    "waterline_flushed": False,
                    "assistant_prep_ready": True,
                },
            ).status_code
            == 409
        )

        # Complete all 4 sanitation & assistant prep steps -> seating succeeds (200)
        ok_turn = client.post(
            f"/api/v1/operations/turnovers/{turnover_id}/complete",
            headers=dentist,
            json={
                "surface_disinfected": True,
                "sterile_kit_verified": True,
                "waterline_flushed": True,
                "assistant_prep_ready": True,
                "notes": "Đã thay bộ khay tiệt trùng lô A1",
            },
        )
        assert ok_turn.status_code == 200
        assert ok_turn.json()["status"] == "sanitized_ready"

        seated = client.post(
            f"/api/v1/operations/checkins/{ci_id}/status",
            headers=receptionist,
            json={"next_status": "in_chair"},
        )
        assert seated.status_code == 200
        assert seated.json()["status"] == "in_chair"


def test_consent_safe_recall_and_marketing_opt_out_enforcement(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'ops_recall.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        coordinator = _headers(client, "treatment_coordinator")
        dentist = _headers(client, "dentist")

        pat_id = client.post(
            "/api/v1/patients",
            headers=coordinator,
            json={"display_name": "BN Tái khám & Tiếp thị", "birth_year": 1987},
        ).json()["id"]

        # Negative 1 (CRM-010): Marketing outreach without granted marketing consent -> 409
        assert (
            client.post(
                "/api/v1/operations/recalls",
                headers=coordinator,
                json={
                    "patient_id": pat_id,
                    "kind": "marketing_outreach",
                    "due_date": "2027-01-15",
                    "reason": "Ưu đãi tẩy trắng răng đầu năm",
                    "clinician_approved": False,
                },
            ).status_code
            == 409
        )

        # Negative 2 (CRM-005): Clinical recall without clinician_approved=True -> 409
        assert (
            client.post(
                "/api/v1/operations/recalls",
                headers=coordinator,
                json={
                    "patient_id": pat_id,
                    "kind": "clinical_recall",
                    "due_date": "2027-06-01",
                    "reason": "Tái khám kiểm tra tích hợp xương Implant 6 tháng",
                    "clinician_approved": False,
                },
            ).status_code
            == 409
        )

        # Grant marketing consent -> marketing outreach succeeds -> withdraw marketing consent -> blocked again!
        mkt_consent = client.post(
            "/api/v1/consents",
            headers=coordinator,
            json={
                "patient_id": pat_id,
                "purpose": "marketing",
                "template_version": "mkt-v1",
                "disclosure_summary": "Đồng ý nhận bản tin khuyến mãi nha khoa",
                "signer_name": "BN Tái khám",
            },
        ).json()

        mkt_ok = client.post(
            "/api/v1/operations/recalls",
            headers=coordinator,
            json={
                "patient_id": pat_id,
                "kind": "marketing_outreach",
                "due_date": "2027-01-15",
                "reason": "Ưu đãi tẩy trắng răng",
                "clinician_approved": False,
            },
        )
        assert mkt_ok.status_code == 201

        client.post(
            f"/api/v1/consents/{mkt_consent['id']}/withdraw",
            headers=coordinator,
            json={"reason": "Bệnh nhân hủy nhận tin tiếp thị"},
        )
        assert (
            client.post(
                "/api/v1/operations/recalls",
                headers=coordinator,
                json={
                    "patient_id": pat_id,
                    "kind": "marketing_outreach",
                    "due_date": "2027-02-01",
                    "reason": "Chiến dịch mới sau khi đã opt-out",
                    "clinician_approved": False,
                },
            ).status_code
            == 409
        )

        # Meanwhile, clinician-approved clinical recall remains permitted after marketing withdrawal!
        clin_recall = client.post(
            "/api/v1/operations/recalls",
            headers=dentist,
            json={
                "patient_id": pat_id,
                "kind": "clinical_recall",
                "due_date": "2027-06-01",
                "reason": "Tái khám kiểm tra tích hợp xương Implant 6 tháng",
                "clinician_approved": True,
            },
        )
        assert clin_recall.status_code == 201
        closed = client.post(
            f"/api/v1/operations/recalls/{clin_recall.json()['id']}/close",
            headers=coordinator,
            json={"closure_evidence": "Đã đặt lịch hẹn tái khám ngày 2027-06-02"},
        )
        assert closed.status_code == 200
        assert closed.json()["status"] == "closed"
