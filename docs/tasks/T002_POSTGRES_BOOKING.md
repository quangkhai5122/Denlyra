# T002 — PostgreSQL constraints and concurrent booking proof
Priority P0 · Owner: Platform/Scheduling Agent · Depends T001 or isolated synthetic integration

**Status (2026-11-17):** Pending — implementation not started. See `docs/PROJECT_STATE.md` for current ordering.

## Goal
Confirm that two concurrent requests cannot occupy same doctor/chair/time, without relying on pre-read in application.

## Work
- Review and replace initial Alembic demo migration with explicit approved migration strategy; add version metadata.
- Use Postgres range + GiST exclusion constraint for `(clinic_id, resource_key, timespan)`, half-open `[start,end)` intervals.
- Service writes all chair, clinician and optional equipment bookings atomically; catch exclusion error and return 409; no partial records or sent notices.
- Add controlled concurrent test using two independent DB connections and barrier synchronization; exactly one commit.
- Test cancellation preserving history, adjacent slots, overlapping resources, different clinics and idempotent retries.

## Acceptance
No overlap at DB level, actual test on live PostgreSQL, migration upgrade from empty and existing synthetic fixture, rollback/forward plan and benchmark. SQLite tests alone do not satisfy this task.
