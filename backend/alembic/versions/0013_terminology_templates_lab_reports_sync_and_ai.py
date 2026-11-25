"""T025 versioned medical code sets & exact mappings, clinic-reviewed specialty plan
templates, PHI-free lab vendor price list & invoice reconciliation, labeled longitudinal
imaging overlays, and DLY1-encrypted PHI-free scheduled report exports + T026 canary
release approvals, multi-branch operator scopes, conflict-safe offline sync, and
fair calibrated no-show risk + timeout-safe CP-SAT scheduling optimization.

Revision ID: 0013_terminology_templates_lab_reports_sync_and_ai
Revises: 0012_telemetry_onboarding_incident_portal_and_hr
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0013_terminology_templates_lab_reports_sync_and_ai"
down_revision = "0012_telemetry_onboarding_incident_portal_and_hr"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "terminology_code_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("code_system", sa.String(40), nullable=False),
        sa.Column("system_version", sa.String(30), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("display_vi", sa.String(240), nullable=False),
        sa.Column("approved_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id",
            "code_system",
            "system_version",
            "code",
            name="uq_term_code_clinic_sys_ver_code",
        ),
    )

    op.create_table(
        "terminology_mapping_rule",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("source_code", sa.String(60), nullable=False),
        sa.Column("target_code_system", sa.String(40), nullable=False),
        sa.Column("target_system_version", sa.String(30), nullable=False),
        sa.Column("target_code", sa.String(60), nullable=False),
        sa.Column("equivalence", sa.String(24), nullable=False),
        sa.Column(
            "mapping_method",
            sa.String(40),
            nullable=False,
            server_default="clinician_verified_exact",
        ),
        sa.Column("reviewed_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "mapping_method = 'clinician_verified_exact'",
            name="ck_term_no_guessed_map",
        ),
        sa.UniqueConstraint(
            "clinic_id",
            "source_code",
            "target_code_system",
            name="uq_term_map_clinic_src_sys",
        ),
    )

    op.create_table(
        "specialty_plan_template",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("template_code", sa.String(60), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("specialty", sa.String(40), nullable=False),
        sa.Column("title_vi", sa.String(200), nullable=False),
        sa.Column("tasks_blueprint_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "source_kind",
            sa.String(40),
            nullable=False,
            server_default="clinic_clinician_authored",
        ),
        sa.Column(
            "review_status",
            sa.String(36),
            nullable=False,
            server_default="draft_unreviewed",
        ),
        sa.Column("reviewed_by_staff_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id",
            "template_code",
            "version_number",
            name="uq_spec_tpl_clinic_code_ver",
        ),
    )

    op.create_table(
        "lab_vendor_price_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("vendor_code", sa.String(60), nullable=False),
        sa.Column("prosthesis_code", sa.String(60), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price_vnd", sa.Integer(), nullable=False),
        sa.Column("remake_surcharge_vnd", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("unit_price_vnd > 0", name="ck_lab_price_unit_pos"),
        sa.CheckConstraint("remake_surcharge_vnd >= 0", name="ck_lab_price_remake_nonneg"),
        sa.UniqueConstraint(
            "clinic_id",
            "vendor_code",
            "prosthesis_code",
            "version_number",
            name="uq_lab_vendor_price_ver",
        ),
    )

    op.create_table(
        "lab_invoice_reconciliation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("lab_case_id", sa.String(36), sa.ForeignKey("lab_case.id"), nullable=False),
        sa.Column("vendor_code", sa.String(60), nullable=False),
        sa.Column("prosthesis_code", sa.String(60), nullable=False),
        sa.Column("vendor_invoice_ref", sa.String(80), nullable=False),
        sa.Column("price_version_number", sa.Integer(), nullable=False),
        sa.Column("contracted_amount_vnd", sa.Integer(), nullable=False),
        sa.Column("billed_amount_vnd", sa.Integer(), nullable=False),
        sa.Column("variance_vnd", sa.Integer(), nullable=False),
        sa.Column("reconciliation_status", sa.String(32), nullable=False),
        sa.Column("sanitized_vendor_payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("contains_phi", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT contains_phi", name="ck_lab_inv_no_phi"),
    )

    op.create_table(
        "longitudinal_imaging_overlay",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("tooth_code", sa.String(2), nullable=False),
        sa.Column(
            "baseline_archive_object_id",
            sa.String(36),
            sa.ForeignKey("archive_object.id"),
            nullable=False,
        ),
        sa.Column(
            "followup_archive_object_id",
            sa.String(36),
            sa.ForeignKey("archive_object.id"),
            nullable=False,
        ),
        sa.Column("alignment_label_vi", sa.String(260), nullable=False),
        sa.Column(
            "visualization_provenance_label",
            sa.String(64),
            nullable=False,
            server_default="SYNTHETIC_VISUAL_COMPARISON_NOT_DIAGNOSTIC",
        ),
        sa.Column(
            "auto_diagnosis_generated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT auto_diagnosis_generated", name="ck_overlay_no_auto_diag"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "scheduled_report_export",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("owner_group_key", sa.String(80), nullable=True),
        sa.Column("report_kind", sa.String(40), nullable=False),
        sa.Column("recipient_email", sa.String(160), nullable=False),
        sa.Column("include_phi", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "key_id",
            sa.String(36),
            sa.ForeignKey("tenant_encryption_key.id"),
            nullable=False,
        ),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("encrypted_envelope_b64", sa.Text(), nullable=False),
        sa.Column("plaintext_sha256", sa.String(64), nullable=False),
        sa.Column("ciphertext_sha256", sa.String(64), nullable=False),
        sa.Column("exported_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT include_phi", name="ck_rpt_export_no_phi"),
    )

    op.create_table(
        "release_change_approval",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("release_tag", sa.String(60), nullable=False),
        sa.Column("target_migration_revision", sa.String(80), nullable=False),
        sa.Column("canary_stage", sa.String(32), nullable=False, server_default="pre_canary"),
        sa.Column(
            "backward_compatible_schema",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("forward_fix_and_backup_plan", sa.String(400), nullable=False),
        sa.Column("proposer_staff_id", sa.String(36), nullable=False),
        sa.Column("approver_staff_id", sa.String(36), nullable=True),
        sa.Column(
            "status",
            sa.String(36),
            nullable=False,
            server_default="pending_change_approval",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("backward_compatible_schema", name="ck_release_backward_compat"),
    )

    op.create_table(
        "multibranch_operator_assignment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_group_key", sa.String(80), nullable=False),
        sa.Column("operator_staff_id", sa.String(36), nullable=False),
        sa.Column("home_clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("assigned_clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "operational_scope",
            sa.String(48),
            nullable=False,
            server_default="aggregate_kpi_and_ops_read_only",
        ),
        sa.Column(
            "grants_clinical_chart_access",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("granted_by_staff_id", sa.String(36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "NOT grants_clinical_chart_access", name="ck_mb_op_no_chart_bleed"
        ),
    )

    op.create_table(
        "offline_sync_mutation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("client_mutation_id", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column(
            "resolution_strategy",
            sa.String(40),
            nullable=False,
            server_default="optimistic_version_check",
        ),
        sa.Column("sync_status", sa.String(36), nullable=False),
        sa.Column("conflict_reason", sa.String(260), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "resolution_strategy = 'optimistic_version_check'",
            name="ck_offline_no_lww",
        ),
        sa.UniqueConstraint("clinic_id", "client_mutation_id", name="uq_offline_mut_client_id"),
    )

    op.create_table(
        "noshow_risk_assessment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=False),
        sa.Column("risk_band", sa.String(32), nullable=False),
        sa.Column("calibrated_probability_bp", sa.Integer(), nullable=False),
        sa.Column(
            "uses_protected_demographics",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "auto_cancelled_or_overbooked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("recommended_human_action", sa.String(260), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT uses_protected_demographics", name="ck_noshow_fairness"),
        sa.CheckConstraint(
            "NOT auto_cancelled_or_overbooked", name="ck_noshow_no_auto_cancel"
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id"],
            ["appointment.clinic_id", "appointment.id"],
        ),
    )

    op.create_table(
        "cpsat_optimization_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("solver_budget_ms", sa.Integer(), nullable=False),
        sa.Column("solver_outcome", sa.String(48), nullable=False),
        sa.Column("proposed_assignments_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "existing_bookings_mutated_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "existing_bookings_mutated_count = 0", name="ck_cpsat_zero_auto_mutation"
        ),
    )

    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    op.execute(
        sa.text(
            "INSERT INTO schema_migration_meta (revision_id, description, applied_at) "
            "VALUES ('0013_terminology_templates_lab_reports_sync_and_ai', "
            "'T025 terminology/specialty templates/lab billing/overlays/reports + T026 canary release/offline sync/scheduling AI', :ts)"
        ).bindparams(ts=now_iso)
    )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
