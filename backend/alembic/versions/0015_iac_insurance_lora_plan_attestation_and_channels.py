"""T029 Vietnam-region IaC blueprint & secret guard, partner dental insurance claim
sandbox, licensed de-identified LoRA lift gate, and clinician treatment plan simulation
attestation + T030 channel-specific Zalo OA/ZNS, SMS DLR, and SPF/DKIM/DMARC Email
rate-limited sandbox contracts.

Revision ID: 0015_iac_insurance_lora_plan_attestation_and_channels
Revises: 0014_sandbox_contracts_dicom_speech_and_release_gates
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0015_iac_insurance_lora_plan_attestation_and_channels"
down_revision = "0014_sandbox_contracts_dicom_speech_and_release_gates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "iac_blueprint_validation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("blueprint_name", sa.String(120), nullable=False),
        sa.Column("primary_region", sa.String(48), nullable=False),
        sa.Column("dpa_contract_reference", sa.String(80), nullable=False),
        sa.Column("secrets_externalized", sa.Boolean(), nullable=False),
        sa.Column("live_cloud_provisioned", sa.Boolean(), nullable=False),
        sa.Column("blueprint_sha256", sa.String(64), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("secrets_externalized", name="ck_iac_secrets_external"),
        sa.CheckConstraint("NOT live_cloud_provisioned", name="ck_iac_no_live_provision"),
    )

    op.create_table(
        "insurance_partner_contract",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("partner_code", sa.String(60), nullable=False),
        sa.Column("partner_name", sa.String(160), nullable=False),
        sa.Column("integration_kind", sa.String(40), nullable=False),
        sa.Column("contract_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "integration_kind = 'private_dental_tpa_sandbox'", name="ck_ins_no_gov_bhyt"
        ),
        sa.UniqueConstraint("clinic_id", "partner_code", name="uq_ins_partner_clinic_code"),
    )

    op.create_table(
        "insurance_claim_draft",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column(
            "partner_id",
            sa.String(36),
            sa.ForeignKey("insurance_partner_contract.id"),
            nullable=False,
        ),
        sa.Column("charge_id", sa.String(36), nullable=False),
        sa.Column("claimed_amount_vnd", sa.Integer(), nullable=False),
        sa.Column("claim_status", sa.String(48), nullable=False),
        sa.Column("auto_settled_payment", sa.Boolean(), nullable=False),
        sa.Column("called_government_bhyt_api", sa.Boolean(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("claimed_amount_vnd > 0", name="ck_ins_claim_positive_vnd"),
        sa.CheckConstraint("NOT auto_settled_payment", name="ck_ins_claim_no_autosettle"),
        sa.CheckConstraint("NOT called_government_bhyt_api", name="ck_ins_claim_no_bhyt_api"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        sa.ForeignKeyConstraint(["clinic_id", "charge_id"], ["charge.clinic_id", "charge.id"]),
    )

    op.create_table(
        "ai_adaptation_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("adapter_code", sa.String(80), nullable=False),
        sa.Column("base_model_digest", sa.String(80), nullable=False),
        sa.Column("dataset_license_id", sa.String(80), nullable=False),
        sa.Column("deidentification_verified", sa.Boolean(), nullable=False),
        sa.Column("baseline_f1_bp", sa.Integer(), nullable=False),
        sa.Column("candidate_f1_bp", sa.Integer(), nullable=False),
        sa.Column("measured_lift_bp", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("deployed_to_clinical_production", sa.Boolean(), nullable=False),
        sa.Column("wrote_to_emr", sa.Boolean(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("deidentification_verified", name="ck_lora_deid_req"),
        sa.CheckConstraint("measured_lift_bp > 0", name="ck_lora_positive_lift"),
        sa.CheckConstraint(
            "NOT deployed_to_clinical_production", name="ck_lora_no_prod_deploy"
        ),
        sa.CheckConstraint("NOT wrote_to_emr", name="ck_lora_no_emr_write"),
    )

    op.create_table(
        "plan_review_attestation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "plan_id", sa.String(36), sa.ForeignKey("treatment_plan.id"), nullable=False
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("reviewer_staff_id", sa.String(36), nullable=False),
        sa.Column("reviewer_role", sa.String(30), nullable=False),
        sa.Column("version_canonical_sha256", sa.String(64), nullable=False),
        sa.Column("review_note_vi", sa.String(300), nullable=False),
        sa.Column("simulation_label", sa.String(64), nullable=False),
        sa.Column("is_legal_clinical_approval", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "NOT is_legal_clinical_approval", name="ck_plan_att_no_legal_approval"
        ),
        sa.UniqueConstraint("plan_id", "version_number", name="uq_plan_att_plan_ver"),
        sa.ForeignKeyConstraint(
            ["clinic_id", "reviewer_staff_id"], ["staff.clinic_id", "staff.id"]
        ),
    )

    op.create_table(
        "zalo_zns_contract",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("oa_id_demo", sa.String(60), nullable=False),
        sa.Column("zns_template_id", sa.String(60), nullable=False),
        sa.Column("official_api_only", sa.Boolean(), nullable=False),
        sa.Column("legal_basis_purpose", sa.String(32), nullable=False),
        sa.Column("price_per_message_vnd", sa.Integer(), nullable=False),
        sa.Column("pricing_confirmed", sa.Boolean(), nullable=False),
        sa.Column("allowed_param_keys_json", sa.Text(), nullable=False),
        sa.Column("created_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("official_api_only", name="ck_zalo_official_api_only"),
        sa.CheckConstraint("price_per_message_vnd > 0", name="ck_zalo_positive_price"),
        sa.UniqueConstraint("clinic_id", "zns_template_id", name="uq_zalo_clinic_tpl"),
    )

    op.create_table(
        "zalo_zns_dispatch_preview",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column(
            "contract_id",
            sa.String(36),
            sa.ForeignKey("zalo_zns_contract.id"),
            nullable=False,
        ),
        sa.Column("params_json", sa.Text(), nullable=False),
        sa.Column("quoted_cost_vnd", sa.Integer(), nullable=False),
        sa.Column("live_external_egress", sa.Boolean(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT live_external_egress", name="ck_zalo_disp_no_live_egress"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "sms_sandbox_dispatch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("brandname_sender", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("message_ascii_or_ucs2", sa.String(320), nullable=False),
        sa.Column("carrier_delivery_status", sa.String(40), nullable=False),
        sa.Column("dlr_evidence_sha256", sa.String(64), nullable=True),
        sa.Column("patient_confirmed_appointment", sa.Boolean(), nullable=False),
        sa.Column("live_external_egress", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "NOT patient_confirmed_appointment", name="ck_sms_no_confirmed_infer"
        ),
        sa.CheckConstraint("NOT live_external_egress", name="ck_sms_no_live_egress"),
        sa.UniqueConstraint("clinic_id", "idempotency_key", name="uq_sms_clinic_idem"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "email_verified_sender",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("sender_address", sa.String(160), nullable=False),
        sa.Column("spf_verified", sa.Boolean(), nullable=False),
        sa.Column("dkim_verified", sa.Boolean(), nullable=False),
        sa.Column("dmarc_verified", sa.Boolean(), nullable=False),
        sa.Column("hourly_rate_limit", sa.Integer(), nullable=False),
        sa.Column("created_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("hourly_rate_limit > 0", name="ck_email_positive_rate"),
        sa.UniqueConstraint("clinic_id", "sender_address", name="uq_email_clinic_addr"),
    )

    op.create_table(
        "email_sandbox_dispatch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column(
            "sender_id",
            sa.String(36),
            sa.ForeignKey("email_verified_sender.id"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("subject_minimized", sa.String(160), nullable=False),
        sa.Column("body_safe_text", sa.String(1000), nullable=False),
        sa.Column("live_external_egress", sa.Boolean(), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("NOT live_external_egress", name="ck_email_no_live_egress"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
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
                "description": "T029 Vietnam IaC guard, partner insurance, LoRA lift & plan attestation + T030 Zalo ZNS, SMS DLR & verified Email rate limits",
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
    op.drop_table("email_sandbox_dispatch")
    op.drop_table("email_verified_sender")
    op.drop_table("sms_sandbox_dispatch")
    op.drop_table("zalo_zns_dispatch_preview")
    op.drop_table("zalo_zns_contract")
    op.drop_table("plan_review_attestation")
    op.drop_table("ai_adaptation_run")
    op.drop_table("insurance_claim_draft")
    op.drop_table("insurance_partner_contract")
    op.drop_table("iac_blueprint_validation")
