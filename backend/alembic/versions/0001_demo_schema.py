"""Frozen baseline schema (18 tables) with explicit DDL; does not import mutable ORM metadata.

Revision ID: 0001_demo
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_demo"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clinic",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("demo_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "staff",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "patient",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("phone_demo", sa.String(40), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default="demo_native"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "birth_year IS NULL OR (birth_year BETWEEN 1900 AND 2100)",
            name="ck_patient_birth_year",
        ),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_index("ix_patient_clinic_name", "patient", ["clinic_id", "display_name"])
    op.create_table(
        "resource",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "appointment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("practitioner_id", sa.String(36), nullable=False),
        sa.Column("chair_id", sa.String(36), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="confirmed"),
        sa.Column("reason_demo", sa.String(260), nullable=False, server_default="Demo appointment"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        sa.ForeignKeyConstraint(["clinic_id", "practitioner_id"], ["staff.clinic_id", "staff.id"]),
        sa.ForeignKeyConstraint(["clinic_id", "chair_id"], ["resource.clinic_id", "resource.id"]),
        sa.CheckConstraint("end_at > start_at", name="ck_appointment_valid_range"),
        sa.CheckConstraint("status IN ('confirmed','cancelled')", name="ck_appointment_demo_status"),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "resource_booking",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=False),
        sa.Column("resource_key", sa.String(80), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]),
        sa.CheckConstraint("end_at > start_at", name="ck_booking_valid_range"),
        sa.CheckConstraint("state IN ('active','cancelled')", name="ck_booking_state"),
    )
    op.create_table(
        "encounter",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("practitioner_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="in_progress"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        sa.ForeignKeyConstraint(["clinic_id", "practitioner_id"], ["staff.clinic_id", "staff.id"]),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "clinical_note",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=False),
        sa.Column("parent_note_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("latest_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("locked_digest", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "note_revision",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_id", sa.String(36), sa.ForeignKey("clinical_note.id"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("source_type", sa.String(24), nullable=False, server_default="manual_demo"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("note_id", "revision_no"),
    )
    op.create_table(
        "dental_finding_demo",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=False),
        sa.Column("tooth_code", sa.String(2), nullable=False),
        sa.Column("surface", sa.String(8), nullable=False),
        sa.Column("finding_text_demo", sa.String(300), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "treatment_plan",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "plan_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("treatment_plan.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(22), nullable=False, server_default="draft"),
        sa.Column("reviewer_demo", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("plan_id", "number"),
    )
    op.create_table(
        "plan_task",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_version_id", sa.String(36), sa.ForeignKey("plan_version.id"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("phase", sa.String(100), nullable=False, server_default="Demo phase"),
        sa.Column("depends_on_task_id", sa.String(36), sa.ForeignKey("plan_task.id"), nullable=True),
        sa.Column("status", sa.String(22), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "lab_case",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("status", sa.String(28), nullable=False, server_default="requested"),
        sa.Column("due_on", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )
    op.create_table(
        "charge",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        sa.CheckConstraint("amount_vnd > 0", name="ck_charge_positive"),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "payment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("external_reference", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        sa.CheckConstraint("amount_vnd > 0", name="ck_payment_positive"),
        sa.UniqueConstraint("clinic_id", "id"),
    )
    op.create_table(
        "payment_allocation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("charge_id", sa.String(36), sa.ForeignKey("charge.id"), nullable=False),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payment.id"), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_vnd > 0", name="ck_allocation_positive"),
    )
    op.create_table(
        "audit_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute(
            """
            ALTER TABLE resource_booking
            ADD CONSTRAINT no_overlapping_active_resource_booking
            EXCLUDE USING gist (
                clinic_id WITH =,
                resource_key WITH =,
                tsrange(start_at, end_at, '[)') WITH &&
            ) WHERE (state = 'active')
            """
        )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
