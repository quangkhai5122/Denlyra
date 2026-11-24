"""T012 Clinic-Scoped HL7 FHIR R4 Read/Export Profiles & Provenance Validator (INT-002 / INT-003).

Generates and validates synthetic HL7 FHIR R4 Bundles containing Patient, Practitioner,
Appointment, Encounter, DocumentReference, and Provenance resources.

SAFETY RULES:
- Every resource carries HL7 v3-ActReason security tag 'HTEST' (test health data).
- Provenance distinguishes 'legacy_scan' vs 'synthetic_signed_NOT_legal' and NEVER claims
  legally valid e-signatures ('legal_authenticated' / legal_signature_valid=True).
"""
from __future__ import annotations

import base64
from datetime import timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m, services as svc

HTEST_TAG = {
    "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
    "code": "HTEST",
    "display": "test health data (synthetic only)",
}
CLINIC_EXT_URL = "https://denlyra.local/fhir/StructureDefinition/clinic-scope"
LEGAL_SIG_EXT_URL = "https://denlyra.local/fhir/StructureDefinition/legal-signature-valid"


def _meta(profile_slug: str) -> dict:
    return {
        "profile": [f"https://denlyra.local/fhir/StructureDefinition/vn-synthetic-{profile_slug}"],
        "security": [dict(HTEST_TAG)],
    }


def _clinic_ext(clinic_id: str) -> dict:
    return {"url": CLINIC_EXT_URL, "valueString": clinic_id}


def export_patient_fhir_r4_bundle(db: Session, clinic_id: str, patient_id: str) -> dict:
    pat = svc.ensure(db, m.Patient, patient_id, clinic_id)
    appts = db.scalars(
        select(m.Appointment)
        .where(m.Appointment.clinic_id == clinic_id, m.Appointment.patient_id == pat.id)
        .order_by(m.Appointment.start_at)
    ).all()
    encs = db.scalars(
        select(m.Encounter)
        .where(m.Encounter.clinic_id == clinic_id, m.Encounter.patient_id == pat.id)
        .order_by(m.Encounter.created_at)
    ).all()

    prac_ids = {a.practitioner_id for a in appts} | {e.practitioner_id for e in encs}
    practitioners = (
        db.scalars(
            select(m.Staff).where(
                m.Staff.clinic_id == clinic_id,
                m.Staff.id.in_(prac_ids),
            )
        ).all()
        if prac_ids
        else []
    )

    enc_ids = [e.id for e in encs]
    snaps = (
        db.scalars(
            select(m.ClinicalDocumentSnapshot)
            .where(
                m.ClinicalDocumentSnapshot.clinic_id == clinic_id,
                m.ClinicalDocumentSnapshot.encounter_id.in_(enc_ids),
            )
            .order_by(m.ClinicalDocumentSnapshot.created_at)
        ).all()
        if enc_ids
        else []
    )

    entries: list[dict] = []

    # 1. Patient + Origin Provenance
    pat_res: dict = {
        "resourceType": "Patient",
        "id": pat.id,
        "meta": _meta("patient"),
        "extension": [_clinic_ext(clinic_id)],
        "active": True,
        "name": [{"text": pat.display_name}],
    }
    if pat.birth_year:
        pat_res["birthDate"] = f"{pat.birth_year:04d}"
    entries.append({"fullUrl": f"urn:uuid:{pat.id}", "resource": pat_res})

    entries.append(
        {
            "fullUrl": f"urn:uuid:prov-pat-{pat.id}",
            "resource": {
                "resourceType": "Provenance",
                "id": f"prov-pat-{pat.id}"[:64],
                "meta": _meta("provenance"),
                "extension": [
                    _clinic_ext(clinic_id),
                    {"url": LEGAL_SIG_EXT_URL, "valueBoolean": False},
                ],
                "target": [{"reference": f"Patient/{pat.id}"}],
                "recorded": pat.created_at.replace(tzinfo=timezone.utc).isoformat(),
                "activity": {
                    "coding": [
                        {
                            "system": "https://denlyra.local/fhir/CodeSystem/record-origin",
                            "code": pat.source,
                        }
                    ]
                },
                "agent": [{"who": {"display": f"Clinic {clinic_id} synthetic registry"}}],
            },
        }
    )

    # 2. Practitioners
    for st in practitioners:
        entries.append(
            {
                "fullUrl": f"urn:uuid:{st.id}",
                "resource": {
                    "resourceType": "Practitioner",
                    "id": st.id,
                    "meta": _meta("practitioner"),
                    "extension": [_clinic_ext(clinic_id)],
                    "active": st.active,
                    "name": [{"text": st.display_name}],
                },
            }
        )

    # 3. Appointments
    for ap in appts:
        fhir_status = "booked" if ap.status == "confirmed" else "cancelled"
        entries.append(
            {
                "fullUrl": f"urn:uuid:{ap.id}",
                "resource": {
                    "resourceType": "Appointment",
                    "id": ap.id,
                    "meta": _meta("appointment"),
                    "extension": [_clinic_ext(clinic_id)],
                    "status": fhir_status,
                    "description": ap.reason_demo,
                    "start": ap.start_at.replace(tzinfo=timezone.utc).isoformat(),
                    "end": ap.end_at.replace(tzinfo=timezone.utc).isoformat(),
                    "participant": [
                        {"actor": {"reference": f"Patient/{pat.id}"}, "status": "accepted"},
                        {
                            "actor": {"reference": f"Practitioner/{ap.practitioner_id}"},
                            "status": "accepted",
                        },
                    ],
                },
            }
        )

    # 4. Encounters
    for enc in encs:
        entries.append(
            {
                "fullUrl": f"urn:uuid:{enc.id}",
                "resource": {
                    "resourceType": "Encounter",
                    "id": enc.id,
                    "meta": _meta("encounter"),
                    "extension": [_clinic_ext(clinic_id)],
                    "status": "in-progress" if enc.status == "draft_open" else "finished",
                    "class": {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                        "code": "AMB",
                        "display": "ambulatory",
                    },
                    "subject": {"reference": f"Patient/{pat.id}"},
                    "participant": [
                        {"individual": {"reference": f"Practitioner/{enc.practitioner_id}"}}
                    ],
                },
            }
        )

    # 5. ClinicalDocumentSnapshots -> DocumentReference + Honest Provenance (INT-003)
    for snap in snaps:
        b64_payload = base64.b64encode(snap.canonical_json.encode("utf-8")).decode("ascii")
        doc_status = "entered-in-error" if snap.status == "entered_in_error" else "current"
        entries.append(
            {
                "fullUrl": f"urn:uuid:{snap.id}",
                "resource": {
                    "resourceType": "DocumentReference",
                    "id": snap.id,
                    "meta": _meta("document-reference"),
                    "extension": [_clinic_ext(clinic_id)],
                    "status": doc_status,
                    "docStatus": "preliminary",
                    "subject": {"reference": f"Patient/{pat.id}"},
                    "context": {"encounter": [{"reference": f"Encounter/{snap.encounter_id}"}]},
                    "content": [
                        {
                            "attachment": {
                                "contentType": "application/json",
                                "data": b64_payload,
                                "hash": snap.canonical_sha256,
                            }
                        }
                    ],
                },
            }
        )
        entries.append(
            {
                "fullUrl": f"urn:uuid:prov-doc-{snap.id}",
                "resource": {
                    "resourceType": "Provenance",
                    "id": f"prov-doc-{snap.id}"[:64],
                    "meta": _meta("provenance"),
                    "extension": [
                        _clinic_ext(clinic_id),
                        {"url": LEGAL_SIG_EXT_URL, "valueBoolean": False},
                    ],
                    "target": [{"reference": f"DocumentReference/{snap.id}"}],
                    "recorded": snap.created_at.replace(tzinfo=timezone.utc).isoformat(),
                    "activity": {
                        "coding": [
                            {
                                "system": "https://denlyra.local/fhir/CodeSystem/seal-status",
                                "code": snap.status,
                            }
                        ]
                    },
                    "agent": [
                        {
                            "who": {
                                "reference": (
                                    f"Practitioner/{snap.signer_staff_id}"
                                    if snap.signer_staff_id
                                    else "Practitioner/unassigned"
                                )
                            }
                        }
                    ],
                },
            }
        )

    return {
        "resourceType": "Bundle",
        "id": f"bundle-{pat.id}",
        "meta": _meta("bundle"),
        "type": "collection",
        "entry": entries,
    }


def _has_htest(meta: dict | None) -> bool:
    if not isinstance(meta, dict):
        return False
    sec = meta.get("security")
    if not isinstance(sec, list):
        return False
    return any(isinstance(s, dict) and s.get("code") == "HTEST" for s in sec)


def validate_fhir_r4_bundle(clinic_id: str, bundle: dict) -> dict:
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise HTTPException(422, "Payload must be an HL7 FHIR R4 Bundle resource")
    if not _has_htest(bundle.get("meta")):
        raise HTTPException(
            422, "FHIR Bundle missing mandatory 'HTEST' security tag for synthetic data"
        )
    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        raise HTTPException(422, "FHIR Bundle must contain a non-empty entry array")

    allowed_types = {
        "Patient",
        "Practitioner",
        "Appointment",
        "Encounter",
        "DocumentReference",
        "Provenance",
    }
    counts: dict[str, int] = {}
    for entry in entries:
        res = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(res, dict):
            raise HTTPException(422, "Invalid entry in FHIR Bundle")
        rtype = res.get("resourceType")
        if rtype not in allowed_types or not res.get("id"):
            raise HTTPException(422, f"Unsupported or incomplete FHIR resourceType: {rtype}")
        if not _has_htest(res.get("meta")):
            raise HTTPException(
                422, f"FHIR {rtype}/{res.get('id')} missing mandatory 'HTEST' security tag"
            )
        counts[rtype] = counts.get(rtype, 0) + 1

        for ext in res.get("extension", []):
            if isinstance(ext, dict) and ext.get("url") == CLINIC_EXT_URL:
                if ext.get("valueString") != clinic_id:
                    raise HTTPException(403, "Cross-clinic resource detected in FHIR Bundle")
            if isinstance(ext, dict) and ext.get("url") == LEGAL_SIG_EXT_URL:
                if ext.get("valueBoolean") is True:
                    raise HTTPException(
                        409,
                        "Unverified legal signature claim in FHIR Provenance rejected (INT-003)",
                    )

        if rtype == "Provenance":
            for sig in res.get("signature", []):
                types = sig.get("type", []) if isinstance(sig, dict) else []
                if any(
                    isinstance(t, dict) and t.get("code") in {"legal_authenticated", "1.2.840.10065.1.12.1.1"}
                    for t in types
                ):
                    raise HTTPException(
                        409,
                        "Forged legal signature entry in FHIR Provenance rejected until real CA provider is approved (INT-003)",
                    )

    return {
        "valid": True,
        "clinic_id": clinic_id,
        "resource_counts": counts,
        "synthetic_only": True,
    }
