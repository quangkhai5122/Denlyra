"""T019 optimistic odontogram legend/restoration revisions & external referrals
+ T020 multi-branch scope grants, auto-expiring delegations, staff tasks, handoffs,
contact logs, and restricted service complaints.

Revision ID: 0010_odontogram_referrals_delegation_and_ops
Revises: 0009_encounter_lifecycle_and_clinical_governance
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0010_odontogram_referrals_delegation_and_ops"
down_revision = "0009_encounter_lifecycle_and_clinical_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "odontogram_legend_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("label_vi", sa.String(180), nullable=False),
        sa.Column("symbol_code", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("clinician_reviewed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reviewed_by_staff_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id", "code", "version_number", name="uq_odn_legend_clinic_code_ver"
        ),
    )

    op.create_table(
        "odontogram_restoration_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("tooth_code", sa.String(2), nullable=False),
        sa.Column("current_revision_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("latest_legend_code", sa.String(40), nullable=False),
        sa.Column("latest_legend_version_number", sa.Integer(), nullable=False),
        sa.Column("latest_surface", sa.String(8), nullable=False),
        sa.Column("latest_material_note", sa.String(260), nullable=False),
        sa.Column("latest_source_kind", sa.String(40), nullable=False),
        sa.Column("latest_documented_date", sa.String(10), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id", "patient_id", "tooth_code", name="uq_odn_restoration_patient_tooth"
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "odontogram_restoration_revision",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "state_id",
            sa.String(36),
            sa.ForeignKey("odontogram_restoration_state.id"),
            nullable=False,
        ),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("tooth_code", sa.String(2), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("legend_code", sa.String(40), nullable=False),
        sa.Column("legend_version_number", sa.Integer(), nullable=False),
        sa.Column("surface", sa.String(8), nullable=False),
        sa.Column("material_note", sa.String(260), nullable=False),
        sa.Column("source_kind", sa.String(40), nullable=False),
        sa.Column("documented_date", sa.String(10), nullable=False),
        sa.Column("evidence_note", sa.String(260), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("author_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("state_id", "revision_no", name="uq_odn_restoration_state_rev"),
    )

    op.create_table(
        "external_referral_document",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("origin_facility_name", sa.String(200), nullable=False),
        sa.Column("referring_clinician_name", sa.String(160), nullable=False),
        sa.Column("referral_date", sa.String(10), nullable=False),
        sa.Column("document_summary_vi", sa.String(300), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("archive_object_id", sa.String(36), nullable=True),
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default="quarantined_unreviewed",
        ),
        sa.Column("reviewed_by_staff_id", sa.String(36), nullable=True),
        sa.Column("review_note", sa.String(300), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "owner_branch_scope_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_group_key", sa.String(80), nullable=False),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False, server_default="branch-main"),
        sa.Column("granted_by_staff_id", sa.String(36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "owner_group_key", "clinic_id", "branch_id", name="uq_owner_group_clinic_branch"
        ),
    )

    op.create_table(
        "temporary_delegation_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("granter_staff_id", sa.String(36), nullable=False),
        sa.Column("delegate_staff_id", sa.String(36), nullable=False),
        sa.Column("permission", sa.String(60), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinic_id", "delegate_staff_id"], ["staff.clinic_id", "staff.id"]
        ),
    )

    op.create_table(
        "staff_operational_task",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("assignee_staff_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column(
            "escalation_owner_role",
            sa.String(32),
            nullable=False,
            server_default="clinic_owner",
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinic_id", "assignee_staff_id"], ["staff.clinic_id", "staff.id"]
        ),
    )

    op.create_table(
        "staff_operational_task_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("staff_operational_task.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("note", sa.String(260), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "internal_handoff_note",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=True),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("message_vi", sa.String(400), nullable=False),
        sa.Column("author_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "patient_contact_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("visibility", sa.String(32), nullable=False),
        sa.Column("summary_text", sa.String(300), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "service_complaint_case",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("public_intake_summary", sa.String(300), nullable=False),
        sa.Column("private_investigation_notes", sa.String(600), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    op.execute(
        sa.text(
            "INSERT INTO schema_migration_meta (revision_id, description, applied_at) "
            "VALUES ('0010_odontogram_referrals_delegation_and_ops', "
            "'T019 odontogram revisions/referrals/export + T020 multi-branch/delegation/handoffs/complaints/ops assistant', :ts)"
        ).bindparams(ts=now_iso)
    )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
