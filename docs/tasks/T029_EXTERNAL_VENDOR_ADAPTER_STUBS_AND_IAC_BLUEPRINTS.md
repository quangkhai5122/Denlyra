# T029 — Vietnam-Region IaC Policy Guard, Partner Insurance Sandbox, Offline LoRA Lift Gate & Plan Review Attestation

- **Status:** Completed (synthetic foundation verified; live cloud provisioning, real BHYT/insurer settlement, clinical model deployment, and legal plan approval remain fail-closed)
- **Feature IDs:** `OPS-003`, `FIN-012`, `AI-012`, `TRT-004`
- **Governing ADR:** [ADR-020](../adr/ADR-020-iac-region-guard-insurance-sandbox-lora-lift-plan-attestation-and-channel-contracts.md)
- **Related Risks:** `R-004` (simulation-only plan review), `R-007` (external insurer & AI adaptation governance)

## 1. Objective & Bounded Scope
1. **`OPS-003` — Vietnam-Region IaC Blueprint & Externalized-Secrets Validator:** Validate declarative hosting blueprints against Vietnam in-country region allowlists (`vn-ho-chi-minh-1`, `vn-ha-noi-1`), recorded synthetic DPA references, and `secret_ref://` externalization while hard-blocking inline credentials (`422`) and live cloud provisioning (`409`, `live_cloud_provisioned=False`).
2. **`FIN-012` — Partner-Scoped Private Dental Insurance Claim Sandbox:** Register non-government TPA sandbox contracts (hard-blocking unverified government BHYT portals with `409`), verify active `financial` + `data_processing` consents (`403`), cap `claimed_amount_vnd <= charge.amount_vnd`, and forbid auto-settling claims as collected payments (`auto_settled_payment=False`).
3. **`AI-012` — Licensed De-Identified Dataset & Measurable LoRA Lift Gate:** Require explicit dataset license + verified de-identification (`403` on unlicensed/scraped data, `422` on PII leakage in samples) and enforce `candidate_f1_bp - baseline_f1_bp >= min_required_lift_bp` (`409` on zero/insufficient lift; `deployed_to_clinical_production=False`).
4. **`TRT-004` — Clinician Plan Version Review Attestation Adapter:** Bind exact `(plan_id, version_number, tasks, DAG edges)` via canonical SHA-256 for verified active clinicians (`dentist`/`medical_director`), seal strictly as `demo_reviewed_simulation_NOT_dentist_approval`, and fail closed (`409`) on `legal_clinical_approval` claims.

## 2. Negative Cases (Red-First)
- IaC blueprint in foreign region (`us-east-1`), containing inline password/key (`422`), or requesting `apply_live_cloud_provisioning=True` (`409`).
- Registering `government_bhyt_portal` (`409`), filing insurance claim without consent (`403`), exceeding charge VND (`409`), or setting `auto_settle_as_paid=True` (`409`).
- LoRA adaptation run with `scraped_web` dataset (`403`), sample phone PII (`422`), or negative/insufficient F1 lift (`409`).
- Plan review attestation claiming `legal_clinical_approval` (`409`) or stale `expected_version_number` (`409`).
