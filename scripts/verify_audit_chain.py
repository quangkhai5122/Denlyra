"""Disposable CLI verifier for T014 per-clinic hash-chained tamper-evident audit journal (SEC-007)."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from fastapi.testclient import TestClient

from denlyra.api import create_app
from denlyra.config import Settings

ROOT = Path(__file__).resolve().parents[1]
CLINIC_A = "11111111-1111-4111-8111-111111111111"


def main() -> None:
    local = ROOT / "local_data"
    local.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="audit-cli-", dir=local))
    try:
        settings = Settings(
            demo_mode=True,
            require_auth=True,
            db_url=f"sqlite+pysqlite:///{scratch / 'audit.db'}",
            archive_dir=str(scratch / "archive"),
        )
        with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
            tok = client.post(
                "/api/v1/auth/token", json={"clinic_id": CLINIC_A, "role": "clinic_owner"}
            ).json()["access_token"]
            headers = {"Authorization": f"Bearer {tok}", "X-Demo-Clinic": CLINIC_A}
            for idx in range(3):
                client.post(
                    "/api/v1/patients",
                    headers=headers,
                    json={"display_name": f"BN Kiểm chứng Audit Chain {idx}", "birth_year": 1990},
                )
            ver = client.get("/api/v1/audit-events/verify-chain", headers=headers)
            assert ver.status_code == 200, ver.text
            res = ver.json()
            assert res["chain_intact"] is True
            print(
                f"Audit Hash Chain PASS: verified_count={res['verified_count']} "
                f"head_seq={res['head_seq']} head_hash={res['head_hash'][:16]}..."
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
