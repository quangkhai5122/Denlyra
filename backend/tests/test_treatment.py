
def make_plan(client, patient):
    result = client.post("/api/v1/treatment-plans", json={
        "patient_id": patient["id"], "title": "Kế hoạch giả lập nhiều giai đoạn"})
    assert result.status_code == 201
    return result.json()


def test_plan_graph_dependencies_and_new_immutable_version(client, patient):
    plan = make_plan(client, patient)
    task_url = f"/api/v1/treatment-plans/{plan['id']}/tasks"
    first = client.post(task_url, json={"title": "Bước mẫu A", "phase": "P1"}).json()
    second = client.post(task_url, json={
        "title": "Bước mẫu B", "phase": "P2", "depends_on_task_id": first["id"]}).json()
    assert client.post(f"/api/v1/treatment-plans/{plan['id']}/demo-review").status_code == 200
    assert client.post(task_url, json={"title": "Sửa kế hoạch đã duyệt"}).status_code == 409
    assert client.post(f"/api/v1/treatment-tasks/{second['id']}/demo-complete").status_code == 409
    assert client.post(f"/api/v1/treatment-tasks/{first['id']}/demo-complete").status_code == 200
    assert client.post(f"/api/v1/treatment-tasks/{second['id']}/demo-complete").status_code == 200
    newer = client.post(f"/api/v1/treatment-plans/{plan['id']}/versions")
    assert newer.status_code == 201
    assert newer.json()["number"] == 2
    latest = client.get(f"/api/v1/treatment-plans/{plan['id']}").json()
    assert len(latest["tasks"]) == 2
    assert all(t["status"] == "pending" for t in latest["tasks"])
    assert any(t["depends_on_task_id"] for t in latest["tasks"])
    assert client.post(f"/api/v1/treatment-tasks/{first['id']}/demo-complete").status_code == 409


def test_plan_without_tasks_not_reviewed(client, patient):
    p = make_plan(client, patient)
    assert client.post(f"/api/v1/treatment-plans/{p['id']}/demo-review").status_code == 422


def test_task_dependency_must_be_in_same_plan_version(client, patient):
    p1 = make_plan(client, patient)
    p2 = make_plan(client, patient)
    task = client.post(f"/api/v1/treatment-plans/{p1['id']}/tasks", json={"title": "Step demo"}).json()
    bad = client.post(f"/api/v1/treatment-plans/{p2['id']}/tasks", json={
        "title": "Unrelated", "depends_on_task_id": task["id"]})
    assert bad.status_code == 422
