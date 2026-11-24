"""T013 clinic operations (shifts, downtime, confirmations, turnovers, check-in, recalls)
and T014 per-clinic hash-chained tamper-evident audit journal + cursor pagination.

Revision ID: 0007_operations_audit_chain_and_pagination
Revises: 0006_inventory_fhir_and_ai_harness
"""
from datetime import datetime, timezone
from alembic import context, op
import sqlalchemy as sa
from denlyra.audit_chain import GENESIS_PREV_HASH, compute_audit_entry_hash
from denlyra.db import (
    SQLITE_AUDIT_NO_DELETE_TRIGGER,
    SQLITE_AUDIT_NO_UPDATE_TRIGGER,
    SQLITE_DOWNTIME_BLOCK_TRIGGER,
)

PG_AUDIT_IMMUTABILITY_DDL = """
CREATE OR REPLACE FUNCTION reject_audit_event_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only; updates and deletes prohibited';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_event_no_update ON audit_event;
CREATE TRIGGER trg_audit_event_no_update
BEFORE UPDATE ON audit_event
FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation();

DROP TRIGGER IF EXISTS trg_audit_event_no_delete ON audit_event;
CREATE TRIGGER trg_audit_event_no_delete
BEFORE DELETE ON audit_event
FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation();
"""

PG_DOWNTIME_BLOCK_DDL = """
CREATE OR REPLACE FUNCTION reject_resource_booking_downtime() RETURNS trigger AS $$
BEGIN
    IF NEW.state = 'booked' AND EXISTS (
        SELECT 1 FROM resource_downtime d
        WHERE d.clinic_id = NEW.clinic_id
          AND d.resource_key = NEW.resource_key
          AND d.status = 'active'
          AND NEW.start_at < d.end_at
          AND NEW.end_at > d.start_at
    ) THEN
        RAISE EXCEPTION 'Resource is under scheduled maintenance downtime';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_resource_booking_downtime ON resource_booking;
CREATE TRIGGER trg_resource_booking_downtime
BEFORE INSERT ON resource_booking
FOR EACH ROW EXECUTE FUNCTION reject_resource_booking_downtime();
"""

revision = "0007_operations_audit_chain_and_pagination"
down_revision = "0006_inventory_fhir_and_ai_harness"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("audit_event") as batch_op:
        batch_op.add_column(sa.Column("chain_seq", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("prev_hash", sa.String(64), nullable=False, server_default=GENESIS_PREV_HASH)
        )
        batch_op.add_column(sa.Column("entry_hash", sa.String(64), nullable=False, server_default=""))

    bind = op.get_bind()
    if not context.is_offline_mode():
        existing_events = bind.execute(
            sa.text(
                "SELECT id, clinic_id, actor_demo, action, subject_type, subject_id, metadata_json, created_at "
                "FROM audit_event ORDER BY clinic_id ASC, created_at ASC, id ASC"
            )
        ).fetchall()
        seq_by_clinic: dict[str, int] = {}
        prev_by_clinic: dict[str, str] = {}
        for row in existing_events:
            ev_id, cid, actor, action, stype, sid, meta, c_at = row
            dt = c_at if isinstance(c_at, datetime) else datetime.fromisoformat(str(c_at))
            seq = seq_by_clinic.get(cid, 0) + 1
            prev_h = prev_by_clinic.get(cid, GENESIS_PREV_HASH)
            entry_h = compute_audit_entry_hash(
                clinic_id=cid,
                chain_seq=seq,
                prev_hash=prev_h,
                actor_demo=actor,
                action=action,
                subject_type=stype,
                subject_id=sid,
                metadata_json=meta or "{}",
                created_at=dt,
            )
            bind.execute(
                sa.text(
                    "UPDATE audit_event SET chain_seq = :seq, prev_hash = :ph, entry_hash = :eh WHERE id = :id"
                ),
                {"seq": seq, "ph": prev_h, "eh": entry_h, "id": ev_id},
            )
            seq_by_clinic[cid] = seq
            prev_by_clinic[cid] = entry_h

    with op.batch_alter_table("audit_event") as batch_op:
        batch_op.create_unique_constraint(
            "uq_audit_clinic_chain_seq", ["clinic_id", "chain_seq"]
        )

    op.create_table(
        "staff_shift",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("staff_id", sa.String(36), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "staff_id"], ["staff.clinic_id", "staff.id"]),
        sa.CheckConstraint("end_at > start_at", name="ck_staff_shift_valid_range"),
    )

    op.create_table(
        "resource_downtime",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("resource_key", sa.String(80), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.String(260), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "resource_id"], ["resource.clinic_id", "resource.id"]),
        sa.CheckConstraint("end_at > start_at", name="ck_downtime_valid_range"),
    )

    op.create_table(
        "appointment_confirmation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("evidence_note", sa.String(260), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]
        ),
    )

    op.create_table(
        "chair_turnover_checklist",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("chair_id", sa.String(36), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=False),
        sa.Column("surface_disinfected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sterile_kit_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("waterline_flushed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assistant_prep_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("notes", sa.String(260), nullable=False, server_default=""),
        sa.Column("completed_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "chair_id"], ["resource.clinic_id", "resource.id"]),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]
        ),
    )

    op.create_table(
        "checkin_queue_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("identity_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_method", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="waiting"),
        sa.Column("notes", sa.String(260), nullable=False, server_default=""),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "recall_followup_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("due_date", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("clinician_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("closure_evidence", sa.String(300), nullable=True),
        sa.Column(
            "owner_role", sa.String(32), nullable=False, server_default="treatment_coordinator"
        ),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    op.execute(
        sa.text(
            "INSERT INTO schema_migration_meta (revision_id, description, applied_at) "
            "VALUES ('0007_operations_audit_chain_and_pagination', "
            "'T013 clinic shifts/downtime/check-in/turnover/recall + T014 hash-chained audit journal', :ts)"
        ).bindparams(ts=now_iso)
    )
    if bind.dialect.name == "sqlite":
        op.execute(SQLITE_DOWNTIME_BLOCK_TRIGGER)
        op.execute(SQLITE_AUDIT_NO_UPDATE_TRIGGER)
        op.execute(SQLITE_AUDIT_NO_DELETE_TRIGGER)
    elif bind.dialect.name == "postgresql":
        op.execute(PG_DOWNTIME_BLOCK_DDL)
        op.execute(PG_AUDIT_IMMUTABILITY_DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
