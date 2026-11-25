"""T023 PHI-redacted structured telemetry, isolated per-clinic onboarding configuration,
consent-gated customer support diagnostics, forensic security incident & breach workflow,
and exact-pinning SBOM supply-chain verifier + T024 retention-aware patient subject access
export, FIFO consent-safe cancellation slot recovery, quarantined portal uploads/support,
and staff competency expiry guard.

Revision ID: 0012_telemetry_onboarding_incident_portal_and_hr
Revises: 0011_facility_optimizer_receipts_comms_and_cutover
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0012_telemetry_onboarding_incident_portal_and_hr"
down_revision = "0011_facility_optimizer_receipts_comms_and_cutover"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "redacted_telemetry_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("span_name", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("sanitized_attributes_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("redacted_field_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "contains_phi_or_note_text",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT contains_phi_or_note_text", name="ck_telemetry_no_phi"),
    )

    op.create_table(
        "clinic_onboarding_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("configured_roles_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("catalog_item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quarantined_form_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("legacy_field_mapping_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "readiness_status",
            sa.String(36),
            nullable=False,
            server_default="draft_incomplete",
        ),
        sa.Column("configured_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "version_number", name="uq_onboard_cfg_clinic_ver"),
    )

    op.create_table(
        "customer_support_consent_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("ticket_reference", sa.String(80), nullable=False),
        sa.Column(
            "scope",
            sa.String(48),
            nullable=False,
            server_default="redacted_system_diagnostics_only",
        ),
        sa.Column(
            "allow_live_patient_records",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("granted_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT allow_live_patient_records", name="ck_support_no_live_phi"),
    )

    op.create_table(
        "support_diagnostic_bundle",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "grant_id",
            sa.String(36),
            sa.ForeignKey("customer_support_consent_grant.id"),
            nullable=False,
        ),
        sa.Column("bundle_sha256", sa.String(64), nullable=False),
        sa.Column("diagnostic_summary_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("exported_by_actor", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "security_incident_case",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("incident_type", sa.String(48), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("preserved_audit_head_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("preserved_audit_head_hash", sa.String(64), nullable=False),
        sa.Column(
            "containment_status",
            sa.String(36),
            nullable=False,
            server_default="triaged_evidence_preserved",
        ),
        sa.Column("counsel_guidance_note", sa.String(400), nullable=True),
        sa.Column("notification_decision", sa.String(120), nullable=True),
        sa.Column("opened_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "security_incident_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "incident_id",
            sa.String(36),
            sa.ForeignKey("security_incident_case.id"),
            nullable=False,
        ),
        sa.Column("step_action", sa.String(36), nullable=False),
        sa.Column("detail_note", sa.String(300), nullable=False),
        sa.Column("actor_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "supply_chain_attestation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("python_constraints_sha256", sa.String(64), nullable=False),
        sa.Column("npm_lockfile_sha256", sa.String(64), nullable=False),
        sa.Column("sbom_component_count", sa.Integer(), nullable=False),
        sa.Column("unpinned_dependency_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sbom_canonical_sha256", sa.String(64), nullable=False),
        sa.Column("attestation_hmac_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="verified_pinned"),
        sa.Column("verified_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "patient_access_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("requester_kind", sa.String(32), nullable=False),
        sa.Column("requester_name", sa.String(160), nullable=False),
        sa.Column("request_type", sa.String(36), nullable=False),
        sa.Column("authority_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(36), nullable=False),
        sa.Column("export_sha256", sa.String(64), nullable=True),
        sa.Column("export_payload_json", sa.Text(), nullable=True),
        sa.Column("decision_reason", sa.String(300), nullable=False),
        sa.Column("handled_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "cancellation_recovery_suggestion",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("cancelled_appointment_id", sa.String(36), nullable=False),
        sa.Column("ranked_candidates_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("excluded_no_consent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "clinical_priority_inferred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "NOT clinical_priority_inferred", name="ck_cancel_rec_no_clin_prio"
        ),
        sa.ForeignKeyConstraint(
            ["clinic_id", "cancelled_appointment_id"],
            ["appointment.clinic_id", "appointment.id"],
        ),
    )

    op.create_table(
        "portal_quarantined_upload",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column(
            "portal_grant_id",
            sa.String(36),
            sa.ForeignKey("portal_session_grant.id"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("declared_media_type", sa.String(80), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256_hex", sa.String(64), nullable=False),
        sa.Column(
            "malware_scan_status",
            sa.String(32),
            nullable=False,
            server_default="clean_quarantined",
        ),
        sa.Column(
            "quarantine_status",
            sa.String(36),
            nullable=False,
            server_default="quarantined_pending_review",
        ),
        sa.Column("reviewed_by_staff_id", sa.String(36), nullable=True),
        sa.Column("review_note", sa.String(300), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("byte_size > 0 AND byte_size <= 5242880", name="ck_portal_upload_size"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "portal_support_message",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("message_text", sa.String(500), nullable=False),
        sa.Column("urgency_flag", sa.String(32), nullable=False),
        sa.Column(
            "triage_status",
            sa.String(32),
            nullable=False,
            server_default="queued_for_human",
        ),
        sa.Column(
            "autonomous_medical_advice_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("human_reply_text", sa.String(500), nullable=True),
        sa.Column("responder_staff_id", sa.String(36), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "NOT autonomous_medical_advice_sent", name="ck_portal_msg_no_auto_advice"
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "staff_competency_record",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("staff_id", sa.String(36), nullable=False),
        sa.Column("competency_code", sa.String(60), nullable=False),
        sa.Column("title_vi", sa.String(200), nullable=False),
        sa.Column("expires_on", sa.String(10), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("verified_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id", "staff_id", "competency_code", name="uq_staff_competency_code"
        ),
        sa.ForeignKeyConstraint(["clinic_id", "staff_id"], ["staff.clinic_id", "staff.id"]),
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
                "revision_id": "0012_telemetry_onboarding_incident_portal_and_hr",
                "description": "T023 redacted telemetry/onboarding/support/incidents/SBOM + T024 subject access/slot recovery/portal quarantine/HR competency",
                "applied_at": now_dt,
            }
        ],
    )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
