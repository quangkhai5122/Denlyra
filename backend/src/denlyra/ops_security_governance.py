"""T023 domain services: PHI-redacted structured telemetry (OPS-005), isolated
per-clinic onboarding configuration (OPS-010), consent-gated customer support
diagnostics (OPS-012), forensic security incident & breach containment workflow
(SEC-012), and exact-pinning SBOM supply-chain verifier (SEC-013).
"""
from __future__ import annotations

from datetime import timedelta
import hashlib
import hmac
import json
from pathlib import Path
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit_chain, models as m, services as svc
from .schemas import (
    ClinicOnboardingConfigCreate,
    RedactedTelemetryCreate,
    SecurityIncidentCreate,
    SecurityIncidentTransitionRequest,
    SupplyChainVerifyRequest,
    SupportConsentGrantCreate,
    SupportDiagnosticExportRequest,
)

ROOT = Path(__file__).resolve().parents[3]

SENSITIVE_TELEMETRY_KEYS = {
    "note_content",
    "clinical_note",
    "draft_text",
    "finding_text",
    "display_name",
    "patient_name",
    "phone",
    "phone_demo",
    "national_id",
    "cccd",
    "email",
    "address",
    "authorization",
    "access_token",
    "portal_token",
}

PHONE_OR_ID_RE = re.compile(r"(?:\+?84|0)\d{8,10}\b|\b\d{9,12}\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){1,2}\b")
PINNED_PY_RE = re.compile(r"^[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+$")


def emit_redacted_telemetry_event(
    db: Session,
    clinic_id: str,
    actor: str,
    data: RedactedTelemetryCreate,
) -> m.RedactedTelemetryEvent:
    patient_names = [
        n
        for n in db.scalars(
            select(m.Patient.display_name).where(m.Patient.clinic_id == clinic_id)
        ).all()
        if n and len(n.strip()) >= 3
    ]
    sanitized: dict[str, str | int | bool] = {}
    redacted_count = 0

    for k, v in data.attributes.items():
        key_norm = k.strip().lower()
        if key_norm in SENSITIVE_TELEMETRY_KEYS or "note" in key_norm or "token" in key_norm:
            sanitized[k] = "[REDACTED_SENSITIVE_KEY]"
            redacted_count += 1
            continue
        if isinstance(v, str):
            scrubbed = v
            changed = False
            for pname in patient_names:
                if pname in scrubbed:
                    scrubbed = scrubbed.replace(pname, "[REDACTED_PATIENT_NAME]")
                    changed = True
            new_s = JWT_RE.sub("[REDACTED_TOKEN]", scrubbed)
            new_s = EMAIL_RE.sub("[REDACTED_EMAIL]", new_s)
            new_s = PHONE_OR_ID_RE.sub("[REDACTED_PII_NUMBER]", new_s)
            if new_s != scrubbed:
                changed = True
            if changed:
                redacted_count += 1
            sanitized[k] = new_s
        else:
            sanitized[k] = v

    row = m.RedactedTelemetryEvent(
        clinic_id=clinic_id,
        trace_id=data.trace_id.strip(),
        span_name=data.span_name.strip(),
        severity=data.severity,
        sanitized_attributes_json=json.dumps(sanitized, sort_keys=True, ensure_ascii=False),
        redacted_field_count=redacted_count,
        contains_phi_or_note_text=False,
        actor_demo=actor,
    )
    db.add(row)
    db.commit()
    return row


def configure_clinic_onboarding(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: ClinicOnboardingConfigCreate,
) -> m.ClinicOnboardingConfig:
    catalog_cnt = int(
        db.scalar(
            select(func.count())
            .select_from(m.ServicePriceCatalogItem)
            .where(m.ServicePriceCatalogItem.clinic_id == clinic_id)
        )
        or 0
    )
    form_cnt = int(
        db.scalar(
            select(func.count())
            .select_from(m.FormTemplateVersion)
            .where(m.FormTemplateVersion.clinic_id == clinic_id)
        )
        or 0
    )
    if data.mark_ready and (catalog_cnt == 0 or form_cnt == 0):
        raise HTTPException(
            409,
            "Per-clinic onboarding cannot be marked ready until this clinic configures its own "
            "service price catalog and quarantined form templates (OPS-010)",
        )

    max_ver = int(
        db.scalar(
            select(func.coalesce(func.max(m.ClinicOnboardingConfig.version_number), 0)).where(
                m.ClinicOnboardingConfig.clinic_id == clinic_id
            )
        )
        or 0
    )
    roles_sorted = sorted(set(data.configured_roles))
    status = "configured_synthetic_ready" if data.mark_ready else "draft_incomplete"
    row = m.ClinicOnboardingConfig(
        clinic_id=clinic_id,
        version_number=max_ver + 1,
        configured_roles_json=json.dumps(roles_sorted),
        catalog_item_count=catalog_cnt,
        quarantined_form_count=form_cnt,
        legacy_field_mapping_json=json.dumps(
            data.legacy_field_mapping, sort_keys=True, ensure_ascii=False
        ),
        readiness_status=status,
        configured_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ops.clinic_onboarding_configured",
        "clinic_onboarding_config",
        row.id,
        {"version_number": row.version_number, "readiness_status": status},
    )
    db.commit()
    return row


def create_support_consent_grant(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: SupportConsentGrantCreate,
) -> m.CustomerSupportConsentGrant:
    if data.allow_live_patient_records:
        svc.audit(
            db,
            clinic_id,
            actor,
            "ops.support_live_phi_grant_blocked",
            "clinic",
            clinic_id,
            {"ticket_reference": data.ticket_reference},
        )
        db.commit()
        raise HTTPException(
            409,
            "Support diagnostic tooling cannot authorize access to live patient records or clinical notes (OPS-012)",
        )
    expires_at = m.utcnow() + timedelta(seconds=data.ttl_seconds)
    row = m.CustomerSupportConsentGrant(
        clinic_id=clinic_id,
        ticket_reference=data.ticket_reference.strip(),
        scope="redacted_system_diagnostics_only",
        allow_live_patient_records=False,
        expires_at=expires_at,
        revoked=False,
        granted_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ops.support_consent_granted",
        "customer_support_consent_grant",
        row.id,
        {"ticket_reference": row.ticket_reference, "ttl_seconds": data.ttl_seconds},
    )
    db.commit()
    return row


def revoke_support_consent_grant(
    db: Session,
    clinic_id: str,
    grant_id: str,
    actor: str,
) -> m.CustomerSupportConsentGrant:
    row = svc.ensure(db, m.CustomerSupportConsentGrant, grant_id, clinic_id)
    row.revoked = True
    svc.audit(
        db,
        clinic_id,
        actor,
        "ops.support_consent_revoked",
        "customer_support_consent_grant",
        row.id,
    )
    db.commit()
    return row


def export_support_diagnostic_bundle(
    db: Session,
    clinic_id: str,
    actor: str,
    data: SupportDiagnosticExportRequest,
) -> m.SupportDiagnosticBundle:
    if data.include_patient_records:
        raise HTTPException(
            409,
            "Support diagnostic bundle cannot include live patient records or clinical notes (OPS-012)",
        )
    grant = db.get(m.CustomerSupportConsentGrant, data.grant_id)
    if (
        grant is None
        or grant.clinic_id != clinic_id
        or grant.revoked
        or m.utcnow() >= grant.expires_at
    ):
        svc.audit(
            db,
            clinic_id,
            actor,
            "ops.support_diagnostic_denied_no_consent",
            "clinic",
            clinic_id,
            {"grant_id": data.grant_id[:36]},
        )
        db.commit()
        raise HTTPException(
            403,
            "Active unrevoked customer consent grant required before exporting support diagnostics (OPS-012)",
        )

    chain_status = audit_chain.verify_clinic_audit_chain(db, clinic_id)
    err_spans = int(
        db.scalar(
            select(func.count())
            .select_from(m.RedactedTelemetryEvent)
            .where(
                m.RedactedTelemetryEvent.clinic_id == clinic_id,
                m.RedactedTelemetryEvent.severity == "error",
            )
        )
        or 0
    )
    summary_payload = {
        "clinic_id": clinic_id,
        "ticket_reference": grant.ticket_reference,
        "scope": grant.scope,
        "audit_chain_intact": chain_status["chain_intact"],
        "audit_verified_count": chain_status["verified_count"],
        "redacted_error_span_count": err_spans,
        "contains_patient_records": False,
    }
    raw = json.dumps(summary_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    bundle_sha = hashlib.sha256(raw).hexdigest()
    bundle = m.SupportDiagnosticBundle(
        clinic_id=clinic_id,
        grant_id=grant.id,
        bundle_sha256=bundle_sha,
        diagnostic_summary_json=raw.decode("utf-8"),
        exported_by_actor=actor,
    )
    db.add(bundle)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "ops.support_diagnostic_exported",
        "support_diagnostic_bundle",
        bundle.id,
        {"grant_id": grant.id, "bundle_sha256": bundle_sha},
    )
    db.commit()
    return bundle


def open_security_incident_case(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    data: SecurityIncidentCreate,
) -> m.SecurityIncidentCase:
    svc.audit(
        db,
        clinic_id,
        actor,
        "security.incident_evidence_checkpoint",
        "clinic",
        clinic_id,
        {"severity": data.severity, "incident_type": data.incident_type},
    )
    db.flush()
    head_audit = db.scalars(
        select(m.AuditEvent)
        .where(m.AuditEvent.clinic_id == clinic_id)
        .order_by(m.AuditEvent.chain_seq.desc())
    ).first()
    head_seq = head_audit.chain_seq if head_audit else 0
    head_hash = (
        head_audit.entry_hash
        if (head_audit and len(head_audit.entry_hash) == 64)
        else "0" * 64
    )

    case = m.SecurityIncidentCase(
        clinic_id=clinic_id,
        severity=data.severity,
        incident_type=data.incident_type,
        summary=data.summary.strip(),
        preserved_audit_head_seq=head_seq,
        preserved_audit_head_hash=head_hash,
        containment_status="triaged_evidence_preserved",
        opened_by_staff_id=staff_id,
    )
    db.add(case)
    db.flush()
    db.add(
        m.SecurityIncidentEvent(
            clinic_id=clinic_id,
            incident_id=case.id,
            step_action="triaged_evidence_preserved",
            detail_note=f"Preserved audit head seq={head_seq}",
            actor_staff_id=staff_id,
        )
    )
    db.commit()
    return case


def transition_security_incident_case(
    db: Session,
    clinic_id: str,
    incident_id: str,
    staff_id: str,
    actor: str,
    data: SecurityIncidentTransitionRequest,
) -> m.SecurityIncidentCase:
    case = svc.ensure(db, m.SecurityIncidentCase, incident_id, clinic_id)
    if case.containment_status == "closed":
        raise HTTPException(409, "Security incident case is already closed")

    if data.counsel_guidance_note and data.counsel_guidance_note.strip():
        case.counsel_guidance_note = data.counsel_guidance_note.strip()
    if data.notification_decision and data.notification_decision.strip():
        case.notification_decision = data.notification_decision.strip()

    if data.next_status == "closed" and case.severity in {
        "high",
        "critical_potential_breach",
    }:
        if not case.counsel_guidance_note or not case.notification_decision:
            raise HTTPException(
                409,
                "High/critical breach incidents require documented legal counsel guidance "
                "and notification decision before closure (SEC-012)",
            )

    case.containment_status = data.next_status
    db.add(
        m.SecurityIncidentEvent(
            clinic_id=clinic_id,
            incident_id=case.id,
            step_action=data.next_status,
            detail_note=data.detail_note.strip(),
            actor_staff_id=staff_id,
        )
    )
    svc.audit(
        db,
        clinic_id,
        actor,
        f"security.incident_{data.next_status}",
        "security_incident_case",
        case.id,
    )
    db.commit()
    return case


def verify_supply_chain_sbom(
    db: Session,
    clinic_id: str,
    staff_id: str,
    actor: str,
    auth_secret: str,
    data: SupplyChainVerifyRequest,
) -> m.SupplyChainAttestation:
    py_path = ROOT / "backend" / "constraints-baseline.txt"
    npm_path = ROOT / "apps" / "clinic-web" / "package-lock.json"

    py_text = (
        data.constraints_override_text
        if data.constraints_override_text is not None
        else py_path.read_text(encoding="utf-8")
    )
    npm_bytes = npm_path.read_bytes()
    py_sha = hashlib.sha256(py_text.encode("utf-8")).hexdigest()
    npm_sha = hashlib.sha256(npm_bytes).hexdigest()

    components: list[dict] = []
    unpinned: list[str] = []
    for raw_line in py_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not PINNED_PY_RE.match(line):
            unpinned.append(line)
        else:
            pkg_name, pkg_ver = line.split("==", 1)
            components.append(
                {"ecosystem": "pypi", "name": pkg_name.lower(), "version": pkg_ver}
            )

    if unpinned:
        svc.audit(
            db,
            clinic_id,
            actor,
            "security.supply_chain_unpinned_rejected",
            "clinic",
            clinic_id,
            {"unpinned": unpinned[:5]},
        )
        db.commit()
        raise HTTPException(
            409,
            f"Unpinned dependency specifications rejected by supply-chain verifier: {', '.join(unpinned[:3])} (SEC-013)",
        )

    npm_json = json.loads(npm_bytes.decode("utf-8"))
    root_pkg = npm_json.get("packages", {}).get("", {})
    for section in ("dependencies", "devDependencies"):
        for dep_name, dep_ver in sorted((root_pkg.get(section) or {}).items()):
            components.append(
                {"ecosystem": "npm", "name": dep_name, "version": str(dep_ver)}
            )

    sbom_doc = {
        "bomFormat": "CycloneDX-Denlyra-Subset",
        "specVersion": "1.5",
        "python_constraints_sha256": py_sha,
        "npm_lockfile_sha256": npm_sha,
        "components": sorted(components, key=lambda c: (c["ecosystem"], c["name"])),
    }
    sbom_bytes = json.dumps(sbom_doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sbom_sha = hashlib.sha256(sbom_bytes).hexdigest()
    att_hmac = hmac.new(
        f"{auth_secret}:{clinic_id}:sbom".encode("utf-8"), sbom_bytes, hashlib.sha256
    ).hexdigest()

    row = m.SupplyChainAttestation(
        clinic_id=clinic_id,
        python_constraints_sha256=py_sha,
        npm_lockfile_sha256=npm_sha,
        sbom_component_count=len(components),
        unpinned_dependency_count=0,
        sbom_canonical_sha256=sbom_sha,
        attestation_hmac_sha256=att_hmac,
        status="verified_pinned",
        verified_by_staff_id=staff_id,
    )
    db.add(row)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "security.supply_chain_sbom_verified",
        "supply_chain_attestation",
        row.id,
        {"sbom_component_count": len(components), "sbom_canonical_sha256": sbom_sha},
    )
    db.commit()
    return row
