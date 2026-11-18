"""Typed request schemas; strings and money are deliberately constrained."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class PatientCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=160)
    birth_year: int | None = Field(None, ge=1900, le=2100)
    phone_demo: str | None = Field(None, max_length=40)


class AppointmentCreate(BaseModel):
    patient_id: str
    practitioner_id: str
    chair_id: str
    start_at: datetime
    end_at: datetime
    reason_demo: str = Field(default="Demo appointment", min_length=2, max_length=260)
    equipment_ids: list[str] = Field(default_factory=list, max_length=10)
    idempotency_key: str | None = Field(default=None, min_length=4, max_length=120)

    @model_validator(mode="after")
    def check_utc(self):
        if not self.start_at.tzinfo or not self.end_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 timestamps")
        if self.end_at <= self.start_at:
            raise ValueError("Appointment end must follow start")
        return self


class EncounterCreate(BaseModel):
    patient_id: str
    practitioner_id: str


class NoteCreate(BaseModel):
    content: str = Field(min_length=5, max_length=10000)
    parent_note_id: str | None = None


class NoteUpdate(BaseModel):
    content: str = Field(min_length=5, max_length=10000)
    expected_revision: int = Field(ge=1)


class PlanCreate(BaseModel):
    patient_id: str
    title: str = Field(min_length=2, max_length=160)


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    phase: str = Field(default="Demo phase", max_length=100)
    depends_on_task_id: str | None = None


class LabCaseCreate(BaseModel):
    patient_id: str
    title: str = Field(min_length=2, max_length=180)


class LabStateUpdate(BaseModel):
    next_status: str


class ChargeCreate(BaseModel):
    patient_id: str
    label: str = Field(min_length=2, max_length=160)
    amount_vnd: int = Field(gt=0, le=10_000_000_000)


class PaymentCreate(BaseModel):
    patient_id: str
    amount_vnd: int = Field(gt=0, le=10_000_000_000)
    external_reference: str | None = Field(default=None, max_length=120)


class AllocationCreate(BaseModel):
    charge_id: str
    payment_id: str
    amount_vnd: int = Field(gt=0, le=10_000_000_000)


class DentalFindingCreate(BaseModel):
    tooth_code: str = Field(min_length=2, max_length=2)
    surface: str = Field(pattern="^(O|M|D|B|L|I|ALL)$")
    finding_text_demo: str = Field(min_length=2, max_length=300)

    @model_validator(mode="after")
    def validate_fdi(self):
        # Two-digit FDI codes (permanent and primary) for a toy odontogram.
        try:
            a, b = int(self.tooth_code[0]), int(self.tooth_code[1])
        except ValueError as exc:
            raise ValueError("FDI code must contain two digits") from exc
        if not ((1 <= a <= 4 and 1 <= b <= 8) or (5 <= a <= 8 and 1 <= b <= 5)):
            raise ValueError("Invalid FDI tooth code")
        return self


class TokenIssueRequest(BaseModel):
    clinic_id: str
    role: Literal[
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator", "finance",
    ]
    staff_id: str | None = None
    branch_id: str = Field(default="branch-main", min_length=2, max_length=36)
    ttl_seconds: int = Field(default=3600, ge=-3600, le=86400)


class SignedUrlCreateRequest(BaseModel):
    subject_type: Literal["clinical_note", "encounter", "lab_case"]
    subject_id: str = Field(min_length=2, max_length=36)
    ttl_seconds: int = Field(default=300, ge=1, le=3600)


class StaffCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    role: Literal[
        "clinic_owner", "medical_director", "dentist", "assistant",
        "receptionist", "treatment_coordinator", "finance",
    ]
    branch_id: str = Field(default="branch-main", min_length=2, max_length=36)


class ResourceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    kind: Literal["chair", "device"]


class FormFieldSchema(BaseModel):
    field_code: str = Field(min_length=2, max_length=80, pattern="^[a-z0-9_]+$")
    label_vi: str = Field(min_length=2, max_length=200)
    field_type: Literal["text", "tri_state", "date", "fdi_tooth", "integer"]
    required_when: Literal["always", "optional", "conditional"] = "always"
    allow_unknown: bool = False


class FormTemplateCreate(BaseModel):
    official_code: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=200)
    schema_version: int = Field(default=1, ge=1, le=1000)
    source_citation: str = Field(min_length=5, max_length=300)
    source_sha256: str = Field(min_length=64, max_length=64)
    fields: list[FormFieldSchema] = Field(min_length=1, max_length=100)


class FormFieldValueInput(BaseModel):
    state: Literal["present", "explicit_negative", "unknown", "not_applicable", "missing"]
    value: str | int | None = None


class FormValidatePreviewRequest(BaseModel):
    template_id: str
    encounter_id: str
    values: dict[str, FormFieldValueInput] = Field(default_factory=dict)


class FormOfficialExportRequest(BaseModel):
    template_id: str
    encounter_id: str
