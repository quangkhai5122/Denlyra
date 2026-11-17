"""Golden synthetic end-to-end journey; NO real clinical care or EMR signature."""


def test_end_to_end_journey(client, context):
    doctor = next(s for s in context['staff'] if s['role'] == 'dentist')
    chair = context['chairs'][0]
    patient = client.post('/api/v1/patients', json={
        'display_name': 'Demo hành trình giả lập', 'birth_year': 1999}).json()
    appt = client.post('/api/v1/appointments', json={
        'patient_id': patient['id'], 'practitioner_id': doctor['id'],
        'chair_id': chair['id'], 'start_at': '2026-12-10T08:00:00+07:00',
        'end_at': '2026-12-10T08:30:00+07:00', 'reason_demo': 'Lịch demo'}).json()
    e = client.post('/api/v1/encounters', json={
        'patient_id': patient['id'], 'practitioner_id': doctor['id']}).json()
    note = client.post(f"/api/v1/encounters/{e['id']}/notes",
                       json={'content': 'Ghi chú giả lập không phải bệnh án thật.'}).json()
    finding = client.post(f"/api/v1/encounters/{e['id']}/findings", json={
        'tooth_code': '24', 'surface': 'ALL', 'finding_text_demo': 'Chỉ ghi nhận demo'}).json()
    plan = client.post('/api/v1/treatment-plans', json={
        'patient_id': patient['id'], 'title': 'Lộ trình giả lập'}).json()
    task = client.post(f"/api/v1/treatment-plans/{plan['id']}/tasks",
                       json={'title': 'Chuẩn bị bản demo'}).json()
    client.post(f"/api/v1/treatment-plans/{plan['id']}/demo-review")
    assert client.post(f"/api/v1/treatment-tasks/{task['id']}/demo-complete").status_code == 200
    lab = client.post('/api/v1/lab-cases', json={
        'patient_id': patient['id'], 'title': 'Labo giả lập'}).json()
    charge = client.post('/api/v1/finance/charges', json={
        'patient_id': patient['id'], 'label': 'Khoản giả lập', 'amount_vnd': 2_000_000}).json()
    payment = client.post('/api/v1/finance/payments', json={
        'patient_id': patient['id'], 'amount_vnd': 500_000}).json()
    assert client.post('/api/v1/finance/allocations', json={
        'charge_id': charge['id'], 'payment_id': payment['id'], 'amount_vnd': 500_000}).status_code == 201
    assert client.post(f"/api/v1/notes/{note['id']}/demo-lock").status_code == 200
    assert client.post(f"/api/v1/appointments/{appt['id']}/cancel").status_code == 200
    audit = client.get('/api/v1/audit-events').json()
    assert any(a['action'] == 'note.demo_locked_NOT_signed' for a in audit)
    assert any(a['action'] == 'plan.task_demo_completed_NOT_procedure' for a in audit)
    assert any(a['action'] == 'appointment.cancelled' for a in audit)
    assert client.get(f"/api/v1/patients/{patient['id']}/odontogram").json()['findings'][0]['id'] == finding['id']
    # Payment and cancelled appointment do not imply performed clinical care.
    assert client.get('/api/v1/encounters').json()[0]['status'] == 'in_progress'
    assert lab['status'] == 'requested'
    assert client.get('/api/v1/capabilities').json()['clinical_e_signature'] is False


def test_seed_is_idempotent_on_reopen(tmp_path):
    from fastapi.testclient import TestClient
    from denlyra.api import create_app
    from denlyra.config import Settings
    cfg = Settings(demo_mode=True, db_url=f"sqlite+pysqlite:///{tmp_path / 'persist.db'}")
    with TestClient(create_app(cfg), base_url='http://127.0.0.1:8766') as c:
        a = c.get('/api/v1/demo/context').json()
        c.post('/api/v1/patients', json={'display_name':'Persistent demo'})
    with TestClient(create_app(cfg), base_url='http://127.0.0.1:8766') as c:
        b = c.get('/api/v1/demo/context').json()
        assert len(b['clinics']) == 2
        assert [s['id'] for s in b['staff']] == [s['id'] for s in a['staff']]
        assert len(c.get('/api/v1/patients').json()) == 1
