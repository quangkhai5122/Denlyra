# T001 — Replace insecure demo identity headers with a real, testable authentication foundation
Priority P0 · Owner: Platform Agent · Depends: R0 synthetic starter

**Status (2026-11-18):** Completed for synthetic foundation (`ADR-007`); independent security review (`SEC-G1`) and live OIDC/MFA provider integration required before PHI.

## Current problem
`X-Demo-Clinic`, `X-Demo-Actor` are intentionally forgeable; no real auth, no role/clinic permission tests. **No PHI until this is addressed and independently audited.**

## Work scope
1. Evaluate OIDC provider choices (Keycloak or managed identity meeting hosting/security requirements) and document ADR (`docs/adr/ADR-007-identity-and-authorization.md`). No real credentials in repo.
2. Build authorization middleware/dependencies resolving user identity, clinic membership and branch scope from verified tokens/session (`backend/src/denlyra/auth.py`, `backend/src/denlyra/api.py`), not headers.
3. Define RBAC roles and ABAC for patient/clinical/finance access, deny-by-default.
4. Implement access audit and membership deactivation invalidation (`POST /api/v1/staff/{staff_id}/deactivate`, `POST /api/v1/auth/revoke`); gate all prototype clinical routes with explicit permission coverage.
5. Provide local synthetic identity/test issuer (`POST /api/v1/auth/token`), one-time scoped signed URL grants (`POST /api/v1/auth/signed-urls`, `GET /api/v1/signed-download/{grant_token}`), and safe failure (`503`) when provider unavailable; forward `Origin`/`Sec-Fetch-Site`/`Authorization` in Next.js proxy (`R-009`).

## Acceptance
- Every API object read/write checks authenticated identity/clinic; cross-clinic ID enumeration denied (`test_identity_auth.py`).
- Receptionist cannot authenticate clinical note; finance cannot access confidential assessment; dentist authority checked.
- Forged/expired/revoked token, mismatched clinic scope, reused signed URL all rejected.
- Existing synthetic tests retained, new negative tests added (`backend/tests/test_identity_auth.py`), documentation updated and independent review scheduled (`SEC-G1`).
- No misleading claim that implementing auth alone approves EMR (`production_auth` remains `False` in `/api/v1/capabilities`).

## Out of scope
Government integration, live patients, clinical signer method, full Next.js portal.
