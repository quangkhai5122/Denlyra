"""T004 synthetic SignatureProvider adapter, canonical document snapshot, addendum, and negative tests."""
from fastapi.testclient import TestClient
import pytest

from denlyra.api import create_app
from denlyra.config import Settings


@pytest.fixture
def signed_doc_client(tmp_path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'sig-demo.db'}",
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as c:
        yield c


def mint(client: TestClient, clinic_id: str, role: str) -> dict:
    res = client.post("/api/v1/auth/token", json={"clinic_id": clinic_id, "role": role})
    assert res.status_code == 201
    return res.json()


def test_signature_negative_cases_timeout_mismatch_stale_role_and_legal_gate(signed_doc_client):
    clinic_id = "11111111-1111-4111-8111-111111111111"
    dentist = mint(signed_doc_client, clinic_id, "dentist")
    recep = mint(signed_doc_client, clinic_id, "receptionist")
    owner = mint(signed_doc_client, clinic_id, "clinic_owner")

    h_dentist = {"Authorization": f"Bearer {dentist['access_token']}"}
    h_recep = {"Authorization": f"Bearer {recep['access_token']}"}
    h_owner = {"Authorization": f"Bearer {owner['access_token']}"}

    pat = signed_doc_client.post(
        "/api/v1/patients", json={"display_name": "Bệnh nhân Ký Giả Lập"}, headers=h_dentist
    ).json()
    enc = signed_doc_client.post(
        "/api/v1/encounters",
        json={"patient_id": pat["id"], "practitioner_id": dentist["staff_id"]},
        headers=h_dentist,
    ).json()
    note = signed_doc_client.post(
        f"/api/v1/encounters/{enc['id']}/notes",
        json={"content": "Bản ghi lâm sàng gốc chuẩn bị đóng gói snapshot."},
        headers=h_dentist,
    ).json()

    # Prepare canonical snapshot envelope
    snap = signed_doc_client.post(
        "/api/v1/clinical-documents/snapshots",
        json={"note_id": note["id"], "expected_revision": 1},
        headers=h_dentist,
    )
    assert snap.status_code == 201, snap.text
    snap_body = snap.json()
    snap_id = snap_body["id"]
    assert snap_body["status"] == "ready_for_signature"

    # 1. Receptionist cannot sign clinical document snapshot (403)
    assert signed_doc_client.post(
        f"/api/v1/clinical-documents/{snap_id}/sign-synthetic",
        json={"expected_sha256": snap_body["canonical_sha256"]},
        headers=h_recep,
    ).status_code == 403

    # 2. Requesting real legal 'authenticated' status fails closed with 409 (NEEDS_CLINICAL_REVIEW.md gate)
    assert signed_doc_client.post(
        f"/api/v1/clinical-documents/{snap_id}/sign-synthetic",
        json={
            "expected_sha256": snap_body["canonical_sha256"],
            "mode": "legal_authenticated",
        },
        headers=h_dentist,
    ).status_code == 409

    # 3. Altered content / digest mismatch fails closed (NEG-03 -> 409)
    assert signed_doc_client.post(
        f"/api/v1/clinical-documents/{snap_id}/sign-synthetic",
        json={"expected_sha256": "f" * 64},
        headers=h_dentist,
    ).status_code == 409

    # 4. Provider timeout leaves document unsealed in ready_for_signature (NEG-14 / DR-07 -> 503)
    timeout_res = signed_doc_client.post(
        f"/api/v1/clinical-documents/{snap_id}/sign-synthetic",
        json={
            "expected_sha256": snap_body["canonical_sha256"],
            "simulate_failure": "timeout",
        },
        headers=h_dentist,
    )
    assert timeout_res.status_code == 503
    assert (
        signed_doc_client.get(f"/api/v1/clinical-documents/{snap_id}", headers=h_dentist)
        .json()["status"]
        == "ready_for_signature"
    )

    # 5. Provider signature mismatch rejected (409) and remains unsealed
    assert signed_doc_client.post(
        f"/api/v1/clinical-documents/{snap_id}/sign-synthetic",
        json={
            "expected_sha256": snap_body["canonical_sha256"],
            "simulate_failure": "signature_mismatch",
        },
        headers=h_dentist,
    ).status_code == 409

    # 6. Concurrent note revision invalidates stale snapshot signing (409)
    signed_doc_client.put(
        f"/api/v1/notes/{note['id']}",
        json={"content": "Bản ghi đã cập nhật lên revision 2.", "expected_revision": 1},
        headers=h_dentist,
    )
    assert signed_doc_client.post(
        f"/api/v1/clinical-documents/{snap_id}/sign-synthetic",
        json={"expected_sha256": snap_body["canonical_sha256"]},
        headers=h_dentist,
    ).status_code == 409

    # 7. Create fresh snapshot for revision 2, seal with synthetic double, verify bit-for-bit retention
    snap2 = signed_doc_client.post(
        "/api/v1/clinical-documents/snapshots",
        json={"note_id": note["id"], "expected_revision": 2},
        headers=h_dentist,
    ).json()
    sealed = signed_doc_client.post(
        f"/api/v1/clinical-documents/{snap2['id']}/sign-synthetic",
        json={"expected_sha256": snap2["canonical_sha256"]},
        headers=h_dentist,
    )
    assert sealed.status_code == 200, sealed.text
    sealed_body = sealed.json()
    assert sealed_body["status"] == "synthetic_signed_NOT_legal"
    assert sealed_body["legal_signature_valid"] is False

    # Verify cryptographic receipt and manifest integrity
    verified = signed_doc_client.get(
        f"/api/v1/clinical-documents/{snap2['id']}/verify", headers=h_dentist
    )
    assert verified.status_code == 200
    assert verified.json()["integrity_verified"] is True

    # 8. Create linked addendum snapshot without altering original sealed bytes
    addendum = signed_doc_client.post(
        f"/api/v1/clinical-documents/{snap2['id']}/addenda",
        json={
            "content": "Bổ sung thông tin sau kiểm tra lại phim X-quang demo.",
            "amendment_reason": "Bổ sung mô tả lâm sàng mô phỏng",
        },
        headers=h_dentist,
    )
    assert addendum.status_code == 201, addendum.text
    assert addendum.json()["parent_snapshot_id"] == snap2["id"]
    orig_after_addendum = signed_doc_client.get(
        f"/api/v1/clinical-documents/{snap2['id']}", headers=h_dentist
    ).json()
    assert orig_after_addendum["canonical_sha256"] == snap2["canonical_sha256"]
    assert orig_after_addendum["canonical_json"] == snap2["canonical_json"]

    # 9. Mark addendum entered_in_error requires non-empty reason and preserves original bytes
    add_id = addendum.json()["id"]
    assert signed_doc_client.post(
        f"/api/v1/clinical-documents/{add_id}/enter-in-error",
        json={"reason": ""},
        headers=h_dentist,
    ).status_code == 422
    voided = signed_doc_client.post(
        f"/api/v1/clinical-documents/{add_id}/enter-in-error",
        json={"reason": "Nhập nhầm lượt khám giả lập"},
        headers=h_dentist,
    )
    assert voided.status_code == 200
    assert voided.json()["status"] == "entered_in_error"
    assert voided.json()["canonical_sha256"] == addendum.json()["canonical_sha256"]

    # 10. Deactivated dentist cannot sign any new snapshot (NEG-15 / CLIN-08)
    signed_doc_client.post(f"/api/v1/staff/{dentist['staff_id']}/deactivate", headers=h_owner)
    assert signed_doc_client.post(
        f"/api/v1/clinical-documents/{add_id}/sign-synthetic",
        json={"expected_sha256": addendum.json()["canonical_sha256"]},
        headers=h_dentist,
    ).status_code == 401
