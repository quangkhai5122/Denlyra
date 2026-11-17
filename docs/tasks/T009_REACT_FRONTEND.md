# T009 — Role-based React/Next.js clinic workspaces
Priority P1 · Owner: Frontend · Depends T001, stabilized OpenAPI contracts

**Status (2026-11-17):** Pending — implementation not started. See `docs/PROJECT_STATE.md` for current ordering.

## Current
`apps/demo-web` works without npm; `apps/clinic-web` has a small patients/plans prototype with Windows typecheck/build verified during T000. Direct dependency versions and npm lockfile are pinned; PostCSS override passed npm audit. Role workspaces, generated client, browser E2E, security and accessibility remain pending. Neither frontend is production safe.

## Work
Maintain pinned dependencies, review licenses/security, generate TS client, migrate front desk and clinical workflows to React by role, add calendar resource lanes and odontogram SVG, note/plan version handling and responsive tablet UI. Use server identities, not local headers. Add Playwright E2E, keyboard and accessibility tests.

## Acceptance
End-to-end synthetic workflows pass on Windows tablet/desktop, no optimistic false success, 409 collisions handled, production auth and PHI-safe logs used, frontend matches source API contracts.
