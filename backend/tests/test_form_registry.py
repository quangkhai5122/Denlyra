"""T003 synthetic FormRegistry, version immutability, unknown/negative semantics, and clinical review gate tests."""


def test_form_template_quarantined_by_default_and_blocks_self_approval(client):
    payload = {
        "official_code": "16/BV-01",
        "title": "Bệnh án ngoại trú chuyên khoa Răng Hàm Mặt (Synthetic Draft)",
        "schema_version": 1,
        "source_citation": "Circular 32/2023/TT-BYT Appendix XXVIII (unverified synthetic worksheet)",
        "source_sha256": "0" * 64,
        "fields": [
            {
                "field_code": "reason_for_visit",
                "label_vi": "Lý do đến khám",
                "field_type": "text",
                "required_when": "always",
                "allow_unknown": False,
            },
            {
                "field_code": "allergy_history",
                "label_vi": "Tiền sử dị ứng",
                "field_type": "tri_state",
                "required_when": "always",
                "allow_unknown": True,
            },
            {
                "field_code": "dental_findings_summary",
                "label_vi": "Khám chuyên khoa Răng Hàm Mặt",
                "field_type": "text",
                "required_when": "always",
                "allow_unknown": False,
            },
        ],
    }
    created = client.post("/api/v1/clinical-forms/templates", json=payload)
    assert created.status_code == 201, created.text
    tpl = created.json()
    assert tpl["approval_status"] == "quarantined_synthetic_draft"
    assert tpl["clinical_review_blocked"] is True

    # Duplicate (official_code, schema_version) cannot overwrite historical template version (NEG-16)
    dup = client.post("/api/v1/clinical-forms/templates", json=payload)
    assert dup.status_code == 409

    # Registering schema_version=2 preserves schema_version=1
    v2 = client.post(
        "/api/v1/clinical-forms/templates",
        json=dict(payload, schema_version=2, title="16/BV-01 Synthetic Draft v2"),
    )
    assert v2.status_code == 201
    listed = client.get("/api/v1/clinical-forms/templates").json()
    assert [x["schema_version"] for x in listed if x["official_code"] == "16/BV-01"] == [1, 2]

    # Coding agent / API cannot self-approve a clinical template in synthetic mode (NEG-20)
    approve = client.post(f"/api/v1/clinical-forms/templates/{tpl['id']}/approve")
    assert approve.status_code == 409


def test_unknown_vs_negative_vs_missing_semantics_and_export_gate(client, patient, doctor):
    tpl = client.post(
        "/api/v1/clinical-forms/templates",
        json={
            "official_code": "16/BV-01-TEST",
            "title": "Biểu mẫu kiểm thử ngữ nghĩa âm tính/chưa rõ",
            "schema_version": 1,
            "source_citation": "Synthetic fixture",
            "source_sha256": "a" * 64,
            "fields": [
                {
                    "field_code": "reason_for_visit",
                    "label_vi": "Lý do đến khám",
                    "field_type": "text",
                    "required_when": "always",
                    "allow_unknown": False,
                },
                {
                    "field_code": "allergy_history",
                    "label_vi": "Tiền sử dị ứng",
                    "field_type": "tri_state",
                    "required_when": "always",
                    "allow_unknown": True,
                },
            ],
        },
    ).json()

    enc = client.post(
        "/api/v1/encounters",
        json={"patient_id": patient["id"], "practitioner_id": doctor["id"]},
    ).json()

    # Case 1: Omitted allergy_history is reported as missing_required, NEVER coerced to negative (INV-022 / CLIN-12)
    incomplete = client.post(
        "/api/v1/clinical-forms/validate-preview",
        json={
            "template_id": tpl["id"],
            "encounter_id": enc["id"],
            "values": {
                "reason_for_visit": {"state": "present", "value": "Đau răng hàm dưới mô phỏng"},
            },
        },
    )
    assert incomplete.status_code == 200
    body_inc = incomplete.json()
    assert body_inc["complete"] is False
    assert "allergy_history" in body_inc["missing_required_fields"]
    assert body_inc["normalized_values"]["allergy_history"]["state"] == "missing"

    # Case 2: Explicit "unknown" is preserved as "unknown", distinct from "explicit_negative"
    unknown_case = client.post(
        "/api/v1/clinical-forms/validate-preview",
        json={
            "template_id": tpl["id"],
            "encounter_id": enc["id"],
            "values": {
                "reason_for_visit": {"state": "present", "value": "Khám định kỳ mô phỏng"},
                "allergy_history": {"state": "unknown", "value": None},
            },
        },
    )
    assert unknown_case.status_code == 200
    body_unk = unknown_case.json()
    assert body_unk["complete"] is True
    assert body_unk["normalized_values"]["allergy_history"]["state"] == "unknown"
    assert body_unk["synthetic_only"] is True
    assert body_unk["clinical_approval"] is False

    # Case 3: Attempting to finalize/export as an approved legal EMR record fails closed (409)
    assert client.post(
        "/api/v1/clinical-forms/official-export",
        json={"template_id": tpl["id"], "encounter_id": enc["id"]},
    ).status_code == 409
