# Denlyra quick commands

Read AGENTS and PROJECT_STATE first. Synthetic data and loopback only.

Windows PowerShell:
```powershell
# Reuse a Python 3.11+ interpreter; pass its full path if python is not on PATH.
.\scripts\dev_windows.ps1 -Python python
```

Linux/macOS: `bash scripts/dev_unix.sh`.

After activating the repository .venv, from the root:
```text
python -m pip install -c backend/constraints-baseline.txt -e "./backend[dev]"
python -m pytest backend/tests -q
python -m ruff check backend/src backend/tests
python -m compileall -q backend/src
node --check apps/demo-web/app.js
python scripts/verify_artifact.py
python scripts/smoke_baseline.py
python scripts/update_manifest.py --check
```

Inside `apps/clinic-web` (synthetic optional prototype): copy `.env.example` to `.env.local`,
set `NEXT_TELEMETRY_DISABLED=1`, then run `npm ci --ignore-scripts --no-audit --no-fund`,
`npm run typecheck`, `npm run build`, `npm audit`, `npm run dev`.

Optional PostgreSQL requires Docker and driver (not verified in onboarding):
`docker compose -f infra/docker/compose.demo.yml up -d`.
Alembic reads `backend/alembic.ini`, not DENLYRA_DATABASE_URL. From `backend`, use
`../.venv/Scripts/python.exe -m alembic upgrade head` only on a fresh disposable synthetic
DB matching the inspected config. Automatic create_all does not install exclusion.
No concurrency, migration-upgrade or rollback safety claim before T002.
