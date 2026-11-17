# T000 — Repository onboarding and baseline establishment

Priority P0 · Owner: repository technical lead · Status: Completed — baseline verified (2026-11-17)

## Scope
Inventory all documentation, source, tests and infrastructure; compare actual behavior
with the catalog; rename project identifiers to Denlyra; establish reproducible checks
and durable session handoff. Owner authorized the initial scoped commit and normal push
to the configured remote when safe. No feature module, clinical approval or deployment.

## Acceptance
- Mandatory reads including T001 and ADRs completed before source edits.
- Project package, environment variables, UI, scripts, CI and documentation use Denlyra.
  Third-party source URLs remain intact.
- Backend tests, lint, artifact guard, static JS syntax and Next typecheck/build executed;
  exact results and omitted integration checks recorded.
- PROJECT_STATE links current milestone, backlog, risks, decisions, evidence and next task.
- Mandatory before/after workflow and Vietnamese session report documented for fresh agents.
- Initial Git state, remote safety, commit/push outcome and recovery recorded truthfully.

## Data and recovery
No schema change, real data, provider integration or clinical/legal reinterpretation.
Reinstall the editable backend after package rename; use only `DENLYRA_*` variables.
No existing data/volume is moved, renamed or deleted. Existing synthetic databases require
an explicitly selected URL if reused; the new defaults use a new filename/volume.

## Evidence and continuation
See `docs/sessions/2026-11-17_T000_ONBOARDING.md` and `docs/PROJECT_STATE.md`.
T001 remains the next engineering task, with negative tests first and an identity ADR.
