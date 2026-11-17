# Developer contribution procedure

Read `AGENTS.md` first and follow the mandatory opening/closing and Vietnamese report in `docs/engineering/AGENT_WORKFLOW.md`. Read PROJECT_STATE and the latest linked session before editing. The project is a synthetic-only dental software research starter. No medical/patient data or real clinic credentials in issues, commits, PRs or coding agent conversations. Verify official clinical/legal source before discussing compliance. No automated authority to sign records, import real patients, or launch publicly.

## Typical change
1. Open relevant task packet and identify stable functional requirement IDs.
2. Write negative tests first; build small domain feature with typed API.
3. Run backend tests, JS syntax, optional Next frontend checks and PostgreSQL integration if applicable.
4. Update docs/PROJECT_STATE, API contract, ADR and task status.
5. Perform security/clinical/legal code review where needed; no force push or destructive migrations.

## Commit subjects
`feat(schedule): enforce atomic chair booking [T002]`, `test(clinical): reject stale signed note [T004]`, `docs(legal): update outpatient form mapping`. Do not mix large unrelated features. Sign/review commits and release assets once trusted signing infrastructure exists.

## GitHub issues/PR
Use synthetic examples only; list specific tests run, skipped tests and evidence, risk impact and rollback. Do not share backup files, patient images, database dumps or raw production HTTP traces.
