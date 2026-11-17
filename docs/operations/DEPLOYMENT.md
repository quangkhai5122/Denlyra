# Deployment architecture and environment strategy

## Environment tiers
| Stage | Data | Runtime | Access | Approval |
|---|---|---|---|---|
| Developer demo | synthetic only | Local SQLite with web app on 127.0.0.1 | Unauthenticated demo selectors | Developer testing only |
| PostgreSQL integration | synthetic only | Local Docker Postgres, reviewed migrations and exclusion | Test identities | DevOps/QA |
| Staging | synthetic/de-identified authorized only | Protected Vietnam-hosted environment | Real OIDC/MFA + role policies | Security review |
| Clinical pilot | PHI only after full gates | Approved hosting, clinic-specific DB/archive and backup | Verified clinic identities | Clinical+legal+security sign-off |
| Commercial | governed PHI | Managed or dedicated env, monitoring and DR | Contracted, audited, reviewed | Product/operations board |

## Local bootstrap
`README.md` runs SQLite, explicitly sets DENLYRA_DEMO_MODE=1. API and static UI share origin on localhost:8766; no public CORS, no real credentials. Stop with Ctrl+C.

## Optional PostgreSQL demo
1. Install Docker and Postgres driver, inspect `infra/docker/compose.demo.yml` (DEMO credentials).
2. Start: `docker compose -f infra/docker/compose.demo.yml up -d`.
3. `pip install -e './backend[dev,postgres]'` from repo root.
4. Start an empty demo DB with env `DENLYRA_DEMO_MODE=1` and `DENLYRA_DATABASE_URL=postgresql+psycopg://denlyra_demo:DEMO_ONLY_CHANGE_ME@127.0.0.1:5433/denlyra_demo`.
5. **Important:** starter runtime uses `metadata.create_all` in DEMO mode, which will create tables without the PostgreSQL exclusion constraint. For concurrency tests, run reviewed Alembic revision on an EMPTY DB *before* runtime creates tables, then inspect `pg_constraint` to confirm `no_overlapping_active_resource_booking`. Do not claim safety until this is verified.
6. CI PostgreSQL integration setup is a planned task T002; Docker not executed in authoring environment.

## Commercial control-plane / data-plane proposal
Shared stateless app and identity, central tenant metadata without PHI where possible, per-clinic logical PostgreSQL DB/connection policy, clinic-specific object storage namespace/keys and archive manifests. Workers receive signed authorized tenant scopes and restrict all media queries. Patient portal may use a separate lower-privilege API. Imaging edge connector isolated from general web network.

## High availability and backup targets (proposals, not claims)
Uptime 99.9%, RPO<=15min, RTO<=4h after measured infrastructure. PITR PostgreSQL, encrypted object versioning, DICOM PACS archive, clinical document/signature manifest and KMS key backup/escrow, regular isolated restore drills. A successful PostgreSQL restore alone does not prove medical record recovery.

## Failover / rollout
Feature flags fail closed for clinical signature and medical AI; reviewed migrations staged on restored copy; old signed bytes must render/verifiable after upgrade. Canary on synthetic tenant first; health probes never expose medical data; rollback or forward-fix plan with backup.

## Security minimum
TLS, private database, network isolation, signed/managed secrets and key rotation, OIDC MFA, ABAC, immutable audit, API protections, consent, privacy contracts, monitoring/redaction and patch management. The localhost demo lacks these and must never be exposed to patients.

## Resource sizing: assumptions
Start from measured clinic encounter volume, concurrent front-desk sessions, imaging file counts, CBCT size, retention rules and RPO, not fixed monthly server guesses. Plan storage = relational metadata + DICOM/media + versions + off-site backup and restores. Measure costs after sampling synthetic equivalents of real equipment and workflow structure.
