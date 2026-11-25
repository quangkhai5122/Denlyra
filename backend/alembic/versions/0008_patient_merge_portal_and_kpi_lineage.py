"""T015 reversible patient merge, short-TTL break-glass, and clinician-published patient portal
+ T016 versioned service price catalog, estimate price snapshots, and dual-control discount requests.

Revision ID: 0008_patient_merge_portal_and_kpi_lineage
Revises: 0007_operations_audit_chain_and_pagination
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0008_patient_merge_portal_and_kpi_lineage"
down_revision = "0007_operations_audit_chain_and_pagination"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "patient_merge_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("primary_patient_id", sa.String(36), nullable=False),
        sa.Column("secondary_patient_id", sa.String(36), nullable=False),
        sa.Column("rationale", sa.String(300), nullable=False),
        sa.Column("contradictions_noted", sa.String(300), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending_second_confirmation",
        ),
        sa.Column("requester_staff_id", sa.String(36), nullable=False),
        sa.Column("approver_staff_id", sa.String(36), nullable=True),
        sa.Column("confirmation_note", sa.String(300), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("reversal_reason", sa.String(300), nullable=True),
        sa.Column("reversed_by_staff_id", sa.String(36), nullable=True),
        sa.Column("reversed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "primary_patient_id != secondary_patient_id", name="ck_merge_distinct_patients"
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "primary_patient_id"], ["patient.clinic_id", "patient.id"]
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "secondary_patient_id"], ["patient.clinic_id", "patient.id"]
        ),
    )

    op.create_table(
        "break_glass_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("requester_staff_id", sa.String(36), nullable=False),
        sa.Column("requester_role", sa.String(32), nullable=False),
        sa.Column("emergency_reason", sa.String(300), nullable=False),
        sa.Column("granted_permissions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default="pending_independent_review",
        ),
        sa.Column("reviewer_staff_id", sa.String(36), nullable=True),
        sa.Column("review_notes", sa.String(300), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "portal_session_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("actor_kind", sa.String(20), nullable=False, server_default="self"),
        sa.Column("actor_display_name", sa.String(160), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "portal_published_instruction",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("title_vi", sa.String(180), nullable=False),
        sa.Column("body_vi", sa.Text(), nullable=False),
        sa.Column("published_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "portal_published_plan_summary",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("treatment_plan.id"), nullable=False),
        sa.Column("plan_version_number", sa.Integer(), nullable=False),
        sa.Column("lay_summary_vi", sa.Text(), nullable=False),
        sa.Column("published_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "portal_reschedule_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=False),
        sa.Column("requested_start_at", sa.DateTime(), nullable=False),
        sa.Column("requested_end_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.String(260), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending_staff_validation",
        ),
        sa.Column("resolved_appointment_id", sa.String(36), nullable=True),
        sa.Column("resolved_by_staff_id", sa.String(36), nullable=True),
        sa.Column("resolution_note", sa.String(260), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "requested_end_at > requested_start_at", name="ck_portal_reschedule_range"
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]
        ),
    )

    op.create_table(
        "portal_intake_submission",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("form_code", sa.String(60), nullable=False),
        sa.Column("form_version", sa.String(30), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "provenance", sa.String(40), nullable=False, server_default="patient_portal_intake"
        ),
        sa.Column("legal_consent_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "review_status", sa.String(32), nullable=False, server_default="pending_staff_review"
        ),
        sa.Column("submitted_by_actor", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "service_price_catalog_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("service_code", sa.String(60), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name_vi", sa.String(200), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("unit_price_vnd", sa.Integer(), nullable=False),
        sa.Column("max_auto_discount_pct", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("unit_price_vnd > 0", name="ck_catalog_price_positive"),
        sa.CheckConstraint(
            "max_auto_discount_pct BETWEEN 0 AND 100", name="ck_catalog_discount_bounds"
        ),
        sa.UniqueConstraint(
            "clinic_id", "service_code", "version_number", name="uq_catalog_clinic_code_version"
        ),
    )

    op.create_table(
        "estimate_price_snapshot",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "estimate_id", sa.String(36), sa.ForeignKey("estimate_version.id"), nullable=False
        ),
        sa.Column(
            "catalog_item_id",
            sa.String(36),
            sa.ForeignKey("service_price_catalog_item.id"),
            nullable=False,
        ),
        sa.Column("service_code", sa.String(60), nullable=False),
        sa.Column("catalog_version_number", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("locked_unit_price_vnd", sa.Integer(), nullable=False),
        sa.Column("line_total_vnd", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_est_line_qty_positive"),
        sa.CheckConstraint("locked_unit_price_vnd > 0", name="ck_est_line_unit_positive"),
    )

    op.create_table(
        "discount_approval_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column(
            "estimate_id", sa.String(36), sa.ForeignKey("estimate_version.id"), nullable=False
        ),
        sa.Column("original_amount_vnd", sa.Integer(), nullable=False),
        sa.Column("discount_amount_vnd", sa.Integer(), nullable=False),
        sa.Column("discount_pct_bp", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requester_staff_id", sa.String(36), nullable=False),
        sa.Column("approver_staff_id", sa.String(36), nullable=True),
        sa.Column("decision_note", sa.String(300), nullable=True),
        sa.Column("resulting_estimate_id", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "discount_amount_vnd > 0 AND discount_amount_vnd < original_amount_vnd",
            name="ck_discount_bounds",
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
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
                "revision_id": "0008_patient_merge_portal_and_kpi_lineage",
                "description": "T015 reversible patient merge/break-glass/portal + T016 price catalog/discount/KPI lineage",
                "applied_at": now_dt,
            }
        ],
    )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
