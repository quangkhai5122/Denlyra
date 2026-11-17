def test_fdi_event_history_and_reject_invalid_codes(client, patient, doctor):
    e = client.post('/api/v1/encounters', json={
        'patient_id': patient['id'], 'practitioner_id': doctor['id']}).json()
    url = f"/api/v1/encounters/{e['id']}/findings"
    for text in ['Quan sát mô phỏng A', 'Quan sát mô phỏng B']:
        r = client.post(url, json={
            'tooth_code':'11', 'surface':'M', 'finding_text_demo':text})
        assert r.status_code == 201
    result = client.get(f"/api/v1/patients/{patient['id']}/odontogram").json()
    assert len(result['findings']) == 2
    assert [x['finding_text_demo'] for x in result['findings']] == [
        'Quan sát mô phỏng A', 'Quan sát mô phỏng B']
    assert client.post(url, json={
        'tooth_code':'19', 'surface':'M','finding_text_demo':'Không hợp lệ'}).status_code == 422
    assert client.post(url, json={
        'tooth_code':'51', 'surface':'ALL','finding_text_demo':'Demo răng sữa'}).status_code == 201
    assert client.post(url, json={
        'tooth_code':'89', 'surface':'ALL','finding_text_demo':'Không hợp lệ'}).status_code == 422


def test_fdi_records_cannot_cross_clinic(client, patient, doctor, context):
    e=client.post('/api/v1/encounters',json={
        'patient_id': patient['id'], 'practitioner_id':doctor['id']}).json()
    other=next(c['id'] for c in context['clinics'] if c['id'] != context['clinic_id'])
    assert client.post(f"/api/v1/encounters/{e['id']}/findings",
                       json={'tooth_code':'11','surface':'ALL','finding_text_demo':'Fake'},
                       headers={'X-Demo-Clinic':other}).status_code == 404
