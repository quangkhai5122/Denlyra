# Operational runbooks and incident response

## Runbook 1 — Start synthetic demo
1. Confirm project root, Python>=3.11, no real PHI in working directory.
2. Create/activate .venv; `pip install -e './backend[dev]'`.
3. Set `DENLYRA_DEMO_MODE=1`, `DENLYRA_DATABASE_URL=sqlite+pysqlite:///./local_data/denlyra-demo.db`.
4. `python -m denlyra`; open http://127.0.0.1:8766; run `python -m pytest backend/tests -q`.
5. If no clients yet, create fictional patient in UI. Do not bind to LAN IP.

## Runbook 2 — Demo DB reset
Stop app and archive/delete ONLY explicitly created `local_data/denlyra-demo.db` containing fictional data. Do not run blind deletion commands against real data or shared database. Restart to recreate demo clinics.

## Runbook 3 — Booking race / integrity issue
Stop scheduling writes, capture redacted request IDs and conflicting booking identifiers, verify PostgreSQL constraint presence, run concurrent test on staging, reconcile allocations/bookings and notify clinic operational owner. Do not silently delete one appointment or generate fake confirmations.

## Runbook 4 — EMR signature provider failure (future)
Treat as unsealed draft, preserve exact input version and provider error, do not mark authenticated or fabricate timestamp. If provider charged/partially completed, investigate external evidence and reconcile before retry with idempotency.

## Runbook 5 — Lost/incorrect clinical attachment (future)
Freeze affected association, preserve object manifests, investigate mismatched patient/study ID, notify clinical owner, reimport from source if authorized and keep audit. Do not edit already authenticated record silently.

## Runbook 6 — Data breach / suspected cross-tenant leak
Suspend affected access, revoke credentials, preserve evidence securely, identify impact and seek qualified privacy/legal counsel for reporting requirements. Never copy medical notes into bug trackers, Slack or coding prompts. Issue signed patch after tests and document audit trail.

## Runbook 7 — Full disaster recovery drill (future)
Restore PostgreSQL PITR, object storage, media/DICOM archives, exact signed record artifacts, audit journal and encryption keys into isolated environment. Enumerate restored patient/encounter/file manifests, verify digests, signature validation and cross-reference consistency; compare snapshot counts and test access controls before returning to service.

## Runbook 8 — Agent context recovery
`git status --short`, `git log -5 --oneline`, `cat AGENTS.md`, `cat docs/PROJECT_STATE.md`, review task ID, run tests, inspect diff. Do not trust prior agent's 'done' statement without runnable evidence.

## Mandatory escalation
Any clinical safety or privacy incident: humans with clinical and security/legal authority. AI Agents can collect redacted technical evidence and propose mitigations, not approve public notification, clinical corrections or regulatory signoff.
