# ADR-017: PHI-Redacted Telemetry, Consent-Gated Support, Incident/SBOM Governance, Quarantined Portal Uploads/Messaging & HR Competency/Commission Separation

- **Status:** Accepted (synthetic research demonstrator)
- **Date:** 2026-11-25
- **Related tasks:** `T023` (`OPS-005`, `OPS-010`, `OPS-012`, `SEC-012`, `SEC-013`), `T024` (`PAT-011`, `SCH-014`, `PORT-008`, `PORT-010`, `HR-007`, `HR-009`)
- **Builds on:** `ADR-007` (RBAC), `ADR-010` (archive retention), `ADR-012` (hash-chained audit), `ADR-013` (patient portal), `ADR-014` (performed procedure evidence), `ADR-016` (facility scope & cutover)

## Context
Operational observability, tenant onboarding, customer support diagnostics, security incident response, dependency supply-chain verification, patient subject-access exports, cancellation recovery, patient-uploaded files/messages, and clinical HR competency/payroll reporting sit directly on high-risk privacy and clinical safety boundaries. Without structural guards, operational logs leak clinical notes, support tools silently dump PHI, portal uploads introduce active content into charts, support bots dispense medical advice, expired credentials slip into restricted procedures, or payroll conflates collected cash with clinical execution.

## Decisions
1. **Telemetry Redaction & Consent-Gated Support (`OPS-005`, `OPS-012`):**
   - `redacted_telemetry_event` applies key-denylist, PII-regex, and tenant patient-name scrubbing prior to storage (`CheckConstraint("NOT contains_phi_or_note_text")`).
   - `support_diagnostic_bundle` requires an active, unrevoked `customer_support_consent_grant` (`CheckConstraint("NOT allow_live_patient_records")`) and exports only aggregate counts, migration state, and audit-chain health.
2. **Per-Clinic Onboarding Isolation, Forensic Breach Triage & Pinned SBOMs (`OPS-010`, `SEC-012`, `SEC-013`):**
   - `clinic_onboarding_config` validates each clinic's own price catalog and quarantined form registry without cross-clinic inheritance.
   - `security_incident_case` captures `AuditEvent` head sequence/digest on creation and blocks closing `high`/`critical_potential_breach` cases absent counsel guidance and notification decisions.
   - `supply_chain_attestation` parses `backend/constraints-baseline.txt` and `apps/clinic-web/package-lock.json`, failing closed (`409`) on unpinned Python specifications.
3. **Retention-Guarded Subject Access & Non-Clinical Cancellation Recovery (`PAT-011`, `SCH-014`):**
   - `patient_access_request` verifies self/guardian authority, blocks clinical record erasure under statutory retention (`409`), and strips internal staff notes from exports.
   - `cancellation_recovery_suggestion` filters waitlist candidates by active consent and ranks strictly FIFO (`CheckConstraint("NOT clinical_priority_inferred")`).
4. **Portal Quarantine, Human-Only Support Triage & HR Competency/Commission Boundaries (`PORT-008`, `PORT-010`, `HR-007`, `HR-009`):**
   - `portal_quarantined_upload` rejects executables, scripts, PDF `/JavaScript`, and EICAR payloads (`422`) and holds clean uploads in quarantine until clinician review.
   - `portal_support_message` routes urgent symptom keywords to human triage via `OutboxEvent` and enforces `CheckConstraint("NOT autonomous_medical_advice_sent")`.
   - `staff_competency_record` gates governed procedure codes inside `clinical_lifecycle.record_performed_procedure_evidence` (`409` when expired/missing), while `commission-preview` reports `PerformedProcedureEvidence` and `PaymentAllocation` on strictly separate axes.

## Consequences
- Migration `0012_telemetry_onboarding_incident_portal_and_hr` adds 12 normalized tables (total **109 domain tables**), raising synthetic catalog coverage to **187/222 (`D`)**.
- External cloud SIEM/WORM sinks, real antivirus daemons (ClamAV/sandboxed CDR), statutory counsel sign-offs, and live PostgreSQL 16 concurrency execution remain explicitly gated.
