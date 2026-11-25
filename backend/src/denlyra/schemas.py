"""Typed request schemas; strings and money are deliberately constrained."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, StrictInt, model_validator


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
    override_shift_reason: str | None = Field(default=None, min_length=3, max_length=260)

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
    override_shift_reason: str | None = Field(default=None, min_length=3, max_length=260)

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


class ArchiveObjectCreate(BaseModel):
    patient_id: str
    encounter_id: str | None = None
    snapshot_id: str | None = None
    object_kind: Literal[
        "clinical_attachment",
        "dicom_study_stub",
        "legacy_paper_scan",
        "signed_snapshot_export",
    ] = "clinical_attachment"
    media_type: str = Field(default="application/octet-stream", min_length=3, max_length=80)
    original_filename: str = Field(min_length=1, max_length=200)
    content_b64: str = Field(min_length=4, max_length=2_000_000)
    retention_class: Literal[
        "clinical_emr_quarantined",
        "radiology_dicom_quarantined",
        "financial_record",
    ] = "clinical_emr_quarantined"


class ArchiveLegalHoldRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=260)


class BackupCreateRequest(BaseModel):
    label: str = Field(min_length=2, max_length=160)
    object_store_lag_seconds: int = Field(default=0, ge=0, le=86400)


class RestoreDrillRequest(BaseModel):
    target_clinic_id: str | None = None
    override_master_secret: str | None = None


class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    tax_code_demo: str = Field(min_length=3, max_length=60)


class SkuCreate(BaseModel):
    sku_code: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=180)
    unit: str = Field(min_length=1, max_length=32)
    lot_tracked: bool = True
    reorder_threshold: int = Field(default=0, ge=0, le=100000)


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    sku_id: str
    ordered_qty: int = Field(ge=1, le=100000)


class PurchaseOrderReceiveRequest(BaseModel):
    lot_number: str = Field(min_length=2, max_length=80)
    expiry_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    delivered_qty: int = Field(ge=1, le=100000)
    inspected_accepted_qty: int = Field(ge=0, le=100000)
    quarantined: bool = False


class StockReservationCreate(BaseModel):
    sku_id: str
    lot_id: str
    reserved_qty: int = Field(ge=1, le=100000)
    patient_id: str
    appointment_id: str | None = None


class StockReservationReleaseRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=260)


class StockConsumptionCreate(BaseModel):
    lot_id: str
    encounter_id: str
    consumed_qty: int = Field(ge=1, le=100000)
    reservation_id: str | None = None
    procedure_note_demo: str = Field(default="", max_length=260)
    as_of_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class StockAdjustmentCreate(BaseModel):
    lot_id: str
    delta_qty: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=3, max_length=300)


class StockAdjustmentApproveRequest(BaseModel):
    approval_note: str = Field(min_length=3, max_length=300)


class FhirBundleValidateRequest(BaseModel):
    bundle: dict


class AIDictationExtractRequest(BaseModel):
    encounter_id: str
    dictation_text: str = Field(min_length=3, max_length=8000)


class AITimelineSummaryRequest(BaseModel):
    patient_id: str


class AIDraftAcceptRequest(BaseModel):
    clinician_edited_content: str = Field(min_length=5, max_length=10000)


class StaffShiftCreate(BaseModel):
    staff_id: str
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def check_range(self):
        if not self.start_at.tzinfo or not self.end_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 timestamps")
        if self.end_at <= self.start_at:
            raise ValueError("Shift end_at must follow start_at")
        return self


class ResourceDowntimeCreate(BaseModel):
    resource_id: str
    start_at: datetime
    end_at: datetime
    reason: str = Field(min_length=3, max_length=260)

    @model_validator(mode="after")
    def check_range(self):
        if not self.start_at.tzinfo or not self.end_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 timestamps")
        if self.end_at <= self.start_at:
            raise ValueError("Downtime end_at must follow start_at")
        return self


class AppointmentConfirmationCreate(BaseModel):
    event_type: Literal["sent", "delivered", "patient_confirmed", "declined"]
    channel: Literal["phone", "sms_stub", "zalo_stub", "in_person"] = "phone"
    evidence_note: str = Field(min_length=2, max_length=260)


class ChairTurnoverCreate(BaseModel):
    chair_id: str
    appointment_id: str


class ChairTurnoverCompleteRequest(BaseModel):
    surface_disinfected: bool
    sterile_kit_verified: bool
    waterline_flushed: bool
    assistant_prep_ready: bool
    notes: str = Field(default="", max_length=260)


class CheckinCreate(BaseModel):
    appointment_id: str
    identity_verified: bool
    verification_method: Literal["photo_id_checked", "guardian_verified", "returning_verified"]
    notes: str = Field(default="", max_length=260)


class CheckinStatusUpdate(BaseModel):
    next_status: Literal["in_chair", "checked_out", "no_show"]
    notes: str = Field(default="", max_length=260)


class RecallCreate(BaseModel):
    patient_id: str
    kind: Literal["clinical_recall", "marketing_outreach"]
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: str = Field(min_length=3, max_length=300)
    clinician_approved: bool = False
    owner_role: Literal["treatment_coordinator", "receptionist", "dentist"] = "treatment_coordinator"


class RecallCloseRequest(BaseModel):
    closure_evidence: str = Field(min_length=3, max_length=300)


class PatientMergeCreate(BaseModel):
    primary_patient_id: str
    secondary_patient_id: str
    rationale: str = Field(min_length=5, max_length=300)
    contradictions_noted: str = Field(default="", max_length=300)


class PatientMergeConfirmRequest(BaseModel):
    confirmation_note: str = Field(min_length=3, max_length=300)


class PatientMergeReverseRequest(BaseModel):
    reversal_reason: str = Field(min_length=5, max_length=300)


class BreakGlassCreateRequest(BaseModel):
    patient_id: str
    emergency_reason: str = Field(min_length=15, max_length=300)
    ttl_seconds: StrictInt = Field(default=300, ge=1, le=900)


class BreakGlassReviewRequest(BaseModel):
    outcome: Literal["reviewed_justified", "reviewed_violation"]
    review_notes: str = Field(min_length=5, max_length=300)


class PortalGrantCreate(BaseModel):
    patient_id: str
    actor_kind: Literal["self", "guardian"] = "self"
    actor_display_name: str = Field(min_length=2, max_length=160)
    ttl_seconds: StrictInt = Field(default=1800, ge=60, le=86400)


class PortalInstructionPublish(BaseModel):
    patient_id: str
    encounter_id: str | None = None
    title_vi: str = Field(min_length=3, max_length=180)
    body_vi: str = Field(min_length=5, max_length=4000)


class PortalPlanSummaryPublish(BaseModel):
    patient_id: str
    plan_id: str
    lay_summary_vi: str = Field(min_length=5, max_length=4000)


class PortalRescheduleCreate(BaseModel):
    requested_start_at: datetime
    requested_end_at: datetime
    reason: str = Field(min_length=3, max_length=260)

    @model_validator(mode="after")
    def check_range(self):
        if not self.requested_start_at.tzinfo or not self.requested_end_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 timestamps")
        if self.requested_end_at <= self.requested_start_at:
            raise ValueError("requested_end_at must follow requested_start_at")
        return self


class PortalRescheduleDecisionRequest(BaseModel):
    resolution_note: str = Field(min_length=3, max_length=260)


class PortalIntakeCreate(BaseModel):
    form_code: str = Field(min_length=3, max_length=60)
    form_version: str = Field(min_length=1, max_length=30)
    answers: dict = Field(default_factory=dict)


class PriceCatalogCreate(BaseModel):
    service_code: str = Field(min_length=2, max_length=60)
    name_vi: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=2, max_length=40)
    unit_price_vnd: StrictInt = Field(gt=0)
    max_auto_discount_pct: StrictInt = Field(default=5, ge=0, le=100)


class EstimateCatalogLineInput(BaseModel):
    catalog_item_id: str
    quantity: StrictInt = Field(default=1, gt=0, le=100)


class EstimateFromCatalogCreate(BaseModel):
    patient_id: str
    plan_id: str
    lines: list[EstimateCatalogLineInput] = Field(min_length=1)


class DiscountRequestCreate(BaseModel):
    discount_amount_vnd: StrictInt = Field(gt=0)
    reason: str = Field(min_length=5, max_length=300)


class DiscountDecisionRequest(BaseModel):
    approve: bool
    decision_note: str = Field(min_length=3, max_length=300)


TriStateRisk = Literal[
    "present", "explicit_negative", "unknown", "not_applicable", "unanswered"
]


def _check_fdi_code(code: str) -> None:
    if len(code) != 2 or not code.isdigit():
        raise ValueError("FDI tooth_code must contain exactly two digits")
    a, b = int(code[0]), int(code[1])
    if not ((1 <= a <= 4 and 1 <= b <= 8) or (5 <= a <= 8 and 1 <= b <= 5)):
        raise ValueError("Invalid FDI tooth code")


class MedicalRiskReviewCreate(BaseModel):
    encounter_id: str | None = None
    drug_allergy_state: TriStateRisk = "unanswered"
    drug_allergy_detail: str | None = Field(default=None, max_length=300)
    bleeding_anticoagulant_state: TriStateRisk = "unanswered"
    cardiovascular_hypertension_state: TriStateRisk = "unanswered"
    pregnancy_nursing_state: TriStateRisk = "unanswered"
    source: Literal[
        "patient_interview_demo", "clinician_review_demo", "legacy_record_demo"
    ] = "clinician_review_demo"

    @model_validator(mode="after")
    def check_present_detail(self):
        if self.drug_allergy_state == "present" and (
            not self.drug_allergy_detail or not self.drug_allergy_detail.strip()
        ):
            raise ValueError(
                "drug_allergy_detail is required when drug_allergy_state is 'present' (EMR-003)"
            )
        return self


class EncounterDiagnosisCreate(BaseModel):
    tooth_code: str | None = None
    diagnosis_code_demo: str = Field(min_length=2, max_length=60)
    summary_vi: str = Field(min_length=3, max_length=300)
    authoring_source: Literal["clinician_manual"] = "clinician_manual"

    @model_validator(mode="after")
    def check_optional_tooth(self):
        if self.tooth_code is not None:
            _check_fdi_code(self.tooth_code)
        return self


class PerformedProcedureCreate(BaseModel):
    plan_task_id: str | None = None
    tooth_code: str = Field(min_length=2, max_length=2)
    surface: str = Field(min_length=1, max_length=8)
    procedure_code_demo: str = Field(min_length=2, max_length=60)
    description_vi: str = Field(min_length=3, max_length=300)
    clinical_evidence_note: str = Field(min_length=3, max_length=300)
    authoring_source: Literal["clinician_manual"] = "clinician_manual"

    @model_validator(mode="after")
    def check_tooth(self):
        _check_fdi_code(self.tooth_code)
        return self


class MilestoneChecklistCreate(BaseModel):
    title_vi: str = Field(min_length=3, max_length=180)
    criteria_items: list[str] = Field(min_length=1, max_length=20)


class MilestoneEvaluateRequest(BaseModel):
    all_criteria_met: bool
    clinician_override_reason: str | None = Field(default=None, max_length=300)


class PlanLifecycleTransitionCreate(BaseModel):
    action: Literal["pause", "resume", "cancel", "terminate"]
    reason: str = Field(min_length=5, max_length=300)
    clinical_handoff_note: str = Field(default="", max_length=300)


class WaitlistCreate(BaseModel):
    patient_id: str
    preferred_practitioner_id: str | None = None
    preferred_date_window: str = Field(min_length=3, max_length=60)
    service_note_minimized: str = Field(min_length=3, max_length=200)


class InstallmentTrancheInput(BaseModel):
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount_vnd: StrictInt = Field(gt=0)


class InstallmentScheduleCreate(BaseModel):
    estimate_id: str
    consent_id: str
    tranches: list[InstallmentTrancheInput] = Field(min_length=1, max_length=36)


class QualityIncidentCreate(BaseModel):
    category: Literal[
        "sterilization_breach",
        "near_miss",
        "equipment_hazard",
        "medication_label",
        "workflow_delay",
    ]
    severity: Literal["low", "moderate", "high", "critical"]
    summary: str = Field(min_length=5, max_length=300)
    evidence_note: str = Field(min_length=3, max_length=300)
    encounter_id: str | None = None
    source_kind: Literal["staff_reported"] = "staff_reported"


DELEGATABLE_PERMISSIONS = Literal[
    "finance.catalog_manage",
    "operations.shift_manage",
    "operations.downtime_manage",
    "inventory.adjust_request",
    "portal.manage",
]


class OdontogramLegendCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    label_vi: str = Field(min_length=3, max_length=180)
    symbol_code: str = Field(min_length=1, max_length=16)
    category: Literal["restoration", "prosthesis", "endodontic", "missing", "implant"]


class OdontogramRestorationUpsert(BaseModel):
    expected_revision: StrictInt = Field(ge=0)
    legend_code: str = Field(min_length=2, max_length=40)
    surface: str = Field(min_length=1, max_length=8)
    material_note: str = Field(min_length=3, max_length=260)
    source_kind: Literal["existing_external_reported", "performed_in_clinic_demo"]
    documented_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    evidence_note: str = Field(min_length=3, max_length=260)
    encounter_id: str | None = None


class ExternalReferralCreate(BaseModel):
    encounter_id: str | None = None
    origin_facility_name: str = Field(min_length=3, max_length=200)
    referring_clinician_name: str = Field(min_length=3, max_length=160)
    referral_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    document_summary_vi: str = Field(min_length=5, max_length=300)
    content_sha256: str = Field(min_length=64, max_length=64)
    archive_object_id: str | None = None


class ExternalReferralReviewRequest(BaseModel):
    review_note: str = Field(min_length=3, max_length=300)


class BranchScopeGrantCreate(BaseModel):
    owner_group_key: str = Field(min_length=3, max_length=80)
    branch_id: str = Field(default="branch-main", min_length=2, max_length=36)


class TemporaryDelegationCreate(BaseModel):
    delegate_staff_id: str
    permission: DELEGATABLE_PERMISSIONS
    ttl_seconds: StrictInt = Field(default=600, ge=1, le=86400)
    reason: str = Field(min_length=5, max_length=300)


class StaffOperationalTaskCreate(BaseModel):
    assignee_staff_id: str
    patient_id: str | None = None
    title: str = Field(min_length=3, max_length=200)
    due_at: datetime
    escalation_owner_role: Literal[
        "clinic_owner", "medical_director", "dentist", "treatment_coordinator"
    ] = "clinic_owner"

    @model_validator(mode="after")
    def check_due_tz(self):
        if not self.due_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 due_at timestamp")
        return self


class InternalHandoffCreate(BaseModel):
    patient_id: str | None = None
    task_id: str | None = None
    message_vi: str = Field(min_length=3, max_length=400)

    @model_validator(mode="after")
    def check_tethered(self):
        if not self.patient_id and not self.task_id:
            raise ValueError(
                "Internal handoff note must be tied to patient_id or task_id (HR-006)"
            )
        return self


class PatientContactLogCreate(BaseModel):
    channel: Literal["phone", "sms_stub", "zalo_stub", "in_person", "portal"]
    visibility: Literal["internal_staff_only", "patient_visible"]
    summary_text: str = Field(min_length=3, max_length=300)


class ServiceComplaintCreate(BaseModel):
    patient_id: str
    severity: Literal["low", "moderate", "high", "critical"]
    public_intake_summary: str = Field(min_length=5, max_length=300)
    private_investigation_notes: str = Field(min_length=3, max_length=600)


class OpsAssistantQueryRequest(BaseModel):
    tool_name: Literal[
        "chair_utilization_summary",
        "low_stock_alerts",
        "overdue_staff_tasks",
        "waitlist_count",
    ]
    prompt_note: str = Field(default="", max_length=400)


FACILITY_PERMITTED_SCOPE = Literal[
    "general_dentistry",
    "prosthodontics",
    "endodontics",
    "orthodontics",
    "oral_surgery_minor",
    "implant_demo",
]


class FacilityLicenseProfileCreate(BaseModel):
    legal_entity_name_demo: str = Field(min_length=3, max_length=200)
    license_number_demo: str = Field(min_length=5, max_length=80)
    license_type: Literal[
        "specialist_dental_clinic",
        "polyclinic_dental_dept",
        "hospital_odonto_dept",
    ]
    permitted_scopes: list[FACILITY_PERMITTED_SCOPE] = Field(min_length=1, max_length=12)
    regulating_authority_demo: str = Field(min_length=3, max_length=160)
    verification_status: Literal[
        "unverified_synthetic",
        "pending_counsel_review",
        "verified_demo_only",
    ] = "unverified_synthetic"

    @model_validator(mode="after")
    def check_synthetic_license_prefix(self):
        norm = self.license_number_demo.strip().upper()
        if not (norm.startswith("DEMO-") or norm.startswith("SYN-")):
            raise ValueError(
                "license_number_demo must begin with DEMO- or SYN-; real clinic license numbers are prohibited (AGENTS.md / ORG-001)"
            )
        return self


class ProcedureDurationTemplateCreate(BaseModel):
    procedure_code: str = Field(min_length=2, max_length=60)
    title_vi: str = Field(min_length=3, max_length=180)
    recommended_minutes: StrictInt = Field(ge=15, le=240)
    buffer_minutes: StrictInt = Field(default=0, ge=0, le=60)
    fallback_minutes: StrictInt = Field(default=30, ge=15, le=120)


class ScheduleOptimizerProposeRequest(BaseModel):
    patient_id: str
    practitioner_id: str
    chair_id: str
    procedure_code: str = Field(min_length=2, max_length=60)
    window_start_at: datetime
    window_end_at: datetime
    override_duration_minutes: StrictInt | None = Field(default=None, ge=15, le=240)

    @model_validator(mode="after")
    def check_window(self):
        if not self.window_start_at.tzinfo or not self.window_end_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 window timestamps")
        if self.window_end_at <= self.window_start_at:
            raise ValueError("window_end_at must be after window_start_at")
        return self


class ScheduleOptimizerAcceptRequest(BaseModel):
    slot_index: StrictInt = Field(default=0, ge=0, le=50)
    reason_demo: str = Field(
        default="Lịch hẹn duyệt từ gợi ý tối ưu hóa (SCH-012)", max_length=260
    )


class FinancialReceiptExportCreate(BaseModel):
    export_note: str = Field(default="", max_length=260)
    claim_verified_bank_settlement: bool = False


class StaffAttendanceCreate(BaseModel):
    staff_id: str
    check_in_at: datetime
    check_out_at: datetime
    note: str = Field(default="", max_length=260)

    @model_validator(mode="after")
    def check_attendance_times(self):
        if not self.check_in_at.tzinfo or not self.check_out_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 check-in/check-out timestamps")
        if self.check_out_at <= self.check_in_at:
            raise ValueError("check_out_at must be strictly after check_in_at")
        return self


class ReminderTemplateCreate(BaseModel):
    template_code: str = Field(min_length=2, max_length=60)
    channel: Literal["sms_stub", "zalo_stub", "email_stub", "portal"]
    purpose_category: Literal["appointment_care_notice", "marketing_promo"]
    body_template_vi: str = Field(min_length=5, max_length=400)
    window_start_hour_hcm: StrictInt = Field(default=8, ge=0, le=23)
    window_end_hour_hcm: StrictInt = Field(default=20, ge=1, le=24)

    @model_validator(mode="after")
    def check_hours(self):
        if self.window_end_hour_hcm <= self.window_start_hour_hcm:
            raise ValueError("window_end_hour_hcm must exceed window_start_hour_hcm")
        return self


class CommunicationDraftCreate(BaseModel):
    patient_id: str
    template_code: str = Field(min_length=2, max_length=60)
    proposed_send_at: datetime
    appointment_id: str | None = None
    custom_context_note: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def check_send_tz(self):
        if not self.proposed_send_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 proposed_send_at")
        return self


class SatisfactionTokenIssueRequest(BaseModel):
    appointment_id: str


class SatisfactionSurveySubmit(BaseModel):
    clinic_id: str
    survey_token: str = Field(min_length=16, max_length=600)
    service_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    overall_rating: StrictInt = Field(ge=1, le=5)
    wait_time_rating: StrictInt = Field(ge=1, le=5)
    clarity_rating: StrictInt = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=400)

    @model_validator(mode="after")
    def reject_pii_in_anonymous_comment(self):
        import re

        txt = self.comment.strip()
        if txt:
            if (
                re.search(r"(?:\+?84|0)\d{8,10}\b", txt)
                or re.search(r"\b\d{9,12}\b", txt)
                or "@" in txt
            ):
                raise ValueError(
                    "Do not include phone numbers, email, or national ID in anonymous satisfaction survey (CRM-011)"
                )
        return self


class IncumbentPatientRecordInput(BaseModel):
    legacy_patient_id: str = Field(min_length=1, max_length=80)
    display_name_demo: str = Field(min_length=2, max_length=160)
    birth_year: StrictInt = Field(ge=1900, le=2100)
    historical_balance_vnd: StrictInt = Field(ge=0)
    legacy_signature_label: Literal[
        "legacy_unsigned_or_paper",
        "legacy_vendor_record_not_denlyra_signed",
    ] = "legacy_unsigned_or_paper"


class IncumbentExportIngestCreate(BaseModel):
    source_vendor_code: str = Field(min_length=2, max_length=60)
    schema_version: str = Field(min_length=1, max_length=30)
    export_license_confirmed: bool
    export_license_note: str = Field(min_length=5, max_length=300)
    declared_sha256: str = Field(min_length=64, max_length=64)
    records: list[IncumbentPatientRecordInput] = Field(min_length=1, max_length=500)


class IncumbentExportApproveRequest(BaseModel):
    review_note: str = Field(min_length=3, max_length=300)


class MigrationCutoverPlanCreate(BaseModel):
    incumbent_package_id: str
    cutover_mode: Literal["parallel_run_read_only_legacy", "cutover_locked_legacy"]
    legacy_write_freeze_confirmed: bool
    reconciled_patient_count: StrictInt = Field(ge=0)
    reconciled_total_balance_vnd: StrictInt = Field(ge=0)
    rollback_runbook_note: str = Field(min_length=5, max_length=300)


class RedactedTelemetryCreate(BaseModel):
    trace_id: str = Field(min_length=4, max_length=64)
    span_name: str = Field(min_length=2, max_length=120)
    severity: Literal["info", "warn", "error"] = "info"
    attributes: dict[str, str | int | bool] = Field(default_factory=dict)


class ClinicOnboardingConfigCreate(BaseModel):
    configured_roles: list[
        Literal[
            "clinic_owner",
            "medical_director",
            "dentist",
            "assistant",
            "receptionist",
            "treatment_coordinator",
            "finance",
        ]
    ] = Field(min_length=1, max_length=10)
    legacy_field_mapping: dict[str, str] = Field(default_factory=dict)
    mark_ready: bool = False


class SupportConsentGrantCreate(BaseModel):
    ticket_reference: str = Field(min_length=3, max_length=80)
    ttl_seconds: StrictInt = Field(default=600, ge=60, le=86400)
    allow_live_patient_records: bool = False


class SupportDiagnosticExportRequest(BaseModel):
    grant_id: str
    include_patient_records: bool = False


class SecurityIncidentCreate(BaseModel):
    severity: Literal["low", "medium", "high", "critical_potential_breach"]
    incident_type: Literal[
        "unauthorized_access_attempt",
        "token_compromise",
        "device_theft",
        "malware_upload_quarantined",
        "data_exfiltration_alert",
    ]
    summary: str = Field(min_length=5, max_length=300)


class SecurityIncidentTransitionRequest(BaseModel):
    next_status: Literal["contained", "counsel_reviewed", "closed"]
    detail_note: str = Field(min_length=3, max_length=300)
    counsel_guidance_note: str | None = Field(default=None, max_length=400)
    notification_decision: str | None = Field(default=None, max_length=120)


class SupplyChainVerifyRequest(BaseModel):
    constraints_override_text: str | None = Field(default=None, max_length=8000)


class PatientAccessRequestCreate(BaseModel):
    requester_kind: Literal["self", "guardian", "unverified_third_party"]
    requester_name: str = Field(min_length=2, max_length=160)
    request_type: Literal["structured_access_export", "erasure_request"]
    authority_verified: bool


class CancellationRecoveryRequest(BaseModel):
    claim_clinical_urgency_ranking: bool = False


class PortalUploadCreate(BaseModel):
    original_filename: str = Field(min_length=3, max_length=200)
    declared_media_type: str = Field(min_length=3, max_length=80)
    content_b64: str = Field(min_length=4, max_length=80000)


class PortalUploadReviewRequest(BaseModel):
    decision: Literal["approved_by_staff", "rejected_by_staff"]
    review_note: str = Field(min_length=3, max_length=300)


class PortalSupportMessageCreate(BaseModel):
    message_text: str = Field(min_length=3, max_length=500)


class PortalSupportReplyRequest(BaseModel):
    reply_text: str = Field(min_length=3, max_length=500)
    authoring_source: Literal["human_staff"] = "human_staff"


class StaffCompetencyUpsert(BaseModel):
    staff_id: str
    competency_code: str = Field(min_length=2, max_length=60)
    title_vi: str = Field(min_length=3, max_length=200)
    expires_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class StaffCompetencyValidateRequest(BaseModel):
    staff_id: str
    competency_code: str = Field(min_length=2, max_length=60)
    as_of_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class TerminologyCodeCreate(BaseModel):
    code_system: Literal["ICD-10-VN-DEMO", "SNOMED-DENTAL-DEMO", "LOCAL-PROC-DEMO"]
    system_version: str = Field(min_length=1, max_length=30)
    code: str = Field(min_length=1, max_length=60)
    display_vi: str = Field(min_length=2, max_length=240)


class TerminologyMappingCreate(BaseModel):
    source_code: str = Field(min_length=2, max_length=60)
    target_code_system: Literal["ICD-10-VN-DEMO", "SNOMED-DENTAL-DEMO", "LOCAL-PROC-DEMO"]
    target_system_version: str = Field(min_length=1, max_length=30)
    target_code: str = Field(min_length=1, max_length=60)
    equivalence: Literal["exact", "narrower"] = "exact"
    mapping_method: Literal["clinician_verified_exact"] = "clinician_verified_exact"


class SpecialtyTaskBlueprintItem(BaseModel):
    phase: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=3, max_length=160)


class SpecialtyPlanTemplateCreate(BaseModel):
    template_code: str = Field(min_length=2, max_length=60)
    specialty: Literal["implant", "orthodontics", "endodontics", "prosthodontics", "pediatric"]
    title_vi: str = Field(min_length=3, max_length=200)
    source_kind: Literal["clinic_clinician_authored"] = "clinic_clinician_authored"
    tasks_blueprint: list[SpecialtyTaskBlueprintItem] = Field(min_length=1, max_length=25)


class InstantiateSpecialtyTemplateRequest(BaseModel):
    patient_id: str
    template_id: str


class LabVendorPriceCreate(BaseModel):
    vendor_code: str = Field(min_length=2, max_length=60)
    prosthesis_code: str = Field(min_length=2, max_length=60)
    unit_price_vnd: StrictInt = Field(gt=0, le=500_000_000)
    remake_surcharge_vnd: StrictInt = Field(default=0, ge=0, le=500_000_000)


class LabInvoiceReconcileCreate(BaseModel):
    vendor_code: str = Field(min_length=2, max_length=60)
    prosthesis_code: str = Field(min_length=2, max_length=60)
    billed_amount_vnd: StrictInt = Field(gt=0, le=500_000_000)
    vendor_invoice_ref: str = Field(min_length=3, max_length=80)


class LongitudinalOverlayCreate(BaseModel):
    tooth_code: str = Field(min_length=2, max_length=2)
    baseline_archive_object_id: str
    followup_archive_object_id: str
    alignment_label_vi: str = Field(min_length=5, max_length=260)
    claim_auto_diagnosis: bool = False

    @model_validator(mode="after")
    def check_overlay_tooth(self):
        _check_fdi_code(self.tooth_code)
        return self


class ScheduledReportExportCreate(BaseModel):
    report_kind: Literal["single_clinic_kpi", "multi_branch_aggregate"]
    owner_group_key: str | None = Field(default=None, max_length=80)
    recipient_email: str = Field(min_length=5, max_length=160)
    include_phi: bool = False


class ReleaseProposalCreate(BaseModel):
    release_tag: str = Field(min_length=3, max_length=60)
    target_migration_revision: str = Field(min_length=4, max_length=80)
    backward_compatible_schema: bool
    forward_fix_and_backup_plan: str = Field(min_length=5, max_length=400)


class ReleaseCanaryApproveRequest(BaseModel):
    canary_stage: Literal["canary_5pct", "canary_25pct", "promoted_100pct", "rolled_back"]


class MultibranchOperatorCreate(BaseModel):
    owner_group_key: str = Field(min_length=3, max_length=80)
    operator_staff_id: str
    assigned_clinic_id: str
    grants_clinical_chart_access: bool = False


class OfflineSyncMutationCreate(BaseModel):
    client_mutation_id: str = Field(min_length=3, max_length=80)
    entity_type: Literal["draft_note", "signed_clinical_snapshot", "appointment_booking"]
    entity_id: str = Field(min_length=2, max_length=36)
    base_version: StrictInt = Field(ge=0)
    resolution_strategy: Literal["optimistic_version_check"] = "optimistic_version_check"
    payload: dict = Field(default_factory=dict)


class NoshowRiskRequest(BaseModel):
    include_demographic_features: bool = False
    simulate_model_unavailable: bool = False


class CpsatJobInput(BaseModel):
    patient_id: str
    practitioner_id: str
    duration_minutes: StrictInt = Field(ge=15, le=240)


class CpsatOptimizeRequest(BaseModel):
    window_start_at: datetime
    window_end_at: datetime
    solver_budget_ms: StrictInt = Field(default=250, ge=0, le=5000)
    simulate_solver_timeout: bool = False
    requests: list[CpsatJobInput] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def check_cpsat_window(self):
        if not self.window_start_at.tzinfo or not self.window_end_at.tzinfo:
            raise ValueError("Provide timezone-aware RFC3339 window timestamps")
        if self.window_end_at <= self.window_start_at:
            raise ValueError("window_end_at must exceed window_start_at")
        return self
