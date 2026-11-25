# T030 — Channel-Specific Messaging Sandbox Contracts: Zalo OA/ZNS, SMS DLR & Verified Email Rate Limiting

- **Status:** Completed (synthetic loopback sandbox contracts verified; live external vendor API egress remains disabled)
- **Feature IDs:** `CRM-006`, `CRM-007`, `CRM-008`
- **Governing ADR:** [ADR-020](../adr/ADR-020-iac-region-guard-insurance-sandbox-lora-lift-plan-attestation-and-channel-contracts.md)
- **Related Risks:** `R-007` (messaging consent, sender verification, and zero external PHI egress)

## 1. Objective & Bounded Scope
1. **`CRM-006` — Official Zalo OA/ZNS Contract, Legal-Basis & Pricing Gate:** Enforce `official_api_only=True` (`422` on unofficial personal-account automation), require confirmed integer `price_per_message_vnd` (`409` if pricing unconfirmed), restrict parameters to approved template keys without clinical diagnosis PHI (`422`), verify purpose-matched consent & opt-out status (`403`), and keep `live_external_egress=False`.
2. **`CRM-007` — SMS Brandname Provider DLR Evidence & Opt-Out Controls:** Enforce consent & channel opt-out checks (`403`), record cryptographic SHA-256 carrier delivery receipts (`carrier_delivered` / `handset_rejected` / `expired_unreached`) separated from appointment confirmation (`patient_confirmed_appointment=False`), and honor DLR-triggered opt-outs atomically.
3. **`CRM-008` — Clinic-Verified Email Sender (`SPF`/`DKIM`/`DMARC`), Safe Template & Rate-Limit Gate:** Block unverified sender domains (`409`), strip/reject HTML scripts, tracking pixels, header newline injection, and clinical PHI (`422`), verify consent/opt-out (`403`), and enforce per-sender rolling 60-minute rate limits (`429 Too Many Requests`).

## 2. Negative Cases (Red-First)
- Zalo dispatch using unofficial scraping (`422`), unconfirmed pricing (`409`), undeclared template parameter (`422`), or missing consent (`403`).
- SMS dispatch after carrier DLR `opt_out_triggered=True` -> `403`.
- Email dispatch from sender missing `dkim_verified` (`409`), containing `<script>` or tracking pixel (`422`), or exceeding `hourly_rate_limit` (`429`).
