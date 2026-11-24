"""T017 tri-state medical/allergy risk review, encounter closure gate, and clinician-authored
diagnosis/performed procedure evidence + T018 milestone checklists, treatment plan lifecycle,
consent-safe waitlist, installment schedules, and protected quality incident queue.

Revision ID: 0009_encounter_lifecycle_and_clinical_governance
Revises: 0008_patient_merge_portal_and_kpi_lineage
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = "0009_encounter_lifecycle_and_clinical_governance"
down_revision = "0008_patient_merge_portal_and_kpi_lineage"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "patient_medical_risk_review",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("drug_allergy_state", sa.String(24), nullable=False, server_default="unanswered"),
        sa.Column("drug_allergy_detail", sa.String(300), nullable=True),
        sa.Column(
            "bleeding_anticoagulant_state",
            sa.String(24),
            nullable=False,
            server_default="unanswered",
        ),
        sa.Column(
            "cardiovascular_hypertension_state",
            sa.String(24),
            nullable=False,
            server_default="unanswered",
        ),
        sa.Column(
            "pregnancy_nursing_state",
            sa.String(24),
            nullable=False,
            server_default="unanswered",
        ),
        sa.Column("high_risk_banner_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("reviewed_by_staff_id", sa.String(36), nullable=False),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "clinic_id", "patient_id", "revision_number", name="uq_med_risk_patient_revision"
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "encounter_diagnosis_demo",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("tooth_code", sa.String(2), nullable=True),
        sa.Column(
            "code_system_demo",
            sa.String(40),
            nullable=False,
            server_default="SYNTHETIC-DENTAL-DX-V1",
        ),
        sa.Column("diagnosis_code_demo", sa.String(60), nullable=False),
        sa.Column("summary_vi", sa.String(300), nullable=False),
        sa.Column("author_staff_id", sa.String(36), nullable=False),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="recorded_demo_not_certified",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "performed_procedure_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("plan_task_id", sa.String(36), nullable=True),
        sa.Column("tooth_code", sa.String(2), nullable=False),
        sa.Column("surface", sa.String(8), nullable=False),
        sa.Column("procedure_code_demo", sa.String(60), nullable=False),
        sa.Column("description_vi", sa.String(300), nullable=False),
        sa.Column("clinical_evidence_note", sa.String(300), nullable=False),
        sa.Column("performed_by_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]
        ),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "plan_milestone_checklist",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("treatment_plan.id"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("plan_task.id"), nullable=False),
        sa.Column("title_vi", sa.String(180), nullable=False),
        sa.Column("criteria_items_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("clinician_override_reason", sa.String(300), nullable=True),
        sa.Column("evaluated_by_staff_id", sa.String(36), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "treatment_plan_lifecycle_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("treatment_plan.id"), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("resulting_state", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("clinical_handoff_note", sa.String(300), nullable=False, server_default=""),
        sa.Column("actor_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "schedule_waitlist_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column("preferred_practitioner_id", sa.String(36), nullable=True),
        sa.Column("preferred_date_window", sa.String(60), nullable=False),
        sa.Column("service_note_minimized", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="waiting"),
        sa.Column("booked_appointment_id", sa.String(36), nullable=True),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "installment_schedule",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("patient_id", sa.String(36), nullable=False),
        sa.Column(
            "estimate_id", sa.String(36), sa.ForeignKey("estimate_version.id"), nullable=False
        ),
        sa.Column("consent_id", sa.String(36), sa.ForeignKey("consent_record.id"), nullable=False),
        sa.Column("total_amount_vnd", sa.Integer(), nullable=False),
        sa.Column("auto_charge_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("actor_demo", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("total_amount_vnd > 0", name="ck_installment_total_positive"),
        sa.CheckConstraint("auto_charge_enabled = 0", name="ck_installment_no_autocharge"),
        sa.ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )

    op.create_table(
        "installment_tranche",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column(
            "schedule_id", sa.String(36), sa.ForeignKey("installment_schedule.id"), nullable=False
        ),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.String(10), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("reminder_status", sa.String(24), nullable=False, server_default="none"),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount_vnd > 0", name="ck_tranche_amount_positive"),
    )

    op.create_table(
        "quality_incident_report",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clinic_id", sa.String(36), sa.ForeignKey("clinic.id"), nullable=False),
        sa.Column("encounter_id", sa.String(36), nullable=True),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("evidence_note", sa.String(300), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("reporter_staff_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    now_iso = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    op.execute(
        sa.text(
            "INSERT INTO schema_migration_meta (revision_id, description, applied_at) "
            "VALUES ('0009_encounter_lifecycle_and_clinical_governance', "
            "'T017 medical/allergy review, encounter closure & procedure evidence + T018 milestones/waitlist/installments/incidents', :ts)"
        ).bindparams(ts=now_iso)
    )


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
