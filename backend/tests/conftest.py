import pytest
from fastapi.testclient import TestClient
from denlyra.api import create_app
from denlyra.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(demo_mode=True, db_url=f"sqlite+pysqlite:///{tmp_path / 'demo.db'}")
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8766") as c:
        yield c


@pytest.fixture
def context(client):
    return client.get("/api/v1/demo/context").json()


@pytest.fixture
def patient(client):
    resp = client.post("/api/v1/patients", json={"display_name": "Bệnh nhân Demo A", "birth_year": 2000})
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def doctor(context):
    return next(x for x in context["staff"] if x["role"] == "dentist")


@pytest.fixture
def chair(context):
    return context["chairs"][0]


@pytest.fixture
def appointment_payload(patient, doctor, chair):
    return {"patient_id": patient["id"], "practitioner_id": doctor["id"],
            "chair_id": chair["id"], "start_at": "2026-12-01T09:00:00+07:00",
            "end_at": "2026-12-01T10:00:00+07:00", "reason_demo": "Khám demo"}
