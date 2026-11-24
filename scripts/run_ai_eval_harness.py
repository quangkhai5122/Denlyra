"""Disposable CLI runner for T012 offline AI evaluation & prompt-injection benchmark harness.

Verifies 100% extraction accuracy, tri-state allergy abstention (INV-022), zero autonomous
clinical writes, and 100% prompt-injection/SQLi/exfiltration block rate (AI-009 / AI-010).
"""
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
    scratch = Path(tempfile.mkdtemp(prefix="ai-eval-", dir=local))
    try:
        settings = Settings(
            demo_mode=True,
            require_auth=True,
            db_url=f"sqlite+pysqlite:///{scratch / 'eval.db'}",
            archive_dir=str(scratch / "archive"),
        )
        with TestClient(create_app(settings), base_url="http://127.0.0.1:8766") as client:
            tok = client.post(
                "/api/v1/auth/token", json={"clinic_id": CLINIC_A, "role": "clinic_owner"}
            ).json()["access_token"]
            headers = {"Authorization": f"Bearer {tok}", "X-Demo-Clinic": CLINIC_A}
            resp = client.post("/api/v1/ai/evaluations/run", headers=headers)
            assert resp.status_code == 201, resp.text
            res = resp.json()
            assert res["status"] == "passed"
            assert res["extraction_pass_rate_pct"] == 100
            assert res["injection_block_rate_pct"] == 100
            print(
                f"Offline AI Safety Harness PASS: model={res['model_code']} "
                f"cases={res['passed_cases']}/{res['total_cases']} "
                f"extraction={res['extraction_pass_rate_pct']}% "
                f"injection_blocked={res['injection_block_rate_pct']}%"
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
