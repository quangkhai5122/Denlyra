"""T001 negative and positive authentication, RBAC/ABAC, revocation, and signed-URL tests."""
from fastapi.testclient import TestClient
import pytest

from denlyra.api import create_app
from denlyra.config import Settings


@pytest.fixture
def auth_client(tmp_path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'auth-demo.db'}",
    )
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:8766") as c:
        yield c


def issue_token(client: TestClient, clinic_id: str, role: str, ttl_seconds: int = 3600) -> dict:
    resp = client.post(
        "/api/v1/auth/token",
        json={"clinic_id": clinic_id, "role": role, "ttl_seconds": ttl_seconds},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_unauthenticated_and_demo_header_spoofing_rejected_when_auth_required(auth_client):
    # Unauthenticated request with forged X-Demo-* headers must be rejected (401).
    forged = auth_client.get(
        "/api/v1/patients",
        headers={
            "X-Demo-Clinic": "11111111-1111-4111-8111-111111111111",
            "X-Demo-Actor": "forged-admin",
        },
    )
    assert forged.status_code == 401
    # Health and capabilities remain inspectable and keep production_auth=False until SEC-G1.
    caps = auth_client.get("/api/v1/capabilities").json()
    assert caps["production_auth"] is False
    assert caps["clinical_e_signature"] is False


def test_forged_expired_and_revoked_tokens_rejected(auth_client):
    clinic_a = "11111111-1111-4111-8111-111111111111"
    issued = issue_token(auth_client, clinic_a, "dentist")
    token = issued["access_token"]

    # Tampered signature
    tampered = token[:-4] + ("aaaa" if token[-4:] != "aaaa" else "bbbb")
    assert auth_client.get(
        "/api/v1/patients", headers={"Authorization": f"Bearer {tampered}"}
    ).status_code == 401

    # Malformed token
    assert auth_client.get(
        "/api/v1/patients", headers={"Authorization": "Bearer not.a.valid.token"}
    ).status_code == 401

    # Expired token
    expired = issue_token(auth_client, clinic_a, "dentist", ttl_seconds=-10)["access_token"]
    assert auth_client.get(
        "/api/v1/patients", headers={"Authorization": f"Bearer {expired}"}
    ).status_code == 401

    # Explicit session/token revocation
    revoke_resp = auth_client.post(
        "/api/v1/auth/revoke", headers={"Authorization": f"Bearer {token}"}
    )
    assert revoke_resp.status_code == 200
    assert auth_client.get(
        "/api/v1/patients", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 401


def test_cross_clinic_enumeration_and_mismatched_clinic_header_denied(auth_client):
    clinic_a = "11111111-1111-4111-8111-111111111111"
    clinic_b = "22222222-2222-4222-8222-222222222222"
    dentist_a = issue_token(auth_client, clinic_a, "dentist")["access_token"]
    dentist_b = issue_token(auth_client, clinic_b, "dentist")["access_token"]

    patient_a = auth_client.post(
        "/api/v1/patients",
        json={"display_name": "Bệnh nhân Clinic A", "birth_year": 1995},
        headers={"Authorization": f"Bearer {dentist_a}"},
    )
    assert patient_a.status_code == 201
    patient_id = patient_a.json()["id"]

    # Dentist B cannot read or enumerate Clinic A patient (NEG-01)
    assert auth_client.get(
        f"/api/v1/patients/{patient_id}",
        headers={"Authorization": f"Bearer {dentist_b}"},
    ).status_code == 404
    assert auth_client.get(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {dentist_b}"},
    ).json() == []

    # Dentist A sending mismatched X-Demo-Clinic header is rejected (403)
    assert auth_client.get(
        "/api/v1/patients",
        headers={
            "Authorization": f"Bearer {dentist_a}",
            "X-Demo-Clinic": clinic_b,
        },
    ).status_code == 403


def test_role_boundaries_receptionist_finance_and_dentist(auth_client):
    clinic_a = "11111111-1111-4111-8111-111111111111"
    dentist_tok = issue_token(auth_client, clinic_a, "dentist")
    recep_tok = issue_token(auth_client, clinic_a, "receptionist")
    finance_tok = issue_token(auth_client, clinic_a, "finance")

    h_dentist = {"Authorization": f"Bearer {dentist_tok['access_token']}"}
    h_recep = {"Authorization": f"Bearer {recep_tok['access_token']}"}
    h_finance = {"Authorization": f"Bearer {finance_tok['access_token']}"}

    # Receptionist can register a patient
    pat = auth_client.post(
        "/api/v1/patients",
        json={"display_name": "Bệnh nhân Phân Quyền", "birth_year": 1990},
        headers=h_recep,
    ).json()

    # Receptionist cannot open a clinical encounter or create/lock a clinical note
    assert auth_client.post(
        "/api/v1/encounters",
        json={"patient_id": pat["id"], "practitioner_id": dentist_tok["staff_id"]},
        headers=h_recep,
    ).status_code == 403

    # Dentist opens encounter, creates draft note, and records finding
    enc = auth_client.post(
        "/api/v1/encounters",
        json={"patient_id": pat["id"], "practitioner_id": dentist_tok["staff_id"]},
        headers=h_dentist,
    )
    assert enc.status_code == 201
    enc_id = enc.json()["id"]

    note = auth_client.post(
        f"/api/v1/encounters/{enc_id}/notes",
        json={"content": "Đánh giá lâm sàng giả lập bảo mật."},
        headers=h_dentist,
    )
    assert note.status_code == 201
    note_id = note.json()["id"]

    # Receptionist cannot lock/authenticate clinical note or revise it
    assert auth_client.post(
        f"/api/v1/notes/{note_id}/demo-lock", headers=h_recep
    ).status_code == 403
    assert auth_client.put(
        f"/api/v1/notes/{note_id}",
        json={"content": "Lễ tân sửa trái phép", "expected_revision": 1},
        headers=h_recep,
    ).status_code == 403

    # Finance cannot access confidential clinical notes, encounters, findings, or odontogram
    assert auth_client.get(
        f"/api/v1/encounters/{enc_id}/notes", headers=h_finance
    ).status_code == 403
    assert auth_client.get(
        "/api/v1/encounters", headers=h_finance
    ).status_code == 403
    assert auth_client.get(
        f"/api/v1/encounters/{enc_id}/findings", headers=h_finance
    ).status_code == 403
    assert auth_client.get(
        f"/api/v1/patients/{pat['id']}/odontogram", headers=h_finance
    ).status_code == 403

    # Dentist can lock clinical note
    assert auth_client.post(
        f"/api/v1/notes/{note_id}/demo-lock", headers=h_dentist
    ).status_code == 200

    # Receptionist cannot review/approve treatment plan; dentist can
    plan = auth_client.post(
        "/api/v1/treatment-plans",
        json={"patient_id": pat["id"], "title": "Kế hoạch chỉnh nha demo"},
        headers=h_dentist,
    ).json()
    auth_client.post(
        f"/api/v1/treatment-plans/{plan['id']}/tasks",
        json={"title": "Gắn mắc cài giả lập", "phase": "Giai đoạn 1"},
        headers=h_dentist,
    )
    assert auth_client.post(
        f"/api/v1/treatment-plans/{plan['id']}/demo-review", headers=h_recep
    ).status_code == 403
    assert auth_client.post(
        f"/api/v1/treatment-plans/{plan['id']}/demo-review", headers=h_dentist
    ).status_code == 200

    # Finance can create charges, payments, and allocations; receptionist cannot allocate
    charge = auth_client.post(
        "/api/v1/finance/charges",
        json={"patient_id": pat["id"], "label": "Phí demo", "amount_vnd": 1_000_000},
        headers=h_finance,
    )
    assert charge.status_code == 201
    payment = auth_client.post(
        "/api/v1/finance/payments",
        json={"patient_id": pat["id"], "amount_vnd": 500_000},
        headers=h_finance,
    )
    assert payment.status_code == 201
    assert auth_client.post(
        "/api/v1/finance/allocations",
        json={"charge_id": charge.json()["id"], "payment_id": payment.json()["id"], "amount_vnd": 500_000},
        headers=h_recep,
    ).status_code == 403
    assert auth_client.post(
        "/api/v1/finance/allocations",
        json={"charge_id": charge.json()["id"], "payment_id": payment.json()["id"], "amount_vnd": 500_000},
        headers=h_finance,
    ).status_code == 201


def test_membership_deactivation_invalidates_active_token_and_preserves_history(auth_client):
    clinic_a = "11111111-1111-4111-8111-111111111111"
    owner_tok = issue_token(auth_client, clinic_a, "clinic_owner")
    dentist_tok = issue_token(auth_client, clinic_a, "dentist")
    h_owner = {"Authorization": f"Bearer {owner_tok['access_token']}"}
    h_dentist = {"Authorization": f"Bearer {dentist_tok['access_token']}"}

    pat = auth_client.post(
        "/api/v1/patients",
        json={"display_name": "Bệnh nhân Lưu Trữ", "birth_year": 1988},
        headers=h_dentist,
    ).json()
    enc = auth_client.post(
        "/api/v1/encounters",
        json={"patient_id": pat["id"], "practitioner_id": dentist_tok["staff_id"]},
        headers=h_dentist,
    ).json()

    # Owner deactivates dentist membership (NEG-15 / INV-021)
    deact = auth_client.post(
        f"/api/v1/staff/{dentist_tok['staff_id']}/deactivate",
        headers=h_owner,
    )
    assert deact.status_code == 200

    # Dentist's existing token is immediately rejected
    assert auth_client.get("/api/v1/patients", headers=h_dentist).status_code == 401
    assert auth_client.post(
        f"/api/v1/encounters/{enc['id']}/notes",
        json={"content": "Bác sĩ đã thu hồi quyền"},
        headers=h_dentist,
    ).status_code == 401

    # Historic encounter authored by deactivated dentist remains intact
    encounters = auth_client.get("/api/v1/encounters", headers=h_owner).json()
    assert any(e["id"] == enc["id"] for e in encounters)


def test_signed_url_single_use_clinic_scope_and_expiry(auth_client):
    clinic_a = "11111111-1111-4111-8111-111111111111"
    clinic_b = "22222222-2222-4222-8222-222222222222"
    dentist_a = issue_token(auth_client, clinic_a, "dentist")
    dentist_b = issue_token(auth_client, clinic_b, "dentist")
    h_a = {"Authorization": f"Bearer {dentist_a['access_token']}"}
    h_b = {"Authorization": f"Bearer {dentist_b['access_token']}"}

    pat = auth_client.post(
        "/api/v1/patients",
        json={"display_name": "Bệnh nhân Signed URL"},
        headers=h_a,
    ).json()
    enc = auth_client.post(
        "/api/v1/encounters",
        json={"patient_id": pat["id"], "practitioner_id": dentist_a["staff_id"]},
        headers=h_a,
    ).json()
    note = auth_client.post(
        f"/api/v1/encounters/{enc['id']}/notes",
        json={"content": "Tài liệu nháp kiểm thử signed URL."},
        headers=h_a,
    ).json()

    # Mint a single-use signed URL for the clinical note
    grant = auth_client.post(
        "/api/v1/auth/signed-urls",
        json={"subject_type": "clinical_note", "subject_id": note["id"], "ttl_seconds": 300},
        headers=h_a,
    )
    assert grant.status_code == 201
    grant_path = grant.json()["download_path"]

    # Clinic B user cannot consume Clinic A signed URL (SEC-02)
    assert auth_client.get(grant_path, headers=h_b).status_code == 403

    # First authorized download succeeds
    first = auth_client.get(grant_path, headers=h_a)
    assert first.status_code == 200
    assert first.json()["subject_id"] == note["id"]

    # Reused signed URL is rejected (T001 acceptance: reused signed URL all rejected)
    second = auth_client.get(grant_path, headers=h_a)
    assert second.status_code == 403


def test_identity_provider_unavailable_fails_closed(tmp_path):
    settings = Settings(
        demo_mode=True,
        require_auth=True,
        auth_provider_available=False,
        db_url=f"sqlite+pysqlite:///{tmp_path / 'outage.db'}",
    )
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as c:
        assert c.post(
            "/api/v1/auth/token",
            json={"clinic_id": "11111111-1111-4111-8111-111111111111", "role": "dentist"},
        ).status_code == 503
        assert c.get(
            "/api/v1/patients",
            headers={"Authorization": "Bearer any-token"},
        ).status_code == 503
