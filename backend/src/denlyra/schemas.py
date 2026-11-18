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


class AppointmentReschedule(BaseModel):
    practitioner_id: str | None = None
    chair_id: str | None = None
    start_at: datetime
    end_at: datetime
    reason_demo: str = Field(default="Rescheduled demo appointment", min_length=2, max_length=260)
    equipment_ids: list[str] = Field(default_factory=list, max_length=10)

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
    owner_role: Literal[
        "dentist", "medical_director", "assistant", "receptionist", "treatment_coordinator"
    ] = "dentist"
    due_at: datetime | None = None
    depends_on_task_id: str | None = None
    depends_on_task_ids: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def check_due_tz(self):
        if self.due_at is not None and not self.due_at.tzinfo:
            raise ValueError("due_at must be a timezone-aware RFC3339 timestamp")
        return self


class TaskDependenciesUpdate(BaseModel):
    depends_on_task_ids: list[str] = Field(min_length=1, max_length=20)


class TaskCoordinationLinkCreate(BaseModel):
    target_type: Literal["appointment", "lab_case", "charge"]
    target_id: str = Field(min_length=2, max_length=36)
    requires_verified_lab: bool = False


class PlanReassessmentCreate(BaseModel):
    source_task_id: str = Field(min_length=2, max_length=36)
    reason: str = Field(min_length=5, max_length=400)
    followup_task_title: str = Field(min_length=2, max_length=160)
    followup_phase: str = Field(default="Reassessment phase", min_length=2, max_length=100)
    owner_role: Literal[
        "dentist", "medical_director", "assistant", "treatment_coordinator"
    ] = "dentist"


class LabCaseCreate(BaseModel):
    patient_id: str
    title: str = Field(min_length=2, max_length=180)
    specification_demo: str = Field(default="", max_length=2000)
    due_on: datetime | None = None
    file_references: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def check_due_on_tz(self):
        if self.due_on is not None and not self.due_on.tzinfo:
            raise ValueError("due_on must be a timezone-aware RFC3339 timestamp")
        return self


class LabStateUpdate(BaseModel):
    next_status: str


class LabPartnerGrantCreate(BaseModel):
    partner_name: str = Field(min_length=2, max_length=160)
    ttl_seconds: int = Field(default=3600, ge=-3600, le=604800)


class LabPartnerMilestoneUpdate(BaseModel):
    next_status: str
    partner_note: str = Field(default="", max_length=260)


class LabReceiveRequest(BaseModel):
    condition: str = Field(min_length=2, max_length=200)


class LabRemakeCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=260)
    specification_demo: str = Field(min_length=2, max_length=2000)
    due_on: datetime | None = None


class ConsentCreate(BaseModel):
    patient_id: str
    purpose: Literal["treatment", "data_processing", "marketing", "financial"]
    template_version: str = Field(min_length=2, max_length=40)
    disclosure_summary: str = Field(min_length=5, max_length=400)
    signer_name: str = Field(min_length=2, max_length=160)
    signer_relationship: Literal["self", "guardian"] = "self"
    guardian_authority_verified: bool = False

    @model_validator(mode="after")
    def check_guardian_authority(self):
        if self.signer_relationship == "guardian" and not self.guardian_authority_verified:
            raise ValueError("Guardian authority must be verified for guardian consent (PAT-004)")
        return self


class ConsentWithdrawRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=260)


class ChargeCreate(BaseModel):
    patient_id: str
    label: str = Field(min_length=2, max_length=160)
    amount_vnd: int = Field(gt=0, le=10_000_000_000)
    idempotency_key: str | None = Field(default=None, min_length=4, max_length=120)


class PaymentCreate(BaseModel):
    patient_id: str
    amount_vnd: int = Field(gt=0, le=10_000_000_000)
    payment_method: Literal["cash", "bank_transfer", "card"] = "cash"
    external_reference: str | None = Field(default=None, max_length=120)
    idempotency_key: str | None = Field(default=None, min_length=4, max_length=120)


class AllocationCreate(BaseModel):
    charge_id: str
    payment_id: str
    amount_vnd: int = Field(gt=0, le=10_000_000_000)
    idempotency_key: str | None = Field(default=None, min_length=4, max_length=120)


class RefundCreate(BaseModel):
    amount_vnd: int = Field(gt=0, le=10_000_000_000)
    reason: str = Field(min_length=3, max_length=260)
    idempotency_key: str | None = Field(default=None, min_length=4, max_length=120)


class EstimateCreate(BaseModel):
    patient_id: str
    plan_id: str
    version_number: int = Field(ge=1, le=1000)
    amount_vnd: int = Field(gt=0, le=10_000_000_000)
    items_summary: str = Field(min_length=2, max_length=400)


class EstimateAcceptRequest(BaseModel):
    accepted_by: str = Field(min_length=2, max_length=160)


class CashierReconciliationCreate(BaseModel):
    counted_cash_vnd: int = Field(ge=0, le=100_000_000_000)
    counted_transfer_vnd: int = Field(ge=0, le=100_000_000_000)
    counted_card_vnd: int = Field(ge=0, le=100_000_000_000)
    notes: str = Field(default="", max_length=300)


class ScannedPageSchema(BaseModel):
    page_number: int = Field(ge=1, le=500)
    sha256: str = Field(min_length=64, max_length=64)
    legible: bool = True
    ocr_unverified_text: str | None = Field(default=None, max_length=4000)


class PaperBatchCreate(BaseModel):
    source_cabinet: str = Field(min_length=3, max_length=200)
    expected_item_count: int = Field(default=1, ge=1, le=10000)


class PaperItemCreate(BaseModel):
    legacy_folder_id: str = Field(min_length=2, max_length=80)
    patient_display_name: str = Field(min_length=2, max_length=160)
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    phone_demo: str | None = Field(default=None, max_length=40)
    expected_page_count: int = Field(ge=1, le=500)
    pages: list[ScannedPageSchema] = Field(min_length=1, max_length=500)


class PaperItemVerifyLinkRequest(BaseModel):
    resolution_mode: Literal["link_existing_patient", "create_distinct_patient"]
    target_patient_id: str | None = None
    reviewer_note: str = Field(min_length=3, max_length=300)
    claim_digitally_signed: bool = False


class PaperBatchRollbackRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=260)


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


class DocumentSnapshotCreate(BaseModel):
    note_id: str
    expected_revision: int = Field(ge=1)
    template_id: str | None = None


class DocumentSyntheticSignRequest(BaseModel):
    expected_sha256: str = Field(min_length=64, max_length=64)
    mode: Literal["synthetic_test_double", "legal_authenticated"] = "synthetic_test_double"
    simulate_failure: Literal["timeout", "signature_mismatch"] | None = None


class DocumentAddendumCreate(BaseModel):
    content: str = Field(min_length=5, max_length=10000)
    amendment_reason: str = Field(min_length=3, max_length=300)


class DocumentEnterInErrorRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)
