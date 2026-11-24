"""T016 versioned service price catalog without retroactive estimate mutation (FIN-001),
discount & override dual-control approval without hidden treatment changes (FIN-014),
and attributable owner KPI lineage & metric dictionary (RPT-002, RPT-004..007, RPT-011).

Written BEFORE T016 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"


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


def test_versioned_price_catalog_and_dual_control_discount_preserve_quoted_estimates_and_plans(
    tmp_path: Path,
):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'catalog_discount.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        dentist = _headers(client, "dentist")
        finance = _headers(client, "finance")
        receptionist = _headers(client, "receptionist")

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Bảng giá & Phê duyệt Giảm giá", "birth_year": 1988},
        ).json()["id"]

        plan = client.post(
            "/api/v1/treatment-plans",
            headers=dentist,
            json={"patient_id": pat_id, "title": "Cấy ghép 2 trụ Implant vùng răng hàm"},
        ).json()
        plan_id = plan["id"]
        task = client.post(
            f"/api/v1/treatment-plans/{plan_id}/tasks",
            headers=dentist,
            json={"title": "Đặt trụ Implant răng 36 và 46", "phase": "Phẫu thuật"},
        ).json()

        # Publish catalog v1: IMP-001 = 20,000,000 VND, max_auto_discount_pct = 5%
        cat_v1 = client.post(
            "/api/v1/finance/price-catalog",
            headers=owner,
            json={
                "service_code": "IMP-001",
                "name_vi": "Trụ Implant Titanium tiêu chuẩn",
                "category": "implant",
                "unit_price_vnd": 20000000,
                "max_auto_discount_pct": 5,
            },
        )
        assert cat_v1.status_code == 201, cat_v1.text
        v1_id = cat_v1.json()["id"]
        assert cat_v1.json()["version_number"] == 1
        assert cat_v1.json()["status"] == "active"

        # Build EstimateVersion v1 from catalog (2 units * 20,000,000 = 40,000,000 VND)
        est_v1 = client.post(
            "/api/v1/finance/estimates/from-catalog",
            headers=finance,
            json={
                "patient_id": pat_id,
                "plan_id": plan_id,
                "lines": [{"catalog_item_id": v1_id, "quantity": 2}],
            },
        )
        assert est_v1.status_code == 201, est_v1.text
        est_v1_id = est_v1.json()["estimate"]["id"]
        assert est_v1.json()["estimate"]["amount_vnd"] == 40000000
        assert est_v1.json()["estimate"]["version_number"] == 1

        # Negative 1 (FIN-001): Updating IMP-001 price to 24,000,000 creates v2 and NEVER overwrites est_v1
        cat_v2 = client.post(
            "/api/v1/finance/price-catalog",
            headers=owner,
            json={
                "service_code": "IMP-001",
                "name_vi": "Trụ Implant Titanium tiêu chuẩn (biểu giá mới)",
                "category": "implant",
                "unit_price_vnd": 24000000,
                "max_auto_discount_pct": 5,
            },
        )
        assert cat_v2.status_code == 201
        assert cat_v2.json()["version_number"] == 2

        check_est_v1 = client.get(
            f"/api/v1/finance/estimates/{est_v1_id}/lines", headers=finance
        )
        assert check_est_v1.status_code == 200
        assert check_est_v1.json()["estimate"]["amount_vnd"] == 40000000
        assert check_est_v1.json()["lines"][0]["locked_unit_price_vnd"] == 20000000
        assert check_est_v1.json()["lines"][0]["catalog_version_number"] == 1

        # Negative 2 (FIN-014): 15% discount (6,000,000 VND > 5% threshold) enters pending_owner_approval
        disc_req = client.post(
            f"/api/v1/finance/estimates/{est_v1_id}/discounts",
            headers=finance,
            json={
                "discount_amount_vnd": 6000000,
                "reason": "Chương trình tri ân gia đình cấy 2 trụ Implant",
            },
        )
        assert disc_req.status_code == 201
        req_id = disc_req.json()["id"]
        assert disc_req.json()["status"] == "pending_owner_approval"
        assert disc_req.json()["resulting_estimate_id"] is None

        # Finance cannot approve owner-level discount override -> 403
        assert (
            client.post(
                f"/api/v1/finance/discount-requests/{req_id}/decide",
                headers=finance,
                json={"approve": True, "decision_note": "Tự duyệt sai thẩm quyền"},
            ).status_code
            == 403
        )

        # Owner initiating an above-threshold discount cannot self-approve -> 409
        owner_disc = client.post(
            f"/api/v1/finance/estimates/{est_v1_id}/discounts",
            headers=owner,
            json={"discount_amount_vnd": 5000000, "reason": "Chủ phòng khám tạo đề xuất giảm giá"},
        ).json()["id"]
        assert (
            client.post(
                f"/api/v1/finance/discount-requests/{owner_disc}/decide",
                headers=owner,
                json={"approve": True, "decision_note": "Tự phê duyệt"},
            ).status_code
            == 409
        )

        # Independent clinic_owner approves finance's request -> creates EstimateVersion v2 (34,000,000 VND)
        # while leaving est_v1 (40,000,000) AND TreatmentPlan / PlanTask completely unchanged!
        decided = client.post(
            f"/api/v1/finance/discount-requests/{req_id}/decide",
            headers=owner,
            json={"approve": True, "decision_note": "Đồng ý mức ưu đãi 15% không đổi phác đồ"},
        )
        assert decided.status_code == 200
        assert decided.json()["status"] == "approved"
        est_v2_id = decided.json()["resulting_estimate_id"]
        assert est_v2_id is not None and est_v2_id != est_v1_id

        est_v2_detail = client.get(
            f"/api/v1/finance/estimates/{est_v2_id}/lines", headers=finance
        ).json()
        assert est_v2_detail["estimate"]["version_number"] == 2
        assert est_v2_detail["estimate"]["amount_vnd"] == 34000000

        # Original v1 estimate and clinical TreatmentPlan remain untouched
        assert (
            client.get(f"/api/v1/finance/estimates/{est_v1_id}/lines", headers=finance).json()[
                "estimate"
            ]["amount_vnd"]
            == 40000000
        )
        plan_after = client.get(f"/api/v1/treatment-plans/{plan_id}", headers=dentist).json()
        assert plan_after["plan"]["current_version"] == 1
        assert [t["id"] for t in plan_after["tasks"]] == [task["id"]]


def test_owner_kpi_lineage_separates_scheduled_vs_utilized_and_billed_vs_cash(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'kpi_lineage.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner")
        dentist = _headers(client, "dentist")
        assistant = _headers(client, "assistant")
        receptionist = _headers(client, "receptionist")
        finance = _headers(client, "finance")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        pat_a = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN KPI Ghế & Doanh thu A", "birth_year": 1991},
        ).json()["id"]
        pat_b = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN KPI Tái khám Opt-Out B", "birth_year": 1994},
        ).json()["id"]

        # Book two 60-minute appointments (total scheduled = 120 min), but seat ONLY appt_1 (utilized = 60 min)
        appt_1 = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_a,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-26T08:00:00+07:00",
                "end_at": "2026-12-26T09:00:00+07:00",
                "reason_demo": "Ca thực tế đã vào ghế",
            },
        ).json()["id"]
        appt_2 = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_b,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-26T09:30:00+07:00",
                "end_at": "2026-12-26T10:30:00+07:00",
                "reason_demo": "Ca mới đặt lịch, chưa vào ghế",
            },
        ).json()["id"]

        # Complete turnover and seat appt_1 into in_chair
        to_id = client.post(
            "/api/v1/operations/turnovers",
            headers=assistant,
            json={"chair_id": chair_id, "appointment_id": appt_1},
        ).json()["id"]
        client.post(
            f"/api/v1/operations/turnovers/{to_id}/complete",
            headers=assistant,
            json={
                "surface_disinfected": True,
                "sterile_kit_verified": True,
                "waterline_flushed": True,
                "assistant_prep_ready": True,
                "notes": "Hoàn tất vô khuẩn",
            },
        )
        ci_id = client.post(
            "/api/v1/operations/checkins",
            headers=receptionist,
            json={
                "appointment_id": appt_1,
                "identity_verified": True,
                "verification_method": "photo_id_checked",
            },
        ).json()["id"]
        assert (
            client.post(
                f"/api/v1/operations/checkins/{ci_id}/status",
                headers=assistant,
                json={"next_status": "in_chair"},
            ).status_code
            == 200
        )

        # Finance: Billed charge = 10,000,000 VND; Payment = 3,000,000 VND; Allocated = 2,000,000 VND
        chg_id = client.post(
            "/api/v1/finance/charges",
            headers=finance,
            json={"patient_id": pat_a, "label": "Phục hình sứ Zirconia", "amount_vnd": 10000000},
        ).json()["id"]
        pay_id = client.post(
            "/api/v1/finance/payments",
            headers=finance,
            json={"patient_id": pat_a, "amount_vnd": 3000000, "payment_method": "cash"},
        ).json()["id"]
        client.post(
            "/api/v1/finance/allocations",
            headers=finance,
            json={"charge_id": chg_id, "payment_id": pay_id, "amount_vnd": 2000000},
        )

        # Lab case: received from lab, NOT clinically verified yet (RPT-007)
        lab_id = client.post(
            "/api/v1/lab-cases",
            headers=dentist,
            json={
                "patient_id": pat_a,
                "title": "Mão Zirconia răng 16",
                "specification_demo": "Màu A2",
                "due_on": "2026-11-01T10:00:00+07:00",
            },
        ).json()["id"]
        for st in ("accepted", "in_progress", "ready"):
            client.post(
                f"/api/v1/lab-cases/{lab_id}/state", headers=dentist, json={"next_status": st}
            )
        client.post(
            f"/api/v1/lab-cases/{lab_id}/receive",
            headers=dentist,
            json={"condition": "Nguyên niêm phong hộp labo"},
        )

        # Recall: 2 clinical recalls (1 closed for pat_a; 1 open for pat_b who withdraws treatment notice consent)
        rec_a = client.post(
            "/api/v1/operations/recalls",
            headers=dentist,
            json={
                "patient_id": pat_a,
                "kind": "clinical_recall",
                "due_date": "2026-11-20",
                "reason": "Tái khám kiểm tra khớp cắn",
                "clinician_approved": True,
            },
        ).json()["id"]
        client.post(
            f"/api/v1/operations/recalls/{rec_a}/close",
            headers=receptionist,
            json={"closure_evidence": "Đã gọi xác nhận và đặt lịch tái khám"},
        )
        client.post(
            "/api/v1/operations/recalls",
            headers=dentist,
            json={
                "patient_id": pat_b,
                "kind": "clinical_recall",
                "due_date": "2026-11-20",
                "reason": "Tái khám định kỳ 6 tháng",
                "clinician_approved": True,
            },
        )
        c_b = client.post(
            "/api/v1/consents",
            headers=receptionist,
            json={
                "patient_id": pat_b,
                "purpose": "treatment",
                "template_version": "CONSENT-2026-V1",
                "disclosure_summary": "Đồng thuận thông báo điều trị",
                "signer_name": "BN B",
                "signer_relationship": "self",
            },
        ).json()["id"]
        client.post(
            f"/api/v1/consents/{c_b}/withdraw",
            headers=receptionist,
            json={"reason": "Từ chối nhận liên hệ tái khám"},
        )

        # Verify RPT-011 dictionary & KPI lineage report
        dict_resp = client.get("/api/v1/reports/dictionary", headers=owner)
        assert dict_resp.status_code == 200
        dict_codes = {d["metric_code"] for d in dict_resp.json()}
        assert {"RPT-002", "RPT-004", "RPT-005", "RPT-006", "RPT-007"}.issubset(dict_codes)

        kpi_resp = client.get("/api/v1/reports/kpi-lineage", headers=owner)
        assert kpi_resp.status_code == 200, kpi_resp.text
        kpis = {k["metric_code"]: k for k in kpi_resp.json()["metrics"]}

        # RPT-002: Scheduled (120m) != Utilized (60m)
        rpt2 = kpis["RPT-002"]
        assert rpt2["values"]["scheduled_chair_minutes"] == 120
        assert rpt2["values"]["utilized_chair_minutes"] == 60
        assert appt_1 in rpt2["source_record_ids"] and appt_2 in rpt2["source_record_ids"]
        assert rpt2["formula_expression"] and rpt2["review_owner_role"]

        # RPT-006: Accrual billed (10M) != Net cash collected (3M) != Allocated (2M)
        rpt6 = kpis["RPT-006"]
        assert rpt6["values"]["billed_charges_vnd"] == 10000000
        assert rpt6["values"]["net_collected_cash_vnd"] == 3000000
        assert rpt6["values"]["allocated_to_charges_vnd"] == 2000000
        assert rpt6["values"]["unallocated_deposit_liability_vnd"] == 1000000
        assert rpt6["values"]["outstanding_receivable_vnd"] == 8000000

        # RPT-007: Delivered lab case awaiting clinical verification is explicitly flagged
        rpt7 = kpis["RPT-007"]
        assert rpt7["values"]["delivered_awaiting_clinical_verification_count"] == 1
        assert lab_id in rpt7["source_record_ids"]

        # RPT-004: Opt-out patient excluded from denominator, documented in exclusions
        rpt4 = kpis["RPT-004"]
        assert rpt4["values"]["excluded_opt_out_count"] == 1
        assert rpt4["values"]["due_recall_denominator_count"] == 1
        assert rpt4["values"]["completed_followup_numerator_count"] == 1
        assert rpt4["values"]["followup_rate_bp"] == 10000
