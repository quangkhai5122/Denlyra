"""T021 licensed facility metadata, procedure duration templates, non-mutating
slot optimizer, traceable financial receipt exports, and timezone-correct staff
attendance/overtime + T022 reviewed reminder templates, consent-gated communication
drafts, decoupled anonymous satisfaction survey, and incumbent migration cutover.

Revision ID: 0011_facility_optimizer_receipts_comms_and_cutover
Revises: 0010_odontogram_referrals_delegation_and_ops
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0011_facility_optimizer_receipts_comms_and_cutover"
down_revision = "0010_odontogram_referrals_delegation_and_ops"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "facility_license_profile",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("legal_entity_name_demo", sa.String(200), nullable=False),
        sa.Column("license_number_demo", sa.String(80), nullable=False),
        sa.Column("license_type", sa.String(40), nullable=False),
        sa.Column("permitted_scopes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("regulating_authority_demo", sa.String(160), nullable=False),
        sa.Column(
            "verification_status",
            sa.String(40),
            nullable=False,
            server_default="unverified_synthetic",
        ),
        sa.Column("updated_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id", "version_number", name="uq_facility_profile_clinic_ver"
        ),
    )

    op.create_table(
        "procedure_duration_template",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("procedure_code", sa.String(60), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title_vi", sa.String(180), nullable=False),
        sa.Column("recommended_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallback_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("approved_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("recommended_minutes >= 15", name="ck_proc_dur_rec_min"),
        sa.CheckConstraint("buffer_minutes >= 0", name="ck_proc_dur_buf_min"),
        sa.UniqueConstraint(
            "clinic_id",
            "procedure_code",
            "version_number",
            name="uq_proc_dur_clinic_code_ver",
        ),
    )

    op.create_table(
        "schedule_optimizer_proposal",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("practitioner_id", sa.String(36), nullable=False),
        sa.Column("chair_id", sa.String(36), nullable=False),
        sa.Column("procedure_code", sa.String(60), nullable=False),
        sa.Column("window_start_at", sa.DateTime(), nullable=False),
        sa.Column("window_end_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("proposed_slots_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "solver_engine",
            sa.String(48),
            nullable=False,
            server_default="deterministic_constraint_grid_v1",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="proposed_pending_human",
        ),
        sa.Column("accepted_appointment_id", sa.String(36), nullable=True),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("window_end_at > window_start_at", name="ck_opt_prop_window"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "financial_receipt_export",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payment.id"), nullable=False),
        sa.Column("receipt_number", sa.String(64), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(24), nullable=False),
        sa.Column("allocated_charges_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("ledger_entry_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("export_note", sa.String(260), nullable=False, server_default=""),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("signature_hmac_sha256", sa.String(64), nullable=False),
        sa.Column(
            "synthetic_non_bank_receipt",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("exported_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_vnd > 0", name="ck_receipt_export_positive"),
        sa.UniqueConstraint("clinic_id", "receipt_number", name="uq_receipt_export_clinic_num"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "staff_attendance_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("staff_id", sa.String(36), nullable=False),
        sa.Column("check_in_at", sa.DateTime(), nullable=False),
        sa.Column("check_out_at", sa.DateTime(), nullable=False),
        sa.Column("local_date_hcm", sa.String(10), nullable=False),
        sa.Column("worked_minutes", sa.Integer(), nullable=False),
        sa.Column("regular_minutes", sa.Integer(), nullable=False),
        sa.Column("overtime_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "standard_daily_limit_minutes",
            sa.Integer(),
            nullable=False,
            server_default="480",
        ),
        sa.Column("note", sa.String(260), nullable=False, server_default=""),
        sa.Column("recorded_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("check_out_at > check_in_at", name="ck_attendance_valid_range"),
        sa.CheckConstraint("worked_minutes > 0", name="ck_attendance_worked_positive"),
        sa.ForeignKeyConstraint(["clinic_id", "staff_id"], ["staff.clinic_id", "staff.id"]),
    )

    op.create_table(
        "reminder_template_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("template_code", sa.String(60), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("purpose_category", sa.String(32), nullable=False),
        sa.Column("body_template_vi", sa.String(400), nullable=False),
        sa.Column("window_start_hour_hcm", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("window_end_hour_hcm", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("reviewed_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "window_end_hour_hcm > window_start_hour_hcm", name="ck_rem_tpl_window"
        ),
        sa.UniqueConstraint(
            "clinic_id", "template_code", "version_number", name="uq_rem_tpl_clinic_code_ver"
        ),
    )

    op.create_table(
        "communication_draft_record",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("reminder_template_version.id"),
            nullable=False,
        ),
        sa.Column("template_version_number", sa.Integer(), nullable=False),
        sa.Column("purpose_category", sa.String(32), nullable=False),
        sa.Column("proposed_send_hour_hcm", sa.Integer(), nullable=False),
        sa.Column("rendered_draft_text", sa.Text(), nullable=False),
        sa.Column("escalation_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="draft_pending_staff_review",
        ),
        sa.Column("drafted_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT auto_sent", name="ck_comm_draft_no_auto_send"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "satisfaction_token_receipt",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("token_sha256", sa.String(64), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "token_sha256", name="uq_satisfaction_token_once"),
    )

    op.create_table(
        "patient_satisfaction_response",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("service_month", sa.String(7), nullable=False),
        sa.Column("overall_rating", sa.Integer(), nullable=False),
        sa.Column("wait_time_rating", sa.Integer(), nullable=False),
        sa.Column("clarity_rating", sa.Integer(), nullable=False),
        sa.Column("sanitized_comment", sa.String(400), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("overall_rating BETWEEN 1 AND 5", name="ck_sat_overall_1_5"),
        sa.CheckConstraint("wait_time_rating BETWEEN 1 AND 5", name="ck_sat_wait_1_5"),
        sa.CheckConstraint("clarity_rating BETWEEN 1 AND 5", name="ck_sat_clarity_1_5"),
    )

    op.create_table(
        "incumbent_export_package",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("source_vendor_code", sa.String(60), nullable=False),
        sa.Column("schema_version", sa.String(30), nullable=False),
        sa.Column("export_license_note", sa.String(300), nullable=False),
        sa.Column("declared_sha256", sa.String(64), nullable=False),
        sa.Column("computed_sha256", sa.String(64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("total_balance_vnd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "validation_status",
            sa.String(32),
            nullable=False,
            server_default="quarantined_verified",
        ),
        sa.Column(
            "review_status",
            sa.String(36),
            nullable=False,
            server_default="pending_reviewer_signoff",
        ),
        sa.Column("uploader_staff_id", sa.String(36), nullable=False),
        sa.Column("reviewer_staff_id", sa.String(36), nullable=True),
        sa.Column("review_note", sa.String(300), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id",
            "source_vendor_code",
            "declared_sha256",
            name="uq_incumbent_pkg_clinic_vendor_sha",
        ),
    )

    op.create_table(
        "migration_cutover_plan",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "incumbent_package_id",
            sa.String(36),
            sa.ForeignKey("incumbent_export_package.id"),
            nullable=False,
        ),
        sa.Column("cutover_mode", sa.String(36), nullable=False),
        sa.Column(
            "legacy_write_freeze_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("reconciled_patient_count", sa.Integer(), nullable=False),
        sa.Column("reconciled_total_balance_vnd", sa.Integer(), nullable=False),
        sa.Column(
            "double_entry_guard_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("rollback_runbook_note", sa.String(300), nullable=False),
        sa.Column("approved_by_staff_id", sa.String(36), nullable=False),
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
                "revision_id": "0011_facility_optimizer_receipts_comms_and_cutover",
                "description": "T021 facility licensing/optimizer/receipts/HR + T022 reviewed comms/satisfaction/cutover",
                "applied_at": now_dt,
            }
        ],
    )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
