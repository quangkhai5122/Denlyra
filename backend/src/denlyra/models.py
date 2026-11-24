"""Normalized domain research tables. Demo-only, not official medical records.

All IDs are opaque UUID strings. ISO timestamps are stored in UTC.
No API is allowed to infer medical procedure completion from a financial event.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def id_col():
    return mapped_column(String(36), primary_key=True, default=uid)


def created_col():
    return mapped_column(DateTime(), nullable=False, default=utcnow)


class Clinic(Base):
    __tablename__ = "clinic"
    id: Mapped[str] = id_col()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    demo_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_col()


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    branch_id: Mapped[str] = mapped_column(String(36), nullable=False, default="branch-main")
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (UniqueConstraint("clinic_id", "id"),)


class Patient(Base):
    __tablename__ = "patient"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone_demo: Mapped[str | None] = mapped_column(String(40))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="demo_native")
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("birth_year IS NULL OR (birth_year BETWEEN 1900 AND 2100)", name="ck_patient_birth_year"),
        UniqueConstraint("clinic_id", "id"),
        Index("ix_patient_clinic_name", "clinic_id", "display_name"),
    )


class Resource(Base):
    __tablename__ = "resource"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # chair | device
    __table_args__ = (UniqueConstraint("clinic_id", "id"),)


class Appointment(Base):
    __tablename__ = "appointment"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    practitioner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chair_id: Mapped[str] = mapped_column(String(36), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="confirmed")
    reason_demo: Mapped[str] = mapped_column(String(260), nullable=False, default="Demo appointment")
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    rescheduled_from_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = created_col()
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        ForeignKeyConstraint(["clinic_id", "practitioner_id"], ["staff.clinic_id", "staff.id"]),
        ForeignKeyConstraint(["clinic_id", "chair_id"], ["resource.clinic_id", "resource.id"]),
        CheckConstraint("end_at > start_at", name="ck_appointment_valid_range"),
        CheckConstraint("status IN ('confirmed','cancelled')", name="ck_appointment_demo_status"),
        UniqueConstraint("clinic_id", "id"),
        UniqueConstraint("clinic_id", "idempotency_key", name="uq_appointment_clinic_idempotency"),
    )


class ResourceBooking(Base):
    __tablename__ = "resource_booking"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    appointment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(80), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]),
        CheckConstraint("end_at > start_at", name="ck_booking_valid_range"),
        CheckConstraint("state IN ('active','cancelled')", name="ck_booking_state"),
        Index("ix_booking_active_lookup", "clinic_id", "resource_key", "state", "start_at", "end_at"),
    )


class Encounter(Base):
    __tablename__ = "encounter"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    practitioner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="in_progress")
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        ForeignKeyConstraint(["clinic_id", "practitioner_id"], ["staff.clinic_id", "staff.id"]),
        UniqueConstraint("clinic_id", "id"),
    )


class ClinicalNote(Base):
    __tablename__ = "clinical_note"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    encounter_id: Mapped[str] = mapped_column(String(36), nullable=False)
    parent_note_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    latest_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked_digest: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]),
        UniqueConstraint("clinic_id", "id"),
    )


class NoteRevision(Base):
    __tablename__ = "note_revision"
    id: Mapped[str] = id_col()
    note_id: Mapped[str] = mapped_column(ForeignKey("clinical_note.id"), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False, default="manual_demo")
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (UniqueConstraint("note_id", "revision_no"),)


class DentalFinding(Base):
    __tablename__ = "dental_finding_demo"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    encounter_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tooth_code: Mapped[str] = mapped_column(String(2), nullable=False)
    surface: Mapped[str] = mapped_column(String(8), nullable=False)
    finding_text_demo: Mapped[str] = mapped_column(String(300), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]),
        UniqueConstraint("clinic_id", "id"),
    )


class TreatmentPlan(Base):
    __tablename__ = "treatment_plan"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        UniqueConstraint("clinic_id", "id"),
    )


class PlanVersion(Base):
    __tablename__ = "plan_version"
    id: Mapped[str] = id_col()
    plan_id: Mapped[str] = mapped_column(ForeignKey("treatment_plan.id"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(22), nullable=False, default="draft")
    reviewer_demo: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (UniqueConstraint("plan_id", "number"),)


class PlanTask(Base):
    __tablename__ = "plan_task"
    id: Mapped[str] = id_col()
    plan_version_id: Mapped[str] = mapped_column(ForeignKey("plan_version.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    phase: Mapped[str] = mapped_column(String(100), nullable=False, default="Demo phase")
    owner_role: Mapped[str] = mapped_column(String(30), nullable=False, default="dentist")
    due_at: Mapped[datetime | None] = mapped_column(DateTime())
    depends_on_task_id: Mapped[str | None] = mapped_column(ForeignKey("plan_task.id"))
    reassessed_from_task_id: Mapped[str | None] = mapped_column(String(36))
    completion_evidence_note: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(22), nullable=False, default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime())


class PlanTaskDependency(Base):
    __tablename__ = "plan_task_dependency"
    id: Mapped[str] = id_col()
    plan_version_id: Mapped[str] = mapped_column(ForeignKey("plan_version.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("plan_task.id"), nullable=False)
    depends_on_task_id: Mapped[str] = mapped_column(ForeignKey("plan_task.id"), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_plan_task_dep_edge"),
    )


class TreatmentCoordinationLink(Base):
    __tablename__ = "treatment_coordination_link"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("plan_task.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    requires_verified_lab: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("task_id", "target_type", "target_id", name="uq_task_coord_link"),
    )


class PlanReassessment(Base):
    __tablename__ = "plan_reassessment"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("treatment_plan.id"), nullable=False)
    from_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    to_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    followup_task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[str] = mapped_column(String(400), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()


class LabCase(Base):
    __tablename__ = "lab_case"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    specification_demo: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_manifest_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    parent_lab_case_id: Mapped[str | None] = mapped_column(String(36))
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(28), nullable=False, default="requested")
    due_on: Mapped[datetime | None] = mapped_column(DateTime())
    delivery_condition: Mapped[str | None] = mapped_column(String(200))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime())
    verified_by_staff_id: Mapped[str | None] = mapped_column(String(36))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class Charge(Base):
    __tablename__ = "charge"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        CheckConstraint("amount_vnd > 0", name="ck_charge_positive"),
        UniqueConstraint("clinic_id", "id"),
        UniqueConstraint("clinic_id", "idempotency_key", name="uq_charge_clinic_idempotency"),
    )


class Payment(Base):
    __tablename__ = "payment"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(24), nullable=False, default="cash")
    external_reference: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        CheckConstraint("amount_vnd > 0", name="ck_payment_positive"),
        UniqueConstraint("clinic_id", "id"),
        UniqueConstraint("clinic_id", "idempotency_key", name="uq_payment_clinic_idempotency"),
    )


class PaymentAllocation(Base):
    __tablename__ = "payment_allocation"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str | None] = mapped_column(String(36))
    charge_id: Mapped[str] = mapped_column(ForeignKey("charge.id"), nullable=False)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payment.id"), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (CheckConstraint("amount_vnd > 0", name="ck_allocation_positive"),)


class PaymentRefund(Base):
    __tablename__ = "payment_refund"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payment.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(260), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("amount_vnd > 0", name="ck_refund_positive"),
        UniqueConstraint("clinic_id", "idempotency_key", name="uq_refund_clinic_idempotency"),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_event"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = created_col()


class ClinicalDocumentSnapshot(Base):
    __tablename__ = "clinical_document_snapshot"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    encounter_id: Mapped[str] = mapped_column(String(36), nullable=False)
    note_id: Mapped[str] = mapped_column(ForeignKey("clinical_note.id"), nullable=False)
    note_revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_snapshot_id: Mapped[str | None] = mapped_column(String(36))
    amendment_reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ready_for_signature")
    canonical_json: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signer_staff_id: Mapped[str | None] = mapped_column(String(36))
    provider_receipt_json: Mapped[str | None] = mapped_column(Text)
    entered_in_error_reason: Mapped[str | None] = mapped_column(String(300))
    entered_in_error_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_col()


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = created_col()


class RevokedToken(Base):
    __tablename__ = "revoked_token"
    id: Mapped[str] = id_col()
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False, default="revoked")
    created_at: Mapped[datetime] = created_col()


class SignedUrlGrant(Base):
    __tablename__ = "signed_url_grant"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    created_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()


class FormTemplateVersion(Base):
    __tablename__ = "form_template_version"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    official_code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_citation: Mapped[str] = mapped_column(String(300), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="quarantined_synthetic_draft"
    )
    approved_by_dentist: Mapped[str | None] = mapped_column(String(120))
    approved_by_counsel: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "official_code", "schema_version",
            name="uq_form_template_clinic_code_version",
        ),
    )


class FormFieldMap(Base):
    __tablename__ = "form_field_map"
    id: Mapped[str] = id_col()
    template_id: Mapped[str] = mapped_column(ForeignKey("form_template_version.id"), nullable=False)
    field_code: Mapped[str] = mapped_column(String(80), nullable=False)
    label_vi: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), nullable=False)
    required_when: Mapped[str] = mapped_column(String(40), nullable=False, default="always")
    allow_unknown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("template_id", "field_code", name="uq_form_field_template_code"),
    )


class SchemaMigrationMeta(Base):
    __tablename__ = "schema_migration_meta"
    revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    applied_at: Mapped[datetime] = created_col()


class ConsentRecord(Base):
    __tablename__ = "consent_record"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    template_version: Mapped[str] = mapped_column(String(40), nullable=False)
    disclosure_summary: Mapped[str] = mapped_column(String(400), nullable=False)
    signer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    signer_relationship: Mapped[str] = mapped_column(String(20), nullable=False, default="self")
    guardian_authority_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="granted")
    withdrawn_reason: Mapped[str | None] = mapped_column(String(260))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime())
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class LabPartnerGrant(Base):
    __tablename__ = "lab_partner_grant"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    lab_case_id: Mapped[str] = mapped_column(ForeignKey("lab_case.id"), nullable=False)
    partner_name: Mapped[str] = mapped_column(String(160), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()


class EstimateVersion(Base):
    __tablename__ = "estimate_version"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("treatment_plan.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    items_summary: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    accepted_by: Mapped[str | None] = mapped_column(String(160))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("amount_vnd > 0", name="ck_estimate_positive"),
        UniqueConstraint("plan_id", "version_number", name="uq_estimate_plan_version"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entry"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(24))
    reference_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (CheckConstraint("amount_vnd > 0", name="ck_ledger_positive"),)


class CashierReconciliation(Base):
    __tablename__ = "cashier_reconciliation"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    expected_cash_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_cash_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    discrepancy_cash_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_transfer_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_transfer_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    discrepancy_transfer_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_card_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    counted_card_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    discrepancy_card_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()


class MigrationBatch(Base):
    __tablename__ = "migration_batch"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    source_cabinet: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="quarantined_open")
    rollback_reason: Mapped[str | None] = mapped_column(String(260))
    operator_actor: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()


class MigrationItem(Base):
    __tablename__ = "migration_item"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    batch_id: Mapped[str] = mapped_column(ForeignKey("migration_batch.id"), nullable=False)
    legacy_folder_id: Mapped[str] = mapped_column(String(80), nullable=False)
    patient_display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    birth_year: Mapped[int | None] = mapped_column(Integer)
    phone_demo: Mapped[str | None] = mapped_column(String(40))
    expected_page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    missing_pages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    completeness_status: Mapped[str] = mapped_column(String(40), nullable=False)
    match_status: Mapped[str] = mapped_column(String(40), nullable=False)
    candidate_patient_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    linked_patient_id: Mapped[str | None] = mapped_column(String(36))
    created_new_patient: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="quarantined")
    provenance_source: Mapped[str] = mapped_column(String(30), nullable=False, default="legacy_scan")
    digital_signature_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="not_digitally_signed_legacy_paper"
    )
    reviewer_note: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_col()


class TenantEncryptionKey(Base):
    __tablename__ = "tenant_encryption_key"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    wrapped_dek_b64: Mapped[str] = mapped_column(Text, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    rotated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("clinic_id", "key_version", name="uq_tenant_key_clinic_version"),
    )


class ArchiveObject(Base):
    __tablename__ = "archive_object"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    encounter_id: Mapped[str | None] = mapped_column(String(36))
    snapshot_id: Mapped[str | None] = mapped_column(String(36))
    object_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    media_type: Mapped[str] = mapped_column(String(80), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    plaintext_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ciphertext_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    key_id: Mapped[str] = mapped_column(ForeignKey("tenant_encryption_key.id"), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_relpath: Mapped[str] = mapped_column(String(260), nullable=False)
    retention_class: Mapped[str] = mapped_column(
        String(40), nullable=False, default="clinical_emr_quarantined"
    )
    retention_until: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    legal_hold_reason: Mapped[str | None] = mapped_column(String(260))
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class BackupManifest(Base):
    __tablename__ = "backup_manifest"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    db_checkpoint_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    object_store_checkpoint_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    bundle_relpath: Mapped[str] = mapped_column(String(260), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="sealed")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()


class RestoreDrillRun(Base):
    __tablename__ = "restore_drill_run"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    backup_id: Mapped[str] = mapped_column(ForeignKey("backup_manifest.id"), nullable=False)
    target_clinic_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    integrity_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    restored_patients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    restored_snapshots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    restored_objects: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rto_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rpo_lag_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_detail: Mapped[str | None] = mapped_column(String(400))
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()


class InventorySupplier(Base):
    __tablename__ = "inventory_supplier"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    tax_code_demo: Mapped[str] = mapped_column(String(60), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("clinic_id", "tax_code_demo", name="uq_supplier_clinic_tax"),
    )


class InventorySku(Base):
    __tablename__ = "inventory_sku"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    sku_code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    lot_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reorder_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("clinic_id", "sku_code", name="uq_sku_clinic_code"),
        UniqueConstraint("clinic_id", "id", name="uq_sku_clinic_id"),
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_order"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("inventory_supplier.id"), nullable=False)
    sku_id: Mapped[str] = mapped_column(ForeignKey("inventory_sku.id"), nullable=False)
    ordered_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    delivered_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inspected_accepted_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ordered")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (CheckConstraint("ordered_qty > 0", name="ck_po_ordered_positive"),)


class InventoryLot(Base):
    __tablename__ = "inventory_lot"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    sku_id: Mapped[str] = mapped_column(ForeignKey("inventory_sku.id"), nullable=False)
    purchase_order_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_order.id"))
    lot_number: Mapped[str] = mapped_column(String(80), nullable=False)
    expiry_date: Mapped[str] = mapped_column(String(10), nullable=False)
    quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("clinic_id", "sku_id", "lot_number", name="uq_lot_clinic_sku_number"),
        UniqueConstraint("clinic_id", "id", name="uq_lot_clinic_id"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movement"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    sku_id: Mapped[str] = mapped_column(ForeignKey("inventory_sku.id"), nullable=False)
    lot_id: Mapped[str] = mapped_column(ForeignKey("inventory_lot.id"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[str] = mapped_column(String(36), nullable=False)
    note_demo: Mapped[str] = mapped_column(String(260), nullable=False, default="")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (CheckConstraint("quantity_delta != 0", name="ck_stock_movement_nonzero"),)


class StockReservation(Base):
    __tablename__ = "stock_reservation"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    sku_id: Mapped[str] = mapped_column(ForeignKey("inventory_sku.id"), nullable=False)
    lot_id: Mapped[str] = mapped_column(ForeignKey("inventory_lot.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(String(36))
    reserved_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    release_reason: Mapped[str | None] = mapped_column(String(260))
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("reserved_qty > 0", name="ck_reservation_positive"),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class StockAdjustmentRequest(Base):
    __tablename__ = "stock_adjustment_request"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    sku_id: Mapped[str] = mapped_column(ForeignKey("inventory_sku.id"), nullable=False)
    lot_id: Mapped[str] = mapped_column(ForeignKey("inventory_lot.id"), nullable=False)
    delta_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_dual_approval")
    requester_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approver_staff_id: Mapped[str | None] = mapped_column(String(36))
    approval_note: Mapped[str | None] = mapped_column(String(300))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (CheckConstraint("delta_qty != 0", name="ck_adj_delta_nonzero"),)


class AIModelRegistry(Base):
    __tablename__ = "ai_model_registry"
    id: Mapped[str] = id_col()
    model_code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    version_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    license_id: Mapped[str] = mapped_column(String(60), nullable=False)
    data_locality: Mapped[str] = mapped_column(
        String(40), nullable=False, default="local_loopback_no_egress"
    )
    purpose: Mapped[str] = mapped_column(String(160), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_col()


class AIDraftArtifact(Base):
    __tablename__ = "ai_draft_artifact"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    encounter_id: Mapped[str | None] = mapped_column(String(36))
    model_code: Mapped[str] = mapped_column(String(80), nullable=False)
    draft_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="unreviewed_ai_draft")
    allergy_state: Mapped[str] = mapped_column(
        String(40), nullable=False, default="abstained_not_stated"
    )
    extracted_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    accepted_note_id: Mapped[str | None] = mapped_column(String(36))
    reviewed_by_staff_id: Mapped[str | None] = mapped_column(String(36))
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()


class AIEvaluationRun(Base):
    __tablename__ = "ai_evaluation_run"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    model_code: Mapped[str] = mapped_column(String(80), nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_pass_rate_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    injection_block_rate_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
