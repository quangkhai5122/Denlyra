"""T010 encrypted record archive, tenant key rotation, backup manifest, and isolated DR drill.

Revision ID: 0005_archive_and_dr
Revises: 0004_lab_consent_finance_and_migration
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0005_archive_and_dr"
down_revision = "0004_lab_consent_finance_and_migration"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tenant_encryption_key",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("wrapped_dek_b64", sa.Text(), nullable=False),
        sa.Column("key_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("rotated_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "key_version", name="uq_tenant_key_clinic_version"),
    )

    op.create_table(
        "archive_object",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("snapshot_id", sa.String(36), nullable=True),
        sa.Column("object_kind", sa.String(40), nullable=False),
        sa.Column("media_type", sa.String(80), nullable=False),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("plaintext_sha256", sa.String(64), nullable=False),
        sa.Column("ciphertext_sha256", sa.String(64), nullable=False),
        sa.Column(
            "key_id",
            sa.String(36),
            sa.ForeignKey("tenant_encryption_key.id"),
            nullable=False,
        ),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("storage_relpath", sa.String(260), nullable=False),
        sa.Column(
            "retention_class",
            sa.String(40),
            nullable=False,
            server_default="clinical_emr_quarantined",
        ),
        sa.Column("retention_until", sa.DateTime(), nullable=False),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("legal_hold_reason", sa.String(260), nullable=True),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "backup_manifest",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("db_checkpoint_at", sa.DateTime(), nullable=False),
        sa.Column("object_store_checkpoint_at", sa.DateTime(), nullable=False),
        sa.Column("bundle_relpath", sa.String(260), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_hmac", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="sealed"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "restore_drill_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "backup_id", sa.String(36), sa.ForeignKey("backup_manifest.id"), nullable=False
        ),
        sa.Column("target_clinic_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("integrity_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("restored_patients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("restored_snapshots", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("restored_objects", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rto_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rpo_lag_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("failure_detail", sa.String(400), nullable=True),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(
        sa.table(
            "schema_migration_meta",
            sa.column("revision_id", sa.String),
            sa.column("description", sa.String),
            sa.column("applied_at", sa.DateTime),
        ),
        [
            {
                "revision_id": "0005_archive_and_dr",
                "description": "T010 encrypted archive objects, tenant key rotation, backup manifest, and DR restore drill",
                "applied_at": now_dt,
            }
        ],
    )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
