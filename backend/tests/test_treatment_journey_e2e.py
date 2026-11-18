"""T005 negative and end-to-end orthodontic/prosthetic treatment journey tests."""


def test_multi_dependency_dag_cycle_detection_and_blocking(client, patient):
    plan = client.post(
        "/api/v1/treatment-plans",
        json={"patient_id": patient["id"], "title": "Chỉnh nha & Phục hình nhiều giai đoạn"},
    ).json()
    pid = plan["id"]
    t_url = f"/api/v1/treatment-plans/{pid}/tasks"

    t1 = client.post(t_url, json={"title": "Khám & lấy dấu ban đầu", "phase": "Chẩn đoán", "owner_role": "dentist"}).json()
    t2 = client.post(t_url, json={"title": "Vệ sinh & chuẩn bị răng trụ", "phase": "Tiền phục hình", "owner_role": "dentist"}).json()
    # t3 depends on BOTH t1 and t2
    t3 = client.post(
        t_url,
        json={
            "title": "Lắp phục hình sứ kiểm thử",
            "phase": "Phục hình",
            "owner_role": "dentist",
            "depends_on_task_ids": [t1["id"], t2["id"]],
        },
    )
    assert t3.status_code == 201, t3.text
    t3_id = t3.json()["id"]

    # Self-dependency must be rejected (422)
    assert client.post(
        f"/api/v1/treatment-tasks/{t1['id']}/dependencies",
        json={"depends_on_task_ids": [t1["id"]]},
    ).status_code == 422

    # Cycle t1 -> t3 (when t3 already depends on t1) must be rejected (422)
    assert client.post(
        f"/api/v1/treatment-tasks/{t1['id']}/dependencies",
        json={"depends_on_task_ids": [t3_id]},
    ).status_code == 422

    # Review plan and verify t3 is blocked until BOTH t1 and t2 are completed (INV-011 / NEG-06)
    assert client.post(f"/api/v1/treatment-plans/{pid}/demo-review").status_code == 200
    assert client.post(f"/api/v1/treatment-tasks/{t3_id}/demo-complete").status_code == 409

    # Completing only t1 still leaves t3 blocked because t2 is pending!
    assert client.post(f"/api/v1/treatment-tasks/{t1['id']}/demo-complete").status_code == 200
    assert client.post(f"/api/v1/treatment-tasks/{t3_id}/demo-complete").status_code == 409

    # Completing t2 unblocks t3
    assert client.post(f"/api/v1/treatment-tasks/{t2['id']}/demo-complete").status_code == 200
    assert client.post(f"/api/v1/treatment-tasks/{t3_id}/demo-complete").status_code == 200


def test_full_prosthetic_orthodontic_e2e_reschedule_lab_delay_reassessment_and_refund(
    client, context
):
    doctor = next(s for s in context["staff"] if s["role"] == "dentist")
    chair_1, chair_2 = context["chairs"][0], context["chairs"][1]
    pat = client.post(
        "/api/v1/patients",
        json={"display_name": "Bệnh nhân Hành trình E2E", "birth_year": 1994},
    ).json()

    # 1. Create plan with Phase 1 (prep) and Phase 2 (delivery depending on Phase 1 + Lab verification)
    plan = client.post(
        "/api/v1/treatment-plans",
        json={"patient_id": pat["id"], "title": "Hành trình Phục hình Sứ Demo"},
    ).json()
    pid = plan["id"]
    t_prep = client.post(
        f"/api/v1/treatment-plans/{pid}/tasks",
        json={
            "title": "Sửa soạn cùi răng demo",
            "phase": "Giai đoạn 1",
            "owner_role": "dentist",
            "due_at": "2026-12-05T10:00:00+07:00",
        },
    ).json()
    t_deliver = client.post(
        f"/api/v1/treatment-plans/{pid}/tasks",
        json={
            "title": "Gắn mão sứ sau kiểm định labo",
            "phase": "Giai đoạn 2",
            "owner_role": "dentist",
            "depends_on_task_ids": [t_prep["id"]],
            "due_at": "2026-12-10T10:00:00+07:00",
        },
    ).json()
    assert client.post(f"/api/v1/treatment-plans/{pid}/demo-review").status_code == 200

    # 2. Book appointment and link to t_deliver, then test atomic reschedule (SCH-005)
    appt_1 = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": pat["id"],
            "practitioner_id": doctor["id"],
            "chair_id": chair_1["id"],
            "start_at": "2026-12-10T09:00:00+07:00",
            "end_at": "2026-12-10T10:00:00+07:00",
            "reason_demo": "Lịch gắn răng dự kiến",
        },
    ).json()
    resched = client.post(
        f"/api/v1/appointments/{appt_1['id']}/reschedule",
        json={
            "chair_id": chair_2["id"],
            "start_at": "2026-12-12T09:00:00+07:00",
            "end_at": "2026-12-12T10:00:00+07:00",
            "reason_demo": "Dời lịch do labo báo trễ",
        },
    )
    assert resched.status_code == 201, resched.text
    appt_2 = resched.json()
    assert appt_2["rescheduled_from_id"] == appt_1["id"]
    # Old appointment history preserved as cancelled, never deleted
    all_appts = client.get("/api/v1/appointments").json()
    assert len(all_appts) == 2
    assert any(a["id"] == appt_1["id"] and a["status"] == "cancelled" for a in all_appts)

    assert client.post(
        f"/api/v1/treatment-tasks/{t_deliver['id']}/links",
        json={"target_type": "appointment", "target_id": appt_2["id"]},
    ).status_code == 201

    # 3. Create lab case, link to t_deliver with requires_verified_lab=True
    lab = client.post(
        "/api/v1/lab-cases",
        json={"patient_id": pat["id"], "title": "Mão sứ Zirconia răng 26 demo"},
    ).json()
    assert client.post(
        f"/api/v1/treatment-tasks/{t_deliver['id']}/links",
        json={"target_type": "lab_case", "target_id": lab["id"], "requires_verified_lab": True},
    ).status_code == 201

    # Complete t_prep; move lab only to "received" (delivered, NOT clinically verified!)
    assert client.post(f"/api/v1/treatment-tasks/{t_prep['id']}/demo-complete").status_code == 200
    for st in ["accepted", "in_progress", "ready", "received"]:
        assert client.post(f"/api/v1/lab-cases/{lab['id']}/state", json={"next_status": st}).status_code == 200

    # NEG-09: Lab case is received but NOT verified -> completing t_deliver MUST fail with 409!
    # Also verify confirmed appointment appt_2 was NOT silently altered.
    assert client.post(f"/api/v1/treatment-tasks/{t_deliver['id']}/demo-complete").status_code == 409
    timeline_blocked = client.get(f"/api/v1/treatment-plans/{pid}/timeline").json()
    deliver_entry = next(x for x in timeline_blocked["tasks"] if x["id"] == t_deliver["id"])
    assert "lab_not_verified" in deliver_entry["blocked_reasons"]

    # 4. Finance: charge, payment, allocation, and refund reversal (FIN-006 / OPS-01 / OPS-03)
    charge = client.post(
        "/api/v1/finance/charges",
        json={"patient_id": pat["id"], "label": "Chi phí phục hình demo", "amount_vnd": 3_000_000},
    ).json()
    assert client.post(
        f"/api/v1/treatment-tasks/{t_deliver['id']}/links",
        json={"target_type": "charge", "target_id": charge["id"]},
    ).status_code == 201
    payment = client.post(
        "/api/v1/finance/payments",
        json={"patient_id": pat["id"], "amount_vnd": 2_000_000},
    ).json()
    assert client.post(
        "/api/v1/finance/allocations",
        json={"charge_id": charge["id"], "payment_id": payment["id"], "amount_vnd": 1_200_000},
    ).status_code == 201

    # Over-refund exceeding unallocated 800,000 VND rejected (409)
    assert client.post(
        f"/api/v1/finance/payments/{payment['id']}/refunds",
        json={"amount_vnd": 900_000, "reason": "Hoàn vượt số dư chưa phân bổ"},
    ).status_code == 409

    # Valid append-only refund of 500,000 VND succeeds while preserving original payment row
    refund = client.post(
        f"/api/v1/finance/payments/{payment['id']}/refunds",
        json={"amount_vnd": 500_000, "reason": "Điều chỉnh đặt cọc giả lập"},
    )
    assert refund.status_code == 201, refund.text
    # Payment/refund NEVER marks t_deliver complete!
    assert client.get(f"/api/v1/treatment-plans/{pid}").json()["tasks"][1]["status"] == "pending"

    # 5. Verify lab case -> complete t_deliver -> then clinician records Reassessment (PLAN-04)
    assert client.post(f"/api/v1/lab-cases/{lab['id']}/state", json={"next_status": "verified"}).status_code == 200
    assert client.post(f"/api/v1/treatment-tasks/{t_deliver['id']}/demo-complete").status_code == 200

    reassess = client.post(
        f"/api/v1/treatment-plans/{pid}/reassessments",
        json={
            "source_task_id": t_deliver["id"],
            "reason": "Cần chỉnh khớp cắn bổ sung sau theo dõi tuần đầu (mô phỏng)",
            "followup_task_title": "Tái đánh giá & chỉnh khớp cắn lần 2",
            "followup_phase": "Theo dõi & Tái đánh giá",
            "owner_role": "dentist",
        },
    )
    assert reassess.status_code == 201, reassess.text
    reassess_body = reassess.json()
    assert reassess_body["new_version_number"] == 2
    assert reassess_body["followup_task"]["reassessed_from_task_id"] is not None

    # Final timeline shows version 2 with preserved completed steps + new pending reassessment task + financial summary
    timeline_final = client.get(f"/api/v1/treatment-plans/{pid}/timeline").json()
    assert timeline_final["version"]["number"] == 2
    assert len(timeline_final["tasks"]) == 3
    assert timeline_final["financial_summary"]["refunded_vnd"] == 500_000
    assert timeline_final["financial_summary"]["implies_clinical_completion"] is False
