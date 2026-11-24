"""Synthetic OIDC-style token issuer, session verification, and deny-by-default RBAC/ABAC engine.

Implements T001 foundation (ADR-007). Production deployment still requires an independent
security review (SEC-G1) and a live OIDC/MFA identity provider.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m

ISSUER = "denlyra-synthetic-local-issuer"

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "context.read": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator", "finance",
    },
    "dashboard.read": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator", "finance",
    },
    "audit.read": {"clinic_owner", "medical_director", "dentist"},
    "staff.manage": {"clinic_owner", "medical_director"},
    "resource.manage": {"clinic_owner", "medical_director", "dentist", "receptionist"},
    "patient.read": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator", "finance",
    },
    "patient.write": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "appointment.read": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator",
    },
    "appointment.write": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "encounter.read": {
        "clinic_owner", "medical_director", "dentist",
        "assistant", "treatment_coordinator",
    },
    "encounter.create": {"medical_director", "dentist"},
    "note.read": {"clinic_owner", "medical_director", "dentist"},
    "note.write": {"medical_director", "dentist"},
    "note.lock": {"medical_director", "dentist"},
    "finding.read": {"clinic_owner", "medical_director", "dentist", "assistant"},
    "finding.write": {"medical_director", "dentist"},
    "odontogram.read": {
        "clinic_owner", "medical_director", "dentist",
        "assistant", "treatment_coordinator",
    },
    "plan.read": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator",
    },
    "plan.write": {"medical_director", "dentist", "treatment_coordinator"},
    "plan.review": {"medical_director", "dentist"},
    "plan.reassess": {"medical_director", "dentist"},
    "plan.complete_task": {
        "medical_director", "dentist", "assistant", "treatment_coordinator",
    },
    "lab.read": {
        "clinic_owner", "medical_director", "dentist",
        "assistant", "treatment_coordinator",
    },
    "lab.write": {"clinic_owner", "medical_director", "dentist", "treatment_coordinator"},
    "finance.read": {"clinic_owner", "finance", "receptionist", "treatment_coordinator"},
    "finance.write": {"clinic_owner", "finance", "receptionist"},
    "finance.allocate": {"clinic_owner", "finance"},
    "finance.refund": {"clinic_owner", "finance"},
    "clinical_form.read": {"clinic_owner", "medical_director", "dentist"},
    "clinical_form.write": {"clinic_owner", "medical_director", "dentist"},
    "clinical_doc.read": {"clinic_owner", "medical_director", "dentist"},
    "clinical_doc.write": {"medical_director", "dentist"},
    "clinical_doc.sign": {"medical_director", "dentist"},
    "consent.read": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator",
    },
    "consent.write": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "migration.read": {"clinic_owner", "medical_director", "dentist", "receptionist"},
    "migration.write": {"clinic_owner", "medical_director", "dentist"},
    "archive.read": {"clinic_owner", "medical_director", "dentist"},
    "archive.write": {"clinic_owner", "medical_director", "dentist"},
    "archive.key_manage": {"clinic_owner", "medical_director"},
    "archive.restore": {"clinic_owner", "medical_director"},
    "inventory.read": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "treatment_coordinator", "finance",
    },
    "inventory.write": {"clinic_owner", "medical_director", "dentist", "treatment_coordinator"},
    "inventory.consume": {"clinic_owner", "medical_director", "dentist", "assistant"},
    "inventory.adjust_request": {
        "clinic_owner", "medical_director", "dentist", "treatment_coordinator",
    },
    "inventory.adjust_approve": {"clinic_owner", "medical_director"},
    "interop.fhir_read": {"clinic_owner", "medical_director", "dentist"},
    "ai.draft": {"clinic_owner", "medical_director", "dentist", "treatment_coordinator"},
    "ai.accept_clinical": {"medical_director", "dentist"},
    "ai.evaluate": {"clinic_owner", "medical_director", "dentist"},
    "operations.read": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator",
    },
    "operations.shift_manage": {"clinic_owner", "medical_director"},
    "operations.downtime_manage": {"clinic_owner", "medical_director", "dentist", "assistant"},
    "operations.checkin": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator",
    },
    "operations.turnover": {"clinic_owner", "medical_director", "dentist", "assistant"},
    "operations.recall": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "patient.merge_request": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "patient.merge_approve": {"clinic_owner", "medical_director", "dentist"},
    "auth.break_glass": {
        "clinic_owner", "medical_director", "dentist",
        "assistant", "treatment_coordinator",
    },
    "portal.manage": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "portal.publish": {"medical_director", "dentist"},
    "finance.catalog_manage": {"clinic_owner", "medical_director", "finance"},
    "finance.discount_approve": {"clinic_owner", "medical_director"},
    "medical_risk.write": {"clinic_owner", "medical_director", "dentist", "assistant"},
    "diagnosis.write": {"medical_director", "dentist"},
    "procedure.record_performed": {"medical_director", "dentist"},
    "encounter.close": {"medical_director", "dentist"},
    "quality.report_create": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator", "finance",
    },
    "quality.report_read": {"clinic_owner", "medical_director"},
    "odontogram.write": {"medical_director", "dentist"},
    "referral.intake": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "referral.review": {"medical_director", "dentist"},
    "handoff.read": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator",
    },
    "handoff.write": {
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator",
    },
    "complaint.create": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "complaint.read": {
        "clinic_owner", "medical_director", "dentist",
        "receptionist", "treatment_coordinator",
    },
    "complaint.read_private": {"clinic_owner", "medical_director"},
    "signed_url.create": {"clinic_owner", "medical_director", "dentist"},
    "signed_url.consume": {"clinic_owner", "medical_director", "dentist"},
}


@dataclass(frozen=True)
class Principal:
    staff_id: str
    clinic_id: str
    branch_id: str
    role: str
    actor_label: str
    jti: str
    authenticated: bool = True


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(segment: str) -> bytes:
    pad = "=" * ((4 - len(segment) % 4) % 4)
    return base64.urlsafe_b64decode((segment + pad).encode("ascii"))


def sign_token(claims: dict, secret: str) -> str:
    header = _b64u_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload = _b64u_encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64u_encode(sig)}"


def decode_and_verify_token(token: str, secret: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(401, "Malformed authentication token")
    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64u_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64u_decode(payload_b64).decode("utf-8"))
        provided_sig = _b64u_decode(sig_b64)
    except Exception as exc:
        raise HTTPException(401, "Malformed authentication token encoding") from exc
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise HTTPException(401, "Unsupported token algorithm")
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(401, "Invalid token signature")
    now = int(time.time())
    if payload.get("iss") != ISSUER:
        raise HTTPException(401, "Untrusted token issuer")
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= now:
        raise HTTPException(401, "Authentication token expired")
    return payload


def issue_synthetic_staff_token(
    db: Session,
    secret: str,
    clinic_id: str,
    role: str,
    staff_id: str | None = None,
    branch_id: str = "branch-main",
    ttl_seconds: int = 3600,
) -> dict:
    clinic = db.get(m.Clinic, clinic_id)
    if not clinic or not clinic.demo_only:
        raise HTTPException(404, "Demo clinic not found")
    if staff_id:
        staff = db.get(m.Staff, staff_id)
        if not staff or staff.clinic_id != clinic_id:
            raise HTTPException(404, "Staff member not found in clinic")
    else:
        staff = db.scalar(
            select(m.Staff).where(
                m.Staff.clinic_id == clinic_id,
                m.Staff.role == role,
                m.Staff.active.is_(True),
            )
        )
        if not staff:
            staff = m.Staff(
                id=m.uid(),
                clinic_id=clinic_id,
                branch_id=branch_id,
                display_name=f"Nhân sự {role} demo",
                role=role,
                active=True,
                token_version=1,
            )
            db.add(staff)
            db.flush()
    if not staff.active:
        raise HTTPException(403, "Cannot issue token for deactivated staff member")
    now = int(time.time())
    jti = str(uuid4())
    claims = {
        "iss": ISSUER,
        "sub": staff.id,
        "clinic_id": clinic_id,
        "branch_id": getattr(staff, "branch_id", branch_id) or branch_id,
        "role": staff.role,
        "token_version": getattr(staff, "token_version", 1),
        "jti": jti,
        "iat": now,
        "exp": now + int(ttl_seconds),
    }
    token = sign_token(claims, secret)
    db.add(
        m.AuditEvent(
            clinic_id=clinic_id,
            actor_demo=f"{staff.role}:{staff.id}"[:100],
            action="auth.token_issued_synthetic",
            subject_type="staff",
            subject_id=staff.id,
            metadata_json=json.dumps({"jti": jti, "role": staff.role}, ensure_ascii=False),
        )
    )
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "staff_id": staff.id,
        "clinic_id": clinic_id,
        "branch_id": claims["branch_id"],
        "role": staff.role,
        "jti": jti,
        "expires_at": claims["exp"],
        "synthetic_only": True,
    }


def resolve_principal_from_token(db: Session, token: str, secret: str) -> Principal:
    claims = decode_and_verify_token(token, secret)
    if claims.get("aud") == "patient_portal":
        raise HTTPException(401, "Portal token is not valid for staff endpoints")
    jti = str(claims.get("jti") or "")
    clinic_id = str(claims.get("clinic_id") or "")
    staff_id = str(claims.get("sub") or "")
    if not jti or not clinic_id or not staff_id:
        raise HTTPException(401, "Incomplete token claims")
    revoked = db.scalar(select(m.RevokedToken).where(m.RevokedToken.jti == jti))
    if revoked is not None:
        raise HTTPException(401, "Token has been revoked")
    staff = db.get(m.Staff, staff_id)
    if (
        staff is None
        or staff.clinic_id != clinic_id
        or not staff.active
        or staff.role != claims.get("role")
        or getattr(staff, "token_version", 1) != claims.get("token_version", 1)
    ):
        raise HTTPException(401, "Staff membership inactive, revoked, or mismatched")
    return Principal(
        staff_id=staff.id,
        clinic_id=clinic_id,
        branch_id=str(claims.get("branch_id") or "branch-main"),
        role=staff.role,
        actor_label=f"{staff.role}:{staff.id}"[:100],
        jti=jti,
        authenticated=True,
    )


def check_permission(
    db: Session,
    principal: Principal,
    permission: str,
    subject_type: str = "endpoint",
    subject_id: str = "api",
    audit_read: bool = False,
) -> None:
    allowed_roles = ROLE_PERMISSIONS.get(permission, set())
    if principal.role not in allowed_roles:
        delegated = None
        if principal.authenticated:
            now = m.utcnow()
            delegated = db.scalar(
                select(m.TemporaryDelegationGrant).where(
                    m.TemporaryDelegationGrant.clinic_id == principal.clinic_id,
                    m.TemporaryDelegationGrant.delegate_staff_id == principal.staff_id,
                    m.TemporaryDelegationGrant.permission == permission,
                    m.TemporaryDelegationGrant.revoked.is_(False),
                    m.TemporaryDelegationGrant.expires_at > now,
                )
            )
        if delegated is not None:
            db.add(
                m.AuditEvent(
                    clinic_id=principal.clinic_id,
                    actor_demo=principal.actor_label,
                    action="auth.delegated_permission_used",
                    subject_type=subject_type,
                    subject_id=subject_id[:36],
                    metadata_json=json.dumps(
                        {
                            "delegation_id": delegated.id,
                            "permission": permission,
                            "reason": delegated.reason,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
            db.commit()
            return
        db.add(
            m.AuditEvent(
                clinic_id=principal.clinic_id,
                actor_demo=principal.actor_label,
                action="auth.access_denied",
                subject_type=subject_type,
                subject_id=subject_id[:36],
                metadata_json=json.dumps(
                    {"permission": permission, "role": principal.role},
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()
        raise HTTPException(
            403, f"Role '{principal.role}' is not authorized for '{permission}'"
        )
    if audit_read and principal.authenticated:
        db.add(
            m.AuditEvent(
                clinic_id=principal.clinic_id,
                actor_demo=principal.actor_label,
                action=f"access.{permission}",
                subject_type=subject_type,
                subject_id=subject_id[:36],
                metadata_json=json.dumps(
                    {"role": principal.role, "branch_id": principal.branch_id},
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()


def revoke_token(db: Session, principal: Principal) -> None:
    existing = db.scalar(select(m.RevokedToken).where(m.RevokedToken.jti == principal.jti))
    if existing is None:
        db.add(
            m.RevokedToken(
                jti=principal.jti,
                clinic_id=principal.clinic_id,
                staff_id=principal.staff_id,
                reason="explicit_revoke",
            )
        )
    db.add(
        m.AuditEvent(
            clinic_id=principal.clinic_id,
            actor_demo=principal.actor_label,
            action="auth.token_revoked",
            subject_type="staff",
            subject_id=principal.staff_id,
            metadata_json=json.dumps({"jti": principal.jti}, ensure_ascii=False),
        )
    )
    db.commit()


def create_signed_url_grant(
    db: Session,
    principal: Principal,
    secret: str,
    subject_type: str,
    subject_id: str,
    ttl_seconds: int = 300,
) -> dict:
    check_permission(db, principal, "signed_url.create", subject_type, subject_id)
    if subject_type == "clinical_note":
        note = db.get(m.ClinicalNote, subject_id)
        if not note or note.clinic_id != principal.clinic_id:
            raise HTTPException(404, "Object not found in this clinic")
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=ttl_seconds)
    grant = m.SignedUrlGrant(
        clinic_id=principal.clinic_id,
        created_by_staff_id=principal.staff_id,
        subject_type=subject_type,
        subject_id=subject_id,
        expires_at=expires_at,
    )
    db.add(grant)
    db.flush()
    sig_payload = f"{grant.id}:{grant.clinic_id}:{grant.subject_type}:{grant.subject_id}:{int(expires_at.replace(tzinfo=timezone.utc).timestamp())}"
    sig = hmac.new(secret.encode("utf-8"), sig_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    grant_token = f"{grant.id}.{sig}"
    db.add(
        m.AuditEvent(
            clinic_id=principal.clinic_id,
            actor_demo=principal.actor_label,
            action="auth.signed_url_created",
            subject_type=subject_type,
            subject_id=subject_id,
            metadata_json=json.dumps({"grant_id": grant.id}, ensure_ascii=False),
        )
    )
    db.commit()
    return {
        "grant_id": grant.id,
        "grant_token": grant_token,
        "download_path": f"/api/v1/signed-download/{grant_token}",
        "expires_at": expires_at.isoformat() + "Z",
    }


def consume_signed_url_grant(
    db: Session,
    principal: Principal,
    secret: str,
    grant_token: str,
) -> dict:
    check_permission(db, principal, "signed_url.consume", "signed_url", grant_token[:36])
    if "." not in grant_token:
        raise HTTPException(403, "Invalid signed URL token")
    grant_id, provided_sig = grant_token.split(".", 1)
    grant = db.get(m.SignedUrlGrant, grant_id)
    if grant is None:
        raise HTTPException(403, "Signed URL grant not found")
    if grant.clinic_id != principal.clinic_id:
        db.add(
            m.AuditEvent(
                clinic_id=principal.clinic_id,
                actor_demo=principal.actor_label,
                action="auth.signed_url_cross_clinic_denied",
                subject_type=grant.subject_type,
                subject_id=grant.subject_id,
            )
        )
        db.commit()
        raise HTTPException(403, "Cross-clinic signed URL access denied")
    exp_ts = int(grant.expires_at.replace(tzinfo=timezone.utc).timestamp())
    expected_payload = f"{grant.id}:{grant.clinic_id}:{grant.subject_type}:{grant.subject_id}:{exp_ts}"
    expected_sig = hmac.new(secret.encode("utf-8"), expected_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise HTTPException(403, "Signed URL signature mismatch")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if now >= grant.expires_at:
        raise HTTPException(403, "Signed URL expired")
    if grant.used_at is not None:
        db.add(
            m.AuditEvent(
                clinic_id=principal.clinic_id,
                actor_demo=principal.actor_label,
                action="auth.signed_url_reuse_denied",
                subject_type=grant.subject_type,
                subject_id=grant.subject_id,
                metadata_json=json.dumps({"grant_id": grant.id}, ensure_ascii=False),
            )
        )
        db.commit()
        raise HTTPException(403, "Signed URL already used; single-use policy enforced")
    grant.used_at = now
    db.add(
        m.AuditEvent(
            clinic_id=principal.clinic_id,
            actor_demo=principal.actor_label,
            action="auth.signed_url_consumed",
            subject_type=grant.subject_type,
            subject_id=grant.subject_id,
            metadata_json=json.dumps({"grant_id": grant.id}, ensure_ascii=False),
        )
    )
    db.commit()
    return {
        "grant_id": grant.id,
        "clinic_id": grant.clinic_id,
        "subject_type": grant.subject_type,
        "subject_id": grant.subject_id,
        "consumed_at": now.isoformat() + "Z",
        "synthetic_only": True,
    }
