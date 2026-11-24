"""T002 migration upgrade chain, atomic multi-resource booking, idempotency, and race tests."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from denlyra import models as m, services as svc
from denlyra.db import session_factory
from denlyra.schemas import AppointmentCreate


def test_alembic_upgrade_from_empty_and_from_0001_fixture_preserves_data(tmp_path):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cfg = Config(os.path.join(root, "backend", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "backend", "alembic"))
    db_url = f"sqlite+pysqlite:///{tmp_path / 'upgrade_chain.db'}"
    cfg.set_main_option("sqlalchemy.url", db_url)

    # Step 1: Upgrade empty DB to 0001_demo and insert synthetic fixture data
    command.upgrade(cfg, "0001_demo")
    engine = create_engine(db_url)
    try:
        tables_v1 = set(inspect(engine).get_table_names())
        assert "patient" in tables_v1 and "appointment" in tables_v1
        with engine.begin() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001_demo"
            conn.execute(
                text(
                    "INSERT INTO clinic (id, name, demo_only, created_at) "
                    "VALUES ('11111111-1111-4111-8111-111111111111', 'Clinic V1', 1, '2026-11-18 00:00:00')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO patient (id, clinic_id, display_name, phone_demo, birth_year, source, created_at) "
                    "VALUES ('pat-v1-0001', '11111111-1111-4111-8111-111111111111', 'Bệnh nhân V1', '0900000000', 1992, 'demo_native', '2026-11-18 00:00:00')"
                )
            )

        # Step 2: Upgrade existing 0001_demo DB through 0002..0008 to head (0009_encounter_lifecycle_and_clinical_governance)
        command.upgrade(cfg, "0002_hardening")
        command.upgrade(cfg, "0003_treatment_and_signing")
        command.upgrade(cfg, "0004_lab_consent_finance_and_migration")
        command.upgrade(cfg, "0005_archive_and_dr")
        command.upgrade(cfg, "0006_inventory_fhir_and_ai_harness")
        command.upgrade(cfg, "0007_operations_audit_chain_and_pagination")
        command.upgrade(cfg, "0008_patient_merge_portal_and_kpi_lineage")
        command.upgrade(cfg, "head")
        tables_head = set(inspect(engine).get_table_names())
        assert "revoked_token" in tables_head
        assert "signed_url_grant" in tables_head
        assert "form_template_version" in tables_head
        assert "plan_task_dependency" in tables_head
        assert "clinical_document_snapshot" in tables_head
        assert "consent_record" in tables_head
        assert "ledger_entry" in tables_head
        assert "migration_batch" in tables_head
        assert "archive_object" in tables_head
        assert "backup_manifest" in tables_head
        assert "restore_drill_run" in tables_head
        assert "stock_movement" in tables_head
        assert "ai_draft_artifact" in tables_head
        assert "checkin_queue_item" in tables_head
        assert "recall_followup_item" in tables_head
        assert "patient_merge_request" in tables_head
        assert "break_glass_grant" in tables_head
        assert "service_price_catalog_item" in tables_head
        assert "patient_medical_risk_review" in tables_head
        assert "performed_procedure_evidence" in tables_head
        assert "quality_incident_report" in tables_head
        assert "schema_migration_meta" in tables_head
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0009_encounter_lifecycle_and_clinical_governance"
            preserved = conn.execute(
                text("SELECT display_name FROM patient WHERE id = 'pat-v1-0001'")
            ).scalar()
            assert preserved == "Bệnh nhân V1"

        # Step 3: Destructive downgrade remains prohibited
        with pytest.raises(RuntimeError, match="Destructive downgrade prohibited"):
            command.downgrade(cfg, "0003_treatment_and_signing")
    finally:
        engine.dispose()


def test_atomic_multi_resource_equipment_booking_and_rollback(client, appointment_payload, context):
    # Create two synthetic equipment resources (devices) in Clinic A
    res_scanner = client.post(
        "/api/v1/resources",
        json={"name": "Máy scan trong miệng Demo 1", "kind": "device"},
    )
    assert res_scanner.status_code == 201
    scanner_id = res_scanner.json()["id"]

    # Book appointment reserving doctor + chair + scanner atomically
    payload_with_eq = dict(appointment_payload, equipment_ids=[scanner_id])
    booked = client.post("/api/v1/appointments", json=payload_with_eq)
    assert booked.status_code == 201, booked.text

    # Second booking at overlapping time with DIFFERENT doctor and DIFFERENT chair,
    # but requesting the SAME scanner equipment must be rejected with 409 (SCH-02)
    other_chair = context["chairs"][1]["id"]
    second_doctor = client.post(
        "/api/v1/staff",
        json={"display_name": "Bác sĩ Demo 2", "role": "dentist"},
    ).json()["id"]
    conflict_eq = dict(
        appointment_payload,
        practitioner_id=second_doctor,
        chair_id=other_chair,
        equipment_ids=[scanner_id],
    )
    assert client.post("/api/v1/appointments", json=conflict_eq).status_code == 409

    # Atomic rollback if one equipment ID in the list is invalid/missing (SCH-03):
    # neither the valid chair nor the valid doctor may be left reserved.
    bad_batch = dict(
        appointment_payload,
        practitioner_id=second_doctor,
        chair_id=other_chair,
        start_at="2026-12-02T09:00:00+07:00",
        end_at="2026-12-02T10:00:00+07:00",
        equipment_ids=["non-existent-device-id"],
    )
    assert client.post("/api/v1/appointments", json=bad_batch).status_code == 404
    # Subsequent valid booking for that exact 2026-12-02 slot succeeds (proving rollback)
    clean_slot = dict(
        appointment_payload,
        practitioner_id=second_doctor,
        chair_id=other_chair,
        start_at="2026-12-02T09:00:00+07:00",
        end_at="2026-12-02T10:00:00+07:00",
    )
    assert client.post("/api/v1/appointments", json=clean_slot).status_code == 201


def test_idempotent_booking_retries_and_conflicting_key_reuse(client, appointment_payload):
    payload = dict(appointment_payload, idempotency_key="idem-booking-0001")
    first = client.post("/api/v1/appointments", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/appointments", json=payload)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert len(client.get("/api/v1/appointments").json()) == 1

    # Reusing the same idempotency_key for a different time interval must fail with 409
    different_slot = dict(
        payload,
        start_at="2026-12-01T14:00:00+07:00",
        end_at="2026-12-01T15:00:00+07:00",
    )
    assert client.post("/api/v1/appointments", json=different_slot).status_code == 409


def test_db_integrity_error_maps_to_409_and_rolls_back_atomically(client, appointment_payload, monkeypatch):
    factory = client.app.state.factory
    with factory() as db:
        clinic_id = "11111111-1111-4111-8111-111111111111"
        data = AppointmentCreate(**appointment_payload)

        orig_commit = db.commit

        def simulated_pg_exclusion_violation():
            raise IntegrityError(
                "INSERT INTO resource_booking",
                params={},
                orig=Exception("conflicting key value violates exclusion constraint no_overlapping_active_resource_booking"),
            )

        monkeypatch.setattr(db, "commit", simulated_pg_exclusion_violation)
        with pytest.raises(HTTPException) as exc:
            svc.schedule(db, clinic_id, data, actor="race-tester")
        assert exc.value.status_code == 409
        monkeypatch.setattr(db, "commit", orig_commit)

    with factory() as verify_db:
        assert verify_db.scalars(select(m.Appointment)).all() == []
        assert verify_db.scalars(select(m.ResourceBooking)).all() == []


def test_two_connection_barrier_concurrent_booking_race(client, appointment_payload):
    """Two independent DB connections synchronized via Barrier attempt the same slot (NEG-02)."""
    factory = client.app.state.factory
    clinic_id = "11111111-1111-4111-8111-111111111111"
    barrier = threading.Barrier(2)

    def worker(idx: int) -> int:
        with factory() as session:
            data = AppointmentCreate(**appointment_payload)
            barrier.wait(timeout=5)
            try:
                svc.schedule(session, clinic_id, data, actor=f"concurrent-worker-{idx}")
                return 201
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(worker, [1, 2]))

    assert outcomes == [201, 409], f"Expected one 201 and one 409, got {outcomes}"
    with factory() as check_db:
        active_appts = check_db.scalars(
            select(m.Appointment).where(m.Appointment.status == "confirmed")
        ).all()
        active_bookings = check_db.scalars(
            select(m.ResourceBooking).where(m.ResourceBooking.state == "active")
        ).all()
        assert len(active_appts) == 1
        assert len(active_bookings) == 2


@pytest.mark.skipif(
    not os.getenv("DENLYRA_TEST_POSTGRES_URL"),
    reason="DENLYRA_TEST_POSTGRES_URL not set; live PostgreSQL exclusion test requires running PostgreSQL",
)
def test_live_postgresql_exclusion_constraint_and_race():
    pg_url = os.environ["DENLYRA_TEST_POSTGRES_URL"]
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cfg = Config(os.path.join(root, "backend", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "backend", "alembic"))
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(cfg, "head")

    engine = create_engine(pg_url, future=True)
    factory = session_factory(engine)
    try:
        with engine.connect() as conn:
            constraint = conn.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname = 'no_overlapping_active_resource_booking'"
                )
            ).scalar()
            assert constraint == "no_overlapping_active_resource_booking"

        with factory() as seed_db:
            svc.demo_seed(seed_db)
            clinic_id = svc.DEMO_CLINICS[0][0]
            pat = m.Patient(clinic_id=clinic_id, display_name="PG Race Demo")
            seed_db.add(pat)
            seed_db.commit()
            doc = seed_db.scalar(
                select(m.Staff).where(m.Staff.clinic_id == clinic_id, m.Staff.role == "dentist")
            )
            chair = seed_db.scalar(
                select(m.Resource).where(m.Resource.clinic_id == clinic_id, m.Resource.kind == "chair")
            )
            payload = {
                "patient_id": pat.id,
                "practitioner_id": doc.id,
                "chair_id": chair.id,
                "start_at": "2026-12-15T09:00:00+07:00",
                "end_at": "2026-12-15T10:00:00+07:00",
                "reason_demo": "PG concurrent race",
            }

        barrier = threading.Barrier(2)

        def pg_worker(idx: int) -> int:
            with factory() as session:
                barrier.wait(timeout=5)
                try:
                    svc.schedule(session, clinic_id, AppointmentCreate(**payload), f"pg-{idx}", skip_preread=True)
                    return 201
                except HTTPException as exc:
                    return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = sorted(pool.map(pg_worker, [1, 2]))
        assert results == [201, 409]
    finally:
        engine.dispose()
