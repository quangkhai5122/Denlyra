"""T011 append-only inventory lot ledger & dual-control adjustments + T012 AI safety harness tables.

Revision ID: 0006_inventory_fhir_and_ai_harness
Revises: 0005_archive_and_dr
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from denlyra.db import (
    SQLITE_STOCK_MOVEMENT_BOUNDS_TRIGGER,
    SQLITE_STOCK_MOVEMENT_NO_DELETE_TRIGGER,
    SQLITE_STOCK_MOVEMENT_NO_UPDATE_TRIGGER,
)

revision = "0006_inventory_fhir_and_ai_harness"
down_revision = "0005_archive_and_dr"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_supplier",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("tax_code_demo", sa.String(60), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "tax_code_demo", name="uq_supplier_clinic_tax"),
    )

    op.create_table(
        "inventory_sku",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("sku_code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("lot_tracked", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reorder_threshold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "sku_code", name="uq_sku_clinic_code"),
        sa.UniqueConstraint("clinic_id", "id", name="uq_sku_clinic_id"),
    )

    op.create_table(
        "purchase_order",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "supplier_id", sa.String(36), sa.ForeignKey("inventory_supplier.id"), nullable=False
        ),
        sa.Column("sku_id", sa.String(36), sa.ForeignKey("inventory_sku.id"), nullable=False),
        sa.Column("ordered_qty", sa.Integer(), nullable=False),
        sa.Column("delivered_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inspected_accepted_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="ordered"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("ordered_qty > 0", name="ck_po_ordered_positive"),
    )

    op.create_table(
        "inventory_lot",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("sku_id", sa.String(36), sa.ForeignKey("inventory_sku.id"), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_order.id")),
        sa.Column("lot_number", sa.String(80), nullable=False),
        sa.Column("expiry_date", sa.String(10), nullable=False),
        sa.Column("quarantined", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "sku_id", "lot_number", name="uq_lot_clinic_sku_number"),
        sa.UniqueConstraint("clinic_id", "id", name="uq_lot_clinic_id"),
    )

    op.create_table(
        "stock_movement",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("sku_id", sa.String(36), sa.ForeignKey("inventory_sku.id"), nullable=False),
        sa.Column("lot_id", sa.String(36), sa.ForeignKey("inventory_lot.id"), nullable=False),
        sa.Column("movement_type", sa.String(40), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(40), nullable=False),
        sa.Column("reference_id", sa.String(36), nullable=False),
        sa.Column("note_demo", sa.String(260), nullable=False, server_default=""),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantity_delta != 0", name="ck_stock_movement_nonzero"),
    )

    op.create_table(
        "stock_reservation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("sku_id", sa.String(36), sa.ForeignKey("inventory_sku.id"), nullable=False),
        sa.Column("lot_id", sa.String(36), sa.ForeignKey("inventory_lot.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=True),
        sa.Column("reserved_qty", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("release_reason", sa.String(260), nullable=True),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("reserved_qty > 0", name="ck_reservation_positive"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "stock_adjustment_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("sku_id", sa.String(36), sa.ForeignKey("inventory_sku.id"), nullable=False),
        sa.Column("lot_id", sa.String(36), sa.ForeignKey("inventory_lot.id"), nullable=False),
        sa.Column("delta_qty", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="pending_dual_approval"
        ),
        sa.Column("requester_staff_id", sa.String(36), nullable=False),
        sa.Column("approver_staff_id", sa.String(36), nullable=True),
        sa.Column("approval_note", sa.String(300), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("delta_qty != 0", name="ck_adj_delta_nonzero"),
    )

    op.create_table(
        "ai_model_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_code", sa.String(80), nullable=False, unique=True),
        sa.Column("version_digest", sa.String(64), nullable=False),
        sa.Column("license_id", sa.String(60), nullable=False),
        sa.Column(
            "data_locality",
            sa.String(40),
            nullable=False,
            server_default="local_loopback_no_egress",
        ),
        sa.Column("purpose", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "ai_draft_artifact",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("model_code", sa.String(80), nullable=False),
        sa.Column("draft_kind", sa.String(40), nullable=False),
        sa.Column(
            "status", sa.String(40), nullable=False, server_default="unreviewed_ai_draft"
        ),
        sa.Column(
            "allergy_state",
            sa.String(40),
            nullable=False,
            server_default="abstained_not_stated",
        ),
        sa.Column("extracted_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("accepted_note_id", sa.String(36), nullable=True),
        sa.Column("reviewed_by_staff_id", sa.String(36), nullable=True),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "ai_evaluation_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("model_code", sa.String(80), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("passed_cases", sa.Integer(), nullable=False),
        sa.Column("extraction_pass_rate_pct", sa.Integer(), nullable=False),
        sa.Column("injection_block_rate_pct", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    bind = op.get_bind()
    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    op.execute(
        sa.text(
            "INSERT INTO schema_migration_meta (revision_id, description, applied_at) "
            "VALUES ('0006_inventory_fhir_and_ai_harness', "
            "'T011 append-only inventory lot ledger & dual control + T012 FHIR R4 & AI safety harness', :ts)"
        ).bindparams(ts=now_iso)
    )
    if bind.dialect.name == "sqlite":
        op.execute(SQLITE_STOCK_MOVEMENT_NO_UPDATE_TRIGGER)
        op.execute(SQLITE_STOCK_MOVEMENT_NO_DELETE_TRIGGER)
        op.execute(SQLITE_STOCK_MOVEMENT_BOUNDS_TRIGGER)


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
