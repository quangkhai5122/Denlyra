"""T024 retention-aware patient subject access export (PAT-011), FIFO consent-safe
cancellation slot recovery (SCH-014), malware-scanned quarantined portal uploads &
human-triaged support messaging (PORT-008, PORT-010), and staff competency expiry
guard + performed-vs-collected commission preview (HR-007, HR-009).

Written BEFORE T024 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

import base64
from pathlib import Path
from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"


def _headers(client: TestClient, role: str, clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_subject_access_authority_and_retention_erasure_block(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'pat_sar.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=dentist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")

        pat = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Quyền Truy Xuất Dữ Liệu", "birth_year": 2014},
        ).json()["id"]

        # Open clinical encounter & record an internal_staff_only contact log
        client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat, "practitioner_id": doc_id},
        )
        secret_internal_log = "GHI_CHU_NOI_BO_KHONG_XUAT_SAR"
        client.post(
            f"/api/v1/patients/{pat}/contact-timeline",
            headers=receptionist,
            json={
                "channel": "phone",
                "visibility": "internal_staff_only",
                "summary_text": secret_internal_log,
            },
        )

        # Negative 1 (PAT-011): Unverified requester authority denied -> 403
        assert (
            client.post(
                f"/api/v1/patients/{pat}/access-requests",
                headers=receptionist,
                json={
                    "requester_kind": "self",
                    "requester_name": "Người lạ chưa xác minh",
                    "request_type": "structured_access_export",
                    "authority_verified": False,
                },
            ).status_code
            == 403
        )

        # Negative 2 (PAT-011): Guardian export without verified guardian ConsentRecord -> 403
        assert (
            client.post(
                f"/api/v1/patients/{pat}/access-requests",
                headers=receptionist,
                json={
                    "requester_kind": "guardian",
                    "requester_name": "Phụ huynh chưa có hồ sơ giám hộ",
                    "request_type": "structured_access_export",
                    "authority_verified": True,
                },
            ).status_code
            == 403
        )

        # Negative 3 (PAT-011 / SEC-010): Erasure request blocked when retained clinical encounter exists -> 409
        assert (
            client.post(
                f"/api/v1/patients/{pat}/access-requests",
                headers=receptionist,
                json={
                    "requester_kind": "self",
                    "requester_name": "BN Quyền Truy Xuất Dữ Liệu",
                    "request_type": "erasure_request",
                    "authority_verified": True,
                },
            ).status_code
            == 409
        )

        # Grant verified guardian consent -> guardian structured_access_export succeeds & omits internal notes
        client.post(
            "/api/v1/consents",
            headers=receptionist,
            json={
                "patient_id": pat,
                "purpose": "data_processing",
                "template_version": "DP-GUARDIAN-V1",
                "disclosure_summary": "Đồng ý xử lý và trích xuất dữ liệu người giám hộ hợp pháp",
                "signer_name": "Mẹ Giám Hộ Đã Xác Minh",
                "signer_relationship": "guardian",
                "guardian_authority_verified": True,
            },
        )
        sar = client.post(
            f"/api/v1/patients/{pat}/access-requests",
            headers=receptionist,
            json={
                "requester_kind": "guardian",
                "requester_name": "Mẹ Giám Hộ Đã Xác Minh",
                "request_type": "structured_access_export",
                "authority_verified": True,
            },
        )
        assert sar.status_code == 201, sar.text
        assert secret_internal_log not in sar.text
        assert sar.json()["status"] == "fulfilled_export_ready"
        assert len(sar.json()["export_sha256"]) == 64


def test_cancellation_recovery_and_portal_upload_malware_quarantine_and_support_triage(
    tmp_path: Path,
):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'portal_rec.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=dentist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        pat_booked = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Hủy Lịch", "birth_year": 1990},
        ).json()["id"]
        pat_no_consent = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Chờ Chưa Đồng Ý", "birth_year": 1992},
        ).json()["id"]
        pat_consented = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Chờ Có Đồng Ý", "birth_year": 1995},
        ).json()["id"]

        client.post(
            "/api/v1/consents",
            headers=receptionist,
            json={
                "patient_id": pat_consented,
                "purpose": "treatment",
                "template_version": "TRT-V1",
                "disclosure_summary": "Đồng ý khám và liên hệ lịch hẹn",
                "signer_name": "BN Chờ Có Đồng Ý",
            },
        )
        client.post(
            "/api/v1/operations/waitlist",
            headers=receptionist,
            json={
                "patient_id": pat_no_consent,
                "preferred_practitioner_id": doc_id,
                "preferred_date_window": "2026-12",
                "service_note_minimized": "Khám định kỳ",
            },
        )
        client.post(
            "/api/v1/operations/waitlist",
            headers=receptionist,
            json={
                "patient_id": pat_consented,
                "preferred_practitioner_id": doc_id,
                "preferred_date_window": "2026-12",
                "service_note_minimized": "Tư vấn phục hình",
            },
        )

        appt = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_booked,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-15T09:00:00+07:00",
                "end_at": "2026-12-15T10:00:00+07:00",
            },
        ).json()["id"]

        # Negative 1 (SCH-014): Cannot run cancellation recovery on active confirmed appointment -> 409
        assert (
            client.post(
                f"/api/v1/scheduling/appointments/{appt}/cancellation-recovery",
                headers=receptionist,
                json={},
            ).status_code
            == 409
        )

        client.post(f"/api/v1/appointments/{appt}/cancel", headers=receptionist)

        # Negative 2 (SCH-014): Clinical urgency priority inference prohibited -> 409
        assert (
            client.post(
                f"/api/v1/scheduling/appointments/{appt}/cancellation-recovery",
                headers=receptionist,
                json={"claim_clinical_urgency_ranking": True},
            ).status_code
            == 409
        )

        rec = client.post(
            f"/api/v1/scheduling/appointments/{appt}/cancellation-recovery",
            headers=receptionist,
            json={},
        )
        assert rec.status_code == 201, rec.text
        rb = rec.json()
        assert rb["clinical_priority_inferred"] is False
        assert rb["excluded_no_consent_count"] == 1
        assert len(rb["ranked_candidates"]) == 1
        assert rb["ranked_candidates"][0]["patient_id"] == pat_consented

        # PORT-008 & PORT-010: Issue patient portal token
        grant = client.post(
            "/api/v1/portal/grants",
            headers=receptionist,
            json={
                "patient_id": pat_consented,
                "actor_kind": "self",
                "actor_display_name": "BN Chờ Có Đồng Ý",
            },
        ).json()
        portal_hdr = {"Authorization": f"Bearer {grant['portal_token']}"}

        # Negative 3 (PORT-008): EICAR / executable / active-script upload blocked -> 422
        eicar_b64 = base64.b64encode(
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        ).decode("ascii")
        assert (
            client.post(
                "/api/v1/patient-portal/uploads",
                headers=portal_hdr,
                json={
                    "original_filename": "scan.pdf",
                    "declared_media_type": "application/pdf",
                    "content_b64": eicar_b64,
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/patient-portal/uploads",
                headers=portal_hdr,
                json={
                    "original_filename": "payload.exe",
                    "declared_media_type": "application/octet-stream",
                    "content_b64": base64.b64encode(b"MZ-executable").decode("ascii"),
                },
            ).status_code
            == 422
        )

        # Clean PDF lands in quarantine_status='quarantined_pending_review' until clinician approves
        clean_pdf_b64 = base64.b64encode(b"%PDF-1.4 synthetic referral image stub").decode("ascii")
        up = client.post(
            "/api/v1/patient-portal/uploads",
            headers=portal_hdr,
            json={
                "original_filename": "phim-cu-ngoai-vien.pdf",
                "declared_media_type": "application/pdf",
                "content_b64": clean_pdf_b64,
            },
        )
        assert up.status_code == 201, up.text
        assert up.json()["quarantine_status"] == "quarantined_pending_review"
        up_id = up.json()["id"]

        # Receptionist cannot clinically approve quarantined upload -> 403; dentist approves -> 200
        assert (
            client.post(
                f"/api/v1/portal/uploads/{up_id}/review",
                headers=receptionist,
                json={"decision": "approved_by_staff", "review_note": "Lễ tân thử duyệt"},
            ).status_code
            == 403
        )
        rev_up = client.post(
            f"/api/v1/portal/uploads/{up_id}/review",
            headers=dentist,
            json={"decision": "approved_by_staff", "review_note": "Bác sĩ xác nhận tệp PDF hợp lệ"},
        )
        assert rev_up.status_code == 200
        assert rev_up.json()["quarantine_status"] == "approved_by_staff"

        # PORT-010: Urgent portal message triaged to human queue, zero autonomous medical advice
        msg = client.post(
            "/api/v1/patient-portal/support-messages",
            headers=portal_hdr,
            json={"message_text": "Em bị sưng to và chảy máu nhiều sau nhổ răng khôn, uống thuốc gì ạ?"},
        )
        assert msg.status_code == 201, msg.text
        mb = msg.json()
        assert mb["urgency_flag"] == "urgent_human_triage"
        assert mb["autonomous_medical_advice_sent"] is False
        assert mb["triage_status"] == "queued_for_human"

        # Negative 4 (PORT-010): AI autonomous reply rejected -> 422; human staff reply succeeds
        assert (
            client.post(
                f"/api/v1/portal/support-messages/{mb['id']}/reply",
                headers=dentist,
                json={
                    "reply_text": "Tự động kê kháng sinh",
                    "authoring_source": "ai_autonomous",
                },
            ).status_code
            == 422
        )
        rep = client.post(
            f"/api/v1/portal/support-messages/{mb['id']}/reply",
            headers=dentist,
            json={
                "reply_text": "Mời bạn quay lại phòng khám ngay để bác sĩ trực kiểm tra cầm máu trực tiếp.",
                "authoring_source": "human_staff",
            },
        )
        assert rep.status_code == 200, rep.text
        assert rep.json()["triage_status"] == "responded_by_human"


def test_staff_competency_expiry_guard_and_performed_vs_collected_commission_separation(
    tmp_path: Path,
):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'hr_comp_comm.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        dentist = _headers(client, "dentist")
        finance = _headers(client, "finance")
        receptionist = _headers(client, "receptionist")

        ctx = client.get("/api/v1/demo/context", headers=owner).json()
        doc_1_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        doc_2_id = client.post(
            "/api/v1/staff",
            headers=owner,
            json={"display_name": "Bác sĩ Implant Chứng Chỉ Còn Hạn", "role": "dentist"},
        ).json()["id"]
        dentist_2_tok = client.post(
            "/api/v1/auth/token",
            json={"clinic_id": CLINIC_A, "role": "dentist", "staff_id": doc_2_id},
        ).json()["access_token"]
        dentist_2 = {"Authorization": f"Bearer {dentist_2_tok}", "X-Demo-Clinic": CLINIC_A}

        # HR-009: Register expired competency for doc_1 (2025-01-01) and active competency for doc_2 (2028-12-31)
        assert (
            client.post(
                "/api/v1/hr/competencies",
                headers=owner,
                json={
                    "staff_id": doc_1_id,
                    "competency_code": "IMP-SINUS-LIFT",
                    "title_vi": "Nâng xoang ghép xương Implant nâng cao",
                    "expires_on": "2025-01-01",
                },
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/hr/competencies",
                headers=owner,
                json={
                    "staff_id": doc_2_id,
                    "competency_code": "IMP-SINUS-LIFT",
                    "title_vi": "Nâng xoang ghép xương Implant nâng cao",
                    "expires_on": "2028-12-31",
                },
            ).status_code
            == 201
        )

        pat_paid_only = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Đã Đóng Tiền Chưa Làm Thủ Thuật", "birth_year": 1985},
        ).json()["id"]
        pat_performed_only = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Đã Làm Thủ Thuật Chưa Thu Tiền", "birth_year": 1990},
        ).json()["id"]

        enc_1 = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat_performed_only, "practitioner_id": doc_1_id},
        ).json()["id"]
        enc_2 = client.post(
            "/api/v1/encounters",
            headers=dentist_2,
            json={"patient_id": pat_performed_only, "practitioner_id": doc_2_id},
        ).json()["id"]

        # Negative 1 (HR-009): doc_1 has EXPIRED IMP-SINUS-LIFT -> both assignment check and performed procedure blocked (409)!
        assert (
            client.post(
                "/api/v1/hr/competencies/validate-assignment",
                headers=receptionist,
                json={
                    "staff_id": doc_1_id,
                    "competency_code": "IMP-SINUS-LIFT",
                    "as_of_date": "2026-11-25",
                },
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/encounters/{enc_1}/performed-procedures",
                headers=dentist,
                json={
                    "tooth_code": "16",
                    "surface": "O",
                    "procedure_code_demo": "IMP-SINUS-LIFT",
                    "description_vi": "Nâng xoang hàm trên R16",
                    "clinical_evidence_note": "Thử ghi nhận khi chứng chỉ hết hạn",
                },
            ).status_code
            == 409
        )

        # doc_2 has active competency -> succeeds recording performed procedure (with ZERO payment collected)
        proc_ok = client.post(
            f"/api/v1/encounters/{enc_2}/performed-procedures",
            headers=dentist_2,
            json={
                "tooth_code": "16",
                "surface": "O",
                "procedure_code_demo": "IMP-SINUS-LIFT",
                "description_vi": "Nâng xoang hàm trên R16 giả lập",
                "clinical_evidence_note": "X-quang kiểm tra sau đặt màng",
            },
        )
        assert proc_ok.status_code == 201, proc_ok.text

        # Meanwhile pat_paid_only pays 10,000,000 VND upfront deposit with ZERO performed procedures!
        chg = client.post(
            "/api/v1/finance/charges",
            headers=finance,
            json={"patient_id": pat_paid_only, "label": "Tạm ứng gói chỉnh nha", "amount_vnd": 10000000},
        ).json()["id"]
        pmt = client.post(
            "/api/v1/finance/payments",
            headers=finance,
            json={"patient_id": pat_paid_only, "amount_vnd": 10000000, "payment_method": "bank_transfer"},
        ).json()["id"]
        client.post(
            "/api/v1/finance/allocations",
            headers=finance,
            json={"charge_id": chg, "payment_id": pmt, "amount_vnd": 10000000},
        )

        # HR-007: Commission preview strictly separates clinically performed vs financially collected!
        comm = client.get("/api/v1/hr/commission-preview", headers=owner)
        assert comm.status_code == 200, comm.text
        cb = comm.json()
        assert cb["performed_equated_to_collected"] is False
        assert cb["clinic_totals"]["total_performed_procedures_count"] == 1
        assert cb["clinic_totals"]["total_allocated_collected_vnd"] == 10000000
        doc_2_row = next(r for r in cb["clinician_performed_ledger"] if r["staff_id"] == doc_2_id)
        assert doc_2_row["performed_procedures_count"] == 1
        doc_1_row = next(r for r in cb["clinician_performed_ledger"] if r["staff_id"] == doc_1_id)
        assert doc_1_row["performed_procedures_count"] == 0
