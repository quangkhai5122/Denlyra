"""T019 clinician-reviewed odontogram legend without silent history remapping (ODN-006),
optimistic tooth restoration/prosthesis revisions & structured print/export (ODN-007, ODN-008, ODN-010),
reviewed external referrals (EMR-013), non-destructive document eligibility flags (PAT-010),
and structured clinical archive export with attachment digests (EMR-014).

Written BEFORE T019 domain/API implementation per AGENTS.md negative-test-first rule.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

CLINIC_A = "11111111-1111-4111-8111-111111111111"


def _headers(client: TestClient, role: str, clinic_id: str = CLINIC_A) -> dict[str, str]:
    resp = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}", "X-Demo-Clinic": clinic_id}


def test_optimistic_odontogram_restoration_revisions_legend_versioning_and_export(tmp_path: Path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'odn_rev.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Phục hình Sơ đồ Răng & Xung đột Phiên bản", "birth_year": 1989},
        ).json()["id"]

        # Negative 1 (ODN-006): Receptionist cannot publish odontogram legend -> 403
        assert (
            client.post(
                "/api/v1/odontogram/legend",
                headers=receptionist,
                json={
                    "code": "CROWN-ZIR",
                    "label_vi": "Mão sứ Zirconia v1",
                    "symbol_code": "ZR",
                    "category": "prosthesis",
                },
            ).status_code
            == 403
        )

        leg_v1 = client.post(
            "/api/v1/odontogram/legend",
            headers=dentist,
            json={
                "code": "CROWN-ZIR",
                "label_vi": "Mão sứ Zirconia toàn phần (v1)",
                "symbol_code": "ZR1",
                "category": "prosthesis",
            },
        )
        assert leg_v1.status_code == 201, leg_v1.text
        assert leg_v1.json()["version_number"] == 1

        # Record initial tooth 16 restoration state (expected_revision=0 -> revision 1, ODN-007)
        r1 = client.put(
            f"/api/v1/patients/{pat_id}/odontogram/restorations/16",
            headers=dentist,
            json={
                "expected_revision": 0,
                "legend_code": "CROWN-ZIR",
                "surface": "ALL",
                "material_note": "Mão sứ Zirconia làm tại cơ sở trước",
                "source_kind": "existing_external_reported",
                "documented_date": "2024-08-10",
                "evidence_note": "Ghi nhận qua khám lâm sàng và phim quanh chóp",
            },
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["current_revision_no"] == 1
        assert r1.json()["latest_legend_version_number"] == 1

        # Negative 2 (ODN-010): Concurrent stale edit with expected_revision=0 -> 409 (no silent last-write-wins!)
        stale = client.put(
            f"/api/v1/patients/{pat_id}/odontogram/restorations/16",
            headers=dentist,
            json={
                "expected_revision": 0,
                "legend_code": "CROWN-ZIR",
                "surface": "ALL",
                "material_note": "Ghi đè nhầm phiên bản cũ",
                "source_kind": "existing_external_reported",
                "documented_date": "2024-08-10",
                "evidence_note": "Xung đột đồng thời",
            },
        )
        assert stale.status_code == 409

        # Publish legend v2 -> historical revision 1 MUST keep legend_version_number=1 (ODN-006)
        leg_v2 = client.post(
            "/api/v1/odontogram/legend",
            headers=dentist,
            json={
                "code": "CROWN-ZIR",
                "label_vi": "Mão sứ Zirconia đa lớp thẩm mỹ (v2)",
                "symbol_code": "ZR2",
                "category": "prosthesis",
            },
        )
        assert leg_v2.status_code == 201
        assert leg_v2.json()["version_number"] == 2

        # Valid optimistic revision expected_revision=1 -> revision 2 using legend v2
        r2 = client.put(
            f"/api/v1/patients/{pat_id}/odontogram/restorations/16",
            headers=dentist,
            json={
                "expected_revision": 1,
                "legend_code": "CROWN-ZIR",
                "surface": "ALL",
                "material_note": "Thay mão sứ Zirconia đa lớp mới khít sát bờ viền",
                "source_kind": "performed_in_clinic_demo",
                "documented_date": "2026-11-24",
                "evidence_note": "Kiểm tra khít sát hoàn tất sau gắn",
            },
        )
        assert r2.status_code == 200
        assert r2.json()["current_revision_no"] == 2
        assert r2.json()["latest_legend_version_number"] == 2

        # Deterministic odontogram print/export reconciles full timeline + preserved v1/v2 legend history (ODN-008)
        exp = client.get(f"/api/v1/patients/{pat_id}/odontogram/export", headers=dentist)
        assert exp.status_code == 200
        eb = exp.json()
        assert eb["certified_clinical_print"] is False
        assert len(eb["export_sha256"]) == 64
        tooth_16 = next(x for x in eb["restorations"] if x["tooth_code"] == "16")
        assert tooth_16["current_revision_no"] == 2
        assert [h["legend_version_number"] for h in tooth_16["revisions"]] == [1, 2]


def test_reviewed_external_referrals_eligibility_flags_and_structured_clinical_export(
    tmp_path: Path,
):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'ref_export.db'}",
        archive_dir=str(tmp_path / "archive"),
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
        dentist = _headers(client, "dentist")
        receptionist = _headers(client, "receptionist")
        ctx = client.get("/api/v1/demo/context", headers=receptionist).json()
        doc_id = next(s["id"] for s in ctx["staff"] if s["role"] == "dentist")

        pat_id = client.post(
            "/api/v1/patients",
            headers=receptionist,
            json={"display_name": "BN Chuyển tuyến Ngoài & Xuất Hồ sơ Cấu trúc", "birth_year": 1984},
        ).json()["id"]

        # EMR-013: Receptionist registers external referral in quarantined_unreviewed; cannot clinically review -> 403
        raw_ref = b"Giay chuyen tuyen RHM benh vien tuyen truoc (synthetic)"
        ref = client.post(
            f"/api/v1/patients/{pat_id}/referrals",
            headers=receptionist,
            json={
                "origin_facility_name": "Khoa RHM Bệnh viện Đa khoa Giả lập",
                "referring_clinician_name": "BS. Lê Hoàng Nam (Giả lập)",
                "referral_date": "2026-11-20",
                "document_summary_vi": "Chuyển khám chuyên sâu răng khôn 48 mọc lệch",
                "content_sha256": hashlib.sha256(raw_ref).hexdigest(),
            },
        )
        assert ref.status_code == 201, ref.text
        ref_id = ref.json()["id"]
        assert ref.json()["review_status"] == "quarantined_unreviewed"

        assert (
            client.post(
                f"/api/v1/referrals/{ref_id}/review",
                headers=receptionist,
                json={"review_note": "Lễ tân cố duyệt lâm sàng"},
            ).status_code
            == 403
        )
        rev_ok = client.post(
            f"/api/v1/referrals/{ref_id}/review",
            headers=dentist,
            json={"review_note": "Đã đối chiếu giấy chuyển tuyến và phim kèm theo"},
        )
        assert rev_ok.status_code == 200
        assert rev_ok.json()["review_status"] == "clinician_reviewed"

        # EMR-014: Prepare snapshot -> unsigned structured export rejected (409)
        enc_id = client.post(
            "/api/v1/encounters",
            headers=dentist,
            json={"patient_id": pat_id, "practitioner_id": doc_id},
        ).json()["id"]
        note_id = client.post(
            f"/api/v1/encounters/{enc_id}/notes",
            headers=dentist,
            json={"content": "Tiếp nhận ca chuyển tuyến răng 48, đánh giá tương quan ống thần kinh."},
        ).json()["id"]
        client.post(f"/api/v1/notes/{note_id}/demo-lock", headers=dentist)
        snap = client.post(
            "/api/v1/clinical-documents/snapshots",
            headers=dentist,
            json={"note_id": note_id, "expected_revision": 1},
        ).json()
        orig_sha = snap["canonical_sha256"]

        assert (
            client.get(
                f"/api/v1/clinical-documents/{snap['id']}/structured-export", headers=dentist
            ).status_code
            == 409
        )

        # Sign synthetic snapshot + attach encrypted clinical photo -> structured export binds exact digests
        client.post(
            f"/api/v1/clinical-documents/{snap['id']}/sign-synthetic",
            headers=dentist,
            json={"expected_sha256": orig_sha},
        )
        att = client.post(
            "/api/v1/archive/objects",
            headers=dentist,
            json={
                "patient_id": pat_id,
                "encounter_id": enc_id,
                "snapshot_id": snap["id"],
                "object_kind": "clinical_attachment",
                "media_type": "image/png",
                "original_filename": "panoramic_48_synthetic.png",
                "content_b64": base64.b64encode(b"SYNTHETIC_PANO_BYTES_48").decode("ascii"),
            },
        ).json()

        pkg = client.get(
            f"/api/v1/clinical-documents/{snap['id']}/structured-export", headers=dentist
        )
        assert pkg.status_code == 200, pkg.text
        pb = pkg.json()
        assert pb["legally_certified_pdf"] is False
        assert pb["snapshot"]["canonical_sha256"] == orig_sha
        assert any(
            a["id"] == att["id"] and a["plaintext_sha256"] == att["plaintext_sha256"]
            for a in pb["attachment_manifest"]
        )

        # PAT-010: Document eligibility flags missing consent/allergy review WITHOUT altering signed snapshot!
        elig_missing = client.get(
            f"/api/v1/patients/{pat_id}/document-eligibility", headers=receptionist
        ).json()
        assert elig_missing["eligible_for_elective_procedure"] is False
        assert "missing_active_treatment_consent" in elig_missing["flags"]

        # Grant treatment consent + medical risk review -> becomes eligible; withdraw consent -> flagged again,
        # while signed snapshot canonical_sha256 stays bit-for-bit identical!
        c_id = client.post(
            "/api/v1/consents",
            headers=receptionist,
            json={
                "patient_id": pat_id,
                "purpose": "treatment",
                "template_version": "CONSENT-2026-V1",
                "disclosure_summary": "Đồng thuận khám và điều trị phẫu thuật miệng",
                "signer_name": "BN Chuyển tuyến",
                "signer_relationship": "self",
            },
        ).json()["id"]
        client.post(
            f"/api/v1/patients/{pat_id}/medical-risk-reviews",
            headers=dentist,
            json={
                "encounter_id": enc_id,
                "drug_allergy_state": "explicit_negative",
                "bleeding_anticoagulant_state": "explicit_negative",
                "source": "clinician_review_demo",
            },
        )
        elig_ok = client.get(
            f"/api/v1/patients/{pat_id}/document-eligibility", headers=receptionist
        ).json()
        assert elig_ok["eligible_for_elective_procedure"] is True

        client.post(
            f"/api/v1/consents/{c_id}/withdraw",
            headers=receptionist,
            json={"reason": "Tạm hoãn phẫu thuật theo yêu cầu cá nhân"},
        )
        elig_withdrawn = client.get(
            f"/api/v1/patients/{pat_id}/document-eligibility", headers=receptionist
        ).json()
        assert elig_withdrawn["eligible_for_elective_procedure"] is False
        assert (
            client.get(f"/api/v1/clinical-documents/{snap['id']}", headers=dentist).json()[
                "canonical_sha256"
            ]
            == orig_sha
        )
