# Frontend/UX specification — role-based Dental Practice Management

## Current frontend
`apps/demo-web/`: **working dependency-free static HTML/CSS/JS**, served same-origin by FastAPI. Includes clinic selector, overview, synthetic patient registry, appointment creation/cancel, encounters/notes, plans/tasks, tooth-code event grid, lab lifecycle, demo financial input and audit. It is accessible on mobile-ish widths but not independently accessibility-certified, not a React application and not production capable.

## Target frontend technology
Next.js + React + TypeScript with a tokenized design system, shadcn/ui/Tailwind or equivalent accessible components, TanStack Query and Zod or schema-derived validators. Generate typed client from backend OpenAPI, lint/format/check TS, E2E Playwright tests. Do not replicate API state in fragile global frontend stores. The full role-based Next.js frontend is **designed, not shipped**. A small patients/plans prototype exists in `apps/clinic-web` with typecheck/build verified on Windows on 2026-11-17; no browser E2E/auth/accessibility acceptance is established. Migrate workflows after stabilizing backend contracts and domain tests.

## Information architecture by persona
### Front desk
Primary workspace: Today calendar (day/week/provider/chair), patient quick search, check-in queue, reschedule, unpaid balance badges, pending confirmation, waiting list. Keyboard shortcuts and touch support, but destructive actions always confirm. Show chair color consistently and clear error when rebooking conflicts.

### Dentist
Primary workspace: next patient/encounter; FDI-based interactive odontogram (SVG); findings, allergies/medical history review, imaging, clinical note and authenticated document review, plan version changes and procedure events. No automatically generated clinical conclusion. Draft indicator mandatory; signature state visibly distinct from saved draft.

### Assistant
Today chair preparation, case checklist, instrument/lot availability, tasks and handoff status. Must not see all medical notes or financial records by default. Authorized to add preparation evidence; cannot impersonate dentist.

### Treatment coordinator
Treatment journeys by `blocked / ready / overdue / active`, plan milestone status, lab deadlines, consent outstanding, patient communication queue, appointment dependency, financial pending. Each card links to source evidence and responsible owner. Timeline shows reviewed plan version and change history.

### Billing/cashier
Price catalog, estimates, deposit and payment allocations, real receipts only via approved provider, daily reconciliation, overdue balances. Clearly separate `proposed`, `charged`, `collected`, `refunded`, `clinically performed` and `invoiced`.

### Clinic owner
Performance and exception dashboard: schedule utilization, bill vs collect, overdue lab cases, unsigned docs, treatment pipeline, stock/expiry; definitions and source drilldown. No generic export of all patient chart content by default.

### Patient/guardian portal
Secure, low-friction web portal first. View verified appointments, clinically approved instructions, accepted estimates and permitted payment info; upload consented documents. Never display clinician drafts or raw clinical incident notes; guardians must have verified authority and scoped permissions.

## Screen-level specification
| Screen | Key widgets | Acceptance / empty / error states |
|---|---|---|
| Overview | KPIs, exceptions, upcoming appointments | Unsupported metrics shown as N/A, never invented |
| Patient list | Search, filters, duplicate candidates, creation | Same phone used by relatives not auto merged |
| Patient 360 | Timeline, encounters, chart, treatment, billing, files | View only authorized sensitive parts; lazy load images |
| Calendar | Drag/drop slots, provider and chair lanes, hold state | Two simultaneous bookings -> one rejects; UI refreshes on 409 |
| Clinical encounter | Findings, allergy badge, note, form validation, auth | Draft/signed/addendum clearly separate; no silent overwrites |
| Odontogram | SVG tooth quadrants and surfaces, history | Correct FDI mapping and accessible text alternatives |
| Treatment timeline | DAG/milestones, responsibility, blockers | Approvals bound to exact version, track re-evaluation |
| Lab board | Case status, due, source files, handoff | Delivered vs verified distinct; case-scoped access |
| Billing | Estimates, ledger, allocations, invoice references | No automatic completed procedure from payment |
| Inventory | Lot movement, FEFO suggestions, quarantined stock | No consumption without authenticated actor/event |
| AI draft | Transcript side-by-side, highlights, source spans | Human explicit review; hallucinated numbers flagged |
| Audit and exports | Actor/time/source/changes, archive | No mass chart export without purpose and authorization |

## Interaction design rules
- Patient/doctor identifiers displayed with safe labels; sensitive demographics only where needed.
- Every mutation is either optimistic with explicit version conflict recovery or pessimistic/transactional with server result; frontend never claims success before server commits.
- A scheduled appointment cannot be “saved locally” if backend fails. Show retry after clear error and no duplicate client submits.
- A signature is a separate deliberate action, displaying signer identity, document version and legal scope. Do not use standard checkbox as legal signature substitute.
- Clinical form autosave may save only drafts; signed content must use explicit correction workflow.
- Date display `Asia/Ho_Chi_Minh`, API uses RFC3339; preserve user-entered local time including date, handle DST for international expansion.
- All notifications distinguish `queued`, `sent`, `delivered`, `read`, `confirmed`. Delivery is not consent.
- Responsive tablet first for clinical chair; mobile compact for patient and assistants. WCAG AA visual contrast, label controls, keyboard focus and screen-reader navigation.

## Design tokens (proposed)
Primary teal #0f766e, dark navy #103b4b, neutral slate, off-white #f5f8fa, amber for human review, red reserved for actual critical errors. Do not equate green with legally signed or clinically safe. P0 forms prioritize reliability and clarity over animations.

## UI test list
Registration with same phone; duplicate candidate resolution; appointment collision refresh; signed record immutable display; cross-clinic access denied; lab delivered-not-verified; patient portal limited info; long Vietnamese names; touch display; keyboard focus; offline banner; loading/empty/error/success states; no PHI in browser console or analytics.
