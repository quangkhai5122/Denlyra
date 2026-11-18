# T002 — PostgreSQL constraints and concurrent booking proof
Priority P0 · Owner: Platform/Scheduling Agent · Depends T001 or isolated integration

**Status (2026-11-18):** In progress — explicit Alembic migration chain (`0001_demo` -> `0002_hardening`), atomic doctor+chair+equipment booking, `IntegrityError` -> `409` rollback, idempotency keys, SQLite trigger + 2-connection barrier test harness implemented (`backend/tests/test_scheduling_concurrency.py`). **Blocked on a live PostgreSQL server (`DENLYRA_TEST_POSTGRES_URL`) for final PostgreSQL exclusion acceptance.**

## Goal
Confirm that two concurrent requests cannot occupy same doctor/chair/time, without relying on pre-read in application.

## Work
- Replaced mutable `Base.metadata.create_all` in `0001_demo_schema.py` with explicit frozen DDL and added `0002_hardening.py` with `schema_migration_meta` version tracking (`R-010` resolved).
- Supplied Postgres range + GiST exclusion constraint for `(clinic_id, resource_key, timespan)`, half-open `[start,end)` intervals, plus SQLite `BEFORE INSERT` trigger for local disposable testing.
- `services.schedule()` writes chair, clinician and optional `equipment_ids` bookings atomically, supports `idempotency_key`, catches `IntegrityError` with `db.rollback()`, and returns HTTP `409` with zero partial records.
- Added controlled concurrent test (`test_two_connection_barrier_concurrent_booking_race` and `test_live_postgresql_exclusion_constraint_and_race`) using two independent DB connections and `threading.Barrier(2)`; verified 1 commit (`201`) and 1 conflict (`409`).
- Tested cancellation preserving history, adjacent slots, overlapping equipment resources, different clinics and idempotent retries.

## Acceptance
- Implemented and verified on SQLite + offline PostgreSQL DDL, with automated live PostgreSQL verifier (`scripts/verify_postgres_live.py`) and GitHub Actions `postgres-concurrency-tests` (`postgres:16` service container in `.github/workflows/ci.yml`).
- **Remaining gate to close T002:** Inspect remote GitHub Actions `postgres-concurrency-tests` run or execute `python scripts/verify_postgres_live.py` with `DENLYRA_TEST_POSTGRES_URL` pointing to a live disposable PostgreSQL 16 instance. SQLite tests alone do not satisfy final PostgreSQL acceptance.
