"""Live PostgreSQL 16 migration, GiST exclusion constraint, and 2-connection race verifier (T002).

Requires DENLYRA_TEST_POSTGRES_URL pointing to an isolated disposable synthetic database.
Never point this script at real patient data or shared production infrastructure.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import statistics
import sys
import threading
import time

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    pg_url = os.getenv("DENLYRA_TEST_POSTGRES_URL")
    if not pg_url:
        raise SystemExit(
            "SKIPPED/BLOCKED: Set DENLYRA_TEST_POSTGRES_URL to a disposable PostgreSQL 16 URL "
            "(e.g. postgresql+psycopg://denlyra_demo:DEMO_ONLY_CHANGE_ME@127.0.0.1:5433/denlyra_demo)"
        )
    if not pg_url.startswith("postgresql"):
        raise SystemExit("DENLYRA_TEST_POSTGRES_URL must use a postgresql:// or postgresql+psycopg:// scheme")

    from denlyra import models as m, services as svc
    from denlyra.db import session_factory
    from denlyra.schemas import AppointmentCreate

    cfg = Config(str(ROOT / "backend/alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend/alembic"))
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(cfg, "head")

    engine = create_engine(pg_url, future=True, pool_pre_ping=True)
    factory = session_factory(engine)
    try:
        with engine.connect() as conn:
            conname = conn.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname = 'no_overlapping_active_resource_booking'"
                )
            ).scalar()
            if conname != "no_overlapping_active_resource_booking":
                raise SystemExit("FAILED: PostgreSQL exclusion constraint missing in pg_constraint")

        with factory() as db:
            svc.demo_seed(db)
            clinic_id = svc.DEMO_CLINICS[0][0]
            pat = m.Patient(clinic_id=clinic_id, display_name="PG Live Concurrency Synthetic")
            db.add(pat)
            db.commit()
            doc = db.scalar(
                select(m.Staff).where(m.Staff.clinic_id == clinic_id, m.Staff.role == "dentist")
            )
            chair = db.scalar(
                select(m.Resource).where(m.Resource.clinic_id == clinic_id, m.Resource.kind == "chair")
            )
            doc_id, chair_id, pat_id = doc.id, chair.id, pat.id

        latencies_ms: list[float] = []
        for slot_hour in range(8, 13):
            barrier = threading.Barrier(2)
            payload = {
                "patient_id": pat_id,
                "practitioner_id": doc_id,
                "chair_id": chair_id,
                "start_at": f"2027-01-15T{slot_hour:02d}:00:00+07:00",
                "end_at": f"2027-01-15T{slot_hour:02d}:45:00+07:00",
                "reason_demo": f"PG race trial {slot_hour}",
            }

            def attempt(idx: int) -> int:
                with factory() as session:
                    barrier.wait(timeout=5)
                    t0 = time.perf_counter()
                    try:
                        svc.schedule(
                            session,
                            clinic_id,
                            AppointmentCreate(**payload),
                            actor=f"pg-bench-{idx}",
                            skip_preread=True,
                        )
                        return 201
                    except HTTPException as exc:
                        return exc.status_code
                    finally:
                        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = sorted(pool.map(attempt, [1, 2]))
            if outcomes != [201, 409]:
                raise SystemExit(f"FAILED race trial {slot_hour}: expected [201, 409], got {outcomes}")

        latencies_ms.sort()
        p95 = latencies_ms[int(len(latencies_ms) * 0.95) - 1]
        median = statistics.median(latencies_ms)
        print(
            f"PostgreSQL live exclusion PASS: 5 concurrent barrier races -> [201, 409]; "
            f"median={median:.1f}ms, p95={p95:.1f}ms"
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
