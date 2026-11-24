"""T010 Encrypted Record Archive, Key Rotation, Retention Hold, and Isolated DR Restore Drill.

Implements per-clinic envelope encryption (Encrypt-then-MAC using Python 3.12 stdlib HMAC-SHA256),
retention/legal-hold deletion blocking (INV-018 / DR-08), signed cross-store backup manifests,
and isolated SQLite + object + signature restore verification (INV-024 / NEG-13 / DR-04 / DR-05).

IMPORTANT: Synthetic demonstrator only. Production deployment before real PHI requires external
Cloud KMS/HSM key custody and legal sign-off in docs/clinical/NEEDS_CLINICAL_REVIEW.md.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import shutil
import tempfile
import time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m, services as svc, signing
from .db import build_engine, init_demo_schema, session_factory
from .schemas import ArchiveObjectCreate, BackupCreateRequest, RestoreDrillRequest

ENVELOPE_MAGIC = b"DLY1"
PROVISIONAL_RETENTION_DAYS = 365 * 20


def _derive_pair(secret_bytes: bytes, context_label: str) -> tuple[bytes, bytes]:
    ctx = context_label.encode("utf-8")
    key_enc = hmac.new(secret_bytes, b"enc:" + ctx, hashlib.sha256).digest()
    key_mac = hmac.new(secret_bytes, b"mac:" + ctx, hashlib.sha256).digest()
    return key_enc, key_mac


def derive_kek(master_secret: str, clinic_id: str, key_version: int) -> tuple[bytes, bytes]:
    return _derive_pair(master_secret.encode("utf-8"), f"kek:{clinic_id}:v{key_version}")


def derive_dek_subkeys(raw_dek: bytes, clinic_id: str, key_version: int) -> tuple[bytes, bytes]:
    return _derive_pair(raw_dek, f"dek-sub:{clinic_id}:v{key_version}")


def _xor_keystream(key_enc: bytes, nonce: bytes, data: bytes) -> bytes:
    out = bytearray(len(data))
    blocks = (len(data) + 31) // 32
    for counter in range(blocks):
        start = counter * 32
        chunk = data[start : start + 32]
        stream = hmac.new(
            key_enc, nonce + counter.to_bytes(8, "big"), hashlib.sha256
        ).digest()[: len(chunk)]
        xored = (
            int.from_bytes(chunk, "big") ^ int.from_bytes(stream, "big")
        ).to_bytes(len(chunk), "big")
        out[start : start + len(chunk)] = xored
    return bytes(out)


def encrypt_envelope(key_enc: bytes, key_mac: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = secrets.token_bytes(16)
    ciphertext = _xor_keystream(key_enc, nonce, plaintext)
    mac_input = len(aad).to_bytes(4, "big") + aad + nonce + ciphertext
    tag = hmac.new(key_mac, mac_input, hashlib.sha256).digest()
    return ENVELOPE_MAGIC + nonce + tag + ciphertext


def decrypt_envelope(key_enc: bytes, key_mac: bytes, blob: bytes, aad: bytes) -> bytes:
    if len(blob) < 52 or blob[:4] != ENVELOPE_MAGIC:
        raise ValueError("Malformed encrypted envelope header")
    nonce = blob[4:20]
    provided_tag = blob[20:52]
    ciphertext = blob[52:]
    mac_input = len(aad).to_bytes(4, "big") + aad + nonce + ciphertext
    expected_tag = hmac.new(key_mac, mac_input, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_tag, expected_tag):
        raise ValueError("Envelope authentication tag mismatch (wrong key or tampered ciphertext)")
    return _xor_keystream(key_enc, nonce, ciphertext)


def _create_wrapped_key_row(
    db: Session,
    clinic_id: str,
    key_version: int,
    master_secret: str,
    actor: str,
) -> m.TenantEncryptionKey:
    raw_dek = secrets.token_bytes(32)
    kek_enc, kek_mac = derive_kek(master_secret, clinic_id, key_version)
    aad = f"wrap-dek:{clinic_id}:v{key_version}".encode("utf-8")
    wrapped = encrypt_envelope(kek_enc, kek_mac, raw_dek, aad)
    fingerprint = hashlib.sha256(b"fp:" + raw_dek).hexdigest()
    row = m.TenantEncryptionKey(
        clinic_id=clinic_id,
        key_version=key_version,
        wrapped_dek_b64=base64.b64encode(wrapped).decode("ascii"),
        key_fingerprint=fingerprint,
        status="active",
        rotated_by=actor,
    )
    db.add(row)
    db.flush()
    return row


def ensure_active_tenant_key(
    db: Session,
    clinic_id: str,
    master_secret: str,
    actor: str,
) -> m.TenantEncryptionKey:
    active = db.scalar(
        select(m.TenantEncryptionKey)
        .where(
            m.TenantEncryptionKey.clinic_id == clinic_id,
            m.TenantEncryptionKey.status == "active",
        )
        .order_by(m.TenantEncryptionKey.key_version.desc())
    )
    if active is not None:
        return active
    latest = db.scalar(
        select(m.TenantEncryptionKey)
        .where(m.TenantEncryptionKey.clinic_id == clinic_id)
        .order_by(m.TenantEncryptionKey.key_version.desc())
    )
    next_ver = 1 if latest is None else latest.key_version + 1
    row = _create_wrapped_key_row(db, clinic_id, next_ver, master_secret, actor)
    svc.audit(
        db,
        clinic_id,
        actor,
        "archive.key_initialized",
        "tenant_encryption_key",
        row.id,
        {"key_version": row.key_version, "fingerprint": row.key_fingerprint[:16]},
    )
    return row


def rotate_tenant_key(
    db: Session,
    clinic_id: str,
    master_secret: str,
    actor: str,
) -> m.TenantEncryptionKey:
    active_keys = db.scalars(
        select(m.TenantEncryptionKey).where(
            m.TenantEncryptionKey.clinic_id == clinic_id,
            m.TenantEncryptionKey.status == "active",
        )
    ).all()
    for k in active_keys:
        k.status = "retired_decrypt_only"
    latest = db.scalar(
        select(m.TenantEncryptionKey)
        .where(m.TenantEncryptionKey.clinic_id == clinic_id)
        .order_by(m.TenantEncryptionKey.key_version.desc())
    )
    next_ver = 1 if latest is None else latest.key_version + 1
    new_key = _create_wrapped_key_row(db, clinic_id, next_ver, master_secret, actor)
    svc.audit(
        db,
        clinic_id,
        actor,
        "archive.key_rotated",
        "tenant_encryption_key",
        new_key.id,
        {"key_version": new_key.key_version, "fingerprint": new_key.key_fingerprint[:16]},
    )
    db.commit()
    return new_key


def revoke_tenant_key(
    db: Session,
    clinic_id: str,
    key_id: str,
    actor: str,
) -> m.TenantEncryptionKey:
    key_row = svc.ensure(db, m.TenantEncryptionKey, key_id, clinic_id)
    key_row.status = "revoked"
    svc.audit(
        db,
        clinic_id,
        actor,
        "archive.key_revoked",
        "tenant_encryption_key",
        key_row.id,
        {"key_version": key_row.key_version},
    )
    db.commit()
    return key_row


def unwrap_dek_subkeys(
    key_row: m.TenantEncryptionKey,
    master_secret: str,
) -> tuple[bytes, bytes]:
    if key_row.status == "revoked":
        raise ValueError(f"Tenant encryption key v{key_row.key_version} is revoked")
    kek_enc, kek_mac = derive_kek(master_secret, key_row.clinic_id, key_row.key_version)
    aad = f"wrap-dek:{key_row.clinic_id}:v{key_row.key_version}".encode("utf-8")
    wrapped = base64.b64decode(key_row.wrapped_dek_b64.encode("ascii"))
    raw_dek = decrypt_envelope(kek_enc, kek_mac, wrapped, aad)
    if hashlib.sha256(b"fp:" + raw_dek).hexdigest() != key_row.key_fingerprint:
        raise ValueError("Unwrapped DEK fingerprint mismatch")
    return derive_dek_subkeys(raw_dek, key_row.clinic_id, key_row.key_version)


def store_archive_object(
    db: Session,
    clinic_id: str,
    archive_dir: str,
    master_secret: str,
    data: ArchiveObjectCreate,
    actor: str,
) -> m.ArchiveObject:
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    if data.encounter_id:
        enc = svc.ensure(db, m.Encounter, data.encounter_id, clinic_id)
        if enc.patient_id != data.patient_id:
            raise HTTPException(422, "Encounter does not belong to specified patient")
    if data.snapshot_id:
        svc.ensure(db, m.ClinicalDocumentSnapshot, data.snapshot_id, clinic_id)
    try:
        plaintext = base64.b64decode(data.content_b64.encode("ascii"), validate=True)
    except Exception as exc:
        raise HTTPException(422, "Invalid base64 payload for archive object") from exc
    if not plaintext:
        raise HTTPException(422, "Archive object payload cannot be empty")

    key_row = ensure_active_tenant_key(db, clinic_id, master_secret, actor)
    dek_enc, dek_mac = unwrap_dek_subkeys(key_row, master_secret)

    obj_id = m.uid()
    aad = f"obj:{clinic_id}:{data.patient_id}:{obj_id}:v{key_row.key_version}".encode("utf-8")
    ciphertext_blob = encrypt_envelope(dek_enc, dek_mac, plaintext, aad)
    plaintext_sha = hashlib.sha256(plaintext).hexdigest()
    ciphertext_sha = hashlib.sha256(ciphertext_blob).hexdigest()

    relpath = f"objects/{clinic_id}/{obj_id}.bin"
    full_path = Path(archive_dir) / relpath
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(ciphertext_blob)

    retention_until = m.utcnow() + timedelta(days=PROVISIONAL_RETENTION_DAYS)
    obj = m.ArchiveObject(
        id=obj_id,
        clinic_id=clinic_id,
        patient_id=data.patient_id,
        encounter_id=data.encounter_id,
        snapshot_id=data.snapshot_id,
        object_kind=data.object_kind,
        media_type=data.media_type.strip(),
        original_filename=data.original_filename.strip(),
        byte_size=len(plaintext),
        plaintext_sha256=plaintext_sha,
        ciphertext_sha256=ciphertext_sha,
        key_id=key_row.id,
        key_version=key_row.key_version,
        storage_relpath=relpath,
        retention_class=data.retention_class,
        retention_until=retention_until,
        legal_hold=False,
        actor_demo=actor,
    )
    db.add(obj)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "archive.object_stored_encrypted",
        "archive_object",
        obj.id,
        {
            "object_kind": obj.object_kind,
            "key_version": obj.key_version,
            "plaintext_sha256": obj.plaintext_sha256,
        },
    )
    db.commit()
    return obj


def verify_archive_object(
    db: Session,
    clinic_id: str,
    object_id: str,
    archive_dir: str,
    master_secret: str,
) -> dict:
    obj = svc.ensure(db, m.ArchiveObject, object_id, clinic_id)
    full_path = Path(archive_dir) / obj.storage_relpath
    if not full_path.is_file():
        raise HTTPException(409, f"Missing encrypted archive object file for {obj.id} (NEG-13)")
    blob = full_path.read_bytes()
    if not hmac.compare_digest(hashlib.sha256(blob).hexdigest(), obj.ciphertext_sha256):
        raise HTTPException(409, f"Corrupted archive object {obj.id}: ciphertext SHA-256 mismatch")
    key_row = svc.ensure(db, m.TenantEncryptionKey, obj.key_id, clinic_id)
    try:
        dek_enc, dek_mac = unwrap_dek_subkeys(key_row, master_secret)
        aad = f"obj:{clinic_id}:{obj.patient_id}:{obj.id}:v{obj.key_version}".encode("utf-8")
        plaintext = decrypt_envelope(dek_enc, dek_mac, blob, aad)
    except ValueError as exc:
        raise HTTPException(409, f"Archive verification failed for {obj.id}: {exc}") from exc
    if not hmac.compare_digest(hashlib.sha256(plaintext).hexdigest(), obj.plaintext_sha256):
        raise HTTPException(409, f"Plaintext digest mismatch for {obj.id}")
    return {
        "object_id": obj.id,
        "clinic_id": clinic_id,
        "key_version": obj.key_version,
        "byte_size": len(plaintext),
        "plaintext_sha256": obj.plaintext_sha256,
        "ciphertext_sha256": obj.ciphertext_sha256,
        "integrity_ok": True,
        "synthetic_only": True,
    }


def place_legal_hold(
    db: Session,
    clinic_id: str,
    object_id: str,
    reason: str,
    actor: str,
) -> m.ArchiveObject:
    obj = svc.ensure(db, m.ArchiveObject, object_id, clinic_id)
    obj.legal_hold = True
    obj.legal_hold_reason = reason.strip()
    svc.audit(
        db,
        clinic_id,
        actor,
        "archive.legal_hold_placed",
        "archive_object",
        obj.id,
        {"reason": obj.legal_hold_reason},
    )
    db.commit()
    return obj


def delete_archive_object_blocked(
    db: Session,
    clinic_id: str,
    object_id: str,
    actor: str,
) -> None:
    obj = svc.ensure(db, m.ArchiveObject, object_id, clinic_id)
    now = m.utcnow()
    if obj.legal_hold or now < obj.retention_until:
        svc.audit(
            db,
            clinic_id,
            actor,
            "archive.deletion_blocked_retention",
            "archive_object",
            obj.id,
            {
                "legal_hold": obj.legal_hold,
                "retention_until": obj.retention_until.isoformat() + "Z",
            },
        )
        db.commit()
        raise HTTPException(
            409,
            "Physical deletion blocked by active clinical retention or legal hold policy (INV-018 / DR-08)",
        )
    raise HTTPException(
        409,
        "Archive purge requires legal counsel sign-off on Circular 33/2025/TT-BYT retention schedule",
    )


def _dump_row(item) -> dict:
    row = {}
    for col in item.__table__.columns:
        val = getattr(item, col.name)
        row[col.name] = val.isoformat() if isinstance(val, datetime) else val
    return row


def _parse_row(model_cls, raw: dict):
    parsed = {}
    for col in model_cls.__table__.columns:
        val = raw.get(col.name)
        if val is not None and isinstance(col.type, m.DateTime):
            val = datetime.fromisoformat(val)
        parsed[col.name] = val
    return model_cls(**parsed)


def create_backup_snapshot(
    db: Session,
    clinic_id: str,
    archive_dir: str,
    auth_secret: str,
    data: BackupCreateRequest,
    actor: str,
) -> m.BackupManifest:
    clinic = svc.ensure(db, m.Clinic, clinic_id)
    db_checkpoint_at = m.utcnow()
    object_checkpoint_at = db_checkpoint_at - timedelta(seconds=data.object_store_lag_seconds)

    backup_id = m.uid()
    bundle_relpath = f"backups/{clinic_id}/{backup_id}"
    bundle_dir = Path(archive_dir) / bundle_relpath
    objects_out_dir = bundle_dir / "objects"
    objects_out_dir.mkdir(parents=True, exist_ok=True)

    staff_rows = db.scalars(select(m.Staff).where(m.Staff.clinic_id == clinic_id)).all()
    patients = db.scalars(select(m.Patient).where(m.Patient.clinic_id == clinic_id)).all()
    encounters = db.scalars(select(m.Encounter).where(m.Encounter.clinic_id == clinic_id)).all()
    notes = db.scalars(select(m.ClinicalNote).where(m.ClinicalNote.clinic_id == clinic_id)).all()
    note_ids = [n.id for n in notes]
    revisions = (
        db.scalars(select(m.NoteRevision).where(m.NoteRevision.note_id.in_(note_ids))).all()
        if note_ids
        else []
    )
    snapshots = db.scalars(
        select(m.ClinicalDocumentSnapshot).where(
            m.ClinicalDocumentSnapshot.clinic_id == clinic_id
        )
    ).all()
    consents = db.scalars(
        select(m.ConsentRecord).where(m.ConsentRecord.clinic_id == clinic_id)
    ).all()
    ledger_rows = db.scalars(
        select(m.LedgerEntry).where(m.LedgerEntry.clinic_id == clinic_id)
    ).all()
    keys = db.scalars(
        select(m.TenantEncryptionKey).where(m.TenantEncryptionKey.clinic_id == clinic_id)
    ).all()
    archive_objs = db.scalars(
        select(m.ArchiveObject).where(m.ArchiveObject.clinic_id == clinic_id)
    ).all()

    for obj in archive_objs:
        src = Path(archive_dir) / obj.storage_relpath
        if src.is_file():
            shutil.copy2(src, objects_out_dir / f"{obj.id}.bin")

    relational_dump = {
        "clinic": [_dump_row(clinic)],
        "staff": [_dump_row(x) for x in staff_rows],
        "patient": [_dump_row(x) for x in patients],
        "encounter": [_dump_row(x) for x in encounters],
        "clinical_note": [_dump_row(x) for x in notes],
        "note_revision": [_dump_row(x) for x in revisions],
        "clinical_document_snapshot": [_dump_row(x) for x in snapshots],
        "consent_record": [_dump_row(x) for x in consents],
        "ledger_entry": [_dump_row(x) for x in ledger_rows],
        "tenant_encryption_key": [_dump_row(x) for x in keys],
        "archive_object": [_dump_row(x) for x in archive_objs],
    }
    dump_bytes = json.dumps(
        relational_dump, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    (bundle_dir / "relational_dump.json").write_bytes(dump_bytes)
    dump_sha256 = hashlib.sha256(dump_bytes).hexdigest()

    manifest_payload = {
        "backup_id": backup_id,
        "clinic_id": clinic_id,
        "label": data.label.strip(),
        "db_checkpoint_at": db_checkpoint_at.isoformat() + "Z",
        "object_store_checkpoint_at": object_checkpoint_at.isoformat() + "Z",
        "relational_dump_sha256": dump_sha256,
        "counts": {
            "patients": len(patients),
            "encounters": len(encounters),
            "snapshots": len(snapshots),
            "archive_objects": len(archive_objs),
            "ledger_entries": len(ledger_rows),
        },
        "sealed_snapshots": [
            {
                "id": s.id,
                "status": s.status,
                "canonical_sha256": s.canonical_sha256,
                "manifest_sha256": s.manifest_sha256,
                "has_signature_receipt": bool(s.provider_receipt_json),
            }
            for s in snapshots
        ],
        "archive_objects": [
            {
                "id": o.id,
                "object_kind": o.object_kind,
                "plaintext_sha256": o.plaintext_sha256,
                "ciphertext_sha256": o.ciphertext_sha256,
                "key_id": o.key_id,
                "key_version": o.key_version,
                "created_at": o.created_at.isoformat() + "Z",
            }
            for o in archive_objs
        ],
    }
    manifest_json = json.dumps(
        manifest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    manifest_bytes = manifest_json.encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_hmac = hmac.new(
        auth_secret.encode("utf-8"), manifest_bytes, hashlib.sha256
    ).hexdigest()

    bkp = m.BackupManifest(
        id=backup_id,
        clinic_id=clinic_id,
        label=data.label.strip(),
        db_checkpoint_at=db_checkpoint_at,
        object_store_checkpoint_at=object_checkpoint_at,
        bundle_relpath=bundle_relpath,
        manifest_json=manifest_json,
        manifest_sha256=manifest_sha256,
        manifest_hmac=manifest_hmac,
        status="sealed",
        actor_demo=actor,
    )
    db.add(bkp)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "archive.backup_created",
        "backup_manifest",
        bkp.id,
        {"manifest_sha256": manifest_sha256, "objects": len(archive_objs)},
    )
    db.commit()
    return bkp


def run_isolated_restore_drill(
    db: Session,
    clinic_id: str,
    backup_id: str,
    archive_dir: str,
    master_secret: str,
    auth_secret: str,
    data: RestoreDrillRequest,
    actor: str,
) -> dict:
    bkp = svc.ensure(db, m.BackupManifest, backup_id, clinic_id)
    target_clinic_id = data.target_clinic_id or clinic_id
    if target_clinic_id != clinic_id:
        svc.audit(
            db,
            clinic_id,
            actor,
            "archive.cross_tenant_restore_blocked",
            "backup_manifest",
            bkp.id,
            {"target_clinic_id": target_clinic_id},
        )
        db.commit()
        raise HTTPException(
            403, "Cross-tenant backup restore is strictly forbidden (INV-001 / T010)"
        )

    t0 = time.perf_counter()
    effective_master_secret = data.override_master_secret or master_secret
    rpo_lag_ms = max(
        0,
        int((bkp.db_checkpoint_at - bkp.object_store_checkpoint_at).total_seconds() * 1000),
    )

    archive_root = Path(archive_dir)
    archive_root.mkdir(parents=True, exist_ok=True)
    drill_dir = Path(tempfile.mkdtemp(prefix="dr-drill-", dir=archive_root))
    drill_engine = None
    failure_code: str | None = None
    failure_detail: str | None = None
    restored_patients = 0
    restored_snapshots = 0
    restored_objects = 0

    try:
        manifest_bytes = bkp.manifest_json.encode("utf-8")
        expected_sha = hashlib.sha256(manifest_bytes).hexdigest()
        expected_hmac = hmac.new(
            auth_secret.encode("utf-8"), manifest_bytes, hashlib.sha256
        ).hexdigest()
        if not (
            hmac.compare_digest(expected_sha, bkp.manifest_sha256)
            and hmac.compare_digest(expected_hmac, bkp.manifest_hmac)
        ):
            failure_code = "manifest_tampered"
            failure_detail = "Backup manifest HMAC or SHA-256 verification failed"
        else:
            manifest_data = json.loads(bkp.manifest_json)
            bundle_dir = archive_root / bkp.bundle_relpath
            dump_file = bundle_dir / "relational_dump.json"
            if not dump_file.is_file():
                failure_code = "missing_relational_dump"
                failure_detail = "Missing relational_dump.json in backup bundle"
            else:
                dump_bytes = dump_file.read_bytes()
                if not hmac.compare_digest(
                    hashlib.sha256(dump_bytes).hexdigest(),
                    manifest_data["relational_dump_sha256"],
                ):
                    failure_code = "corrupted_relational_dump"
                    failure_detail = "Corrupted relational dump SHA-256 mismatch"
                else:
                    dump = json.loads(dump_bytes.decode("utf-8"))
                    drill_db_url = f"sqlite+pysqlite:///{drill_dir / 'isolated_restore.db'}"
                    drill_engine = build_engine(drill_db_url)
                    init_demo_schema(drill_engine)
                    drill_factory = session_factory(drill_engine)

                    load_order = [
                        ("clinic", m.Clinic),
                        ("staff", m.Staff),
                        ("patient", m.Patient),
                        ("encounter", m.Encounter),
                        ("clinical_note", m.ClinicalNote),
                        ("note_revision", m.NoteRevision),
                        ("clinical_document_snapshot", m.ClinicalDocumentSnapshot),
                        ("consent_record", m.ConsentRecord),
                        ("ledger_entry", m.LedgerEntry),
                        ("tenant_encryption_key", m.TenantEncryptionKey),
                        ("archive_object", m.ArchiveObject),
                    ]
                    with drill_factory() as iso_db:
                        for key_name, cls in load_order:
                            for raw_row in dump.get(key_name, []):
                                iso_db.add(_parse_row(cls, raw_row))
                            iso_db.flush()
                        iso_db.commit()

                    with drill_factory() as verify_db:
                        pats = verify_db.scalars(
                            select(m.Patient).where(m.Patient.clinic_id == clinic_id)
                        ).all()
                        snaps = verify_db.scalars(
                            select(m.ClinicalDocumentSnapshot).where(
                                m.ClinicalDocumentSnapshot.clinic_id == clinic_id
                            )
                        ).all()
                        objs = verify_db.scalars(
                            select(m.ArchiveObject).where(m.ArchiveObject.clinic_id == clinic_id)
                        ).all()
                        restored_patients = len(pats)
                        restored_snapshots = len(snaps)
                        restored_objects = len(objs)

                        # 1. Verify cross-store checkpoint alignment & object decryption (DR-05, NEG-13)
                        for obj in objs:
                            if obj.created_at > bkp.object_store_checkpoint_at:
                                failure_code = "stale_object_store_checkpoint"
                                failure_detail = (
                                    f"Stale object-store backup checkpoint is older than "
                                    f"referenced archive object {obj.id} (DR-05)"
                                )
                                break
                            blob_path = bundle_dir / "objects" / f"{obj.id}.bin"
                            if not blob_path.is_file():
                                failure_code = "missing_archive_object"
                                failure_detail = (
                                    f"Missing encrypted archive object {obj.id} in backup bundle (NEG-13)"
                                )
                                break
                            blob = blob_path.read_bytes()
                            if not hmac.compare_digest(
                                hashlib.sha256(blob).hexdigest(), obj.ciphertext_sha256
                            ):
                                failure_code = "corrupted_archive_object"
                                failure_detail = (
                                    f"Corrupted archive object {obj.id}: ciphertext digest mismatch"
                                )
                                break
                            key_row = verify_db.get(m.TenantEncryptionKey, obj.key_id)
                            if key_row is None or key_row.status == "revoked":
                                failure_code = "key_revoked"
                                failure_detail = (
                                    f"Tenant encryption key {obj.key_id} is revoked or missing"
                                )
                                break
                            try:
                                dek_enc, dek_mac = unwrap_dek_subkeys(
                                    key_row, effective_master_secret
                                )
                            except ValueError as exc:
                                failure_code = "key_unwrap_failed"
                                failure_detail = (
                                    f"Key unwrap failed for archive object {obj.id}: {exc}"
                                )
                                break
                            try:
                                aad = (
                                    f"obj:{clinic_id}:{obj.patient_id}:{obj.id}:v{obj.key_version}"
                                ).encode("utf-8")
                                plaintext = decrypt_envelope(dek_enc, dek_mac, blob, aad)
                            except ValueError as exc:
                                failure_code = "corrupted_archive_object"
                                failure_detail = (
                                    f"Corrupted archive object {obj.id} failed authenticated decryption: {exc}"
                                )
                                break
                            if not hmac.compare_digest(
                                hashlib.sha256(plaintext).hexdigest(), obj.plaintext_sha256
                            ):
                                failure_code = "plaintext_digest_mismatch"
                                failure_detail = (
                                    f"Corrupted plaintext digest after decrypting {obj.id}"
                                )
                                break

                        # 2. Verify signature evidence on every sealed snapshot (DR-04)
                        if failure_code is None:
                            provider = signing.FakeSyntheticSignatureProvider(auth_secret)
                            for snap in snaps:
                                if snap.status != "synthetic_signed_NOT_legal":
                                    continue
                                if not snap.provider_receipt_json:
                                    failure_code = "missing_signature_evidence"
                                    failure_detail = (
                                        f"Missing signature evidence receipt on sealed snapshot {snap.id} (DR-04)"
                                    )
                                    break
                                try:
                                    receipt_dict = json.loads(snap.provider_receipt_json)
                                    receipt = signing.SignatureReceipt(**receipt_dict)
                                    sig_ok = provider.verify_receipt(
                                        snap.canonical_json.encode("utf-8"), receipt, clinic_id
                                    )
                                except Exception:
                                    sig_ok = False
                                if not sig_ok:
                                    failure_code = "invalid_signature_evidence"
                                    failure_detail = (
                                        f"Invalid or tampered signature evidence on sealed snapshot {snap.id} (DR-04)"
                                    )
                                    break
    finally:
        if drill_engine is not None:
            drill_engine.dispose()
        shutil.rmtree(drill_dir, ignore_errors=True)

    rto_ms = max(1, int((time.perf_counter() - t0) * 1000))
    passed = failure_code is None
    drill_row = m.RestoreDrillRun(
        clinic_id=clinic_id,
        backup_id=bkp.id,
        target_clinic_id=target_clinic_id,
        status="passed" if passed else "failed",
        integrity_ok=passed,
        restored_patients=restored_patients,
        restored_snapshots=restored_snapshots,
        restored_objects=restored_objects,
        rto_ms=rto_ms,
        rpo_lag_ms=rpo_lag_ms,
        failure_code=failure_code,
        failure_detail=failure_detail,
        actor_demo=actor,
    )
    db.add(drill_row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "archive.restore_drill_passed" if passed else "archive.restore_drill_failed",
        "restore_drill_run",
        drill_row.id,
        {
            "backup_id": bkp.id,
            "rto_ms": rto_ms,
            "rpo_lag_ms": rpo_lag_ms,
            "failure_code": failure_code,
        },
    )
    db.commit()
    if not passed:
        raise HTTPException(409, failure_detail or "Isolated DR restore drill failed")
    return {
        "id": drill_row.id,
        "clinic_id": clinic_id,
        "backup_id": bkp.id,
        "target_clinic_id": target_clinic_id,
        "status": drill_row.status,
        "integrity_ok": True,
        "restored_patients": restored_patients,
        "restored_snapshots": restored_snapshots,
        "restored_objects": restored_objects,
        "rto_ms": rto_ms,
        "rpo_lag_ms": rpo_lag_ms,
        "synthetic_only": True,
        "created_at": drill_row.created_at.isoformat() + "Z",
    }
