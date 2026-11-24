"""Disposable CLI runner for T010 encrypted backup & isolated DR restore drill.

Creates a disposable synthetic clinic dataset (patient, encounter, sealed clinical snapshot,
rotated v1+v2 encrypted archive objects, DICOM stub, revenue ledger entry), executes an
isolated cross-store restore drill, verifies 0 missing/tampered artifacts and 100% signature
integrity, prints measured RTO/RPO, and removes temporary files.
"""
from __future__ import annotations

import base64
from pathlib import Path
import shutil
import tempfile

from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

ROOT = Path(__file__).resolve().parents[1]
CLINIC_A = "11111111-1111-4111-8111-111111111111"


def main() -> None:
    local = ROOT / "local_data"
    local.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="dr-cli-", dir=local))
    try:
        settings = Settings(
            demo_mode=True,
            require_auth=True,
            db_url=f"sqlite+pysqlite:///{scratch / 'source.db'}",
            archive_dir=str(scratch / "archive"),
        )
        app = create_app(settings)
        with TestClient(app, base_url="http://127.0.0.1:8766") as client:
            dentist_tok = client.post(
                "/api/v1/auth/token", json={"clinic_id": CLINIC_A, "role": "dentist"}
            ).json()["access_token"]
            owner_tok = client.post(
                "/api/v1/auth/token", json={"clinic_id": CLINIC_A, "role": "clinic_owner"}
            ).json()["access_token"]
            h_dentist = {"Authorization": f"Bearer {dentist_tok}", "X-Demo-Clinic": CLINIC_A}
            h_owner = {"Authorization": f"Bearer {owner_tok}", "X-Demo-Clinic": CLINIC_A}

            ctx = client.get("/api/v1/demo/context", headers=h_dentist).json()
            dentist_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")

            pat = client.post(
                "/api/v1/patients",
                headers=h_dentist,
                json={"display_name": "Bệnh nhân DR Drill CLI", "birth_year": 1995},
            ).json()
            enc = client.post(
                "/api/v1/encounters",
                headers=h_dentist,
                json={"patient_id": pat["id"], "practitioner_id": dentist_id, "summary_demo": "DR CLI"},
            ).json()
            note = client.post(
                f"/api/v1/encounters/{enc['id']}/notes",
                headers=h_dentist,
                json={"content": "Bản ghi nháp giả lập cho diễn tập DR tự động."},
            ).json()
            snap = client.post(
                "/api/v1/clinical-documents/snapshots",
                headers=h_dentist,
                json={"note_id": note["id"], "expected_revision": 1},
            ).json()
            signed = client.post(
                f"/api/v1/clinical-documents/{snap['id']}/sign-synthetic",
                headers=h_dentist,
                json={"expected_sha256": snap["canonical_sha256"]},
            )
            assert signed.status_code == 200

            # Object 1 under key v1
            r1 = client.post(
                "/api/v1/archive/objects",
                headers=h_dentist,
                json={
                    "patient_id": pat["id"],
                    "encounter_id": enc["id"],
                    "snapshot_id": snap["id"],
                    "object_kind": "clinical_attachment",
                    "original_filename": "synthetic-xray-v1.bin",
                    "content_b64": base64.b64encode(b"SYNTHETIC-XRAY-BYTES-V1").decode("ascii"),
                },
            )
            assert r1.status_code == 201

            # Rotate key -> v2 and upload DICOM stub
            rot = client.post("/api/v1/archive/keys/rotate", headers=h_owner)
            assert rot.status_code == 201 and rot.json()["key_version"] == 2
            r2 = client.post(
                "/api/v1/archive/objects",
                headers=h_dentist,
                json={
                    "patient_id": pat["id"],
                    "encounter_id": enc["id"],
                    "object_kind": "dicom_study_stub",
                    "media_type": "application/dicom",
                    "original_filename": "synthetic-cbct-v2.dcm",
                    "content_b64": base64.b64encode(b"DICM-SYNTHETIC-V2-PAYLOAD").decode("ascii"),
                    "retention_class": "radiology_dicom_quarantined",
                },
            )
            assert r2.status_code == 201

            bkp = client.post(
                "/api/v1/archive/backups",
                headers=h_owner,
                json={"label": "cli-dr-drill-verification"},
            )
            assert bkp.status_code == 201
            drill = client.post(
                f"/api/v1/archive/backups/{bkp.json()['id']}/restore-drill",
                headers=h_owner,
                json={},
            )
            assert drill.status_code == 200, drill.text
            res = drill.json()
            assert res["integrity_ok"] is True
            assert res["restored_objects"] == 2
            assert res["restored_snapshots"] == 1
            print(
                f"DR Restore Drill PASS: status={res['status']} "
                f"objects={res['restored_objects']} snapshots={res['restored_snapshots']} "
                f"rto_ms={res['rto_ms']} rpo_lag_ms={res['rpo_lag_ms']}"
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
