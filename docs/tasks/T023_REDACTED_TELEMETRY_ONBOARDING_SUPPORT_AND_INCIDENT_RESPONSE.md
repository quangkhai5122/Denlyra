# T023 — PHI-Redacted Telemetry, Per-Clinic Onboarding, Consent-Gated Support Diagnostics, Incident Response & Supply-Chain Verifier
Priority P1 (`OPS` / `SEC`) · Owner: Platform Reliability, Observability & Security · Depends T001, T010, T014, T016, T021

**Status (2026-11-25):** Completed (denylist + PII-pattern telemetry redactor, isolated per-clinic onboarding checklist, owner-consent-gated support diagnostic bundles without live PHI, forensic-anchored security breach workflow requiring counsel review on high/critical cases, and exact-pinning CycloneDX-style SBOM lockfile verifier verified in `test_ops_security_governance.py`). See [ADR-017](../adr/ADR-017-redacted-telemetry-onboarding-incident-portal-quarantine-and-hr-competency.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **PHI-Redacted Structured Telemetry (`OPS-005`):**
   - `redacted_telemetry_event` scrubs sensitive keys (`note_content`, `clinical_note`, `patient_name`, `phone`, `access_token`, etc.), regex PII (phones, 9–12 digit IDs, emails, JWTs), and clinic patient names before persistence (`CheckConstraint("NOT contains_phi_or_note_text")`).
2. **Isolated Per-Clinic Onboarding Configuration (`OPS-010`):**
   - `clinic_onboarding_config` versions per-clinic roles, catalog readiness, quarantined form bindings, and legacy field mappings; marking Clinic A ready never leaks or satisfies readiness for Clinic B (`409` if Clinic B lacks its own catalog/forms).
3. **Consent-Gated Customer Support Diagnostics (`OPS-012`):**
   - `customer_support_consent_grant` + `support_diagnostic_bundle` block diagnostic exports without an active, unrevoked owner grant (`403`) and forbid `include_patient_records=True` (`409`, `CheckConstraint("NOT allow_live_patient_records")`).
4. **Security Incident & Breach Containment Workflow (`SEC-012`):**
   - `security_incident_case` + `security_incident_event` snapshot the clinic's tamper-evident `AuditEvent` head sequence/hash at triage and block closing `high`/`critical_potential_breach` cases until legal counsel guidance and notification assessment are recorded (`409`).
5. **Software Supply Chain & SBOM Lockfile Verifier (`SEC-013`):**
   - `supply_chain_attestation` inspects `backend/constraints-baseline.txt` and `apps/clinic-web/package-lock.json`, rejects unpinned/floating constraint lines (`409`), and signs a canonical component SBOM digest.

## Mandatory Negative Tests (Written Before Domain Code)
1. Emitting telemetry containing clinical note prose, patient name, phone number, or Bearer JWT scrubs every sensitive value and increments `redacted_field_count` (`OPS-005`).
2. Clinic B attempting `mark_ready=True` onboarding after only Clinic A seeded catalog/forms -> `409` (`OPS-010`); support diagnostic export without active owner grant, after grant revocation, or with `include_patient_records=True` -> `403`/`409` (`OPS-012`).
3. Closing a `critical_potential_breach` incident without `counsel_guidance_note` -> `409` (`SEC-012`); verifying supply chain with unpinned `>=` dependency override -> `409` (`SEC-013`).
