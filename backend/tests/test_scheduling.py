
def test_booking_and_resource_overlap(client, appointment_payload, context):
    first = client.post("/api/v1/appointments", json=appointment_payload)
    assert first.status_code == 201, first.text
    # Overlap at same chair AND same dentist
    overlapping = dict(appointment_payload, start_at="2026-12-01T09:30:00+07:00",
                       end_at="2026-12-01T10:30:00+07:00")
    assert client.post("/api/v1/appointments", json=overlapping).status_code == 409
    other_chair = dict(overlapping, chair_id=context["chairs"][1]["id"])
    assert client.post("/api/v1/appointments", json=other_chair).status_code == 409
    # Adjacent half-open interval should be legal.
    after = dict(appointment_payload, start_at="2026-12-01T10:00:00+07:00",
                 end_at="2026-12-01T11:00:00+07:00")
    assert client.post("/api/v1/appointments", json=after).status_code == 201


def test_cancel_releases_resource_but_preserves_history(client, appointment_payload):
    created = client.post("/api/v1/appointments", json=appointment_payload).json()
    assert client.post(f"/api/v1/appointments/{created['id']}/cancel").status_code == 200
    assert client.post("/api/v1/appointments", json=appointment_payload).status_code == 201
    assert len(client.get("/api/v1/appointments").json()) == 2
    assert client.post(f"/api/v1/appointments/{created['id']}/cancel").status_code == 409


def test_invalid_schedule_rejected(client, appointment_payload):
    bad = dict(appointment_payload, end_at=appointment_payload["start_at"])
    assert client.post("/api/v1/appointments", json=bad).status_code == 422
    naive = dict(appointment_payload, start_at="2026-12-01T09:00:00")
    assert client.post("/api/v1/appointments", json=naive).status_code == 422


def test_cross_tenant_booking_rejected(client, appointment_payload, context):
    other = next(c["id"] for c in context["clinics"] if c["id"] != context["clinic_id"])
    assert client.post("/api/v1/appointments", json=appointment_payload,
                       headers={"X-Demo-Clinic": other}).status_code == 404
