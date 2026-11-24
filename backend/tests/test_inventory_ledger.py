"""T011 append-only inventory lot ledger, reservation != consumption (INV-023), FEFO,
expiry/quarantine guards, DB movement immutability triggers, and dual-control adjustments (INV-010).

Written BEFORE T011 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"
CLINIC_B = "22222222-2222-4222-8222-222222222222"


def _headers(client: TestClient, role: str, clinic_id: str = CLINIC_A, staff_id: str | None = None) -> dict[str, str]:
    payload: dict = {"clinic_id": clinic_id, "role": role}
    if staff_id:
        payload["staff_id"] = staff_id
    resp = client.post("/api/v1/auth/token", json=payload)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_sku_supplier_tenant_isolation_and_po_receipt_separation(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'inv_po.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner_a = _headers(client, "clinic_owner", CLINIC_A)
        owner_b = _headers(client, "clinic_owner", CLINIC_B)

        sup = client.post(
            "/api/v1/inventory/suppliers",
            headers=owner_a,
            json={"name": "Nhà cung cấp Vật tư Nha khoa Demo", "tax_code_demo": "VN-SUP-001"},
        )
        assert sup.status_code == 201, sup.text
        sup_id = sup.json()["id"]

        # Duplicate supplier tax_code in same clinic -> 409
        assert (
            client.post(
                "/api/v1/inventory/suppliers",
                headers=owner_a,
                json={"name": "Trùng MST", "tax_code_demo": "VN-SUP-001"},
            ).status_code
            == 409
        )

        sku = client.post(
            "/api/v1/inventory/skus",
            headers=owner_a,
            json={
                "sku_code": "IMP-TI-4010",
                "name": "Trụ Implant Titanium 4.0x10mm (Demo)",
                "unit": "piece",
                "lot_tracked": True,
                "reorder_threshold": 5,
            },
        )
        assert sku.status_code == 201
        sku_id = sku.json()["id"]

        # Duplicate SKU in Clinic A -> 409; same SKU code in Clinic B -> 201 (INV-001)
        assert (
            client.post(
                "/api/v1/inventory/skus",
                headers=owner_a,
                json={"sku_code": "IMP-TI-4010", "name": "Dup", "unit": "piece"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/inventory/skus",
                headers=owner_b,
                json={"sku_code": "IMP-TI-4010", "name": "Clinic B Implant", "unit": "piece"},
            ).status_code
            == 201
        )

        po = client.post(
            "/api/v1/inventory/purchase-orders",
            headers=owner_a,
            json={"supplier_id": sup_id, "sku_id": sku_id, "ordered_qty": 10},
        )
        assert po.status_code == 201
        po_id = po.json()["id"]

        # Negative: inspected_accepted_qty > delivered_qty -> 422 (INV-003)
        bad_rcpt = client.post(
            f"/api/v1/inventory/purchase-orders/{po_id}/receive",
            headers=owner_a,
            json={
                "lot_number": "LOT-BAD",
                "expiry_date": "2028-06-30",
                "delivered_qty": 6,
                "inspected_accepted_qty": 8,
            },
        )
        assert bad_rcpt.status_code == 422

        # Valid receipt: ordered 10, delivered 10, inspected_accepted 8 -> available is 8, not 10
        rcpt = client.post(
            f"/api/v1/inventory/purchase-orders/{po_id}/receive",
            headers=owner_a,
            json={
                "lot_number": "LOT-2028-01",
                "expiry_date": "2028-06-30",
                "delivered_qty": 10,
                "inspected_accepted_qty": 8,
            },
        )
        assert rcpt.status_code == 201
        stock = client.get(f"/api/v1/inventory/skus/{sku_id}/stock", headers=owner_a).json()
        assert stock["physical_on_hand_qty"] == 8
        assert stock["available_qty"] == 8


def test_reservation_is_not_consumption_and_appointment_never_auto_deducts(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'inv_res.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner", CLINIC_A)
        dentist = _headers(client, "dentist", CLINIC_A)
        receptionist = _headers(client, "receptionist", CLINIC_A)
        ctx = client.get("/api/v1/demo/context", headers=dentist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        chair_id = ctx["chairs"][0]["id"]

        sup_id = client.post(
            "/api/v1/inventory/suppliers",
            headers=owner,
            json={"name": "Supplier A", "tax_code_demo": "SUP-RES-1"},
        ).json()["id"]
        sku_id = client.post(
            "/api/v1/inventory/skus",
            headers=owner,
            json={"sku_code": "BONE-GRAFT-05", "name": "Xương ghép tổng hợp 0.5g", "unit": "vial", "reorder_threshold": 4},
        ).json()["id"]
        po_id = client.post(
            "/api/v1/inventory/purchase-orders",
            headers=owner,
            json={"supplier_id": sup_id, "sku_id": sku_id, "ordered_qty": 5},
        ).json()["id"]
        lot_id = client.post(
            f"/api/v1/inventory/purchase-orders/{po_id}/receive",
            headers=owner,
            json={"lot_number": "LOT-BG-1", "expiry_date": "2028-12-31", "delivered_qty": 5, "inspected_accepted_qty": 5},
        ).json()["lot"]["id"]

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "Bệnh nhân Giữ chỗ Vật tư", "birth_year": 1990},
        ).json()["id"]
        appt = client.post(
            "/api/v1/appointments",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": "2026-12-10T09:00:00+07:00",
                "end_at": "2026-12-10T10:00:00+07:00",
                "reason_demo": "Ghép xương demo",
            },
        )
        assert appt.status_code == 201

        # Booking an appointment NEVER auto-deducts stock (INV-007)
        s0 = client.get(f"/api/v1/inventory/skus/{sku_id}/stock", headers=dentist).json()
        assert s0["physical_on_hand_qty"] == 5 and s0["available_qty"] == 5

        # Reserve 3 vials for planned case -> physical stays 5, available becomes 2 (INV-023)
        res = client.post(
            "/api/v1/inventory/reservations",
            headers=dentist,
            json={"sku_id": sku_id, "lot_id": lot_id, "reserved_qty": 3, "patient_id": pat_id, "appointment_id": appt.json()["id"]},
        )
        assert res.status_code == 201
        res_id = res.json()["id"]

        s1 = client.get(f"/api/v1/inventory/skus/{sku_id}/stock", headers=dentist).json()
        assert s1["physical_on_hand_qty"] == 5
        assert s1["active_reserved_qty"] == 3
        assert s1["available_qty"] == 2

        # Over-reservation (> available_qty=2) -> 409
        assert (
            client.post(
                "/api/v1/inventory/reservations",
                headers=dentist,
                json={"sku_id": sku_id, "lot_id": lot_id, "reserved_qty": 3, "patient_id": pat_id},
            ).status_code
            == 409
        )

        # Release reservation -> available_qty returns to 5 without faking a movement
        rel = client.post(
            f"/api/v1/inventory/reservations/{res_id}/release",
            headers=dentist,
            json={"reason": "Dời lịch phẫu thuật"},
        )
        assert rel.status_code == 200
        s2 = client.get(f"/api/v1/inventory/skus/{sku_id}/stock", headers=dentist).json()
        assert s2["physical_on_hand_qty"] == 5 and s2["available_qty"] == 5

        # Receptionist is denied clinical procedure consumption (403); dentist with active encounter succeeds
        enc_id = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat_id, "practitioner_id": doc_id},
        ).json()["id"]
        assert (
            client.post(
                "/api/v1/inventory/consumptions",
                headers=receptionist,
                json={"lot_id": lot_id, "encounter_id": enc_id, "consumed_qty": 2},
            ).status_code
            == 403
        )
        cons = client.post(
            "/api/v1/inventory/consumptions",
            headers=dentist,
            json={
                "lot_id": lot_id,
                "encounter_id": enc_id,
                "consumed_qty": 2,
                "procedure_note_demo": "Tiêu hao ghép xương tại ghế",
            },
        )
        assert cons.status_code == 201
        s3 = client.get(f"/api/v1/inventory/skus/{sku_id}/stock", headers=dentist).json()
        assert s3["physical_on_hand_qty"] == 3 and s3["available_qty"] == 3
        assert s3["low_stock"] is True  # 3 <= reorder_threshold (4)


def test_expired_and_quarantined_lots_blocked_fefo_order_and_dual_control_adjustments(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'inv_fefo_dual.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8766") as client:
        owner1 = _headers(client, "clinic_owner", CLINIC_A)
        dentist = _headers(client, "dentist", CLINIC_A)
        # Create a second distinct medical_director for dual-control approval
        md_resp = client.post(
            "/api/v1/staff",
            headers=owner1,
            json={"display_name": "Giám đốc chuyên môn Demo", "role": "medical_director"},
        )
        assert md_resp.status_code == 201
        md_headers = _headers(client, "medical_director", CLINIC_A, staff_id=md_resp.json()["id"])

        ctx = client.get("/api/v1/demo/context", headers=dentist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")
        pat_id = client.post(
            "/api/v1/patients",
            headers=dentist,
            json={"display_name": "BN Kiểm tra FEFO & Hạn dùng", "birth_year": 1985},
        ).json()["id"]
        enc_id = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat_id, "practitioner_id": doc_id},
        ).json()["id"]

        sup_id = client.post(
            "/api/v1/inventory/suppliers",
            headers=owner1,
            json={"name": "Supplier FEFO", "tax_code_demo": "SUP-FEFO-1"},
        ).json()["id"]
        sku_id = client.post(
            "/api/v1/inventory/skus",
            headers=owner1,
            json={"sku_code": "ANES-ARTI-4", "name": "Thuốc tê Articaine 4% (Demo)", "unit": "carpule", "reorder_threshold": 10},
        ).json()["id"]

        def receive_lot(lot_no: str, expiry: str, qty: int, quarantined: bool = False) -> str:
            po_id = client.post(
                "/api/v1/inventory/purchase-orders",
                headers=owner1,
                json={"supplier_id": sup_id, "sku_id": sku_id, "ordered_qty": qty},
            ).json()["id"]
            r = client.post(
                f"/api/v1/inventory/purchase-orders/{po_id}/receive",
                headers=owner1,
                json={
                    "lot_number": lot_no,
                    "expiry_date": expiry,
                    "delivered_qty": qty,
                    "inspected_accepted_qty": qty,
                    "quarantined": quarantined,
                },
            )
            assert r.status_code == 201, r.text
            return r.json()["lot"]["id"]

        lot_expired = receive_lot("LOT-EXP-2025", "2025-05-01", 5)
        lot_quarantined = receive_lot("LOT-QUAR-2027", "2027-01-15", 5, quarantined=True)
        lot_later = receive_lot("LOT-2027-DEC", "2027-12-01", 6)
        lot_sooner = receive_lot("LOT-2027-MAR", "2027-03-01", 4)

        # Consuming expired lot -> 409; consuming quarantined lot -> 409 (INV-004)
        assert (
            client.post(
                "/api/v1/inventory/consumptions",
                headers=dentist,
                json={"lot_id": lot_expired, "encounter_id": enc_id, "consumed_qty": 1, "as_of_date": "2026-12-01"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/inventory/consumptions",
                headers=dentist,
                json={"lot_id": lot_quarantined, "encounter_id": enc_id, "consumed_qty": 1, "as_of_date": "2026-12-01"},
            ).status_code
            == 409
        )

        # FEFO picker skips expired & quarantined lots and picks LOT-2027-MAR (4) then LOT-2027-DEC (2)
        fefo = client.get(
            f"/api/v1/inventory/skus/{sku_id}/fefo-picks?required_qty=6&as_of_date=2026-12-01",
            headers=dentist,
        )
        assert fefo.status_code == 200
        picks = fefo.json()["picks"]
        assert [(p["lot_id"], p["pick_qty"]) for p in picks] == [(lot_sooner, 4), (lot_later, 2)]

        # Append-only DB trigger blocks direct UPDATE or DELETE on stock_movement (INV-005)
        with app.state.factory() as db:
            with pytest.raises(IntegrityError):
                db.execute(text("UPDATE stock_movement SET quantity_delta = 999"))
                db.commit()
            db.rollback()
            with pytest.raises(IntegrityError):
                db.execute(text("DELETE FROM stock_movement"))
                db.commit()
            db.rollback()

        # Dual-control stock adjustment (INV-010): owner1 requests -2 shrinkage -> owner1 self-approve fails 409 -> md approves 200
        adj = client.post(
            "/api/v1/inventory/adjustments",
            headers=owner1,
            json={"lot_id": lot_later, "delta_qty": -2, "reason": "Vỡ 2 ống khi vận chuyển nội bộ"},
        )
        assert adj.status_code == 201
        adj_id = adj.json()["id"]

        self_approve = client.post(
            f"/api/v1/inventory/adjustments/{adj_id}/approve",
            headers=owner1,
            json={"approval_note": "Tự duyệt (phải bị chặn)"},
        )
        assert self_approve.status_code == 409

        dual_approve = client.post(
            f"/api/v1/inventory/adjustments/{adj_id}/approve",
            headers=md_headers,
            json={"approval_note": "Giám đốc chuyên môn đối chiếu biên bản xác nhận hủy 2 ống"},
        )
        assert dual_approve.status_code == 200
        assert dual_approve.json()["status"] == "approved"

        alerts = client.get("/api/v1/inventory/alerts?as_of_date=2026-12-01", headers=owner1).json()
        assert any(x["lot_id"] == lot_expired for x in alerts["expired_lots"])
        assert len(alerts["shrinkage_movements"]) == 1
