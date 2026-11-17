
def test_lab_transition_guard(client, patient):
    created = client.post("/api/v1/lab-cases", json={"patient_id": patient["id"],
                                                    "title": "Labo demo"}).json()
    url = f"/api/v1/lab-cases/{created['id']}/state"
    assert client.post(url, json={"next_status": "verified"}).status_code == 409
    for state in ["accepted", "in_progress", "ready", "received", "verified"]:
        response = client.post(url, json={"next_status": state})
        assert response.status_code == 200, response.text
    assert client.post(url, json={"next_status": "in_progress"}).status_code == 409


def test_payment_not_clinical_completion_and_allocation_bounds(client, patient, doctor):
    encounter = client.post("/api/v1/encounters", json={"patient_id": patient["id"],
                                                         "practitioner_id": doctor["id"]}).json()
    charge = client.post("/api/v1/finance/charges", json={"patient_id": patient["id"],
                             "label": "Thu demo", "amount_vnd": 1_000_000}).json()
    payment = client.post("/api/v1/finance/payments", json={"patient_id": patient["id"],
                             "amount_vnd": 300_000}).json()
    url = "/api/v1/finance/allocations"
    assert client.post(url, json={"charge_id": charge["id"], "payment_id": payment["id"],
                                  "amount_vnd": 200_000}).status_code == 201
    assert client.post(url, json={"charge_id": charge["id"], "payment_id": payment["id"],
                                  "amount_vnd": 200_000}).status_code == 409
    e = client.get("/api/v1/encounters").json()
    assert e[0]["id"] == encounter["id"]
    assert e[0]["status"] == "in_progress"


def test_cross_patient_allocation_is_blocked(client, patient):
    another = client.post("/api/v1/patients", json={"display_name": "Bệnh nhân Demo B"}).json()
    charge = client.post("/api/v1/finance/charges", json={"patient_id": patient["id"],
                             "label": "Thu demo", "amount_vnd": 400_000}).json()
    payment = client.post("/api/v1/finance/payments", json={"patient_id": another["id"],
                             "amount_vnd": 400_000}).json()
    assert client.post("/api/v1/finance/allocations", json={"charge_id": charge["id"],
                         "payment_id": payment["id"], "amount_vnd": 100_000}).status_code == 422


def test_negative_amount_and_float_rejected(client, patient):
    for n in [-2, 0, 5.5]:
        assert client.post("/api/v1/finance/charges", json={"patient_id": patient["id"],
                              "label": "Khoản demo", "amount_vnd": n}).status_code == 422


def test_demo_audit_and_dashboard(client, patient):
    a = client.get("/api/v1/audit-events").json()
    assert a and a[0]["action"] == "patient.created_demo"
    dash = client.get("/api/v1/dashboard").json()
    assert dash["patient_count"] == 1
