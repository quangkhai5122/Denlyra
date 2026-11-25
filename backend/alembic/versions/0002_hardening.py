"""T001/T002/T003 schema hardening: identity revocation, booking idempotency, and FormRegistry.

Revision ID: 0002_hardening
Revises: 0001_demo
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from denlyra.db import SQLITE_BOOKING_OVERLAP_TRIGGER

revision = "0002_hardening"
down_revision = "0001_demo"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("staff") as batch_op:
        batch_op.add_column(
            sa.Column("branch_id", sa.String(36), nullable=False, server_default="branch-main")
        )
        batch_op.add_column(
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="1")
        )

    with op.batch_alter_table("appointment") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(120), nullable=True))
        batch_op.create_unique_constraint(
            "uq_appointment_clinic_idempotency", ["clinic_id", "idempotency_key"]
        )

    op.create_index(
        "ix_booking_active_lookup",
        "resource_booking",
        ["clinic_id", "resource_key", "state", "start_at", "end_at"],
    )

    op.create_table(
        "revoked_token",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("jti", sa.String(64), nullable=False, unique=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("staff_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.String(120), nullable=False, server_default="revoked"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "signed_url_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("created_by_staff_id", sa.String(36), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "form_template_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("official_code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_citation", sa.String(300), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column(
            "approval_status",
            sa.String(40),
            nullable=False,
            server_default="quarantined_synthetic_draft",
        ),
        sa.Column("approved_by_dentist", sa.String(120), nullable=True),
        sa.Column("approved_by_counsel", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id",
            "official_code",
            "schema_version",
            name="uq_form_template_clinic_code_version",
        ),
    )

    op.create_table(
        "form_field_map",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("form_template_version.id"),
            nullable=False,
        ),
        sa.Column("field_code", sa.String(80), nullable=False),
        sa.Column("label_vi", sa.String(200), nullable=False),
        sa.Column("field_type", sa.String(30), nullable=False),
        sa.Column("required_when", sa.String(40), nullable=False, server_default="always"),
        sa.Column("allow_unknown", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("template_id", "field_code", name="uq_form_field_template_code"),
    )

    op.create_table(
        "schema_migration_meta",
        sa.Column("revision_id", sa.String(128), primary_key=True),
        sa.Column("description", sa.String(320), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
    )

    bind = op.get_bind()
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    op.execute(
        sa.text(
            "INSERT INTO schema_migration_meta (revision_id, description, applied_at) "
            "VALUES ('0001_demo', 'Frozen R0 baseline schema', :ts), "
            "('0002_hardening', 'T001 auth revocation/signed URLs, T002 booking idempotency, T003 FormRegistry', :ts)"
        ).bindparams(ts=now_iso)
    )
    if bind.dialect.name == "sqlite":
        op.execute(SQLITE_BOOKING_OVERLAP_TRIGGER)


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
