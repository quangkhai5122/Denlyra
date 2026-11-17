# Denlyra — optional Next.js / React prototype

A small synthetic patients/plans interface with a loopback demo proxy. TypeScript and
Next.js production build passed on Windows on 2026-11-17. This is not the complete
role-based clinic frontend; authentication, clinical/financial authority, E2E and
accessibility are not validated. The static `apps/demo-web` remains the default UI.

Start the backend with `DENLYRA_DEMO_MODE=1 python -m denlyra` on 127.0.0.1:8766.
Inside this directory:

```powershell
Copy-Item .env.example .env.local
$env:NEXT_TELEMETRY_DISABLED = "1"
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
npm run build
npm run dev
```

Visit http://127.0.0.1:3000. Both dev/start scripts bind loopback. The proxy requires
`DENLYRA_DEMO_MODE=1` and forwards only to a loopback backend. These checks are not
production authentication. Its missing Origin/Fetch-Metadata forwarding is an open
security finding; do not expose the proxy publicly or process real data (T001/T009).

Direct dependency versions and package-lock.json are pinned to the verified baseline.
A PostCSS 8.5.23 override addresses the advisories observed during onboarding; rerun
`npm audit` when dependencies change. Build and audit do not replace browser/role tests.
The typecheck command generates Next route definitions first, so a fresh checkout does
not depend on an existing `.next/types/routes.d.ts` from an earlier build.
Next: T009, after T001 and stabilized OpenAPI, for generated types, role workspaces,
calendar/clinical screens, stale response handling and browser/accessibility tests.
See `../../docs/PROJECT_STATE.md` for current evidence and task ordering.
