# ADR-020: Vietnam-Region IaC Policy Guard, Partner Insurance Sandbox, Measurable LoRA Lift Gate, Simulation Plan Attestation & Channel-Specific Messaging Contracts

- **Status:** Accepted (synthetic foundation)
- **Date:** 2026-11-25
- **Tasks:** `T029`, `T030`
- **Catalog IDs:** `OPS-003`, `FIN-012`, `AI-012`, `TRT-004`, `CRM-006`, `CRM-007`, `CRM-008`

## Context
Seven remaining product catalog requirements govern hosting sovereignty and secret externalization (`OPS-003`), partner dental insurance claims (`FIN-012`), domain-adapted LoRA/QLoRA model benchmarking (`AI-012`), clinician treatment plan version attestation (`TRT-004`), and channel-specific Zalo OA/ZNS, SMS, and Email governance (`CRM-006`, `CRM-007`, `CRM-008`). Under `AGENTS.md`, the synthetic demonstrator must never provision cloud infrastructure, call government BHYT portals, deploy clinical AI writes, claim legal dentist approval, or transmit real external messages, yet every safety invariant must be machine-enforced and negatively tested before real adapters exist.

## Decision
1. **Declarative Vietnam-Region & Secret-Ref IaC Guard (`OPS-003`):** `IacBlueprintValidation` enforces in-country region allowlists, synthetic DPA references, and `secret_ref://` indirection while constraining `NOT live_cloud_provisioned`.
2. **Partner-Only Non-Settling Insurance Claims (`FIN-012`):** `InsurancePartnerContract` blocks `government_bhyt_portal` (`409`), and `InsuranceClaimDraft` requires `financial` + `data_processing` consents, bounds `claimed_amount_vnd <= charge.amount_vnd`, and constrains `NOT auto_settled_payment` and `NOT called_government_bhyt_api`.
3. **Licensed De-Identified & Positive-Lift LoRA Gate (`AI-012`):** `AiAdaptationRun` rejects unlicensed/un-deidentified corpora and PII tokens, requires `measured_lift_bp >= min_required_lift_bp > 0`, and constrains `NOT deployed_to_clinical_production` and `NOT wrote_to_emr`.
4. **Canonical Simulation-Only Plan Review Attestation (`TRT-004`):** `PlanReviewAttestation` binds `(plan_id, version_number, tasks, dependencies)` by SHA-256 for active `dentist`/`medical_director` principals while hard-blocking `legal_clinical_approval` (`NOT is_legal_clinical_approval`).
5. **Zero-Egress Channel Contracts (`CRM-006`, `CRM-007`, `CRM-008`):** Zalo ZNS contracts require `official_api_only` + confirmed VND pricing + param allowlists; SMS dispatches separate carrier DLR hashes from appointment confirmation and propagate opt-outs; Email dispatches require `SPF + DKIM + DMARC`, block scripts/pixels/CRLF/PHI, and enforce rolling 1-hour `429` rate limits (`NOT live_external_egress`).

## Consequences
- Adds forward-only migration `0015_iac_insurance_lora_plan_attestation_and_channels` (+9 tables -> `144` domain tables).
- Advances `FUNCTION_CATALOG.md` synthetic demo coverage to `216/222` (`D`), leaving strictly the 6 non-fabricable external legal/PKI/government/SaMD items (`AI-013`, `INT-006`, `INT-010`, `SEC-003`, `SEC-005`, `SEC-009`) marked `—`.
