
def create_encounter(client, patient, doctor):
    res = client.post("/api/v1/encounters", json={"patient_id": patient["id"],
                                                     "practitioner_id": doctor["id"]})
    assert res.status_code == 201, res.text
    return res.json()


def test_note_revision_lock_addendum_and_preserved_history(client, patient, doctor):
    encounter = create_encounter(client, patient, doctor)
    url = f"/api/v1/encounters/{encounter['id']}/notes"
    note = client.post(url, json={"content": "Bản nháp giả lập lần 1."}).json()
    updated = client.put(f"/api/v1/notes/{note['id']}", json={
        "content": "Bản nháp giả lập lần 2.", "expected_revision": 1})
    assert updated.status_code == 200
    assert updated.json()["latest_revision"] == 2
    stale = client.put(f"/api/v1/notes/{note['id']}", json={
        "content": "Sửa cũ", "expected_revision": 1})
    assert stale.status_code == 409
    locked = client.post(f"/api/v1/notes/{note['id']}/demo-lock")
    assert locked.status_code == 200
    assert locked.json()["status"] == "demo_locked"
    assert len(locked.json()["locked_digest"]) == 64
    assert client.put(f"/api/v1/notes/{note['id']}", json={
        "content": "Không được sửa", "expected_revision": 2}).status_code == 409
    added = client.post(url, json={"content": "Bản đính chính riêng chỉ để demo.",
                                      "parent_note_id": note["id"]})
    assert added.status_code == 201
    versions = client.get(url).json()
    original = next(x for x in versions if x["id"] == note["id"])
    assert [r["revision_no"] for r in original["revisions"]] == [1, 2]
    assert original["revisions"][0]["content"] == "Bản nháp giả lập lần 1."
    assert len(versions) == 2


def test_cannot_attach_addendum_to_unlocked_or_other_clinic_note(client, patient, doctor, context):
    e = create_encounter(client, patient, doctor)
    u = f"/api/v1/encounters/{e['id']}/notes"
    first = client.post(u, json={"content": "Bản nháp chưa khóa"}).json()
    assert client.post(u, json={"content": "Đính chính không hợp lệ",
                                "parent_note_id": first["id"]}).status_code == 422
    other = next(c["id"] for c in context["clinics"] if c["id"] != context["clinic_id"])
    assert client.get(u, headers={"X-Demo-Clinic": other}).status_code == 404


def test_encounter_rejects_invalid_doctor(client, patient, context):
    receptionist = next(s for s in context["staff"] if s["role"] == "receptionist")
    r = client.post("/api/v1/encounters", json={"patient_id": patient["id"],
                                                    "practitioner_id": receptionist["id"]})
    assert r.status_code == 422
