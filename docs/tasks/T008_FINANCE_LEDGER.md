# T008 — Accurate revenue account and refunds
Priority P1 · Owner: Finance · Depends T001, clinic billing rules reviewed

**Status (2026-11-18):** Completed for synthetic domain/API slice (`ADR-009`, `backend/tests/test_finance_ledger.py`). Real payment gateway webhooks and tax e-invoice integrations remain disabled until provider contracts and PostgreSQL row-lock verification.

## Work
- Added versioned treatment estimates (`EstimateVersion`, `POST /api/v1/finance/estimates`, `POST /api/v1/finance/estimates/{id}/accept`, `FIN-002`, `TRT-011`) with immutable `(plan_id, version_number)`.
- Replaced basic allocations with an append-only `LedgerEntry` journal and `idempotency_key` deduplication across charges, payments (`cash | bank_transfer | card`), allocations, and refunds (`NEG-08`, `NEG-17`).
- Enforced concurrent allocation bounds via DB write-transaction trigger (`tr_payment_allocation_bounds`) and `with_for_update()` (`test_concurrent_payment_allocation_bounds_enforced`).
- Added daily cashier reconciliation (`CashierReconciliation`, `POST /api/v1/finance/reconciliations`, `FIN-010`) and ledger-derived patient revenue account summary (`GET /api/v1/patients/{id}/revenue-account`, `FIN-007`, `FIN-011`) with `implies_clinical_completion: False`.

## Acceptance
No duplicate ledger posting on idempotent retries, allocation bounds hold under concurrent barrier test, refunds retain original payment trace, zero floating-point currency, and no fabricated official invoices or bank receipts.
