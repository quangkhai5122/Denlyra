# T008 — Accurate revenue account and refunds
Priority P1 · Owner: Finance · Depends T001, clinic billing rules reviewed

**Status (2026-11-17):** Pending — implementation not started. See `docs/PROJECT_STATE.md` for current ordering.

## Work
Replace basic demo allocations with append-only ledger, idempotency, provider-safe receipts, refunds/reversals, estimate versions, daily cashier reconciliation and source-linked reports. PostgreSQL locks for concurrent allocation; bank/provider reconciliation separated from clinical performed events. Zero floats.

## Acceptance
No duplicate ledger posting, allocation bounds remain under concurrent load, refund retains original trace, no fabricated official invoices or payment receipts.
