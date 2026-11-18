from pathlib import Path
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from denlyra.api import create_app
from denlyra.config import Settings

_SESSION_BASETEMP: Path | None = None


def pytest_configure(config):
    global _SESSION_BASETEMP
    if not config.option.basetemp:
        local = Path(__file__).resolve().parents[2] / "local_data"
        local.mkdir(exist_ok=True)
        _SESSION_BASETEMP = Path(tempfile.mkdtemp(prefix="pytest-run-", dir=local))
        config.option.basetemp = str(_SESSION_BASETEMP / "tmp")


def pytest_unconfigure(config):
    global _SESSION_BASETEMP
    if _SESSION_BASETEMP and _SESSION_BASETEMP.exists():
        shutil.rmtree(_SESSION_BASETEMP, ignore_errors=True)
        _SESSION_BASETEMP = None


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
