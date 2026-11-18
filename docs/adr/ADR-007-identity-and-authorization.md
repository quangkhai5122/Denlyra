# ADR-007 — Identity, session verification, and deny-by-default RBAC/ABAC foundation

Date: 2026-11-18 · Status: Accepted for synthetic foundation (independent security review required before PHI) · Owners: Platform Lead + Security Reviewer (pending)

## Context & evidence
In the R0 baseline (`T000`), all API endpoints relied on unverified `X-Demo-Clinic` and `X-Demo-Actor` headers (`R-001` in `docs/PROJECT_STATE.md`, `INV-017` and `INV-021` in `docs/architecture/DOMAIN_MODEL.md`). Furthermore, the optional Next.js proxy (`apps/clinic-web/src/app/api/demo/[...path]/route.ts`) dropped browser `Origin` and `Sec-Fetch-Site` headers (`R-009`).

Before any clinical or operational vertical slice (`T005`–`T010`) can be built safely, the backend must resolve actor identity, role, active employment status, clinic membership, and branch scope from verified cryptographic tokens/sessions on the server side, enforce deny-by-default RBAC and ABAC policies, audit sensitive clinical access and denials, and invalidate access immediately when a staff membership is deactivated or a session is revoked.

## Alternatives
- **A) Self-hosted or dedicated OIDC provider (Keycloak) in Vietnam-hosted VPC + backend policy engine:** Supports MFA/WebAuthn, OIDC standards, fine-grained session revocation, and avoids transferring identity metadata to unverified cross-border SaaS providers. Requires operational management in staging/production.
- **B) Managed cloud OIDC provider with regional residency and signed data-processing agreement:** Lower operational overhead, but requires legal verification of subprocessor residency under Law 91/2025/QH15 and Decree 356/2025/ND-CP before real staff/patient identities are onboarded.
- **C) Custom password storage and session management inside the monolith:** Rejected for production due to MFA, credential lifecycle, and audit risk.

## Decision
1. **Production target:** Adopt an OIDC-compliant identity boundary (Option A Keycloak as default reference architecture, or Option B where legally approved) with mandatory MFA for clinical/privileged staff, combined with a backend RBAC + ABAC policy engine that verifies live clinic membership and active status in the domain database.
2. **Local synthetic test issuer (`T001` deliverable):** Provide a deterministic, zero-external-credential `SyntheticIdentityIssuer` (`HMAC-SHA256` signed bearer tokens with `iss`, `sub`, `clinic_id`, `branch_id`, `role`, `jti`, `iat`, `exp`, and `token_version`) inside `backend/src/denlyra/auth.py` to test all authentication and authorization invariants locally without external network dependencies.
3. **Server-side membership and revocation verification (`INV-017`, `INV-021`):**
   - A valid token signature alone is insufficient. On every authenticated request, the backend loads the `Staff` record in the token's `clinic_id`, verifies `staff.active is True`, checks `staff.token_version`, and verifies the token `jti` is not in `revoked_token`.
   - Deactivating a staff member (`POST /api/v1/staff/{staff_id}/deactivate`) increments `token_version` and sets `active = False`, immediately invalidating all outstanding tokens for that actor.
   - Any mismatch between a legacy `X-Demo-Clinic` header and the verified token's `clinic_id` is rejected with `403 Forbidden` and audited.
4. **Deny-by-default RBAC + ABAC matrix:**
   - Roles: `clinic_owner`, `medical_director`, `dentist`, `assistant`, `receptionist`, `treatment_coordinator`, `finance`.
   - Clinical mutations (`encounter.create`, `note.create`, `note.update`, `note.lock`, `finding.create`, `plan.review`) require active `dentist` or `medical_director` authority. Receptionists and finance staff are denied (`403`).
   - Confidential clinical reads (`encounter.read`, `note.read`, `finding.read`, `odontogram.read`) are denied to `finance` (`403`).
   - Financial payment allocation (`finance.allocate`) is restricted to `finance` and `clinic_owner` (`403` for receptionists/assistants/dentists).
5. **Scoped one-time signed URLs (`SEC-02`):**
   - Document/resource download grants (`/api/v1/auth/signed-urls` -> `/api/v1/signed-download/{grant_token}`) are bound to `clinic_id`, `subject_type`, `subject_id`, `expires_at`, and `used_at`. Expired, cross-clinic, tampered, or reused signed URLs fail closed (`403` / `410`).
6. **Fail-closed provider availability:**
   - When `settings.auth_provider_available` is `False` (`DENLYRA_AUTH_PROVIDER_AVAILABLE=0`), authenticated endpoints fail closed with `503 Service Unavailable`.
7. **Compatibility with R0 synthetic demo tests:**
   - `Settings.require_auth` (`DENLYRA_REQUIRE_AUTH=1`) forces strict bearer authentication across all `/api/v1/*` routes and rejects unauthenticated `X-Demo-*` headers (`401`).
   - When `require_auth=False` (default for R0 local demo startup), any request carrying `Authorization`, `X-Enforce-Auth: 1`, or targeting `/api/v1/auth/*`, `/api/v1/staff/*`, or `/api/v1/signed-download/*` still undergoes full cryptographic and RBAC/ABAC verification.
   - `/api/v1/capabilities` keeps `"production_auth": False` until an independent human security review (`SEC-G1`) and live OIDC/MFA deployment are completed.

## Consequences
- Every API route has explicit permission mapping and audit coverage for clinical reads and authorization denials.
- Next.js demo proxy forwards `Authorization`, `Origin`, and `Sec-Fetch-Site` headers (`R-009` mitigated for local proxy).
- Implementing this synthetic auth foundation does NOT authorize real patient data or certify EMR compliance.

## Verification
- Automated negative and positive suite in `backend/tests/test_identity_auth.py` covering `NEG-01`, `NEG-15`, `NEG-18`, forged/expired/revoked tokens, deactivated staff, role violations, one-time signed URL reuse, and provider outage fail-closed behavior.
