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
    chain_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="0" * 64)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("clinic_id", "chain_seq", name="uq_audit_clinic_chain_seq"),
    )


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


class StaffShift(Base):
    __tablename__ = "staff_shift"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "staff_id"], ["staff.clinic_id", "staff.id"]),
        CheckConstraint("end_at > start_at", name="ck_staff_shift_valid_range"),
    )


class ResourceDowntime(Base):
    __tablename__ = "resource_downtime"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(80), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    reason: Mapped[str] = mapped_column(String(260), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "resource_id"], ["resource.clinic_id", "resource.id"]),
        CheckConstraint("end_at > start_at", name="ck_downtime_valid_range"),
    )


class AppointmentConfirmation(Base):
    __tablename__ = "appointment_confirmation"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    appointment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_note: Mapped[str] = mapped_column(String(260), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]),
    )


class ChairTurnoverChecklist(Base):
    __tablename__ = "chair_turnover_checklist"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    chair_id: Mapped[str] = mapped_column(String(36), nullable=False)
    appointment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    surface_disinfected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sterile_kit_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    waterline_flushed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assistant_prep_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    notes: Mapped[str] = mapped_column(String(260), nullable=False, default="")
    completed_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "chair_id"], ["resource.clinic_id", "resource.id"]),
        ForeignKeyConstraint(["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]),
    )


class CheckinQueueItem(Base):
    __tablename__ = "checkin_queue_item"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    appointment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    identity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_method: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="waiting")
    notes: Mapped[str] = mapped_column(String(260), nullable=False, default="")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class RecallFollowupItem(Base):
    __tablename__ = "recall_followup_item"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    due_date: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    clinician_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    closure_evidence: Mapped[str | None] = mapped_column(String(300))
    owner_role: Mapped[str] = mapped_column(String(32), nullable=False, default="treatment_coordinator")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PatientMergeRequest(Base):
    __tablename__ = "patient_merge_request"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    primary_patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    secondary_patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    rationale: Mapped[str] = mapped_column(String(300), nullable=False)
    contradictions_noted: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_second_confirmation"
    )
    requester_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approver_staff_id: Mapped[str | None] = mapped_column(String(36))
    confirmation_note: Mapped[str | None] = mapped_column(String(300))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime())
    reversal_reason: Mapped[str | None] = mapped_column(String(300))
    reversed_by_staff_id: Mapped[str | None] = mapped_column(String(36))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "primary_patient_id != secondary_patient_id", name="ck_merge_distinct_patients"
        ),
        ForeignKeyConstraint(["clinic_id", "primary_patient_id"], ["patient.clinic_id", "patient.id"]),
        ForeignKeyConstraint(
            ["clinic_id", "secondary_patient_id"], ["patient.clinic_id", "patient.id"]
        ),
    )


class BreakGlassGrant(Base):
    __tablename__ = "break_glass_grant"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    requester_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    requester_role: Mapped[str] = mapped_column(String(32), nullable=False)
    emergency_reason: Mapped[str] = mapped_column(String(300), nullable=False)
    granted_permissions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_independent_review"
    )
    reviewer_staff_id: Mapped[str | None] = mapped_column(String(36))
    review_notes: Mapped[str | None] = mapped_column(String(300))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PortalSessionGrant(Base):
    __tablename__ = "portal_session_grant"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="self")
    actor_display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PortalPublishedInstruction(Base):
    __tablename__ = "portal_published_instruction"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    encounter_id: Mapped[str | None] = mapped_column(String(36))
    title_vi: Mapped[str] = mapped_column(String(180), nullable=False)
    body_vi: Mapped[str] = mapped_column(Text, nullable=False)
    published_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PortalPublishedPlanSummary(Base):
    __tablename__ = "portal_published_plan_summary"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("treatment_plan.id"), nullable=False)
    plan_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lay_summary_vi: Mapped[str] = mapped_column(Text, nullable=False)
    published_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PortalRescheduleRequest(Base):
    __tablename__ = "portal_reschedule_request"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    appointment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    requested_start_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    requested_end_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    reason: Mapped[str] = mapped_column(String(260), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_staff_validation"
    )
    resolved_appointment_id: Mapped[str | None] = mapped_column(String(36))
    resolved_by_staff_id: Mapped[str | None] = mapped_column(String(36))
    resolution_note: Mapped[str | None] = mapped_column(String(260))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "requested_end_at > requested_start_at", name="ck_portal_reschedule_range"
        ),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        ForeignKeyConstraint(
            ["clinic_id", "appointment_id"], ["appointment.clinic_id", "appointment.id"]
        ),
    )


class PortalIntakeSubmission(Base):
    __tablename__ = "portal_intake_submission"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    form_code: Mapped[str] = mapped_column(String(60), nullable=False)
    form_version: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    provenance: Mapped[str] = mapped_column(
        String(40), nullable=False, default="patient_portal_intake"
    )
    legal_consent_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_staff_review"
    )
    submitted_by_actor: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class ServicePriceCatalogItem(Base):
    __tablename__ = "service_price_catalog_item"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    service_code: Mapped[str] = mapped_column(String(60), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name_vi: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    max_auto_discount_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("unit_price_vnd > 0", name="ck_catalog_price_positive"),
        CheckConstraint(
            "max_auto_discount_pct BETWEEN 0 AND 100", name="ck_catalog_discount_bounds"
        ),
        UniqueConstraint(
            "clinic_id", "service_code", "version_number", name="uq_catalog_clinic_code_version"
        ),
    )


class EstimatePriceSnapshot(Base):
    __tablename__ = "estimate_price_snapshot"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    estimate_id: Mapped[str] = mapped_column(ForeignKey("estimate_version.id"), nullable=False)
    catalog_item_id: Mapped[str] = mapped_column(
        ForeignKey("service_price_catalog_item.id"), nullable=False
    )
    service_code: Mapped[str] = mapped_column(String(60), nullable=False)
    catalog_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked_unit_price_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_est_line_qty_positive"),
        CheckConstraint("locked_unit_price_vnd > 0", name="ck_est_line_unit_positive"),
    )


class DiscountApprovalRequest(Base):
    __tablename__ = "discount_approval_request"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    estimate_id: Mapped[str] = mapped_column(ForeignKey("estimate_version.id"), nullable=False)
    original_amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_pct_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requester_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approver_staff_id: Mapped[str | None] = mapped_column(String(36))
    decision_note: Mapped[str | None] = mapped_column(String(300))
    resulting_estimate_id: Mapped[str | None] = mapped_column(String(36))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "discount_amount_vnd > 0 AND discount_amount_vnd < original_amount_vnd",
            name="ck_discount_bounds",
        ),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PatientMedicalRiskReview(Base):
    __tablename__ = "patient_medical_risk_review"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    encounter_id: Mapped[str | None] = mapped_column(String(36))
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    drug_allergy_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unanswered"
    )
    drug_allergy_detail: Mapped[str | None] = mapped_column(String(300))
    bleeding_anticoagulant_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unanswered"
    )
    cardiovascular_hypertension_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unanswered"
    )
    pregnancy_nursing_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unanswered"
    )
    high_risk_banner_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewed_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "patient_id",
            "revision_number",
            name="uq_med_risk_patient_revision",
        ),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class EncounterDiagnosisDemo(Base):
    __tablename__ = "encounter_diagnosis_demo"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    encounter_id: Mapped[str] = mapped_column(String(36), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tooth_code: Mapped[str | None] = mapped_column(String(2))
    code_system_demo: Mapped[str] = mapped_column(
        String(40), nullable=False, default="SYNTHETIC-DENTAL-DX-V1"
    )
    diagnosis_code_demo: Mapped[str] = mapped_column(String(60), nullable=False)
    summary_vi: Mapped[str] = mapped_column(String(300), nullable=False)
    author_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="recorded_demo_not_certified"
    )
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]
        ),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PerformedProcedureEvidence(Base):
    __tablename__ = "performed_procedure_evidence"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    encounter_id: Mapped[str] = mapped_column(String(36), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_task_id: Mapped[str | None] = mapped_column(String(36))
    tooth_code: Mapped[str] = mapped_column(String(2), nullable=False)
    surface: Mapped[str] = mapped_column(String(8), nullable=False)
    procedure_code_demo: Mapped[str] = mapped_column(String(60), nullable=False)
    description_vi: Mapped[str] = mapped_column(String(300), nullable=False)
    clinical_evidence_note: Mapped[str] = mapped_column(String(300), nullable=False)
    performed_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinic_id", "encounter_id"], ["encounter.clinic_id", "encounter.id"]
        ),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PlanMilestoneChecklist(Base):
    __tablename__ = "plan_milestone_checklist"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("treatment_plan.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("plan_task.id"), nullable=False)
    title_vi: Mapped[str] = mapped_column(String(180), nullable=False)
    criteria_items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    clinician_override_reason: Mapped[str | None] = mapped_column(String(300))
    evaluated_by_staff_id: Mapped[str | None] = mapped_column(String(36))
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()


class TreatmentPlanLifecycleEvent(Base):
    __tablename__ = "treatment_plan_lifecycle_event"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("treatment_plan.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    resulting_state: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    clinical_handoff_note: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    actor_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()


class ScheduleWaitlistEntry(Base):
    __tablename__ = "schedule_waitlist_entry"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    preferred_practitioner_id: Mapped[str | None] = mapped_column(String(36))
    preferred_date_window: Mapped[str] = mapped_column(String(60), nullable=False)
    service_note_minimized: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="waiting")
    booked_appointment_id: Mapped[str | None] = mapped_column(String(36))
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class InstallmentSchedule(Base):
    __tablename__ = "installment_schedule"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    estimate_id: Mapped[str] = mapped_column(ForeignKey("estimate_version.id"), nullable=False)
    consent_id: Mapped[str] = mapped_column(ForeignKey("consent_record.id"), nullable=False)
    total_amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_charge_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("total_amount_vnd > 0", name="ck_installment_total_positive"),
        CheckConstraint("auto_charge_enabled = 0", name="ck_installment_no_autocharge"),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class InstallmentTranche(Base):
    __tablename__ = "installment_tranche"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey("installment_schedule.id"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[str] = mapped_column(String(10), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    reminder_status: Mapped[str] = mapped_column(String(24), nullable=False, default="none")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (CheckConstraint("amount_vnd > 0", name="ck_tranche_amount_positive"),)


class QualityIncidentReport(Base):
    __tablename__ = "quality_incident_report"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    encounter_id: Mapped[str | None] = mapped_column(String(36))
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence_note: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    reporter_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()


class OdontogramLegendEntry(Base):
    __tablename__ = "odontogram_legend_entry"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    label_vi: Mapped[str] = mapped_column(String(180), nullable=False)
    symbol_code: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    clinician_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reviewed_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "code", "version_number", name="uq_odn_legend_clinic_code_ver"
        ),
    )


class OdontogramRestorationState(Base):
    __tablename__ = "odontogram_restoration_state"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tooth_code: Mapped[str] = mapped_column(String(2), nullable=False)
    current_revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    latest_legend_code: Mapped[str] = mapped_column(String(40), nullable=False)
    latest_legend_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_surface: Mapped[str] = mapped_column(String(8), nullable=False)
    latest_material_note: Mapped[str] = mapped_column(String(260), nullable=False)
    latest_source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    latest_documented_date: Mapped[str] = mapped_column(String(10), nullable=False)
    updated_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "patient_id", "tooth_code", name="uq_odn_restoration_patient_tooth"
        ),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class OdontogramRestorationRevision(Base):
    __tablename__ = "odontogram_restoration_revision"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    state_id: Mapped[str] = mapped_column(
        ForeignKey("odontogram_restoration_state.id"), nullable=False
    )
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tooth_code: Mapped[str] = mapped_column(String(2), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    legend_code: Mapped[str] = mapped_column(String(40), nullable=False)
    legend_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    surface: Mapped[str] = mapped_column(String(8), nullable=False)
    material_note: Mapped[str] = mapped_column(String(260), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    documented_date: Mapped[str] = mapped_column(String(10), nullable=False)
    evidence_note: Mapped[str] = mapped_column(String(260), nullable=False)
    encounter_id: Mapped[str | None] = mapped_column(String(36))
    author_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("state_id", "revision_no", name="uq_odn_restoration_state_rev"),
    )


class ExternalReferralDocument(Base):
    __tablename__ = "external_referral_document"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    encounter_id: Mapped[str | None] = mapped_column(String(36))
    origin_facility_name: Mapped[str] = mapped_column(String(200), nullable=False)
    referring_clinician_name: Mapped[str] = mapped_column(String(160), nullable=False)
    referral_date: Mapped[str] = mapped_column(String(10), nullable=False)
    document_summary_vi: Mapped[str] = mapped_column(String(300), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_object_id: Mapped[str | None] = mapped_column(String(36))
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="quarantined_unreviewed"
    )
    reviewed_by_staff_id: Mapped[str | None] = mapped_column(String(36))
    review_note: Mapped[str | None] = mapped_column(String(300))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime())
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class OwnerBranchScopeGrant(Base):
    __tablename__ = "owner_branch_scope_grant"
    id: Mapped[str] = id_col()
    owner_group_key: Mapped[str] = mapped_column(String(80), nullable=False)
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    branch_id: Mapped[str] = mapped_column(String(36), nullable=False, default="branch-main")
    granted_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "owner_group_key", "clinic_id", "branch_id", name="uq_owner_group_clinic_branch"
        ),
    )


class TemporaryDelegationGrant(Base):
    __tablename__ = "temporary_delegation_grant"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    granter_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    delegate_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    permission: Mapped[str] = mapped_column(String(60), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinic_id", "delegate_staff_id"], ["staff.clinic_id", "staff.id"]
        ),
    )


class StaffOperationalTask(Base):
    __tablename__ = "staff_operational_task"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    assignee_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    patient_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    escalation_owner_role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="clinic_owner"
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinic_id", "assignee_staff_id"], ["staff.clinic_id", "staff.id"]
        ),
    )


class StaffOperationalTaskEvent(Base):
    __tablename__ = "staff_operational_task_event"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("staff_operational_task.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(String(260), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()


class InternalHandoffNote(Base):
    __tablename__ = "internal_handoff_note"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str | None] = mapped_column(String(36))
    task_id: Mapped[str | None] = mapped_column(String(36))
    message_vi: Mapped[str] = mapped_column(String(400), nullable=False)
    author_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()


class PatientContactLog(Base):
    __tablename__ = "patient_contact_log"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_text: Mapped[str] = mapped_column(String(300), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class ServiceComplaintCase(Base):
    __tablename__ = "service_complaint_case"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    public_intake_summary: Mapped[str] = mapped_column(String(300), nullable=False)
    private_investigation_notes: Mapped[str] = mapped_column(String(600), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class FacilityLicenseProfile(Base):
    __tablename__ = "facility_license_profile"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    legal_entity_name_demo: Mapped[str] = mapped_column(String(200), nullable=False)
    license_number_demo: Mapped[str] = mapped_column(String(80), nullable=False)
    license_type: Mapped[str] = mapped_column(String(40), nullable=False)
    permitted_scopes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    regulating_authority_demo: Mapped[str] = mapped_column(String(160), nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="unverified_synthetic"
    )
    updated_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "version_number", name="uq_facility_profile_clinic_ver"
        ),
    )


class ProcedureDurationTemplate(Base):
    __tablename__ = "procedure_duration_template"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    procedure_code: Mapped[str] = mapped_column(String(60), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title_vi: Mapped[str] = mapped_column(String(180), nullable=False)
    recommended_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    approved_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("recommended_minutes >= 15", name="ck_proc_dur_rec_min"),
        CheckConstraint("buffer_minutes >= 0", name="ck_proc_dur_buf_min"),
        UniqueConstraint(
            "clinic_id", "procedure_code", "version_number", name="uq_proc_dur_clinic_code_ver"
        ),
    )


class ScheduleOptimizerProposal(Base):
    __tablename__ = "schedule_optimizer_proposal"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    practitioner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chair_id: Mapped[str] = mapped_column(String(36), nullable=False)
    procedure_code: Mapped[str] = mapped_column(String(60), nullable=False)
    window_start_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    window_end_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_slots_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    solver_engine: Mapped[str] = mapped_column(
        String(48), nullable=False, default="deterministic_constraint_grid_v1"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="proposed_pending_human"
    )
    accepted_appointment_id: Mapped[str | None] = mapped_column(String(36))
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("window_end_at > window_start_at", name="ck_opt_prop_window"),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class FinancialReceiptExport(Base):
    __tablename__ = "financial_receipt_export"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payment.id"), nullable=False)
    receipt_number: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(24), nullable=False)
    allocated_charges_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ledger_entry_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    export_note: Mapped[str] = mapped_column(String(260), nullable=False, default="")
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_hmac_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    synthetic_non_bank_receipt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    exported_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("amount_vnd > 0", name="ck_receipt_export_positive"),
        UniqueConstraint("clinic_id", "receipt_number", name="uq_receipt_export_clinic_num"),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class StaffAttendanceLog(Base):
    __tablename__ = "staff_attendance_log"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    check_out_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    local_date_hcm: Mapped[str] = mapped_column(String(10), nullable=False)
    worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    regular_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    standard_daily_limit_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=480
    )
    note: Mapped[str] = mapped_column(String(260), nullable=False, default="")
    recorded_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("check_out_at > check_in_at", name="ck_attendance_valid_range"),
        CheckConstraint("worked_minutes > 0", name="ck_attendance_worked_positive"),
        ForeignKeyConstraint(["clinic_id", "staff_id"], ["staff.clinic_id", "staff.id"]),
    )


class ReminderTemplateVersion(Base):
    __tablename__ = "reminder_template_version"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    template_code: Mapped[str] = mapped_column(String(60), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    purpose_category: Mapped[str] = mapped_column(String(32), nullable=False)
    body_template_vi: Mapped[str] = mapped_column(String(400), nullable=False)
    window_start_hour_hcm: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    window_end_hour_hcm: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    reviewed_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "window_end_hour_hcm > window_start_hour_hcm", name="ck_rem_tpl_window"
        ),
        UniqueConstraint(
            "clinic_id", "template_code", "version_number", name="uq_rem_tpl_clinic_code_ver"
        ),
    )


class CommunicationDraftRecord(Base):
    __tablename__ = "communication_draft_record"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(String(36))
    template_id: Mapped[str] = mapped_column(
        ForeignKey("reminder_template_version.id"), nullable=False
    )
    template_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose_category: Mapped[str] = mapped_column(String(32), nullable=False)
    proposed_send_hour_hcm: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered_draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft_pending_staff_review"
    )
    drafted_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("NOT auto_sent", name="ck_comm_draft_no_auto_send"),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class SatisfactionTokenReceipt(Base):
    __tablename__ = "satisfaction_token_receipt"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    token_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("clinic_id", "token_sha256", name="uq_satisfaction_token_once"),
    )


class PatientSatisfactionResponse(Base):
    __tablename__ = "patient_satisfaction_response"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    service_month: Mapped[str] = mapped_column(String(7), nullable=False)
    overall_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    wait_time_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    clarity_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    sanitized_comment: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("overall_rating BETWEEN 1 AND 5", name="ck_sat_overall_1_5"),
        CheckConstraint("wait_time_rating BETWEEN 1 AND 5", name="ck_sat_wait_1_5"),
        CheckConstraint("clarity_rating BETWEEN 1 AND 5", name="ck_sat_clarity_1_5"),
    )


class IncumbentExportPackage(Base):
    __tablename__ = "incumbent_export_package"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    source_vendor_code: Mapped[str] = mapped_column(String(60), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(30), nullable=False)
    export_license_note: Mapped[str] = mapped_column(String(300), nullable=False)
    declared_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    computed_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_balance_vnd: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    validation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="quarantined_verified"
    )
    review_status: Mapped[str] = mapped_column(
        String(36), nullable=False, default="pending_reviewer_signoff"
    )
    uploader_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reviewer_staff_id: Mapped[str | None] = mapped_column(String(36))
    review_note: Mapped[str | None] = mapped_column(String(300))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "source_vendor_code",
            "declared_sha256",
            name="uq_incumbent_pkg_clinic_vendor_sha",
        ),
    )


class MigrationCutoverPlan(Base):
    __tablename__ = "migration_cutover_plan"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    incumbent_package_id: Mapped[str] = mapped_column(
        ForeignKey("incumbent_export_package.id"), nullable=False
    )
    cutover_mode: Mapped[str] = mapped_column(String(36), nullable=False)
    legacy_write_freeze_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    reconciled_patient_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reconciled_total_balance_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    double_entry_guard_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    rollback_runbook_note: Mapped[str] = mapped_column(String(300), nullable=False)
    approved_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()


class RedactedTelemetryEvent(Base):
    __tablename__ = "redacted_telemetry_event"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    span_name: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    sanitized_attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    redacted_field_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contains_phi_or_note_text: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("NOT contains_phi_or_note_text", name="ck_telemetry_no_phi"),
    )


class ClinicOnboardingConfig(Base):
    __tablename__ = "clinic_onboarding_config"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    configured_roles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    catalog_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quarantined_form_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    legacy_field_mapping_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    readiness_status: Mapped[str] = mapped_column(
        String(36), nullable=False, default="draft_incomplete"
    )
    configured_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint("clinic_id", "version_number", name="uq_onboard_cfg_clinic_ver"),
    )


class CustomerSupportConsentGrant(Base):
    __tablename__ = "customer_support_consent_grant"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    ticket_reference: Mapped[str] = mapped_column(String(80), nullable=False)
    scope: Mapped[str] = mapped_column(
        String(48), nullable=False, default="redacted_system_diagnostics_only"
    )
    allow_live_patient_records: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    granted_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("NOT allow_live_patient_records", name="ck_support_no_live_phi"),
    )


class SupportDiagnosticBundle(Base):
    __tablename__ = "support_diagnostic_bundle"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    grant_id: Mapped[str] = mapped_column(
        ForeignKey("customer_support_consent_grant.id"), nullable=False
    )
    bundle_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    diagnostic_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    exported_by_actor: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()


class SecurityIncidentCase(Base):
    __tablename__ = "security_incident_case"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    incident_type: Mapped[str] = mapped_column(String(48), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    preserved_audit_head_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preserved_audit_head_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    containment_status: Mapped[str] = mapped_column(
        String(36), nullable=False, default="triaged_evidence_preserved"
    )
    counsel_guidance_note: Mapped[str | None] = mapped_column(String(400))
    notification_decision: Mapped[str | None] = mapped_column(String(120))
    opened_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()


class SecurityIncidentEvent(Base):
    __tablename__ = "security_incident_event"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    incident_id: Mapped[str] = mapped_column(
        ForeignKey("security_incident_case.id"), nullable=False
    )
    step_action: Mapped[str] = mapped_column(String(36), nullable=False)
    detail_note: Mapped[str] = mapped_column(String(300), nullable=False)
    actor_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()


class SupplyChainAttestation(Base):
    __tablename__ = "supply_chain_attestation"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    python_constraints_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    npm_lockfile_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    sbom_component_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unpinned_dependency_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sbom_canonical_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    attestation_hmac_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="verified_pinned")
    verified_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()


class PatientAccessRequest(Base):
    __tablename__ = "patient_access_request"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    requester_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    requester_name: Mapped[str] = mapped_column(String(160), nullable=False)
    request_type: Mapped[str] = mapped_column(String(36), nullable=False)
    authority_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(36), nullable=False)
    export_sha256: Mapped[str | None] = mapped_column(String(64))
    export_payload_json: Mapped[str | None] = mapped_column(Text)
    decision_reason: Mapped[str] = mapped_column(String(300), nullable=False)
    handled_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class CancellationRecoverySuggestion(Base):
    __tablename__ = "cancellation_recovery_suggestion"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    cancelled_appointment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ranked_candidates_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    excluded_no_consent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clinical_priority_inferred: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("NOT clinical_priority_inferred", name="ck_cancel_rec_no_clin_prio"),
        ForeignKeyConstraint(
            ["clinic_id", "cancelled_appointment_id"],
            ["appointment.clinic_id", "appointment.id"],
        ),
    )


class PortalQuarantinedUpload(Base):
    __tablename__ = "portal_quarantined_upload"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    portal_grant_id: Mapped[str] = mapped_column(
        ForeignKey("portal_session_grant.id"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False)
    declared_media_type: Mapped[str] = mapped_column(String(80), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    malware_scan_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="clean_quarantined"
    )
    quarantine_status: Mapped[str] = mapped_column(
        String(36), nullable=False, default="quarantined_pending_review"
    )
    reviewed_by_staff_id: Mapped[str | None] = mapped_column(String(36))
    review_note: Mapped[str | None] = mapped_column(String(300))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("byte_size > 0 AND byte_size <= 5242880", name="ck_portal_upload_size"),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class PortalSupportMessage(Base):
    __tablename__ = "portal_support_message"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    message_text: Mapped[str] = mapped_column(String(500), nullable=False)
    urgency_flag: Mapped[str] = mapped_column(String(32), nullable=False)
    triage_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued_for_human"
    )
    autonomous_medical_advice_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    human_reply_text: Mapped[str | None] = mapped_column(String(500))
    responder_staff_id: Mapped[str | None] = mapped_column(String(36))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "NOT autonomous_medical_advice_sent", name="ck_portal_msg_no_auto_advice"
        ),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class StaffCompetencyRecord(Base):
    __tablename__ = "staff_competency_record"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    competency_code: Mapped[str] = mapped_column(String(60), nullable=False)
    title_vi: Mapped[str] = mapped_column(String(200), nullable=False)
    expires_on: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    verified_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id", "staff_id", "competency_code", name="uq_staff_competency_code"
        ),
        ForeignKeyConstraint(["clinic_id", "staff_id"], ["staff.clinic_id", "staff.id"]),
    )


class TerminologyCodeEntry(Base):
    __tablename__ = "terminology_code_entry"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    code_system: Mapped[str] = mapped_column(String(40), nullable=False)
    system_version: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    display_vi: Mapped[str] = mapped_column(String(240), nullable=False)
    approved_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "code_system",
            "system_version",
            "code",
            name="uq_term_code_clinic_sys_ver_code",
        ),
    )


class TerminologyMappingRule(Base):
    __tablename__ = "terminology_mapping_rule"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    source_code: Mapped[str] = mapped_column(String(60), nullable=False)
    target_code_system: Mapped[str] = mapped_column(String(40), nullable=False)
    target_system_version: Mapped[str] = mapped_column(String(30), nullable=False)
    target_code: Mapped[str] = mapped_column(String(60), nullable=False)
    equivalence: Mapped[str] = mapped_column(String(24), nullable=False)
    mapping_method: Mapped[str] = mapped_column(
        String(40), nullable=False, default="clinician_verified_exact"
    )
    reviewed_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "mapping_method = 'clinician_verified_exact'",
            name="ck_term_no_guessed_map",
        ),
        UniqueConstraint(
            "clinic_id",
            "source_code",
            "target_code_system",
            name="uq_term_map_clinic_src_sys",
        ),
    )


class SpecialtyPlanTemplate(Base):
    __tablename__ = "specialty_plan_template"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    template_code: Mapped[str] = mapped_column(String(60), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    specialty: Mapped[str] = mapped_column(String(40), nullable=False)
    title_vi: Mapped[str] = mapped_column(String(200), nullable=False)
    tasks_blueprint_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_kind: Mapped[str] = mapped_column(
        String(40), nullable=False, default="clinic_clinician_authored"
    )
    review_status: Mapped[str] = mapped_column(
        String(36), nullable=False, default="draft_unreviewed"
    )
    reviewed_by_staff_id: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime())
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        UniqueConstraint(
            "clinic_id",
            "template_code",
            "version_number",
            name="uq_spec_tpl_clinic_code_ver",
        ),
    )


class LabVendorPriceItem(Base):
    __tablename__ = "lab_vendor_price_item"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    vendor_code: Mapped[str] = mapped_column(String(60), nullable=False)
    prosthesis_code: Mapped[str] = mapped_column(String(60), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    remake_surcharge_vnd: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("unit_price_vnd > 0", name="ck_lab_price_unit_pos"),
        CheckConstraint("remake_surcharge_vnd >= 0", name="ck_lab_price_remake_nonneg"),
        UniqueConstraint(
            "clinic_id",
            "vendor_code",
            "prosthesis_code",
            "version_number",
            name="uq_lab_vendor_price_ver",
        ),
    )


class LabInvoiceReconciliation(Base):
    __tablename__ = "lab_invoice_reconciliation"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    lab_case_id: Mapped[str] = mapped_column(ForeignKey("lab_case.id"), nullable=False)
    vendor_code: Mapped[str] = mapped_column(String(60), nullable=False)
    prosthesis_code: Mapped[str] = mapped_column(String(60), nullable=False)
    vendor_invoice_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    price_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    contracted_amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    billed_amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    variance_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    reconciliation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    sanitized_vendor_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    contains_phi: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("NOT contains_phi", name="ck_lab_inv_no_phi"),
    )


class LongitudinalImagingOverlay(Base):
    __tablename__ = "longitudinal_imaging_overlay"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tooth_code: Mapped[str] = mapped_column(String(2), nullable=False)
    baseline_archive_object_id: Mapped[str] = mapped_column(
        ForeignKey("archive_object.id"), nullable=False
    )
    followup_archive_object_id: Mapped[str] = mapped_column(
        ForeignKey("archive_object.id"), nullable=False
    )
    alignment_label_vi: Mapped[str] = mapped_column(String(260), nullable=False)
    visualization_provenance_label: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="SYNTHETIC_VISUAL_COMPARISON_NOT_DIAGNOSTIC",
    )
    auto_diagnosis_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("NOT auto_diagnosis_generated", name="ck_overlay_no_auto_diag"),
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
    )


class ScheduledReportExport(Base):
    __tablename__ = "scheduled_report_export"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    owner_group_key: Mapped[str | None] = mapped_column(String(80))
    report_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(160), nullable=False)
    include_phi: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    key_id: Mapped[str] = mapped_column(
        ForeignKey("tenant_encryption_key.id"), nullable=False
    )
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    encrypted_envelope_b64: Mapped[str] = mapped_column(Text, nullable=False)
    plaintext_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ciphertext_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    exported_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("NOT include_phi", name="ck_rpt_export_no_phi"),
    )


class ReleaseChangeApproval(Base):
    __tablename__ = "release_change_approval"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    release_tag: Mapped[str] = mapped_column(String(60), nullable=False)
    target_migration_revision: Mapped[str] = mapped_column(String(80), nullable=False)
    canary_stage: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pre_canary"
    )
    backward_compatible_schema: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    forward_fix_and_backup_plan: Mapped[str] = mapped_column(String(400), nullable=False)
    proposer_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approver_staff_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(
        String(36), nullable=False, default="pending_change_approval"
    )
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("backward_compatible_schema", name="ck_release_backward_compat"),
    )


class MultibranchOperatorAssignment(Base):
    __tablename__ = "multibranch_operator_assignment"
    id: Mapped[str] = id_col()
    owner_group_key: Mapped[str] = mapped_column(String(80), nullable=False)
    operator_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    home_clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    assigned_clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    operational_scope: Mapped[str] = mapped_column(
        String(48), nullable=False, default="aggregate_kpi_and_ops_read_only"
    )
    grants_clinical_chart_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    granted_by_staff_id: Mapped[str] = mapped_column(String(36), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "NOT grants_clinical_chart_access", name="ck_mb_op_no_chart_bleed"
        ),
    )


class OfflineSyncMutation(Base):
    __tablename__ = "offline_sync_mutation"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    client_mutation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_strategy: Mapped[str] = mapped_column(
        String(40), nullable=False, default="optimistic_version_check"
    )
    sync_status: Mapped[str] = mapped_column(String(36), nullable=False)
    conflict_reason: Mapped[str | None] = mapped_column(String(260))
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "resolution_strategy = 'optimistic_version_check'",
            name="ck_offline_no_lww",
        ),
        UniqueConstraint("clinic_id", "client_mutation_id", name="uq_offline_mut_client_id"),
    )


class NoshowRiskAssessment(Base):
    __tablename__ = "noshow_risk_assessment"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    appointment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    risk_band: Mapped[str] = mapped_column(String(32), nullable=False)
    calibrated_probability_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    uses_protected_demographics: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    auto_cancelled_or_overbooked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    recommended_human_action: Mapped[str] = mapped_column(String(260), nullable=False)
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint("NOT uses_protected_demographics", name="ck_noshow_fairness"),
        CheckConstraint(
            "NOT auto_cancelled_or_overbooked", name="ck_noshow_no_auto_cancel"
        ),
        ForeignKeyConstraint(
            ["clinic_id", "appointment_id"],
            ["appointment.clinic_id", "appointment.id"],
        ),
    )


class CpsatOptimizationRun(Base):
    __tablename__ = "cpsat_optimization_run"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    solver_budget_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    solver_outcome: Mapped[str] = mapped_column(String(48), nullable=False)
    proposed_assignments_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    existing_bookings_mutated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    actor_demo: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        CheckConstraint(
            "existing_bookings_mutated_count = 0", name="ck_cpsat_zero_auto_mutation"
        ),
    )
