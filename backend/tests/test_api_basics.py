from denlyra.config import Settings
import pytest


def test_production_refusal_and_public_bind_blocked():
    with pytest.raises(RuntimeError, match="NOT A PRODUCTION EMR"):
        Settings(demo_mode=False).validate()
    with pytest.raises(RuntimeError, match="loopback"):
        Settings(demo_mode=True, host="0.0.0.0").validate()


def test_health_flags_and_ui(client):
    assert client.get("/health").json() == {"status": "ok", "demo_only": True, "certified_emr": False}
    caps = client.get("/api/v1/capabilities").json()
    assert caps["clinical_e_signature"] is False
    assert caps["emr_certified"] is False
    assert caps["ai_diagnosis"] is False
    assert caps["use_real_patients"] is False
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").status_code == 200


def test_patient_create_and_list(client, patient):
    patients = client.get("/api/v1/patients").json()
    assert patients[0]["id"] == patient["id"]
    assert patients[0]["source"] == "demo_native"
    assert client.get(f"/api/v1/patients/{patient['id']}").status_code == 200


def test_two_patients_same_phone_not_auto_merged(client):
    for name in ["Bệnh nhân Demo B", "Bệnh nhân Demo C"]:
        assert client.post("/api/v1/patients", json={"display_name": name, "phone_demo": "000000000"}).status_code == 201
    assert len(client.get("/api/v1/patients").json()) == 2


def test_cross_origin_and_untrusted_host_rejected(client):
    assert client.post("/api/v1/patients", json={"display_name": "Test Case"},
                       headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/patients", json={"display_name": "Test Case"},
                       headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.get("/health", headers={"Host": "attacker.test"}).status_code == 400


def test_cross_clinic_isolation_scoped_to_selected_demo_context(client, patient):
    ctx = client.get("/api/v1/demo/context").json()
    clinic_b = next(c for c in ctx["clinics"] if c["id"] != ctx["clinic_id"])["id"]
    headers = {"X-Demo-Clinic": clinic_b}
    assert client.get("/api/v1/patients", headers=headers).json() == []
    assert client.get(f"/api/v1/patients/{patient['id']}", headers=headers).status_code == 404
    # Explicitly NOT authentication: headers are attacker-controllable in demo.
    assert client.get(f"/api/v1/patients/{patient['id']}", headers={"X-Demo-Clinic": ctx["clinic_id"]}).status_code == 200


def test_bad_profile_rejected(client):
    assert client.post("/api/v1/patients", json={"display_name": "X"}).status_code == 422
    assert client.post("/api/v1/patients", json={"display_name": "Demo", "birth_year": 1800}).status_code == 422
