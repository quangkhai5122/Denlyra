"""T014 hash-chained tamper-evident audit journal (SEC-007) and signed clinic-scoped
cursor pagination (PAT-002 / R-012) tests.

Written BEFORE T014 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"
CLINIC_B = "22222222-2222-4222-8222-222222222222"


def _headers(client: TestClient, role: str, clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_hash_chained_audit_journal_immutability_and_out_of_band_tamper_detection(tmp_path: Path):
    db_file = tmp_path / "audit_chain.db"
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{db_file}",
        archive_dir=str(tmp_path / "archive"),
    )
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8766") as client:
        owner = _headers(client, "clinic_owner", CLINIC_A)
        dentist = _headers(client, "dentist", CLINIC_A)

        for idx in range(3):
            r = client.post(
                "/api/v1/patients",
                headers=dentist,
                json={"display_name": f"Bệnh nhân Audit Chain {idx}", "birth_year": 1990 + idx},
            )
            assert r.status_code == 201

        ver = client.get("/api/v1/audit-events/verify-chain", headers=owner)
        assert ver.status_code == 200, ver.text
        ver_body = ver.json()
        assert ver_body["chain_intact"] is True
        assert ver_body["verified_count"] >= 5
        assert len(ver_body["head_hash"]) == 64

        # Preventive layer: direct SQL UPDATE or DELETE on audit_event is blocked by DB trigger
        with app.state.factory() as db:
            with pytest.raises(IntegrityError):
                db.execute(text("UPDATE audit_event SET action = 'forged.action'"))
                db.commit()
            db.rollback()
            with pytest.raises(IntegrityError):
                db.execute(text("DELETE FROM audit_event"))
                db.commit()
            db.rollback()

        # Detective layer (SEC-007): simulate raw disk tamper bypassing trigger -> verify-chain fails 409!
        raw_conn = sqlite3.connect(str(db_file))
        try:
            raw_conn.execute("DROP TRIGGER IF EXISTS tr_audit_event_no_update")
            raw_conn.execute(
                "UPDATE audit_event SET action = 'tampered.on.disk' "
                "WHERE clinic_id = ? AND chain_seq = 2",
                (CLINIC_A,),
            )
            raw_conn.commit()
        finally:
            raw_conn.close()

        tampered_ver = client.get("/api/v1/audit-events/verify-chain", headers=owner)
        assert tampered_ver.status_code == 409
        assert "broken_at_seq=2" in tampered_ver.json()["detail"] or "tamper" in tampered_ver.json()["detail"].lower()


def test_clinic_scoped_signed_cursor_pagination_and_negative_cursor_attacks(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'pagination.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist_a = _headers(client, "dentist", CLINIC_A)
        dentist_b = _headers(client, "dentist", CLINIC_B)

        created_ids_a = []
        for idx in range(5):
            resp = client.post(
                "/api/v1/patients",
                headers=dentist_a,
                json={"display_name": f"Nguyễn Thị Phân Trang {idx}", "birth_year": 1980 + idx},
            )
            assert resp.status_code == 201
            created_ids_a.append(resp.json()["id"])

        client.post(
            "/api/v1/patients",
            headers=dentist_b,
            json={"display_name": "Nguyễn Thị Phòng Khám B", "birth_year": 1999},
        )

        # Iterate through Clinic A patients 2 per page -> exact 5 items, zero duplicates, zero Clinic B leak
        seen_ids: list[str] = []
        cursor: str | None = None
        pages = 0
        while True:
            url = "/api/v1/patients/page?limit=2"
            if cursor:
                url += f"&cursor={cursor}"
            page = client.get(url, headers=dentist_a)
            assert page.status_code == 200, page.text
            body = page.json()
            pages += 1
            for item in body["items"]:
                assert item["id"] not in seen_ids
                seen_ids.append(item["id"])
            if not body["has_more"]:
                assert body["next_cursor"] is None
                break
            cursor = body["next_cursor"]
            assert cursor is not None

        assert pages == 3
        assert set(seen_ids) == set(created_ids_a)

        # Search query filter with pagination (PAT-002)
        filtered = client.get(
            "/api/v1/patients/page?q=Phân Trang 3&limit=10", headers=dentist_a
        ).json()
        assert len(filtered["items"]) == 1
        assert filtered["items"][0]["display_name"] == "Nguyễn Thị Phân Trang 3"

        # Negative 1: Cross-tenant cursor replay (Clinic A cursor used by Clinic B) -> 403
        first_page_a = client.get("/api/v1/patients/page?limit=2", headers=dentist_a).json()
        cursor_a = first_page_a["next_cursor"]
        assert cursor_a is not None
        cross_replay = client.get(
            f"/api/v1/patients/page?limit=2&cursor={cursor_a}", headers=dentist_b
        )
        assert cross_replay.status_code == 403

        # Negative 2: Tampered cursor signature -> 422
        tampered_cursor = cursor_a[:-4] + "0000"
        assert (
            client.get(
                f"/api/v1/patients/page?limit=2&cursor={tampered_cursor}", headers=dentist_a
            ).status_code
            == 422
        )

        # Audit events cursor pagination also works cleanly
        audit_p1 = client.get("/api/v1/audit-events/page?limit=3", headers=dentist_a)
        assert audit_p1.status_code == 200
        assert len(audit_p1.json()["items"]) == 3
        assert audit_p1.json()["has_more"] is True


def test_concurrent_audit_read_requests_serialize_chain_seq_without_collision(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor

    db_file = tmp_path / "concurrent_audit.db"
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{db_file}",
        archive_dir=str(tmp_path / "archive"),
    )
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8766") as client:
        dentist_tok = client.post(
            "/api/v1/auth/token", json={"clinic_id": CLINIC_A, "role": "dentist"}
        ).json()
        dentist = {
            "Authorization": f"Bearer {dentist_tok['access_token']}",
            "X-Demo-Clinic": CLINIC_A,
        }
        owner = _headers(client, "clinic_owner", CLINIC_A)

        pat = client.post(
            "/api/v1/patients",
            headers=dentist,
            json={"display_name": "BN Đồng thời Audit", "birth_year": 1992},
        ).json()["id"]
        enc = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat, "practitioner_id": dentist_tok["staff_id"]},
        ).json()["id"]

        urls = [
            f"/api/v1/encounters/{enc}/notes",
            f"/api/v1/encounters/{enc}/snapshots",
        ] * 8

        def _fetch(path: str) -> int:
            return client.get(path, headers=dentist).status_code

        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(_fetch, urls))

        assert statuses == [200] * len(urls)
        ver = client.get("/api/v1/audit-events/verify-chain", headers=owner)
        assert ver.status_code == 200, ver.text
        assert ver.json()["chain_intact"] is True
