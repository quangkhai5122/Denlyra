"""T015 reversible dual-confirmed patient merge (PAT-006), short-TTL break-glass access
with independent after-action review (ORG-011), and clinician-published patient/guardian
portal views (PORT-001..PORT-007, PORT-009, TRT-016).

Written BEFORE T015 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"
CLINIC_B = "22222222-2222-4222-8222-222222222222"


def _headers(
    client: TestClient,
    role: str,
    clinic_id: str = CLINIC_A,
    staff_id: str | None = None,
) -> dict[str, str]:
    payload: dict = {"clinic_id": clinic_id, "role": role}
    if staff_id:
        payload["staff_id"] = staff_id
    resp = client.post("/api/v1/auth/token", json=payload)
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_reversible_dual_confirmed_patient_merge_preserves_provenance(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'merge.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        finance = _headers(client, "finance")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        # Create primary and duplicate patient records (same synthetic phone, NOT auto-merged)
        p_primary = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "Nguyễn Minh Châu (Hồ sơ gốc)", "birth_year": 1990, "phone_demo": "0900000111"},
        ).json()["id"]
        p_secondary = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "Nguyen M. Chau (Hồ sơ trùng)", "birth_year": 1990, "phone_demo": "0900000111"},
        ).json()["id"]

        # Record clinical encounter on primary and financial charge on secondary
        enc_primary = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": p_primary, "practitioner_id": doc_id},
        ).json()["id"]
        chg_secondary = client.post(
            "/api/v1/finance/charges",
            headers=finance,
            json={"patient_id": p_secondary, "label": "Chụp phim khảo sát", "amount_vnd": 350000},
        ).json()["id"]

        # Request merge (initiated by dentist)
        m_req = client.post(
            "/api/v1/patients/merges",
            headers=dentist,
            json={
                "primary_patient_id": p_primary,
                "secondary_patient_id": p_secondary,
                "rationale": "Xác minh CCCD giả lập tại quầy trùng khớp hai hồ sơ",
                "contradictions_noted": "Viết tắt tên đệm ở hồ sơ thứ hai",
            },
        )
        assert m_req.status_code == 201, m_req.text
        merge_id = m_req.json()["id"]
        assert m_req.json()["status"] == "pending_second_confirmation"

        # Negative 1: Self-confirmation by the same staff member -> 409 Conflict (PAT-006)
        self_confirm = client.post(
            f"/api/v1/patients/merges/{merge_id}/confirm",
            headers=dentist,
            json={"confirmation_note": "Tự duyệt"},
        )
        assert self_confirm.status_code == 409

        # Independent confirmation by clinic_owner -> 200 merged
        ok_confirm = client.post(
            f"/api/v1/patients/merges/{merge_id}/confirm",
            headers=owner,
            json={"confirmation_note": "Đã đối chiếu độc lập hồ sơ gốc và hồ sơ trùng"},
        )
        assert ok_confirm.status_code == 200
        assert ok_confirm.json()["status"] == "merged"

        # Negative 2: Booking new appointment or encounter on retired secondary patient -> 409
        blocked_appt = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": p_secondary,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-22T09:00:00+07:00",
                "end_at": "2026-12-22T09:45:00+07:00",
                "reason_demo": "Đặt nhầm vào hồ sơ phụ đã gộp",
            },
        )
        assert blocked_appt.status_code == 409

        blocked_enc = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": p_secondary, "practitioner_id": doc_id},
        )
        assert blocked_enc.status_code == 409

        # Unified summary resolves secondary -> primary and preserves source_patient_id on all records
        summary = client.get(f"/api/v1/patients/{p_secondary}/unified-summary", headers=dentist)
        assert summary.status_code == 200
        body = summary.json()
        assert body["canonical_patient_id"] == p_primary
        assert p_secondary in body["merged_secondary_patient_ids"]
        assert any(
            e["id"] == enc_primary and e["source_patient_id"] == p_primary
            for e in body["encounters"]
        )
        assert any(
            c["id"] == chg_secondary and c["source_patient_id"] == p_secondary
            for c in body["charges"]
        )

        # Reversible unmerge restores independent records with zero history loss
        rev = client.post(
            f"/api/v1/patients/merges/{merge_id}/reverse",
            headers=owner,
            json={"reversal_reason": "Phát hiện hai chị em sinh đôi dùng chung số điện thoại gia đình"},
        )
        assert rev.status_code == 200
        assert rev.json()["status"] == "reversed"

        unmerged_sec = client.get(f"/api/v1/patients/{p_secondary}/unified-summary", headers=dentist).json()
        assert unmerged_sec["canonical_patient_id"] == p_secondary
        assert unmerged_sec["merged_secondary_patient_ids"] == []
        assert [c["id"] for c in unmerged_sec["charges"]] == [chg_secondary]
        assert unmerged_sec["encounters"] == []

        # Secondary patient can now book independently again
        reopened_appt = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": p_secondary,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-22T09:00:00+07:00",
                "end_at": "2026-12-22T09:45:00+07:00",
                "reason_demo": "Khám riêng sau khi tách hồ sơ",
            },
        )
        assert reopened_appt.status_code == 201


def test_short_ttl_break_glass_and_independent_after_action_review(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'breakglass.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        dentist = _headers(client, "dentist")
        assistant = _headers(client, "assistant")
        other_clinic_owner = _headers(client, "clinic_owner", clinic_id=CLINIC_B)
        ctx = client.get("/api/v1/demo/context", headers=dentist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")

        pat_id = client.post(
            "/api/v1/patients",
            headers=dentist,
            json={"display_name": "BN Cấp cứu Dị ứng Thuốc tê", "birth_year": 1985},
        ).json()["id"]
        enc_id = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat_id, "practitioner_id": doc_id},
        ).json()["id"]
        client.post(
            f"/api/v1/encounters/{enc_id}/notes",
            headers=dentist,
            json={"content": "Tiền sử phản ứng thuốc tê tại phòng khám cũ (dữ liệu giả lập)."},
        )

        # Baseline: assistant lacks note.read -> 403
        assert client.get(f"/api/v1/encounters/{enc_id}/notes", headers=assistant).status_code == 403

        # Negative 1: TTL > 900s (15 min) or vague reason -> 422
        too_long = client.post(
            "/api/v1/auth/break-glass",
            headers=assistant,
            json={
                "patient_id": pat_id,
                "emergency_reason": "Xử trí phản ứng cấp cứu tại ghế nha cần tra cứu tiền sử thuốc tê",
                "ttl_seconds": 3600,
            },
        )
        assert too_long.status_code == 422

        too_short_reason = client.post(
            "/api/v1/auth/break-glass",
            headers=assistant,
            json={"patient_id": pat_id, "emergency_reason": "Khẩn", "ttl_seconds": 300},
        )
        assert too_short_reason.status_code == 422

        # Valid short-TTL break-glass activation -> 201
        bg = client.post(
            "/api/v1/auth/break-glass",
            headers=assistant,
            json={
                "patient_id": pat_id,
                "emergency_reason": "Cấp cứu choáng tại ghế nha số 1, cần đọc ghi chú thuốc tê khẩn cấp",
                "ttl_seconds": 300,
            },
        )
        assert bg.status_code == 201, bg.text
        grant_id = bg.json()["id"]
        assert bg.json()["review_status"] == "pending_independent_review"

        # Requester can read scoped emergency chart; cross-clinic principal denied (403)
        chart = client.get(f"/api/v1/auth/break-glass/{grant_id}/patient-chart", headers=assistant)
        assert chart.status_code == 200
        assert len(chart.json()["notes"]) == 1
        assert (
            client.get(
                f"/api/v1/auth/break-glass/{grant_id}/patient-chart", headers=other_clinic_owner
            ).status_code
            == 403
        )

        # Negative 2: Self-review or unauthorized review blocked; medical_director self-review -> 409
        med_dir_staff = client.post(
            "/api/v1/staff",
            headers=owner,
            json={"display_name": "Giám đốc chuyên môn Demo", "role": "medical_director"},
        ).json()["id"]
        med_dir = _headers(client, "medical_director", staff_id=med_dir_staff)
        bg_md = client.post(
            "/api/v1/auth/break-glass",
            headers=med_dir,
            json={
                "patient_id": pat_id,
                "emergency_reason": "Hội chẩn cấp cứu chảy máu sau nhổ răng khẩn cấp ngoài ca",
                "ttl_seconds": 300,
            },
        ).json()["id"]
        self_rev = client.post(
            f"/api/v1/auth/break-glass/{bg_md}/review",
            headers=med_dir,
            json={"outcome": "reviewed_justified", "review_notes": "Tự hậu kiểm phiếu break-glass"},
        )
        assert self_rev.status_code == 409

        # Independent review by clinic_owner succeeds (200)
        ok_rev = client.post(
            f"/api/v1/auth/break-glass/{grant_id}/review",
            headers=owner,
            json={
                "outcome": "reviewed_justified",
                "review_notes": "Xác nhận đúng tình huống cấp cứu tại ghế số 1",
            },
        )
        assert ok_rev.status_code == 200
        assert ok_rev.json()["review_status"] == "reviewed_justified"

        # Revoking break-glass immediately blocks subsequent chart reads (403)
        rev = client.post(f"/api/v1/auth/break-glass/{grant_id}/revoke", headers=owner)
        assert rev.status_code == 200
        assert (
            client.get(f"/api/v1/auth/break-glass/{grant_id}/patient-chart", headers=assistant).status_code
            == 403
        )


def test_patient_portal_excludes_draft_notes_and_enforces_guardian_and_reschedule_gates(
    tmp_path: Path,
):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'portal.db'}",
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
            json={"display_name": "Bé Trần Gia Huy (Cổng BN)", "birth_year": 2016},
        ).json()["id"]

        # Negative 1 (PORT-001 / PORT-009): Guardian portal grant without verified guardian consent -> 403
        unverified_guardian = client.post(
            "/api/v1/portal/grants",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "actor_kind": "guardian",
                "actor_display_name": "Trần Văn Bình (Phụ huynh chưa xác minh)",
                "ttl_seconds": 1800,
            },
        )
        assert unverified_guardian.status_code == 403

        # Record verified guardian treatment & financial consent -> guardian portal grant succeeds
        for purpose in ("treatment", "financial"):
            c_res = client.post(
                "/api/v1/consents",
                headers=receptionist,
                json={
                    "patient_id": pat_id,
                    "purpose": purpose,
                    "template_version": "CONSENT-2026-V1",
                    "disclosure_summary": f"Đồng thuận {purpose} của người giám hộ hợp pháp",
                    "signer_name": "Trần Văn Bình",
                    "signer_relationship": "guardian",
                    "guardian_authority_verified": True,
                },
            )
            assert c_res.status_code == 201

        grant_resp = client.post(
            "/api/v1/portal/grants",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "actor_kind": "guardian",
                "actor_display_name": "Trần Văn Bình",
                "ttl_seconds": 1800,
            },
        )
        assert grant_resp.status_code == 201, grant_resp.text
        portal_token = grant_resp.json()["portal_token"]
        portal_headers = {"Authorization": f"Bearer {portal_token}"}

        # Negative 2: Portal token cannot be used on staff RBAC endpoints -> 401
        assert client.get("/api/v1/patients", headers=portal_headers).status_code == 401

        # Create appointment, internal draft clinical note, AI draft, internal plan task, and finance items
        appt = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-24T09:00:00+07:00",
                "end_at": "2026-12-24T09:30:00+07:00",
                "reason_demo": "Tái khám chỉnh nha định kỳ",
            },
        ).json()

        enc_id = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat_id, "practitioner_id": doc_id},
        ).json()["id"]
        secret_draft_marker = "GHI_CHU_NHAP_NOI_BO_TUYET_MAT_KHONG_HIEN_THI_PORTAL"
        client.post(
            f"/api/v1/encounters/{enc_id}/notes",
            headers=dentist,
            json={"content": f"Chẩn đoán phân biệt nháp: {secret_draft_marker}"},
        )
        plan_id = client.post(
            "/api/v1/treatment-plans",
            headers=dentist,
            json={"patient_id": pat_id, "title": "Chỉnh nha khí cụ tháo lắp giai đoạn 1"},
        ).json()["id"]
        client.post(
            f"/api/v1/treatment-plans/{plan_id}/tasks",
            headers=dentist,
            json={"title": f"Task nội bộ bác sĩ {secret_draft_marker}", "phase": "Nội bộ"},
        )

        # Receptionist cannot publish clinical instructions -> 403; dentist publishes instruction + lay summary
        assert (
            client.post(
                "/api/v1/portal/instructions",
                headers=receptionist,
                json={
                    "patient_id": pat_id,
                    "encounter_id": enc_id,
                    "title_vi": "Hướng dẫn sai thẩm quyền",
                    "body_vi": "Không hợp lệ",
                },
            ).status_code
            == 403
        )
        pub_inst = client.post(
            "/api/v1/portal/instructions",
            headers=dentist,
            json={
                "patient_id": pat_id,
                "encounter_id": enc_id,
                "title_vi": "Hướng dẫn đeo hàm duy trì tại nhà",
                "body_vi": "Đeo tối thiểu 14 giờ/ngày, vệ sinh bằng bàn chải mềm và nước nguội.",
            },
        )
        assert pub_inst.status_code == 201

        pub_plan = client.post(
            "/api/v1/portal/plan-summaries",
            headers=dentist,
            json={
                "patient_id": pat_id,
                "plan_id": plan_id,
                "lay_summary_vi": "Giai đoạn 1 nong hàm nhẹ trong 3 tháng, tái khám mỗi 4 tuần.",
            },
        )
        assert pub_plan.status_code == 201

        chg = client.post(
            "/api/v1/finance/charges",
            headers=finance,
            json={"patient_id": pat_id, "label": "Khí cụ chỉnh nha đợt 1", "amount_vnd": 5000000},
        ).json()
        pay = client.post(
            "/api/v1/finance/payments",
            headers=finance,
            json={"patient_id": pat_id, "amount_vnd": 2000000, "payment_method": "bank_transfer"},
        ).json()
        client.post(
            "/api/v1/finance/allocations",
            headers=finance,
            json={"charge_id": chg["id"], "payment_id": pay["id"], "amount_vnd": 2000000},
        )

        # Negative 3 (PORT-002..005, PORT-007, TRT-016): Portal overview contains published items & balance, ZERO internal draft text
        overview = client.get("/api/v1/patient-portal/overview", headers=portal_headers)
        assert overview.status_code == 200
        raw_text = overview.text
        assert secret_draft_marker not in raw_text
        ov = overview.json()
        assert len(ov["appointments"]) == 1
        assert len(ov["published_instructions"]) == 1
        assert len(ov["published_plan_summaries"]) == 1
        assert ov["financial_summary"]["total_charges_vnd"] == 5000000
        assert ov["financial_summary"]["total_allocated_vnd"] == 2000000
        assert ov["financial_summary"]["outstanding_balance_vnd"] == 3000000

        # PORT-003: Portal reschedule request does NOT alter appointment until staff validates & commits
        rs_req = client.post(
            f"/api/v1/patient-portal/appointments/{appt['id']}/reschedule-requests",
            headers=portal_headers,
            json={
                "requested_start_at": "2026-12-24T10:30:00+07:00",
                "requested_end_at": "2026-12-24T11:00:00+07:00",
                "reason": "Bé thi học kỳ buổi sáng sớm",
            },
        )
        assert rs_req.status_code == 201
        req_id = rs_req.json()["id"]
        assert rs_req.json()["status"] == "pending_staff_validation"

        # Original appointment remains confirmed at 09:00 (+07:00 = 02:00 UTC) until staff approves
        still_old = next(
            a for a in client.get("/api/v1/appointments", headers=receptionist).json() if a["id"] == appt["id"]
        )
        assert still_old["status"] == "confirmed"

        approved_rs = client.post(
            f"/api/v1/portal/reschedule-requests/{req_id}/approve",
            headers=receptionist,
            json={"resolution_note": "Ghế số 1 và bác sĩ trống lúc 10:30, đã duyệt dời lịch"},
        )
        assert approved_rs.status_code == 200
        assert approved_rs.json()["status"] == "approved_committed"
        assert approved_rs.json()["resolved_appointment_id"] != appt["id"]

        # PORT-006: Portal intake form sets provenance='patient_portal_intake' and legal_consent_granted=False
        intake = client.post(
            "/api/v1/patient-portal/intake-forms",
            headers=portal_headers,
            json={
                "form_code": "PORTAL-INTAKE-PEDIATRIC",
                "form_version": "2026.1",
                "answers": {"preferred_contact_window": "17:00-19:00", "diet_note": "Không kiêng ăn"},
            },
        )
        assert intake.status_code == 201
        assert intake.json()["provenance"] == "patient_portal_intake"
        assert intake.json()["legal_consent_granted"] is False
