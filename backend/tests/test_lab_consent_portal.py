"""T007 negative and acceptance tests: Consent taxonomy, lab requisitions, remakes, delay alerts, and scoped partner portal."""


def test_consent_separation_guardian_check_and_marketing_withdrawal(client, patient):
    # Guardian consent without verified authority must be rejected (422, PAT-004 / CLIN-04)
    bad_guardian = client.post(
        "/api/v1/consents",
        json={
            "patient_id": patient["id"],
            "purpose": "treatment",
            "template_version": "CONSENT-TRT-v1",
            "disclosure_summary": "Đồng thuận kế hoạch phục hình mô phỏng",
            "signer_name": "Người giám hộ Demo",
            "signer_relationship": "guardian",
            "guardian_authority_verified": False,
        },
    )
    assert bad_guardian.status_code == 422

    # Valid treatment, data_processing, and marketing consents recorded separately (INV-024)
    c_trt = client.post(
        "/api/v1/consents",
        json={
            "patient_id": patient["id"],
            "purpose": "treatment",
            "template_version": "CONSENT-TRT-v1",
            "disclosure_summary": "Đồng thuận điều trị phục hình mô phỏng",
            "signer_name": "Người giám hộ Demo",
            "signer_relationship": "guardian",
            "guardian_authority_verified": True,
        },
    )
    assert c_trt.status_code == 201, c_trt.text
    c_mkt = client.post(
        "/api/v1/consents",
        json={
            "patient_id": patient["id"],
            "purpose": "marketing",
            "template_version": "CONSENT-MKT-v1",
            "disclosure_summary": "Đồng thuận nhận tin khuyến mãi mô phỏng",
            "signer_name": "Bệnh nhân Demo A",
            "signer_relationship": "self",
        },
    )
    assert c_mkt.status_code == 201

    # Withdraw marketing consent -> treatment consent MUST remain 'granted' (SEC-07)
    w = client.post(
        f"/api/v1/consents/{c_mkt.json()['id']}/withdraw",
        json={"reason": "Bệnh nhân từ chối nhận tin quảng cáo"},
    )
    assert w.status_code == 200
    assert w.json()["status"] == "withdrawn"

    consents = client.get(f"/api/v1/patients/{patient['id']}/consents").json()
    by_purpose = {c["purpose"]: c["status"] for c in consents}
    assert by_purpose["marketing"] == "withdrawn"
    assert by_purpose["treatment"] == "granted"


def test_lab_partner_scoped_portal_minimized_data_expiry_remake_and_delay_alert(
    client, patient, doctor, chair, context
):
    # Book an appointment for 2026-12-10 09:00
    appt = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": patient["id"],
            "practitioner_id": doctor["id"],
            "chair_id": chair["id"],
            "start_at": "2026-12-10T09:00:00+07:00",
            "end_at": "2026-12-10T10:00:00+07:00",
            "reason_demo": "Lịch lắp phục hình sứ",
        },
    ).json()

    # Create lab case with due_on AFTER the appointment (2026-12-12) -> must trigger delay alert without auto-rescheduling!
    lab = client.post(
        "/api/v1/lab-cases",
        json={
            "patient_id": patient["id"],
            "title": "Mão sứ răng 16 demo",
            "specification_demo": "Zirconia nguyên khối màu A2, răng 16",
            "due_on": "2026-12-12T17:00:00+07:00",
            "file_references": ["scan-16-occlusal.stl", "bite-reg.stl"],
        },
    )
    assert lab.status_code == 201, lab.text
    lab_body = lab.json()
    lab_id = lab_body["id"]

    # Link lab case and appointment to a treatment plan task
    plan = client.post(
        "/api/v1/treatment-plans",
        json={"patient_id": patient["id"], "title": "Kế hoạch mão sứ 16"},
    ).json()
    task = client.post(
        f"/api/v1/treatment-plans/{plan['id']}/tasks",
        json={"title": "Gắn mão sứ 16", "phase": "Phục hình"},
    ).json()
    client.post(
        f"/api/v1/treatment-tasks/{task['id']}/links",
        json={"target_type": "appointment", "target_id": appt["id"]},
    )
    client.post(
        f"/api/v1/treatment-tasks/{task['id']}/links",
        json={"target_type": "lab_case", "target_id": lab_id, "requires_verified_lab": True},
    )

    alerts = client.get(f"/api/v1/lab-cases/{lab_id}/alerts").json()
    assert any(a["alert_code"] == "lab_due_after_appointment" for a in alerts["alerts"])
    # Appointment start_at was NEVER auto-rescheduled!
    appt_check = client.get("/api/v1/appointments").json()[0]
    assert appt_check["id"] == appt["id"]
    assert appt_check["status"] == "confirmed"

    # Mint scoped partner grant token (OPS-06 / LAB-008)
    grant = client.post(
        f"/api/v1/lab-cases/{lab_id}/partner-grants",
        json={"partner_name": "Labo Sứ Việt Demo", "ttl_seconds": 600},
    )
    assert grant.status_code == 201, grant.text
    g_tok = grant.json()["grant_token"]

    # Partner portal returns minimal case specs & files, NEVER patient display_name or phone!
    portal_view = client.get(f"/api/v1/lab-portal/cases/{g_tok}")
    assert portal_view.status_code == 200
    pv = portal_view.json()
    assert pv["lab_case_id"] == lab_id
    assert pv["specification_demo"] == "Zirconia nguyên khối màu A2, răng 16"
    assert "display_name" not in pv
    assert "phone_demo" not in pv
    assert "patient_id" not in pv

    # Wrong clinic header with partner token is rejected (403)
    clinic_b = next(c["id"] for c in context["clinics"] if c["id"] != context["clinic_id"])
    assert client.get(
        f"/api/v1/lab-portal/cases/{g_tok}",
        headers={"X-Demo-Clinic": clinic_b},
    ).status_code == 403

    # Partner can progress requested -> accepted -> in_progress -> ready, but CANNOT mark 'verified' (403)
    for st in ["accepted", "in_progress", "ready"]:
        r = client.post(
            f"/api/v1/lab-portal/cases/{g_tok}/milestones",
            json={"next_status": st, "partner_note": f"Milestone {st}"},
        )
        assert r.status_code == 200
    assert client.post(
        f"/api/v1/lab-portal/cases/{g_tok}/milestones",
        json={"next_status": "verified", "partner_note": "Partner self-verify"},
    ).status_code == 403

    # Expired partner link is rejected (403)
    expired_grant = client.post(
        f"/api/v1/lab-cases/{lab_id}/partner-grants",
        json={"partner_name": "Labo Expired", "ttl_seconds": -10},
    ).json()["grant_token"]
    assert client.get(f"/api/v1/lab-portal/cases/{expired_grant}").status_code == 403

    # Clinic records delivery receipt (ready -> received), distinct from clinical verification (LAB-006 / LAB-009)
    rec = client.post(
        f"/api/v1/lab-cases/{lab_id}/receive",
        json={"condition": "Nguyên niêm phong hộp demo"},
    )
    assert rec.status_code == 200
    assert rec.json()["status"] == "received"

    # Remake / revision creates linked child case preserving original case (LAB-007)
    remake = client.post(
        f"/api/v1/lab-cases/{lab_id}/remakes",
        json={
            "reason": "Chỉnh lại điểm tiếp xúc mặt gần mô phỏng",
            "specification_demo": "Zirconia màu A2, tăng tiếp xúc gần 0.1mm",
        },
    )
    assert remake.status_code == 201, remake.text
    rm_body = remake.json()
    assert rm_body["parent_lab_case_id"] == lab_id
    assert rm_body["revision_number"] == 2
