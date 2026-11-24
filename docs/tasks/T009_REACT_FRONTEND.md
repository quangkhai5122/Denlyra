# T009 — Role-based React/Next.js clinic workspaces
Priority P1 · Owner: Frontend · Depends T001, stabilized OpenAPI contracts

**Status (2026-11-24):** Completed (synthetic role workspaces, generated OpenAPI TS client, fixed `Asia/Ho_Chi_Minh` timezone, SVG FDI odontogram, and Node 24 contract/a11y test suite; live OIDC browser E2E with Playwright headless browsers remains a pre-pilot gate). See [ADR-010](../adr/ADR-010-encrypted-archive-dr-and-role-workspaces.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Implemented in synthetic foundation
- **Generated OpenAPI TypeScript client (`INT-001`, `R-012`):** `scripts/generate_openapi_ts.py` (`--check` enforced in CI) generates `apps/clinic-web/src/lib/generated-api.ts` directly from FastAPI's live OpenAPI schema (`79` paths / `93` operations) with `DenlyraApiClient` returning `{ ok, status, data, conflict }` so HTTP `409` collisions are surfaced pessimistically without optimistic false success.
- **In-memory server-minted Bearer sessions:** Role switches (`receptionist`, `dentist`, `treatment_coordinator`, `finance`, `clinic_owner`) mint/revoke `HS256` tokens via `/api/demo/auth/token` and `/api/demo/auth/revoke` (held strictly in React memory, zero `localStorage`/`sessionStorage`). Next.js loopback proxy (`apps/clinic-web/src/app/api/demo/[...path]/route.ts`) forwards `GET`/`POST`/`PUT`/`DELETE` with `Authorization`, `Origin`, and `Sec-Fetch-Site`.
- **Fixed clinic timezone & integer VND (`R-011`, `INV-019`):** `apps/clinic-web/src/lib/timezone.ts` enforces `Asia/Ho_Chi_Minh` (`UTC+07:00`) display/input construction and integer-only VND formatting.
- **Role workspaces & accessible SVG FDI odontogram (`ODN-004`, `SCH-006`):**
  - `OdontogramSvg.tsx`: permanent (`11–48`) and primary (`51–85`) SVG dental chart with keyboard `Tab`/`Enter`/`Space`, `aria-pressed`, surface picker (`O`/`M`/`D`/`B`/`L`), and historical finding timeline.
  - `page.tsx`: Front Desk chair resource lanes + `409` conflict alert, Dentist encounter/FDI/versioned notes/synthetic snapshot/addendum/encrypted attachment, Coordinator multi-dependency DAG timeline + lab delay alerts, Finance immutable estimates/idempotent ledger/cashier reconciliation, and Owner KPIs/key rotation/legal hold/isolated DR restore drill + audit log.
- **Automated verification:** Pinned dependencies preserved (`0` npm audit vulnerabilities); `apps/clinic-web/tests/frontend_contracts_and_a11y.test.mjs` (`npm test`), `npm run typecheck`, and `npm run build` verified on Windows and wired into `.github/workflows/ci.yml`.

## Remaining before production pilot
Provisioned Playwright multi-browser E2E suite against live OIDC/MFA login (`SEC-G1`) and clinical UX review with partner dentists (`M0`).
