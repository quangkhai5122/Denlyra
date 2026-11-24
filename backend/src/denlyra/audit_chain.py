"""T014 Per-Clinic Hash-Chained Tamper-Evident Audit Journal (SEC-007) & Signed Cursor Pagination (PAT-002 / R-012).

1. Automatically chains every AuditEvent inserted into any SQLAlchemy Session via `before_flush`:
   entry_hash = SHA256(clinic_id | chain_seq | prev_hash | actor_demo | action | subject_type | subject_id | metadata_json | created_at_iso)
2. Verifies full genesis-to-head integrity per clinic (`verify_clinic_audit_chain`), detecting any
   out-of-band storage mutation or sequence gap with HTTP 409.
3. Encodes and verifies HMAC-SHA256-authenticated opaque pagination cursors bound to `(clinic_id, kind, sort_val, id)`,
   rejecting cross-tenant cursor replay (`403`) and tampered cursors (`422`).
"""
from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import hmac
import json

from fastapi import HTTPException
from sqlalchemy import and_, event, or_, select, text
from sqlalchemy.orm import Session

from . import models as m

GENESIS_PREV_HASH = "0" * 64


def format_audit_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")


def compute_audit_entry_hash(
    clinic_id: str,
    chain_seq: int,
    prev_hash: str,
    actor_demo: str,
    action: str,
    subject_type: str,
    subject_id: str,
    metadata_json: str,
    created_at: datetime,
) -> str:
    canonical = (
        f"{clinic_id}|{chain_seq}|{prev_hash}|{actor_demo}|{action}|"
        f"{subject_type}|{subject_id}|{metadata_json}|{format_audit_ts(created_at)}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@event.listens_for(Session, "before_flush")
def _chain_pending_audit_events(session: Session, _flush_context, _instances) -> None:
    pending = [
        obj
        for obj in session.new
        if isinstance(obj, m.AuditEvent) and not getattr(obj, "entry_hash", "")
    ]
    if not pending:
        return

    by_clinic: dict[str, list[m.AuditEvent]] = {}
    for ev in pending:
        by_clinic.setdefault(ev.clinic_id, []).append(ev)

    conn = session.connection()
    for cid, events_list in by_clinic.items():
        head = conn.execute(
            text(
                "SELECT chain_seq, entry_hash FROM audit_event "
                "WHERE clinic_id = :cid ORDER BY chain_seq DESC LIMIT 1"
            ),
            {"cid": cid},
        ).first()
        last_seq = int(head[0]) if head and head[0] else 0
        last_hash = str(head[1]) if head and head[1] else GENESIS_PREV_HASH

        for ev in events_list:
            if not ev.id:
                ev.id = m.uid()
            if ev.created_at is None:
                ev.created_at = m.utcnow()
            if ev.metadata_json is None:
                ev.metadata_json = "{}"
            next_seq = last_seq + 1
            ev.chain_seq = next_seq
            ev.prev_hash = last_hash
            ev.entry_hash = compute_audit_entry_hash(
                clinic_id=cid,
                chain_seq=next_seq,
                prev_hash=last_hash,
                actor_demo=ev.actor_demo,
                action=ev.action,
                subject_type=ev.subject_type,
                subject_id=ev.subject_id,
                metadata_json=ev.metadata_json,
                created_at=ev.created_at,
            )
            last_seq = next_seq
            last_hash = ev.entry_hash


def verify_clinic_audit_chain(db: Session, clinic_id: str) -> dict:
    rows = db.scalars(
        select(m.AuditEvent)
        .where(m.AuditEvent.clinic_id == clinic_id)
        .order_by(m.AuditEvent.chain_seq.asc())
    ).all()

    expected_seq = 1
    expected_prev = GENESIS_PREV_HASH
    head_hash = GENESIS_PREV_HASH
    head_seq = 0

    for row in rows:
        if row.chain_seq != expected_seq:
            raise HTTPException(
                409,
                f"Audit journal tamper detected: sequence gap at broken_at_seq={expected_seq} (found {row.chain_seq})",
            )
        if not hmac.compare_digest(row.prev_hash, expected_prev):
            raise HTTPException(
                409,
                f"Audit journal tamper detected: prev_hash link mismatch at broken_at_seq={row.chain_seq}",
            )
        recomputed = compute_audit_entry_hash(
            clinic_id=row.clinic_id,
            chain_seq=row.chain_seq,
            prev_hash=row.prev_hash,
            actor_demo=row.actor_demo,
            action=row.action,
            subject_type=row.subject_type,
            subject_id=row.subject_id,
            metadata_json=row.metadata_json,
            created_at=row.created_at,
        )
        if not hmac.compare_digest(row.entry_hash, recomputed):
            raise HTTPException(
                409,
                f"Audit journal tamper detected: entry_hash mismatch on event {row.id} at broken_at_seq={row.chain_seq}",
            )
        expected_prev = row.entry_hash
        head_hash = row.entry_hash
        head_seq = row.chain_seq
        expected_seq += 1

    return {
        "clinic_id": clinic_id,
        "verified_count": len(rows),
        "head_seq": head_seq,
        "head_hash": head_hash,
        "chain_intact": True,
        "synthetic_only": True,
    }


def _b64u_enc(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_dec(seg: str) -> bytes:
    pad = "=" * ((4 - len(seg) % 4) % 4)
    return base64.urlsafe_b64decode((seg + pad).encode("ascii"))


def encode_cursor(
    secret: str, clinic_id: str, kind: str, sort_val: str | int, item_id: str
) -> str:
    payload = json.dumps(
        {"c": clinic_id, "k": kind, "s": sort_val, "i": item_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    p_b64 = _b64u_enc(payload)
    sig = hmac.new(secret.encode("utf-8"), p_b64.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return f"{p_b64}.{sig}"


def decode_cursor(secret: str, expected_clinic_id: str, expected_kind: str, token: str) -> dict:
    if "." not in token:
        raise HTTPException(422, "Malformed pagination cursor")
    p_b64, provided_sig = token.split(".", 1)
    expected_sig = hmac.new(
        secret.encode("utf-8"), p_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()[:32]
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(422, "Invalid or tampered pagination cursor signature")
    try:
        data = json.loads(_b64u_dec(p_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(422, "Invalid pagination cursor payload") from exc
    if data.get("c") != expected_clinic_id:
        raise HTTPException(403, "Cross-clinic pagination cursor rejected (INV-001)")
    if data.get("k") != expected_kind:
        raise HTTPException(422, "Pagination cursor resource kind mismatch")
    return data


def paginate_patients(
    db: Session,
    clinic_id: str,
    secret: str,
    q: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> dict:
    bounded = max(1, min(limit, 100))
    stmt = select(m.Patient).where(m.Patient.clinic_id == clinic_id)
    if q and q.strip():
        stmt = stmt.where(m.Patient.display_name.ilike(f"%{q.strip()}%"))
    if cursor:
        cur = decode_cursor(secret, clinic_id, "patient", cursor)
        last_dt = datetime.fromisoformat(str(cur["s"]))
        last_id = str(cur["i"])
        stmt = stmt.where(
            or_(
                m.Patient.created_at < last_dt,
                and_(m.Patient.created_at == last_dt, m.Patient.id < last_id),
            )
        )
    stmt = stmt.order_by(m.Patient.created_at.desc(), m.Patient.id.desc()).limit(bounded + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > bounded
    slice_rows = rows[:bounded]
    next_cur = (
        encode_cursor(
            secret,
            clinic_id,
            "patient",
            slice_rows[-1].created_at.isoformat(),
            slice_rows[-1].id,
        )
        if has_more and slice_rows
        else None
    )
    return {
        "items": [
            {
                "id": p.id,
                "clinic_id": p.clinic_id,
                "display_name": p.display_name,
                "birth_year": p.birth_year,
                "source": p.source,
                "created_at": p.created_at.isoformat() + "Z",
            }
            for p in slice_rows
        ],
        "limit": bounded,
        "has_more": has_more,
        "next_cursor": next_cur,
    }


def paginate_appointments(
    db: Session,
    clinic_id: str,
    secret: str,
    limit: int = 20,
    cursor: str | None = None,
) -> dict:
    bounded = max(1, min(limit, 100))
    stmt = select(m.Appointment).where(m.Appointment.clinic_id == clinic_id)
    if cursor:
        cur = decode_cursor(secret, clinic_id, "appointment", cursor)
        last_dt = datetime.fromisoformat(str(cur["s"]))
        last_id = str(cur["i"])
        stmt = stmt.where(
            or_(
                m.Appointment.start_at > last_dt,
                and_(m.Appointment.start_at == last_dt, m.Appointment.id > last_id),
            )
        )
    stmt = stmt.order_by(m.Appointment.start_at.asc(), m.Appointment.id.asc()).limit(bounded + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > bounded
    slice_rows = rows[:bounded]
    next_cur = (
        encode_cursor(
            secret,
            clinic_id,
            "appointment",
            slice_rows[-1].start_at.isoformat(),
            slice_rows[-1].id,
        )
        if has_more and slice_rows
        else None
    )
    return {
        "items": [
            {
                "id": a.id,
                "patient_id": a.patient_id,
                "practitioner_id": a.practitioner_id,
                "chair_id": a.chair_id,
                "start_at": a.start_at.isoformat() + "Z",
                "end_at": a.end_at.isoformat() + "Z",
                "status": a.status,
                "reason_demo": a.reason_demo,
            }
            for a in slice_rows
        ],
        "limit": bounded,
        "has_more": has_more,
        "next_cursor": next_cur,
    }


def paginate_audit_events(
    db: Session,
    clinic_id: str,
    secret: str,
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    bounded = max(1, min(limit, 200))
    stmt = select(m.AuditEvent).where(m.AuditEvent.clinic_id == clinic_id)
    if cursor:
        cur = decode_cursor(secret, clinic_id, "audit_event", cursor)
        last_seq = int(cur["s"])
        stmt = stmt.where(m.AuditEvent.chain_seq < last_seq)
    stmt = stmt.order_by(m.AuditEvent.chain_seq.desc()).limit(bounded + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > bounded
    slice_rows = rows[:bounded]
    next_cur = (
        encode_cursor(
            secret,
            clinic_id,
            "audit_event",
            slice_rows[-1].chain_seq,
            slice_rows[-1].id,
        )
        if has_more and slice_rows
        else None
    )
    return {
        "items": [
            {
                "id": a.id,
                "chain_seq": a.chain_seq,
                "prev_hash": a.prev_hash,
                "entry_hash": a.entry_hash,
                "actor_demo": a.actor_demo,
                "action": a.action,
                "subject_type": a.subject_type,
                "subject_id": a.subject_id,
                "created_at": a.created_at.isoformat() + "Z",
            }
            for a in slice_rows
        ],
        "limit": bounded,
        "has_more": has_more,
        "next_cursor": next_cur,
    }
