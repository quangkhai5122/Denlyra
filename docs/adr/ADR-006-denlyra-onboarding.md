# ADR-006 — Denlyra naming and durable repository handoff

Date: 2026-11-17 · Status: Accepted for this synthetic repository by owner instruction

## Context and evidence
The owner selected Denlyra and requested initial onboarding without large feature work.
The local main branch had no commits; origin pointed to the Denlyra GitHub repository.
Existing documentation mixed future targets with an unverified Next.js prototype.
ADR-001..005 continue to govern architecture and clinical/security gates; ADR-003 remains
a proposed tenancy target, not an implemented or finally approved isolation design.

## Decision
- Use Denlyra in project documents/UI, distribution `denlyra-foundation`, Python package
  `denlyra`, command `python -m denlyra`, `DENLYRA_*` environment variables and
  `X-Denlyra-Demo-Only` response header. Generic `X-Demo-*` selectors stay visibly untrusted.
- Update sample SQLite filename and PostgreSQL demo database/user/volume names. No automatic
  database migration or alias for previous package/environment names; there is no released
  version history in this checkout. Preserve third-party source URLs unchanged.
- Keep PROJECT_STATE as the one current-state index. Link dated session evidence and task
  status; follow AGENT_WORKFLOW before and after each session, across models/accounts.
- Preserve modular monolith, normalized relational authority, draft-only AI, synthetic-only
  runtime and all independent clinical/legal/security release gates.

## Consequences and verification
Reinstall editable backend and update local environment files after rename. Existing demo
data is not automatically carried into the new defaults; never delete old files/volumes
implicitly. ORM tables/revision IDs and clinical state semantics remain unchanged.
Next.js build success demonstrates buildability, not completed role workspaces or safe auth.
Commercial clearance and software license remain owner/counsel decisions.
Exact tests, audit findings and unverified work are linked from PROJECT_STATE.
