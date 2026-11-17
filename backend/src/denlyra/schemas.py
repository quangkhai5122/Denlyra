"""Typed request schemas; strings and money are deliberately constrained."""
from datetime import datetime
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
