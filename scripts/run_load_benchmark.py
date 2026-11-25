"""Reproducible local synthetic latency & throughput benchmark CLI (T027 / OPS-008).

Measures honest local SQLite/SQLAlchemy P50/P95/Max latencies without inventing cloud SLAs.
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
    scratch = Path(tempfile.mkdtemp(prefix="load-bench-", dir=local))
    try:
        app = create_app(
            Settings(
                demo_mode=True,
                require_auth=True,
                db_url=f"sqlite+pysqlite:///{scratch / 'bench.db'}",
                archive_dir=str(scratch / "archive"),
            )
        )
        with TestClient(app) as client:
            tok = client.post(
                "/api/v1/auth/token",
                json={"clinic_id": CLINIC_A, "role": "clinic_owner"},
            )
            assert tok.status_code == 201, tok.text
            headers = {
                "Authorization": f"Bearer {tok.json()['access_token']}",
                "X-Demo-Clinic": CLINIC_A,
            }
            res = client.post(
                "/api/v1/ops/load-benchmarks/run",
                headers=headers,
                json={
                    "workload_profile": "clinic_read_mix",
                    "iterations": 25,
                    "claim_production_sla": False,
                },
            )
            assert res.status_code == 201, res.text
            body = res.json()
            assert body["claims_production_sla"] is False
            print(
                f"Local Load Benchmark PASS (non-SLA): profile={body['workload_profile']} "
                f"iters={body['iterations']} p50_us={body['p50_latency_us']} "
                f"p95_us={body['p95_latency_us']} ops_s={body['throughput_ops_per_sec']}"
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
