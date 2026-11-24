"""T017 tri-state medical/allergy risk review (EMR-003, PAT-003, INV-022), encounter closure
and missing-signature checklist gate (EMR-009, EMR-018), and clinician-authored dental diagnosis
and FDI tooth performed procedure evidence (EMR-010, EMR-011, ODN-005).

Written BEFORE T017 domain/API implementation per AGENTS.md negative-test-first rule.
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


def test_tristate_allergy_review_and_encounter_closure_missing_signature_gate(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'enc_lifecycle.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        assistant = _headers(client, "assistant")
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Kiểm soát Dị ứng & Đóng Lượt Khám", "birth_year": 1987},
        ).json()["id"]
        enc_id = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat_id, "practitioner_id": doc_id},
        ).json()["id"]

        # Negative 1 (EMR-003 / INV-022): Unanswered allergy is NOT coerced to explicit_negative
        partial_rev = client.post(
            f"/api/v1/patients/{pat_id}/medical-risk-reviews",
            headers=assistant,
            json={
                "encounter_id": enc_id,
                "cardiovascular_hypertension_state": "explicit_negative",
                "source": "patient_interview_demo",
            },
        )
        assert partial_rev.status_code == 201, partial_rev.text
        assert partial_rev.json()["drug_allergy_state"] == "unanswered"
        assert partial_rev.json()["bleeding_anticoagulant_state"] == "unanswered"

        # Present allergy without detail rejected -> 422
        assert (
            client.post(
                f"/api/v1/patients/{pat_id}/medical-risk-reviews",
                headers=dentist,
                json={
                    "encounter_id": enc_id,
                    "drug_allergy_state": "present",
                    "bleeding_anticoagulant_state": "explicit_negative",
                    "source": "clinician_review_demo",
                },
            ).status_code
            == 422
        )

        # Negative 2 (EMR-009): Attempting encounter closure with unanswered allergy & no locked note -> 409
        premature = client.post(f"/api/v1/encounters/{enc_id}/close-demo", headers=dentist)
        assert premature.status_code == 409

        # Record complete allergy review (present Penicillin -> high_risk_banner_active=True)
        full_rev = client.post(
            f"/api/v1/patients/{pat_id}/medical-risk-reviews",
            headers=dentist,
            json={
                "encounter_id": enc_id,
                "drug_allergy_state": "present",
                "drug_allergy_detail": "Tiền sử nổi mề đay với nhóm Penicillin (giả lập)",
                "bleeding_anticoagulant_state": "explicit_negative",
                "cardiovascular_hypertension_state": "explicit_negative",
                "pregnancy_nursing_state": "not_applicable",
                "source": "clinician_review_demo",
            },
        )
        assert full_rev.status_code == 201
        assert full_rev.json()["high_risk_banner_active"] is True
        assert full_rev.json()["revision_number"] == 2

        # Create draft note, lock it, and prepare an unsigned snapshot -> closure still blocked by unsigned snapshot (EMR-018)
        note_id = client.post(
            f"/api/v1/encounters/{enc_id}/notes",
            headers=dentist,
            json={"content": "Khám tổng quát răng hàm, ghi nhận cảnh báo dị ứng Penicillin."},
        ).json()["id"]
        client.post(f"/api/v1/notes/{note_id}/demo-lock", headers=dentist)
        snap = client.post(
            "/api/v1/clinical-documents/snapshots",
            headers=dentist,
            json={"note_id": note_id, "expected_revision": 1},
        ).json()

        chk = client.get(f"/api/v1/encounters/{enc_id}/closure-checklist", headers=dentist).json()
        assert chk["ready_to_close"] is False
        assert snap["id"] in chk["unsigned_snapshot_ids"]
        assert client.post(f"/api/v1/encounters/{enc_id}/close-demo", headers=dentist).status_code == 409

        # Notify responsible clinician of missing signature without fabricating signature (EMR-018)
        notif = client.post(
            f"/api/v1/encounters/{enc_id}/notify-missing-signatures", headers=assistant
        )
        assert notif.status_code == 200
        assert notif.json()["fabricated_signature"] is False
        assert client.get(f"/api/v1/clinical-documents/{snap['id']}", headers=dentist).json()["status"] == "ready_for_signature"

        # Sign synthetic snapshot -> encounter closure succeeds with honest status 'demo_closed_not_certified'
        client.post(
            f"/api/v1/clinical-documents/{snap['id']}/sign-synthetic",
            headers=dentist,
            json={"expected_sha256": snap["canonical_sha256"]},
        )
        closed = client.post(f"/api/v1/encounters/{enc_id}/close-demo", headers=dentist)
        assert closed.status_code == 200, closed.text
        assert closed.json()["status"] == "demo_closed_not_certified"

        # Post-closure direct draft note creation on closed encounter is blocked -> 409
        assert (
            client.post(
                f"/api/v1/encounters/{enc_id}/notes",
                headers=dentist,
                json={"content": "Cố ghi thêm nháp trực tiếp vào lượt khám đã đóng"},
            ).status_code
            == 409
        )


def test_performed_procedure_and_diagnosis_never_inferred_from_payment_or_ai(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'proc_evidence.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        assistant = _headers(client, "assistant")
        finance = _headers(client, "finance")
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Chẩn đoán & Thủ thuật Thực hiện", "birth_year": 1995},
        ).json()["id"]
        enc_id = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat_id, "practitioner_id": doc_id},
        ).json()["id"]

        # Create plan task, complete task administratively, and pay charge in full
        plan_id = client.post(
            "/api/v1/treatment-plans",
            headers=dentist,
            json={"patient_id": pat_id, "title": "Điều trị trám răng 36"},
        ).json()["id"]
        task_id = client.post(
            f"/api/v1/treatment-plans/{plan_id}/tasks",
            headers=dentist,
            json={"title": "Trám phục hồi xoang II răng 36", "phase": "Bảo tồn"},
        ).json()["id"]
        client.post(f"/api/v1/treatment-plans/{plan_id}/demo-review", headers=dentist)
        assert client.post(f"/api/v1/treatment-tasks/{task_id}/demo-complete", headers=dentist).status_code == 200

        chg_id = client.post(
            "/api/v1/finance/charges",
            headers=finance,
            json={"patient_id": pat_id, "label": "Thu tiền trám răng 36", "amount_vnd": 800000},
        ).json()["id"]
        pay_id = client.post(
            "/api/v1/finance/payments",
            headers=finance,
            json={"patient_id": pat_id, "amount_vnd": 800000, "payment_method": "cash"},
        ).json()["id"]
        client.post(
            "/api/v1/finance/allocations",
            headers=finance,
            json={"charge_id": chg_id, "payment_id": pay_id, "amount_vnd": 800000},
        )

        # Negative 1 (EMR-011 / ODN-005): Full payment + admin task completion NEVER creates performed procedure!
        odo_before = client.get(f"/api/v1/patients/{pat_id}/odontogram", headers=dentist).json()
        assert odo_before["performed_procedures"] == []

        # Negative 2 (EMR-010 / EMR-011): Non-clinician (assistant / finance) -> 403; AI direct write -> 422
        assert (
            client.post(
                f"/api/v1/encounters/{enc_id}/diagnoses",
                headers=assistant,
                json={
                    "tooth_code": "36",
                    "diagnosis_code_demo": "DX-CARIES-36",
                    "summary_vi": "Sâu ngà mặt nhai gần răng 36 (giả lập)",
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/encounters/{enc_id}/diagnoses",
                headers=dentist,
                json={
                    "tooth_code": "36",
                    "diagnosis_code_demo": "DX-AI-AUTO",
                    "summary_vi": "AI tự ghi chẩn đoán",
                    "authoring_source": "ai_unreviewed",
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/v1/encounters/{enc_id}/performed-procedures",
                headers=finance,
                json={
                    "tooth_code": "36",
                    "surface": "MO",
                    "procedure_code_demo": "PROC-COMP-II",
                    "description_vi": "Kế toán cố ghi thủ thuật",
                    "clinical_evidence_note": "Sai thẩm quyền",
                },
            ).status_code
            == 403
        )

        # Explicit licensed clinician records diagnosis and performed procedure on FDI tooth 36
        dx = client.post(
            f"/api/v1/encounters/{enc_id}/diagnoses",
            headers=dentist,
            json={
                "tooth_code": "36",
                "diagnosis_code_demo": "DX-CARIES-DENTIN",
                "summary_vi": "Tổn thương mô cứng mặt MO răng 36 (mô phỏng nghiên cứu)",
            },
        )
        assert dx.status_code == 201, dx.text

        proc = client.post(
            f"/api/v1/encounters/{enc_id}/performed-procedures",
            headers=dentist,
            json={
                "plan_task_id": task_id,
                "tooth_code": "36",
                "surface": "MO",
                "procedure_code_demo": "PROC-RESTORE-36MO",
                "description_vi": "Phục hồi Composite xoang II mặt MO răng 36",
                "clinical_evidence_note": "Kiểm tra điểm chạm cắn khít và tiếp xúc bên tốt",
            },
        )
        assert proc.status_code == 201, proc.text

        odo_after = client.get(f"/api/v1/patients/{pat_id}/odontogram", headers=dentist).json()
        assert len(odo_after["performed_procedures"]) == 1
        assert odo_after["performed_procedures"][0]["tooth_code"] == "36"
        assert odo_after["performed_procedures"][0]["plan_task_id"] == task_id
