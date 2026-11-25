# ADR-019: Sandbox Provider Contracts, DICOM Patient-ID Quarantine, Audio-Consented Speech Drafts & Fail-Closed PHI Release Gates

- **Status:** Accepted (synthetic foundation)
- **Date:** 2026-11-25
- **Tasks:** `T027`, `T028`
- **Catalog IDs:** `CRM-012`, `OPS-008`, `ORG-010`, `INT-007`, `INT-008`, `INT-004`, `AI-001`, `FIN-009`, `INT-009`, `SEC-014`, `SEC-015`

## Context
Remaining platform surface areas involve external identity directories (`ORG-010`), payment and messaging webhooks (`INT-007`, `INT-008`), automated cancellation outreach (`CRM-012`), capacity benchmarking (`OPS-008`), medical imaging metadata (`INT-004`), Vietnamese speech dictation (`AI-001`), accounting/e-invoice interchange (`FIN-009`, `INT-009`), and security/production release gating (`SEC-014`, `SEC-015`). In a synthetic demonstrator, fabricating external vendor connections, cloud SLAs, tax invoices, or PHI readiness would violate `AGENTS.md`. Conversely, leaving contract invariants untested invites replay, wrong-patient imaging, stale OIDC sessions, and PHI leaks when adapters are wired later.

## Decision
1. **Policy-Gated Outreach Without Clinical Triage (`CRM-012`):** Automated cancellation outreach requires an `approved_by_leadership` clinic policy and enforces `NOT clinical_triage_inferred` and `NOT auto_booked` via portable SQLite/PostgreSQL `CheckConstraint`s.
2. **Measured Local Benchmarks Without Invented SLAs (`OPS-008`):** `LoadBenchmarkRun` executes bounded real SQLAlchemy round-trips, records observed `p50_latency_us`/`p95_latency_us`/`max_latency_us`, and enforces `NOT claims_production_sla`.
3. **Immediate OIDC Deprovisioning via `token_version` (`ORG-010`):** Directory sync revocations atomically set `staff.active = False` and increment `staff.token_version`, invalidating all in-flight bearer tokens without waiting for TTL expiry.
4. **Loopback Sandbox Webhooks (`INT-007`, `INT-008`):** Messaging dispatches honor `STOP`/`HUY` opt-outs, reject clinical diagnosis text, and enforce `zero_external_egress`. Payment webhooks verify `HMAC-SHA256` + 300s freshness, deduplicate exact retries by `payload_sha256`, reject mutated replays (`409`), and keep `implies_clinical_completion = False`.
5. **Quarantine & Fail-Closed Regulatory Boundaries (`INT-004`, `AI-001`, `FIN-009`, `INT-009`, `SEC-014`, `SEC-015`):**
   - DICOM study manifests require clinic-confirmed modalities and exact `dicom_patient_id_tag == patient_id` (`NOT diagnostic_samd_certified`).
   - Speech dictation requires verified audio + `data_processing` consent, passes prompt-injection screening, and enforces `NOT wrote_to_emr`.
   - Accounting exports emit PHI-free integer `amount_vnd` summaries while hard-blocking official tax e-invoices and government API calls (`409`).
   - Adversarial security checks verify SSRF/traversal/CORS/RBAC blocks while marking `independent_external_pentest_complete = False`, and `ReleaseGateEvaluation` enforces `NOT phi_processing_enabled`.

## Consequences
- Adds forward-only migration `0014_sandbox_contracts_dicom_speech_and_release_gates` (+13 tables -> `134` domain tables).
- Advances `FUNCTION_CATALOG.md` synthetic demo coverage to `209/222` (`D`), leaving the 13 purely external/regulatory/clinical-signoff items honestly marked `—`.
