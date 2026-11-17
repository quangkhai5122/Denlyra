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
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    created_at: Mapped[datetime] = created_col()
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        ForeignKeyConstraint(["clinic_id", "practitioner_id"], ["staff.clinic_id", "staff.id"]),
        ForeignKeyConstraint(["clinic_id", "chair_id"], ["resource.clinic_id", "resource.id"]),
        CheckConstraint("end_at > start_at", name="ck_appointment_valid_range"),
        CheckConstraint("status IN ('confirmed','cancelled')", name="ck_appointment_demo_status"),
        UniqueConstraint("clinic_id", "id"),
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
    depends_on_task_id: Mapped[str | None] = mapped_column(ForeignKey("plan_task.id"))
    status: Mapped[str] = mapped_column(String(22), nullable=False, default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime())


class LabCase(Base):
    __tablename__ = "lab_case"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(28), nullable=False, default="requested")
    due_on: Mapped[datetime | None] = mapped_column(DateTime())
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
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        CheckConstraint("amount_vnd > 0", name="ck_charge_positive"),
        UniqueConstraint("clinic_id", "id"),
    )


class Payment(Base):
    __tablename__ = "payment"
    id: Mapped[str] = id_col()
    clinic_id: Mapped[str] = mapped_column(ForeignKey("clinic.id"), nullable=False)
    patient_id: Mapped[str] = mapped_column(String(36), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (
        ForeignKeyConstraint(["clinic_id", "patient_id"], ["patient.clinic_id", "patient.id"]),
        CheckConstraint("amount_vnd > 0", name="ck_payment_positive"),
        UniqueConstraint("clinic_id", "id"),
    )


class PaymentAllocation(Base):
    __tablename__ = "payment_allocation"
    id: Mapped[str] = id_col()
    charge_id: Mapped[str] = mapped_column(ForeignKey("charge.id"), nullable=False)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payment.id"), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_col()
    __table_args__ = (CheckConstraint("amount_vnd > 0", name="ck_allocation_positive"),)


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
