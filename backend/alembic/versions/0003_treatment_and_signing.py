"""T004/T005 treatment DAG, coordination links, reassessment, refunds, outbox, and document snapshots.

Revision ID: 0003_treatment_and_signing
Revises: 0002_hardening
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0003_treatment_and_signing"
down_revision = "0002_hardening"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("appointment") as batch_op:
        batch_op.add_column(sa.Column("rescheduled_from_id", sa.String(36), nullable=True))

    with op.batch_alter_table("plan_task") as batch_op:
        batch_op.add_column(
            sa.Column("owner_role", sa.String(30), nullable=False, server_default="dentist")
        )
        batch_op.add_column(sa.Column("due_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("reassessed_from_task_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("completion_evidence_note", sa.String(300), nullable=True))

    op.create_table(
        "plan_task_dependency",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "plan_version_id",
            sa.String(36),
            sa.ForeignKey("plan_version.id"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("plan_task.id"), nullable=False),
        sa.Column(
            "depends_on_task_id",
            sa.String(36),
            sa.ForeignKey("plan_task.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("task_id", "depends_on_task_id", name="uq_plan_task_dep_edge"),
    )

    op.create_table(
        "treatment_coordination_link",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("plan_task.id"), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column(
            "requires_verified_lab",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("task_id", "target_type", "target_id", name="uq_task_coord_link"),
    )

    op.create_table(
        "plan_reassessment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "plan_id", sa.String(36), sa.ForeignKey("treatment_plan.id"), nullable=False
        ),
        sa.Column("from_version_number", sa.Integer(), nullable=False),
        sa.Column("to_version_number", sa.Integer(), nullable=False),
        sa.Column("source_task_id", sa.String(36), nullable=False),
        sa.Column("followup_task_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.String(400), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "payment_refund",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payment.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(260), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_vnd > 0", name="ck_refund_positive"),
    )

    op.create_table(
        "outbox_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "clinical_document_snapshot",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=False),
        sa.Column("note_id", sa.String(36), sa.ForeignKey("clinical_note.id"), nullable=False),
        sa.Column("note_revision_no", sa.Integer(), nullable=False),
        sa.Column("parent_snapshot_id", sa.String(36), nullable=True),
        sa.Column("amendment_reason", sa.String(300), nullable=True),
        sa.Column(
            "status",
            sa.String(40),
            nullable=False,
            server_default="ready_for_signature",
        ),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("canonical_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("signer_staff_id", sa.String(36), nullable=True),
        sa.Column("provider_receipt_json", sa.Text(), nullable=True),
        sa.Column("entered_in_error_reason", sa.String(300), nullable=True),
        sa.Column("entered_in_error_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    op.execute(
        sa.text(
            "INSERT INTO schema_migration_meta (revision_id, description, applied_at) "
            "VALUES ('0003_treatment_and_signing', "
            "'T004 synthetic signature envelope and T005 multi-dependency treatment journey', :ts)"
        ).bindparams(ts=now_iso)
    )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
