# T001 — Replace insecure demo identity headers with a real, testable authentication foundation
Priority P0 · Owner: Platform Agent · Depends: R0 synthetic starter

**Status (2026-11-17):** Pending — implementation not started. See `docs/PROJECT_STATE.md` for current ordering.

## Current problem
`X-Demo-Clinic`, `X-Demo-Actor` are intentionally forgeable; no real auth, no role/clinic permission tests. **No PHI until this is addressed and independently audited.**

## Work scope
1. Evaluate OIDC provider choices (Keycloak or managed identity meeting hosting/security requirements) and document ADR. No real credentials in repo.
2. Build authorization middleware resolving user identity, clinic membership and branch scope from verified tokens/session, not headers.
3. Define RBAC roles and ABAC for patient/clinical/finance access, deny-by-default.
4. Implement access audit and membership deactivation invalidation; gate all prototype clinical routes pending permission coverage.
5. Provide local synthetic identity/test issuer and safe failure when provider unavailable; no public deployment.

## Acceptance
- Every API object read/write checks authenticated identity/clinic; cross-clinic ID enumeration denied.
- Receptionist cannot authenticate clinical note; finance cannot access confidential assessment; dentist authority checked.
- Forged/expired/revoked token, mismatched clinic scope, reused signed URL all rejected.
- Existing synthetic tests retained, new negative tests added, documentation updated and independent review scheduled.
- No misleading claim that implementing auth alone approves EMR.

## Out of scope
Government integration, live patients, clinical signer method, full Next.js portal.
