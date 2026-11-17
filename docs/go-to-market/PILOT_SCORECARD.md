# Controlled pilot scorecard — no real data until legal/security gates

## Design partner acceptance
Each clinic identifies named medical director, operations lead, privacy/security approver, agreed work scope and pilot success criteria. No blanket “AI handles the clinic” claims.

| Metric | Baseline | Pilot | Formula and caveat |
|---|---|---|---|
| Registration minutes | Observed | Observed | from patient start to identity-confirmed record; complexity adjusted |
| Appointment conflict count | Observed | Observed | only verified double-booking incidents |
| Encounter note completion | Observed | Observed | proportion of signed/approved where required, not draft saved |
| Lab delivery misses | Observed | Observed | cases not ready by clinical appointment and requiring intervention |
| Treatment handoff tasks overdue | Observed | Observed | tasks with approved due dates + owner; exclude medically paused |
| Cash reconciliation minutes | Observed | Observed | daily cashier close, no fabricated receipts |
| Number of duplicate entries | Observed | Observed | each retyping between disconnected tools |
| Patient complaint rate | Observed | Observed | complaints normalized to appointments, selection bias acknowledged |
| Staff weekly usage | N/A | Measured | by role; opt-in, privacy-preserving aggregation |
| Serious privacy or clinical incidents | 0 desired | 0 mandatory | any critical incident halts affected pilot |

## Pilot go/no-go heuristic (not empirical benchmark)
2–3 partner clinics complete synthetic scenario; 1–2 pilot users have a measurable workflow advantage over incumbent; written conditional payment intent; no critical unresolved compliance/health risk; process can be repeated by staff without engineering presence. This only supports progressing to further validation, not broad launch claims.

## Commercial constraints
Onboarding and data migration are often larger than compute cost. Track time for staff training, data validation, signature vendor setup, support issues, import exceptions and customer renewal. A signed pilot contract should clearly state software limitations, data ownership and exit/export rights.
