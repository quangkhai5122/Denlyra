# T027 — Policy-Governed Cancellation Outreach, Local Capacity Benchmark & Sandbox Integration Contracts

- **Status:** Completed (synthetic foundation verified; external vendor contracts & live cloud SLAs remain gated)
- **Feature IDs:** `CRM-012`, `OPS-008`, `ORG-010`, `INT-007`, `INT-008`
- **Governing ADR:** [ADR-019](../adr/ADR-019-sandbox-provider-contracts-dicom-quarantine-speech-consent-and-release-gates.md)
- **Related Risks:** `R-001` (OIDC deprovisioning), `R-007` (external messaging & payment webhooks)

## 1. Objective & Bounded Scope
Implement safe, deterministic synthetic domain services, schema constraints, and loopback-only sandbox contracts for:
1. **`CRM-012` — Clinic-Policy-Governed Cancellation Slot Outreach:** Require an explicit leadership-approved `CancellationOutreachPolicy` before preparing automated waitlist recovery outreach on cancelled appointments; forbid clinical triage inference and auto-booking without human/patient confirmation.
2. **`OPS-008` — Reproducible Local Latency & Capacity Benchmark:** Measure real local `P50`/`P95`/`Max` query latencies (`µs`) and throughput without inventing cloud or production SLAs (`claims_production_sla=False`).
3. **`ORG-010` — OIDC Directory Group Mapping & Immediate Revocation Harness:** Map explicit `(idp_issuer, external_group_id)` pairs to clinic-scoped roles and immediately deactivate staff + bump `token_version` when directory membership is revoked so active JWTs fail with `401` on the very next request.
4. **`INT-007` — Consent & Opt-Out Messaging Sandbox Contract:** Enforce purpose-separated consent, `STOP`/`HUY` channel opt-out persistence, PHI/diagnosis minimization, and non-equivalence between delivery and appointment confirmation (`zero_external_egress=True`).
5. **`INT-008` — Signed Payment Webhook Sandbox with Replay Protection & Reversals:** Verify HMAC-SHA256 webhook signatures and 300s timestamp freshness, deduplicate exact retries idempotently, reject mutated payload replays (`409`), record integer `amount_vnd` payments and bounded reversals in `LedgerEntry`, and enforce `implies_clinical_completion=False`.

## 2. Negative Cases (Red-First)
- Preparing cancellation outreach when clinic policy is `draft_unapproved` or requests `clinical_triage_inferred=True` -> `409` / `422`.
- Running load benchmark with `claim_production_sla=True` -> `409 Conflict`.
- Wildcard `*` OIDC group mapping -> `422`; revoked IdP directory sync -> previously issued staff Bearer token immediately fails with `401`.
- Sending sandbox message after `STOP` opt-out webhook or containing clinical diagnosis text -> `403` / `422`.
- Payment webhook with forged HMAC signature (`401`), mutated payload replay on same `provider_event_id` (`409`), or reversal exceeding original payment (`409`).
