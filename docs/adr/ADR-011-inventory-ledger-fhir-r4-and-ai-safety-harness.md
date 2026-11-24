# ADR-011 — Append-Only Inventory Lot Ledger (`T011`), Honest FHIR R4 Export, and Offline Draft-Only AI Safety Harness (`T012`)

- **Status:** Accepted (synthetic research foundation; real external AI models, government health exchange, and live clinical workflows remain disabled/gated)
- **Date:** 2026-11-24
- **Tasks:** [T011](../tasks/T011_INVENTORY_LEDGER.md), [T012](../tasks/T012_FHIR_AND_AI_HARNESS.md)
- **Related invariants:** `INV-001`, `INV-006`, `INV-013`, `INV-019`, `INV-022`, `INV-023`, `ADR-004`

## Context

1. **Inventory governance (`M5` / `T011`):** Dental clinics manage lot-tracked, expiry-sensitive materials (implants, healing abutments, membranes, bone grafts, anesthetics). Naive CRUD inventory tables that overwrite a `quantity` integer lose auditability, conflate planned case reservations with actual chairside consumption (`INV-023`), allow expired lots to be picked, and permit single-actor shrinkage write-offs without independent review (`INV-010`).
2. **Interoperability & AI safety (`M6` / `M7` / `T012`):** Future clinic integrations require structured FHIR R4 exports (`INT-002`, `INT-003`) without misrepresenting legacy paper scans or synthetic signatures as legally authenticated EMRs. Likewise, per `ADR-004` and `AGENTS.md`, assistive AI features must be strictly **draft-only**, offline/zero-egress in the synthetic build, resilient against prompt injection embedded in untrusted notes/scans (`AI-010`), measurable via an automated evaluation harness (`AI-009`), and cleanly disableable via a kill switch (`AI-014`).

## Decisions

### 1. Append-Only Stock Movement Ledger, FEFO & Dual Control (`T011`)
- Add 6 relational tables in forward-only migration `0006_inventory_fhir_and_ai_harness.py`: `inventory_supplier`, `inventory_sku`, `purchase_order`, `inventory_lot`, `stock_movement`, `stock_reservation`, and `stock_adjustment_request` (plus 3 AI tables -> **50 tables total**).
- Enforce `stock_movement` immutability via DB triggers (`tr_stock_movement_no_update`, `tr_stock_movement_no_delete`) and non-negative lot balance bounds (`tr_stock_movement_lot_bounds`).
- Compute `physical_on_hand_qty` exclusively from `stock_movement` (`+qty` for `receipt_accepted` / `adjustment_in`, `-qty` for `procedure_consumed` / `adjustment_out`), and `available_qty = physical_on_hand_qty - active_reserved_qty` (`INV-023`).
- Require an active clinic `encounter_id` and non-expired, non-quarantined `lot_id` for `procedure_consumed`; provide deterministic FEFO lot recommendations (`expiry_date ASC`).
- Require dual-control approval (`approver_staff_id != requester_staff_id`, restricted to `clinic_owner` / `medical_director`) before a `stock_adjustment_request` emits a `stock_movement`.

### 2. Clinic-Scoped FHIR R4 Export with Explicit `HTEST` & Provenance (`T012`)
- Implement `fhir_interop.py` generating HL7 FHIR R4 `Bundle` (`type: "collection"`) containing `Patient`, `Practitioner`, `Appointment`, `Encounter`, `DocumentReference`, and `Provenance`.
- Every exported resource carries `meta.security = [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST"}]` and honest `Provenance` distinguishing `legacy_scan` (`T006`) and `synthetic_signed_NOT_legal` (`T004`), rejecting any attempt to validate bundles lacking `HTEST` or asserting unverified legal signatures.

### 3. Zero-Egress Draft-Only AI Copilot, Prompt-Injection Firewall & Eval Harness (`T012`)
- Implement `ai_harness.py` using a deterministic local rule/span extractor registered in `ai_model_registry` (`data_locality="local_loopback_no_egress"`, zero external network calls).
- Inspect all untrusted input text through a prompt-injection / exfiltration / SQL-command detector (`AI-010`) before extraction; malicious inputs are quarantined (`status="blocked_prompt_injection"`), audited, and blocked with `409`.
- Extraction outputs include exact character spans `[start_char, end_char]` and abstain (`abstained_not_stated`) when allergy or symptom state is absent or ambiguous (`INV-022`).
- Clinicians (`dentist` / `medical_director`) must explicitly review and accept an `ai_draft_artifact` to create an ordinary `draft` `ClinicalNote` (`AI-003`), which still requires normal clinician editing/sealing.
- Ship `POST /api/v1/ai/evaluations/run` and `scripts/run_ai_eval_harness.py` (`AI-009`) verifying held-out clinical extraction accuracy, tri-state abstention, and `100%` prompt-injection block rate in CI.

## Consequences
- Completes the `M5` inventory governance slice and `M6`/`M7` synthetic FHIR R4 + AI safety harness while keeping `"ai_diagnosis": False`, `"ai_sends_patient_data": False`, `"clinical_e_signature": False`, and `"emr_certified": False` strictly enforced.
