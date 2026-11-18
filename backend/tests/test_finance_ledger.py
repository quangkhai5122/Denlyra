"""T008 negative and acceptance tests: Versioned estimates, idempotent ledger, concurrent allocation bounds, and daily cashier reconciliation."""
from concurrent.futures import ThreadPoolExecutor
import threading
from fastapi import HTTPException

from denlyra import services as svc


def test_versioned_estimates_and_idempotent_charge_payment_allocation_refund(client, patient):
    plan = client.post(
        "/api/v1/treatment-plans",
        json={"patient_id": patient["id"], "title": "Kế hoạch Implant Demo"},
    ).json()

    # 1. Create Estimate v1 and accept it; modifying v1 requires Estimate v2 (FIN-002 / TRT-011)
    est1 = client.post(
        "/api/v1/finance/estimates",
        json={
            "patient_id": patient["id"],
            "plan_id": plan["id"],
            "version_number": 1,
            "amount_vnd": 15_000_000,
            "items_summary": "Trụ Implant + Abutment + Mão sứ demo",
        },
    )
    assert est1.status_code == 201, est1.text
    est1_id = est1.json()["id"]

    # Duplicate version_number=1 rejected (409)
    assert client.post(
        "/api/v1/finance/estimates",
        json={
            "patient_id": patient["id"],
            "plan_id": plan["id"],
            "version_number": 1,
            "amount_vnd": 16_000_000,
            "items_summary": "Ghi đè báo giá cũ",
        },
    ).status_code == 409

    acc = client.post(
        f"/api/v1/finance/estimates/{est1_id}/accept",
        json={"accepted_by": "Bệnh nhân Demo A"},
    )
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"

    # Version 2 estimate preserves Version 1
    est2 = client.post(
        "/api/v1/finance/estimates",
        json={
            "patient_id": patient["id"],
            "plan_id": plan["id"],
            "version_number": 2,
            "amount_vnd": 18_000_000,
            "items_summary": "Bổ sung ghép xương nhân tạo mô phỏng",
        },
    )
    assert est2.status_code == 201

    # 2. Idempotent Charge & Payment webhook/receipt deduplication (NEG-08 / NEG-17)
    c1 = client.post(
        "/api/v1/finance/charges",
        json={
            "patient_id": patient["id"],
            "label": "Đợt 1 đặt trụ demo",
            "amount_vnd": 10_000_000,
            "idempotency_key": "chg-idem-001",
        },
    )
    assert c1.status_code == 201
    c1_retry = client.post(
        "/api/v1/finance/charges",
        json={
            "patient_id": patient["id"],
            "label": "Đợt 1 đặt trụ demo",
            "amount_vnd": 10_000_000,
            "idempotency_key": "chg-idem-001",
        },
    )
    assert c1_retry.status_code == 201
    assert c1_retry.json()["id"] == c1.json()["id"]

    # Conflicting amount with same idempotency_key rejected (409)
    assert client.post(
        "/api/v1/finance/charges",
        json={
            "patient_id": patient["id"],
            "label": "Đợt 1 đặt trụ demo",
            "amount_vnd": 9_000_000,
            "idempotency_key": "chg-idem-001",
        },
    ).status_code == 409

    # Duplicate payment webhook with same idempotency_key / external_reference posts only ONCE
    p_payload = {
        "patient_id": patient["id"],
        "amount_vnd": 6_000_000,
        "payment_method": "bank_transfer",
        "external_reference": "WEBHOOK-TXN-999",
        "idempotency_key": "pay-idem-999",
    }
    p1 = client.post("/api/v1/finance/payments", json=p_payload)
    assert p1.status_code == 201
    p1_dup = client.post("/api/v1/finance/payments", json=p_payload)
    assert p1_dup.status_code == 201
    assert p1_dup.json()["id"] == p1.json()["id"]
    assert len(client.get("/api/v1/finance/payments").json()) == 1

    # Idempotent allocation & refund
    a_payload = {
        "charge_id": c1.json()["id"],
        "payment_id": p1.json()["id"],
        "amount_vnd": 4_000_000,
        "idempotency_key": "alloc-idem-001",
    }
    a1 = client.post("/api/v1/finance/allocations", json=a_payload)
    assert a1.status_code == 201
    a1_dup = client.post("/api/v1/finance/allocations", json=a_payload)
    assert a1_dup.status_code == 201
    assert a1_dup.json()["id"] == a1.json()["id"]

    r_payload = {
        "amount_vnd": 1_000_000,
        "reason": "Hoàn một phần đặt cọc chuyển khoản",
        "idempotency_key": "ref-idem-001",
    }
    r1 = client.post(f"/api/v1/finance/payments/{p1.json()['id']}/refunds", json=r_payload)
    assert r1.status_code == 201
    r1_dup = client.post(f"/api/v1/finance/payments/{p1.json()['id']}/refunds", json=r_payload)
    assert r1_dup.status_code == 201
    assert r1_dup.json()["id"] == r1.json()["id"]

    # 3. Verify append-only ledger & patient revenue account summary (FIN-007 / FIN-011)
    acct = client.get(f"/api/v1/patients/{patient['id']}/revenue-account").json()
    assert acct["proposed_estimate_vnd"] == 18_000_000
    assert acct["charged_vnd"] == 10_000_000
    assert acct["collected_gross_vnd"] == 6_000_000
    assert acct["refunded_vnd"] == 1_000_000
    assert acct["net_collected_vnd"] == 5_000_000
    assert acct["allocated_vnd"] == 4_000_000
    assert acct["unallocated_credit_vnd"] == 1_000_000
    assert acct["outstanding_balance_vnd"] == 6_000_000
    assert acct["implies_clinical_completion"] is False
    assert len(acct["ledger_entries"]) == 4

    # 4. Daily Cashier Reconciliation (FIN-010)
    # Net bank_transfer collected today = 6,000,000 - 1,000,000 = 5,000,000 VND; cash = 0; card = 0
    rec_mismatch = client.post(
        "/api/v1/finance/reconciliations",
        json={
            "counted_cash_vnd": 0,
            "counted_transfer_vnd": 4_800_000,
            "counted_card_vnd": 0,
            "notes": "Lệch 200k chờ kiểm tra sao kê demo",
        },
    )
    assert rec_mismatch.status_code == 201
    assert rec_mismatch.json()["status"] == "discrepancy_flagged"
    assert rec_mismatch.json()["discrepancy_transfer_vnd"] == -200_000

    rec_exact = client.post(
        "/api/v1/finance/reconciliations",
        json={
            "counted_cash_vnd": 0,
            "counted_transfer_vnd": 5_000_000,
            "counted_card_vnd": 0,
            "notes": "Khớp sổ cuối ca demo",
        },
    )
    assert rec_exact.status_code == 201
    assert rec_exact.json()["status"] == "balanced"


def test_concurrent_payment_allocation_bounds_enforced(client, patient):
    charge = client.post(
        "/api/v1/finance/charges",
        json={"patient_id": patient["id"], "label": "Phí kiểm thử đua phân bổ", "amount_vnd": 2_000_000},
    ).json()
    payment = client.post(
        "/api/v1/finance/payments",
        json={"patient_id": patient["id"], "amount_vnd": 1_000_000, "payment_method": "cash"},
    ).json()

    factory = client.app.state.factory
    clinic_id = "11111111-1111-4111-8111-111111111111"
    barrier = threading.Barrier(2)

    def worker(idx: int) -> int:
        with factory() as session:
            barrier.wait(timeout=5)
            try:
                svc.allocate(
                    session,
                    clinic_id,
                    charge["id"],
                    payment["id"],
                    600_000,
                    actor=f"alloc-race-{idx}",
                )
                return 201
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(worker, [1, 2]))

    assert outcomes == [201, 409], f"Expected [201, 409], got {outcomes}"
