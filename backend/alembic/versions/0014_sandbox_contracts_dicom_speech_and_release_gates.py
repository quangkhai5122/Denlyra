"""T027 policy-governed cancellation outreach, reproducible local load benchmark,
OIDC directory group mapping & immediate revocation, consent/opt-out messaging sandbox,
and HMAC-signed payment webhook replay protection & reversals + T028 DICOM modality &
patient-ID quarantine gateway, audio-consented speech transcription drafts, PHI-free
accounting exports, and adversarial security & fail-closed PHI release gates.

Revision ID: 0014_sandbox_contracts_dicom_speech_and_release_gates
Revises: 0013_terminology_templates_lab_reports_sync_and_ai
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0014_sandbox_contracts_dicom_speech_and_release_gates"
down_revision = "0013_terminology_templates_lab_reports_sync_and_ai"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cancellation_outreach_policy",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("policy_code", sa.String(60), nullable=False),
        sa.Column("max_candidates_per_slot", sa.Integer(), nullable=False),
        sa.Column("require_marketing_consent", sa.Boolean(), nullable=False),
        sa.Column("prioritization_mode", sa.String(40), nullable=False),
        sa.Column("clinical_triage_inferred", sa.Boolean(), nullable=False),
        sa.Column("auto_book_without_confirmation", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(36), nullable=False),
        sa.Column("approved_by_staff_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "prioritization_mode = 'fifo_waitlist_only'", name="ck_cancel_pol_fifo_only"
        ),
        sa.CheckConstraint("NOT clinical_triage_inferred", name="ck_cancel_pol_no_triage"),
        sa.CheckConstraint(
            "NOT auto_book_without_confirmation", name="ck_cancel_pol_no_autobook"
        ),
        sa.UniqueConstraint("clinic_id", "policy_code", name="uq_cancel_pol_clinic_code"),
    )

    op.create_table(
        "cancellation_outreach_batch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("appointment_id", sa.String(36), nullable=False),
        sa.Column(
            "policy_id",
            sa.String(36),
            sa.ForeignKey("cancellation_outreach_policy.id"),
            nullable=False,
        ),
        sa.Column("queued_count", sa.Integer(), nullable=False),
        sa.Column("candidates_json", sa.Text(), nullable=False),
        sa.Column("clinical_triage_inferred", sa.Boolean(), nullable=False),
        sa.Column("auto_booked", sa.Boolean(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT clinical_triage_inferred", name="ck_cancel_batch_no_triage"),
        sa.CheckConstraint("NOT auto_booked", name="ck_cancel_batch_no_autobook"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "appointment_id"],
            ["appointment.clinic_id", "appointment.id"],
        ),
    )

    op.create_table(
        "load_benchmark_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("workload_profile", sa.String(48), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("p50_latency_us", sa.Integer(), nullable=False),
        sa.Column("p95_latency_us", sa.Integer(), nullable=False),
        sa.Column("max_latency_us", sa.Integer(), nullable=False),
        sa.Column("throughput_ops_per_sec", sa.Integer(), nullable=False),
        sa.Column("environment_label", sa.String(64), nullable=False),
        sa.Column("claims_production_sla", sa.Boolean(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("iterations > 0", name="ck_bench_positive_iters"),
        sa.CheckConstraint("NOT claims_production_sla", name="ck_bench_no_sla_claim"),
    )

    op.create_table(
        "oidc_group_mapping_rule",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("idp_issuer", sa.String(200), nullable=False),
        sa.Column("external_group_id", sa.String(120), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("mapped_role", sa.String(30), nullable=False),
        sa.Column("created_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id",
            "idp_issuer",
            "external_group_id",
            name="uq_oidc_map_clinic_iss_grp",
        ),
    )

    op.create_table(
        "oidc_directory_sync_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("idp_issuer", sa.String(200), nullable=False),
        sa.Column("staff_id", sa.String(36), nullable=False),
        sa.Column("external_subject", sa.String(120), nullable=False),
        sa.Column("sync_outcome", sa.String(48), nullable=False),
        sa.Column("resulting_token_version", sa.Integer(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "staff_id"], ["staff.clinic_id", "staff.id"]),
    )

    op.create_table(
        "messaging_channel_preference",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("opted_out", sa.Boolean(), nullable=False),
        sa.Column("last_keyword", sa.String(32), nullable=True),
        sa.Column("provider_event_id", sa.String(80), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id", "patient_id", "channel", name="uq_msg_pref_clinic_pat_chan"
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "messaging_sandbox_dispatch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(36), nullable=False),
        sa.Column("template_code", sa.String(60), nullable=False),
        sa.Column("rendered_body_minimized", sa.String(320), nullable=False),
        sa.Column("delivery_state", sa.String(48), nullable=False),
        sa.Column("patient_confirmed_appointment", sa.Boolean(), nullable=False),
        sa.Column("zero_external_egress", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "NOT patient_confirmed_appointment", name="ck_msg_no_confirmed_infer"
        ),
        sa.CheckConstraint("zero_external_egress", name="ck_msg_zero_egress"),
        sa.UniqueConstraint("clinic_id", "idempotency_key", name="uq_msg_sbx_clinic_idem"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "payment_webhook_inbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("provider_code", sa.String(60), nullable=False),
        sa.Column("provider_event_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("payment_id", sa.String(36), nullable=True),
        sa.Column("refund_id", sa.String(36), nullable=True),
        sa.Column("implies_clinical_completion", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_vnd > 0", name="ck_pay_wh_positive_vnd"),
        sa.CheckConstraint(
            "NOT implies_clinical_completion", name="ck_pay_wh_no_clinical_infer"
        ),
        sa.UniqueConstraint(
            "clinic_id",
            "provider_code",
            "provider_event_id",
            name="uq_pay_wh_clinic_prov_evt",
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "dicom_modality_registration",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("ae_title", sa.String(32), nullable=False),
        sa.Column("modality_code", sa.String(24), nullable=False),
        sa.Column("device_label", sa.String(160), nullable=False),
        sa.Column("confirmed_for_clinic", sa.Boolean(), nullable=False),
        sa.Column("registered_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "ae_title", name="uq_dicom_mod_clinic_ae"),
    )

    op.create_table(
        "dicom_study_quarantine_manifest",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column(
            "modality_id",
            sa.String(36),
            sa.ForeignKey("dicom_modality_registration.id"),
            nullable=False,
        ),
        sa.Column("study_instance_uid", sa.String(128), nullable=False),
        sa.Column("dicom_patient_id_tag", sa.String(64), nullable=False),
        sa.Column("series_count", sa.Integer(), nullable=False),
        sa.Column("instance_count", sa.Integer(), nullable=False),
        sa.Column("study_sha256", sa.String(64), nullable=False),
        sa.Column("viewer_mode", sa.String(48), nullable=False),
        sa.Column("diagnostic_samd_certified", sa.Boolean(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT diagnostic_samd_certified", name="ck_dicom_no_samd_cert"),
        sa.UniqueConstraint(
            "clinic_id", "study_instance_uid", name="uq_dicom_study_clinic_uid"
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "speech_transcription_draft",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("audio_sha256", sa.String(64), nullable=False),
        sa.Column("audio_consent_verified", sa.Boolean(), nullable=False),
        sa.Column("transcript_draft_vi", sa.Text(), nullable=False),
        sa.Column("matched_terms_json", sa.Text(), nullable=False),
        sa.Column("terminology_benchmark_score_bp", sa.Integer(), nullable=False),
        sa.Column("wrote_to_emr", sa.Boolean(), nullable=False),
        sa.Column("zero_external_egress", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("audio_consent_verified", name="ck_speech_audio_consent_req"),
        sa.CheckConstraint("NOT wrote_to_emr", name="ck_speech_no_emr_write"),
        sa.CheckConstraint("zero_external_egress", name="ck_speech_zero_egress"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "accounting_export_batch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("period_label", sa.String(32), nullable=False),
        sa.Column("provider_profile", sa.String(64), nullable=False),
        sa.Column("total_charged_vnd", sa.Integer(), nullable=False),
        sa.Column("total_collected_vnd", sa.Integer(), nullable=False),
        sa.Column("total_refunded_vnd", sa.Integer(), nullable=False),
        sa.Column("ledger_entry_count", sa.Integer(), nullable=False),
        sa.Column("canonical_sha256", sa.String(64), nullable=False),
        sa.Column("contains_phi", sa.Boolean(), nullable=False),
        sa.Column("official_tax_invoice_issued", sa.Boolean(), nullable=False),
        sa.Column("called_government_api", sa.Boolean(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT contains_phi", name="ck_acct_no_phi"),
        sa.CheckConstraint(
            "NOT official_tax_invoice_issued", name="ck_acct_no_official_tax"
        ),
        sa.CheckConstraint("NOT called_government_api", name="ck_acct_no_gov_api"),
    )

    op.create_table(
        "adversarial_security_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("ssrf_probes_blocked", sa.Integer(), nullable=False),
        sa.Column("traversal_probes_blocked", sa.Integer(), nullable=False),
        sa.Column("all_vectors_blocked", sa.Boolean(), nullable=False),
        sa.Column("independent_external_pentest_complete", sa.Boolean(), nullable=False),
        sa.Column("report_sha256", sa.String(64), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "NOT independent_external_pentest_complete",
            name="ck_adv_sec_no_fake_pentest",
        ),
    )

    op.create_table(
        "release_gate_evaluation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("target_environment", sa.String(32), nullable=False),
        sa.Column("gate_status", sa.String(48), nullable=False),
        sa.Column("phi_processing_enabled", sa.Boolean(), nullable=False),
        sa.Column("open_blockers_json", sa.Text(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT phi_processing_enabled", name="ck_rel_gate_no_phi_enabled"),
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(
        sa.table(
            "schema_migration_meta",
            sa.column("revision_id", sa.String),
            sa.column("description", sa.String),
            sa.column("applied_at", sa.DateTime),
        ),
        [
            {
                "revision_id": revision,
                "description": "T027 sandbox provider contracts, load benchmark & OIDC sync + T028 DICOM quarantine, speech consent, accounting & PHI release gates",
                "applied_at": now,
            }
        ],
    )


def downgrade():
    op.execute(
        sa.text("DELETE FROM schema_migration_meta WHERE revision_id = :rev").bindparams(
            rev=revision
        )
    )
    op.drop_table("release_gate_evaluation")
    op.drop_table("adversarial_security_run")
    op.drop_table("accounting_export_batch")
    op.drop_table("speech_transcription_draft")
    op.drop_table("dicom_study_quarantine_manifest")
    op.drop_table("dicom_modality_registration")
    op.drop_table("payment_webhook_inbox")
    op.drop_table("messaging_sandbox_dispatch")
    op.drop_table("messaging_channel_preference")
    op.drop_table("oidc_directory_sync_event")
    op.drop_table("oidc_group_mapping_rule")
    op.drop_table("load_benchmark_run")
    op.drop_table("cancellation_outreach_batch")
    op.drop_table("cancellation_outreach_policy")
