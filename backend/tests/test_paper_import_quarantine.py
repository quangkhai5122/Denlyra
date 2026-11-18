"""T006 negative and acceptance tests: Paper scan quarantine, missing page block, duplicate candidate review, legacy provenance, and batch rollback."""


def test_paper_import_missing_page_duplicate_review_legacy_provenance_and_rollback(client):
    # Create an existing patient in the clinic to test duplicate name/phone collision (PAT-005 / DR-02)
    existing = client.post(
        "/api/v1/patients",
        json={
            "display_name": "Nguyễn Văn Mẫu Demo",
            "birth_year": 1985,
            "phone_demo": "0901112222",
        },
    ).json()

    batch = client.post(
        "/api/v1/migrations/paper-batches",
        json={"source_cabinet": "Tủ hồ sơ giấy năm 2024 - Phòng khám Demo A", "expected_item_count": 2},
    )
    assert batch.status_code == 201, batch.text
    batch_id = batch.json()["id"]

    # 1. Item 1: Missing page 3 of 5 -> quarantined as incomplete_missing_pages (NEG-10 / DR-01)
    incomplete_item = client.post(
        f"/api/v1/migrations/paper-batches/{batch_id}/items",
        json={
            "legacy_folder_id": "PAPER-2024-001",
            "patient_display_name": "Trần Thị Thiếu Trang Demo",
            "birth_year": 1991,
            "expected_page_count": 5,
            "pages": [
                {"page_number": 1, "sha256": "1" * 64, "legible": True},
                {"page_number": 2, "sha256": "2" * 64, "legible": True},
                # page 3 is missing!
                {"page_number": 4, "sha256": "4" * 64, "legible": True},
                {"page_number": 5, "sha256": "5" * 64, "legible": True},
            ],
        },
    )
    assert incomplete_item.status_code == 201, incomplete_item.text
    inc_body = incomplete_item.json()
    assert inc_body["completeness_status"] == "incomplete_missing_pages"
    assert inc_body["missing_pages"] == [3]

    # Operator CANNOT mark an incomplete paper scan as verified/linked (NEG-10 -> 409)
    assert client.post(
        f"/api/v1/migrations/paper-items/{inc_body['id']}/verify-link",
        json={
            "resolution_mode": "create_distinct_patient",
            "reviewer_note": "Cố tình duyệt hồ sơ thiếu trang",
        },
    ).status_code == 409

    # 2. Item 2: Complete 3/3 pages, but shares name & phone with existing patient -> flagged needs_human_identity_review (DR-02)
    dup_item = client.post(
        f"/api/v1/migrations/paper-batches/{batch_id}/items",
        json={
            "legacy_folder_id": "PAPER-2024-002",
            "patient_display_name": "Nguyễn Văn Mẫu Demo",
            "birth_year": 1985,
            "phone_demo": "0901112222",
            "expected_page_count": 3,
            "pages": [
                {"page_number": 1, "sha256": "a" * 64, "legible": True, "ocr_unverified_text": "Khám răng 36 sâu ngà demo"},
                {"page_number": 2, "sha256": "b" * 64, "legible": True},
                {"page_number": 3, "sha256": "c" * 64, "legible": True},
            ],
        },
    )
    assert dup_item.status_code == 201, dup_item.text
    dup_body = dup_item.json()
    assert dup_body["completeness_status"] == "complete"
    assert dup_body["match_status"] == "needs_human_identity_review"
    assert existing["id"] in dup_body["candidate_patient_ids"]

    # Attempting to claim digital signature on a legacy paper scan is strictly forbidden (DR-03 / MIG-007 -> 409)
    assert client.post(
        f"/api/v1/migrations/paper-items/{dup_body['id']}/verify-link",
        json={
            "resolution_mode": "link_existing_patient",
            "target_patient_id": existing["id"],
            "reviewer_note": "Xác nhận đúng bệnh nhân",
            "claim_digitally_signed": True,
        },
    ).status_code == 409

    # Human reviewer explicitly resolves collision to create a distinct patient (e.g. relative sharing phone)
    verified = client.post(
        f"/api/v1/migrations/paper-items/{dup_body['id']}/verify-link",
        json={
            "resolution_mode": "create_distinct_patient",
            "reviewer_note": "Hai người cùng tên/dùng chung số điện thoại gia đình; tách hồ sơ riêng",
        },
    )
    assert verified.status_code == 200, verified.text
    v_body = verified.json()
    assert v_body["status"] == "verified_legacy_archive"
    assert v_body["provenance_source"] == "legacy_scan"
    assert v_body["digital_signature_status"] == "not_digitally_signed_legacy_paper"
    assert v_body["linked_patient_id"] != existing["id"]

    # Check batch reconciliation report (MIG-008)
    recon = client.get(f"/api/v1/migrations/paper-batches/{batch_id}/reconciliation").json()
    assert recon["submitted_count"] == 2
    assert recon["incomplete_quarantined_count"] == 1
    assert recon["verified_legacy_archive_count"] == 1

    # Rollback batch safely reverses batch-created archive links while preserving original native patient
    rb = client.post(
        f"/api/v1/migrations/paper-batches/{batch_id}/rollback",
        json={"reason": "Diễn tập rollback lô nhập hồ sơ giấy demo"},
    )
    assert rb.status_code == 200
    assert rb.json()["status"] == "rolled_back"
    # Existing native patient remains untouched
    assert client.get(f"/api/v1/patients/{existing['id']}").status_code == 200
