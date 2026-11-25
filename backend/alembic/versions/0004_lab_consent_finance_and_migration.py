"""T006/T007/T008 consent taxonomy, lab partner portal, revenue ledger/estimates/reconciliation, and paper quarantine importer.

Revision ID: 0004_lab_consent_finance_and_migration
Revises: 0003_treatment_and_signing
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from denlyra.db import SQLITE_ALLOCATION_BOUNDS_TRIGGER

revision = "0004_lab_consent_finance_and_migration"
down_revision = "0003_treatment_and_signing"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lab_case") as batch_op:
        batch_op.add_column(sa.Column("specification_demo", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("file_manifest_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("parent_lab_case_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("delivery_condition", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("delivered_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("verified_by_staff_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("charge") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(120), nullable=True))
        batch_op.create_unique_constraint(
            "uq_charge_clinic_idempotency", ["clinic_id", "idempotency_key"]
        )

    with op.batch_alter_table("payment") as batch_op:
        batch_op.add_column(
            sa.Column("payment_method", sa.String(24), nullable=False, server_default="cash")
        )
        batch_op.add_column(sa.Column("idempotency_key", sa.String(120), nullable=True))
        batch_op.create_unique_constraint(
            "uq_payment_clinic_idempotency", ["clinic_id", "idempotency_key"]
        )

    with op.batch_alter_table("payment_allocation") as batch_op:
        batch_op.add_column(sa.Column("clinic_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(120), nullable=True))

    with op.batch_alter_table("payment_refund") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(120), nullable=True))
        batch_op.create_unique_constraint(
            "uq_refund_clinic_idempotency", ["clinic_id", "idempotency_key"]
        )

    op.create_table(
        "consent_record",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("template_version", sa.String(40), nullable=False),
        sa.Column("disclosure_summary", sa.String(400), nullable=False),
        sa.Column("signer_name", sa.String(160), nullable=False),
        sa.Column("signer_relationship", sa.String(20), nullable=False, server_default="self"),
        sa.Column(
            "guardian_authority_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="granted"),
        sa.Column("withdrawn_reason", sa.String(260), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "lab_partner_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("lab_case_id", sa.String(36), sa.ForeignKey("lab_case.id"), nullable=False),
        sa.Column("partner_name", sa.String(160), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "estimate_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("treatment_plan.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("items_summary", sa.String(400), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("accepted_by", sa.String(160), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_vnd > 0", name="ck_estimate_positive"),
        sa.UniqueConstraint("plan_id", "version_number", name="uq_estimate_plan_version"),
    )

    op.create_table(
        "ledger_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("entry_type", sa.String(40), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(24), nullable=True),
        sa.Column("reference_type", sa.String(40), nullable=False),
        sa.Column("reference_id", sa.String(36), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_vnd > 0", name="ck_ledger_positive"),
    )

    op.create_table(
        "cashier_reconciliation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("expected_cash_vnd", sa.Integer(), nullable=False),
        sa.Column("counted_cash_vnd", sa.Integer(), nullable=False),
        sa.Column("discrepancy_cash_vnd", sa.Integer(), nullable=False),
        sa.Column("expected_transfer_vnd", sa.Integer(), nullable=False),
        sa.Column("counted_transfer_vnd", sa.Integer(), nullable=False),
        sa.Column("discrepancy_transfer_vnd", sa.Integer(), nullable=False),
        sa.Column("expected_card_vnd", sa.Integer(), nullable=False),
        sa.Column("counted_card_vnd", sa.Integer(), nullable=False),
        sa.Column("discrepancy_card_vnd", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("notes", sa.String(300), nullable=False, server_default=""),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "migration_batch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("source_cabinet", sa.String(200), nullable=False),
        sa.Column("expected_item_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(30), nullable=False, server_default="quarantined_open"),
        sa.Column("rollback_reason", sa.String(260), nullable=True),
        sa.Column("operator_actor", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "migration_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "batch_id", sa.String(36), sa.ForeignKey("migration_batch.id"), nullable=False
        ),
        sa.Column("legacy_folder_id", sa.String(80), nullable=False),
        sa.Column("patient_display_name", sa.String(160), nullable=False),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("phone_demo", sa.String(40), nullable=True),
        sa.Column("expected_page_count", sa.Integer(), nullable=False),
        sa.Column("pages_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("missing_pages_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("completeness_status", sa.String(40), nullable=False),
        sa.Column("match_status", sa.String(40), nullable=False),
        sa.Column("candidate_patient_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("linked_patient_id", sa.String(36), nullable=True),
        sa.Column(
            "created_new_patient",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("status", sa.String(40), nullable=False, server_default="quarantined"),
        sa.Column(
            "provenance_source",
            sa.String(30),
            nullable=False,
            server_default="legacy_scan",
        ),
        sa.Column(
            "digital_signature_status",
            sa.String(40),
            nullable=False,
            server_default="not_digitally_signed_legacy_paper",
        ),
        sa.Column("reviewer_note", sa.String(300), nullable=True),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    bind = op.get_bind()
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
                "revision_id": "0004_lab_consent_finance_and_migration",
                "description": "T006 paper quarantine importer, T007 consent/lab partner portal, T008 revenue ledger",
                "applied_at": now_dt,
            }
        ],
    )
    if bind.dialect.name == "sqlite":
        op.execute(SQLITE_ALLOCATION_BOUNDS_TRIGGER)


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
