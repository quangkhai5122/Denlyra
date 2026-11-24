"""T010 encrypted archive, key rotation, retention/legal-hold block, and isolated DR restore drill tests.

Written BEFORE T010 domain/API implementation per AGENTS.md negative-test-first rule.
Covers positive lifecycle + 7 mandatory negative scenarios (NEG-13, DR-04, DR-05, DR-08, key rotation/revocation, cross-tenant).
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from sqlalchemy import select

from denlyra import models as m
from denlyra.config import Settings
from denlyra.api import create_app
from fastapi.testclient import TestClient


CLINIC_A = "11111111-1111-4111-8111-111111111111"
CLINIC_B = "22222222-2222-4222-8222-222222222222"


def _issue_headers(client: TestClient, role: str = "clinic_owner", clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Demo-Clinic": clinic_id}


def _seed_clinical_and_archive_state(client: TestClient) -> dict:
    dentist_headers = _issue_headers(client, "dentist", CLINIC_A)
    owner_headers = _issue_headers(client, "clinic_owner", CLINIC_A)
    ctx = client.get("/api/v1/demo/context", headers=dentist_headers).json()
    dentist_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")

    pat = client.post(
        "/api/v1/patients",
        headers=dentist_headers,
        json={"display_name": "Bệnh nhân Lưu trữ DR Demo", "birth_year": 1988},
    )
    assert pat.status_code == 201
    patient_id = pat.json()["id"]

    enc = client.post(
        "/api/v1/encounters",
        headers=dentist_headers,
        json={"patient_id": patient_id, "practitioner_id": dentist_id, "summary_demo": "Khám tổng quát DR"},
    )
    assert enc.status_code == 201
    encounter_id = enc.json()["id"]

    note = client.post(
        f"/api/v1/encounters/{encounter_id}/notes",
        headers=dentist_headers,
        json={"content": "Ghi chú lâm sàng giả lập phục vụ kiểm thử sao lưu và khôi phục thảm họa."},
    )
    assert note.status_code == 201
    note_id = note.json()["id"]

    snap = client.post(
        "/api/v1/clinical-documents/snapshots",
        headers=dentist_headers,
        json={"note_id": note_id, "expected_revision": 1},
    )
    assert snap.status_code == 201
    snap_data = snap.json()

    signed = client.post(
        f"/api/v1/clinical-documents/{snap_data['id']}/sign-synthetic",
        headers=dentist_headers,
        json={"expected_sha256": snap_data["canonical_sha256"], "mode": "synthetic_test_double"},
    )
    assert signed.status_code == 200

    raw_photo = b"SYNTHETIC-INTRAORAL-PHOTO-PAYLOAD-V1"
    obj1 = client.post(
        "/api/v1/archive/objects",
        headers=dentist_headers,
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "snapshot_id": snap_data["id"],
            "object_kind": "clinical_attachment",
            "media_type": "application/octet-stream",
            "original_filename": "intraoral-synthetic-01.bin",
            "content_b64": base64.b64encode(raw_photo).decode("ascii"),
            "retention_class": "clinical_emr_quarantined",
        },
    )
    assert obj1.status_code == 201, obj1.text

    return {
        "dentist_headers": dentist_headers,
        "owner_headers": owner_headers,
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "snapshot_id": snap_data["id"],
        "obj1": obj1.json(),
        "raw_photo": raw_photo,
    }


def test_archive_encryption_key_rotation_and_retention_legal_hold_block(tmp_path: Path):
    archive_dir = tmp_path / "archive"
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'dr_rot.db'}",
        archive_dir=str(archive_dir),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        seeded = _seed_clinical_and_archive_state(client)
        owner_headers = seeded["owner_headers"]
        dentist_headers = seeded["dentist_headers"]
        receptionist_headers = _issue_headers(client, "receptionist", CLINIC_A)

        # Receptionist is denied archive access (deny-by-default RBAC)
        assert client.get("/api/v1/archive/objects", headers=receptionist_headers).status_code == 403

        obj_v1 = seeded["obj1"]
        assert obj_v1["key_version"] == 1
        cipher_file = archive_dir / obj_v1["storage_relpath"]
        assert cipher_file.is_file()
        # Ciphertext on disk must NOT contain plaintext bytes
        assert seeded["raw_photo"] not in cipher_file.read_bytes()

        # Rotate clinic key to v2; v1 becomes retired_decrypt_only
        rot = client.post("/api/v1/archive/keys/rotate", headers=owner_headers)
        assert rot.status_code == 201, rot.text
        assert rot.json()["key_version"] == 2

        # Upload DICOM synthetic stub under v2 key
        raw_dicom = b"DICM-SYNTHETIC-CBCT-HEADER-ONLY-NO-PHI"
        obj_v2 = client.post(
            "/api/v1/archive/objects",
            headers=dentist_headers,
            json={
                "patient_id": seeded["patient_id"],
                "encounter_id": seeded["encounter_id"],
                "object_kind": "dicom_study_stub",
                "media_type": "application/dicom",
                "original_filename": "cbct-study-synthetic.dcm",
                "content_b64": base64.b64encode(raw_dicom).decode("ascii"),
                "retention_class": "radiology_dicom_quarantined",
            },
        )
        assert obj_v2.status_code == 201
        assert obj_v2.json()["key_version"] == 2

        # Both v1 and v2 objects verify cleanly after rotation
        ver1 = client.get(f"/api/v1/archive/objects/{obj_v1['id']}/verify", headers=owner_headers)
        ver2 = client.get(f"/api/v1/archive/objects/{obj_v2.json()['id']}/verify", headers=owner_headers)
        assert ver1.status_code == 200 and ver1.json()["integrity_ok"] is True
        assert ver2.status_code == 200 and ver2.json()["integrity_ok"] is True

        # Retention / legal-hold deletion block (INV-018 / DR-08)
        hold = client.post(
            f"/api/v1/archive/objects/{obj_v1['id']}/legal-hold",
            headers=owner_headers,
            json={"reason": "Giữ nguyên bằng chứng phục vụ kiểm toán nội bộ giả lập"},
        )
        assert hold.status_code == 200
        assert hold.json()["legal_hold"] is True

        del_resp = client.delete(f"/api/v1/archive/objects/{obj_v1['id']}", headers=owner_headers)
        assert del_resp.status_code == 409
        assert cipher_file.is_file()


def test_full_isolated_dr_restore_drill_succeeds_and_measures_rpo_rto(tmp_path: Path):
    archive_dir = tmp_path / "archive"
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'dr_ok.db'}",
        archive_dir=str(archive_dir),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        seeded = _seed_clinical_and_archive_state(client)
        owner_headers = seeded["owner_headers"]

        bkp = client.post(
            "/api/v1/archive/backups",
            headers=owner_headers,
            json={"label": "nightly-synthetic-pitr-01"},
        )
        assert bkp.status_code == 201, bkp.text
        backup_id = bkp.json()["id"]

        drill = client.post(
            f"/api/v1/archive/backups/{backup_id}/restore-drill",
            headers=owner_headers,
            json={},
        )
        assert drill.status_code == 200, drill.text
        body = drill.json()
        assert body["integrity_ok"] is True
        assert body["status"] == "passed"
        assert body["restored_patients"] >= 1
        assert body["restored_snapshots"] == 1
        assert body["restored_objects"] == 1
        assert isinstance(body["rto_ms"], int) and body["rto_ms"] >= 0
        assert body["rpo_lag_ms"] == 0


def test_dr_restore_negative_missing_and_corrupted_archive_object(tmp_path: Path):
    archive_dir = tmp_path / "archive"
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'dr_corrupt.db'}",
        archive_dir=str(archive_dir),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        seeded = _seed_clinical_and_archive_state(client)
        owner_headers = seeded["owner_headers"]
        bkp = client.post(
            "/api/v1/archive/backups",
            headers=owner_headers,
            json={"label": "corrupt-and-missing-test"},
        ).json()
        backup_id = bkp["id"]
        bundle_obj = (
            archive_dir / bkp["bundle_relpath"] / "objects" / f"{seeded['obj1']['id']}.bin"
        )
        assert bundle_obj.is_file()

        # Case A: Altered / bit-flipped encrypted object in backup -> fails closed with 409
        original_bytes = bundle_obj.read_bytes()
        tampered = bytearray(original_bytes)
        tampered[-1] ^= 0xFF
        bundle_obj.write_bytes(bytes(tampered))

        corrupt_drill = client.post(
            f"/api/v1/archive/backups/{backup_id}/restore-drill",
            headers=owner_headers,
            json={},
        )
        assert corrupt_drill.status_code == 409
        assert "corrupt" in corrupt_drill.json()["detail"].lower() or "mismatch" in corrupt_drill.json()["detail"].lower()

        # Case B: Missing archive object file in backup (NEG-13) -> fails closed with 409
        bundle_obj.unlink()
        missing_drill = client.post(
            f"/api/v1/archive/backups/{backup_id}/restore-drill",
            headers=owner_headers,
            json={},
        )
        assert missing_drill.status_code == 409
        assert "missing" in missing_drill.json()["detail"].lower()


def test_dr_restore_negative_wrong_master_key_and_revoked_tenant_key(tmp_path: Path):
    archive_dir = tmp_path / "archive"
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'dr_keys.db'}",
        archive_dir=str(archive_dir),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        seeded = _seed_clinical_and_archive_state(client)
        owner_headers = seeded["owner_headers"]
        bkp = client.post(
            "/api/v1/archive/backups",
            headers=owner_headers,
            json={"label": "wrong-key-test"},
        ).json()
        backup_id = bkp["id"]

        # Case A: Wrong master KEK secret during DR recovery -> fails closed with 409
        wrong_key_drill = client.post(
            f"/api/v1/archive/backups/{backup_id}/restore-drill",
            headers=owner_headers,
            json={"override_master_secret": "wrong-kms-master-secret-during-outage"},
        )
        assert wrong_key_drill.status_code == 409
        assert "key" in wrong_key_drill.json()["detail"].lower()

        # Case B: Revoke the tenant key, take a new backup, and verify drill rejects revoked key
        key_id = seeded["obj1"]["key_id"]
        rev = client.post(f"/api/v1/archive/keys/{key_id}/revoke", headers=owner_headers)
        assert rev.status_code == 200
        bkp2 = client.post(
            "/api/v1/archive/backups",
            headers=owner_headers,
            json={"label": "revoked-key-backup"},
        ).json()
        revoked_drill = client.post(
            f"/api/v1/archive/backups/{bkp2['id']}/restore-drill",
            headers=owner_headers,
            json={},
        )
        assert revoked_drill.status_code == 409
        assert "revoked" in revoked_drill.json()["detail"].lower() or "key" in revoked_drill.json()["detail"].lower()


def test_dr_restore_negative_stale_object_checkpoint_and_invalid_signature_and_cross_tenant(tmp_path: Path):
    archive_dir = tmp_path / "archive"
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'dr_stale_sig.db'}",
        archive_dir=str(archive_dir),
    )
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8766") as client:
        seeded = _seed_clinical_and_archive_state(client)
        owner_a = seeded["owner_headers"]
        owner_b = _issue_headers(client, "clinic_owner", CLINIC_B)

        # Case A: Stale object-store checkpoint older than archived object creation (DR-05) -> 409
        stale_bkp = client.post(
            "/api/v1/archive/backups",
            headers=owner_a,
            json={"label": "stale-object-store-lag", "object_store_lag_seconds": 3600},
        ).json()
        stale_drill = client.post(
            f"/api/v1/archive/backups/{stale_bkp['id']}/restore-drill",
            headers=owner_a,
            json={},
        )
        assert stale_drill.status_code == 409
        assert "stale" in stale_drill.json()["detail"].lower()

        # Case B: Cross-tenant restore attempt (Clinic A -> target Clinic B, or Clinic B reading Clinic A backup)
        clean_bkp = client.post(
            "/api/v1/archive/backups",
            headers=owner_a,
            json={"label": "clean-cross-tenant-check"},
        ).json()
        cross_target = client.post(
            f"/api/v1/archive/backups/{clean_bkp['id']}/restore-drill",
            headers=owner_a,
            json={"target_clinic_id": CLINIC_B},
        )
        assert cross_target.status_code == 403
        cross_actor = client.post(
            f"/api/v1/archive/backups/{clean_bkp['id']}/restore-drill",
            headers=owner_b,
            json={},
        )
        assert cross_actor.status_code == 404

        # Case C: Tampered / unavailable signature receipt on sealed ClinicalDocumentSnapshot (DR-04) -> 409
        with app.state.factory() as db:
            snap = db.scalar(
                select(m.ClinicalDocumentSnapshot).where(
                    m.ClinicalDocumentSnapshot.id == seeded["snapshot_id"]
                )
            )
            receipt = json.loads(snap.provider_receipt_json)
            receipt["signature_hex"] = "f" * 64
            snap.provider_receipt_json = json.dumps(receipt)
            db.commit()

        bad_sig_bkp = client.post(
            "/api/v1/archive/backups",
            headers=owner_a,
            json={"label": "bad-signature-evidence"},
        ).json()
        bad_sig_drill = client.post(
            f"/api/v1/archive/backups/{bad_sig_bkp['id']}/restore-drill",
            headers=owner_a,
            json={},
        )
        assert bad_sig_drill.status_code == 409
        assert "signature" in bad_sig_drill.json()["detail"].lower()
