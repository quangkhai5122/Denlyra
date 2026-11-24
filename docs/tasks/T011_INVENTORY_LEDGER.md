# T011 — Append-Only Inventory Lot, Reservation, FEFO & Dual-Control Reconciliation Ledger
Priority P1 (`M5`) · Owner: Clinic Operations / Backend · Depends T001, T002, T005, T008

**Status (2026-11-24):** Completed (synthetic append-only inventory lot ledger, FEFO, reservation != consumption, DB immutability triggers, and dual-control adjustments verified in `test_inventory_ledger.py`). See [ADR-011](../adr/ADR-011-inventory-ledger-fhir-r4-and-ai-safety-harness.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Preconditions & Invariants
- **`INV-001` (Clinic Tenant Scope):** All SKUs, suppliers, purchase orders, lots, movements, reservations, and adjustments are strictly scoped to `clinic_id` with composite foreign keys where applicable.
- **`INV-005` (Append-Only Stock Movement Ledger):** Physical on-hand balances are NEVER mutated in place; `stock_movement` is strictly append-only (enforced by DB triggers blocking `UPDATE` and `DELETE`) and lot balances are derived from signed movement events (`receipt_accepted`, `procedure_consumed`, `adjustment_in`, `adjustment_out`).
- **`INV-006` / `INV-023` (Reservation != Consumption):** Reserving materials for a planned treatment task or appointment reduces *allocatable* quantity (`available_qty = physical_on_hand_qty - active_reserved_qty`) without deducting `physical_on_hand_qty`. Cancelling/releasing a reservation restores `available_qty` without fabricating a receipt movement. Booking an appointment NEVER auto-consumes inventory.
- **`INV-004` / `INV-007` (Traceable Non-Expired Lot & Authorized Procedure Link):** Lot-tracked clinical materials (e.g., dental implants, bone grafts, anesthetics) cannot be consumed without an explicit `lot_id` and an active `encounter_id`. Consuming from an **expired** (`expiry_date < reference_date`) or **quarantined** lot fails closed with `409 Conflict`.
- **`INV-010` (Dual-Control Stock Adjustments):** Sensitive stock reconciliation/shrinkage adjustments require a two-step workflow: requester submits `stock_adjustment_request` with reason, and a **distinct** authorized approver (`clinic_owner` or `medical_director`, `approver_staff_id != requester_staff_id`) approves it before the reversing/adjusting `stock_movement` is appended. Self-approval is rejected with `409 Conflict`.

## Scope & API Contract
1. `GET/POST /api/v1/inventory/suppliers` (`INV-002` — duplicate tax_code/name detection per clinic).
2. `GET/POST /api/v1/inventory/skus` (`INV-001` — SKU code, unit, `lot_tracked`, `reorder_threshold`).
3. `POST /api/v1/inventory/purchase-orders` & `POST /api/v1/inventory/purchase-orders/{po_id}/receive` (`INV-003`, `INV-004` — separates `ordered_qty`, `delivered_qty`, `inspected_accepted_qty`, creates traceable `inventory_lot` and appends `receipt_accepted` movement).
4. `GET /api/v1/inventory/skus/{sku_id}/stock` & `GET /api/v1/inventory/skus/{sku_id}/fefo-picks` (`INV-009` — FEFO lot recommendation excluding expired and quarantined lots).
5. `POST /api/v1/inventory/reservations` & `POST /api/v1/inventory/reservations/{res_id}/release` (`INV-006`, `INV-023`).
6. `POST /api/v1/inventory/consumptions` (`INV-007` — requires `encounter_id`, checks lot expiry/quarantine/available stock, optionally fulfills a linked `reservation_id`, appends `procedure_consumed` movement).
7. `POST /api/v1/inventory/adjustments` & `POST /api/v1/inventory/adjustments/{adj_id}/approve` (`INV-010` — dual-control approval).
8. `GET /api/v1/inventory/alerts` (`INV-008`, `RPT-008` — low-stock/reorder, expired/near-expiry lots, and shrinkage movements).

## Mandatory Negative Tests (Written Before Domain Code)
1. Duplicate supplier code or SKU code within the same clinic -> `409`; same SKU code in `Clinic B` -> `201` (`INV-001`).
2. `inspected_accepted_qty > delivered_qty` on PO receipt -> `422`.
3. Reservation reduces `available_qty` while leaving `physical_on_hand_qty` unchanged (`INV-023`); over-reserving beyond `available_qty` -> `409`; releasing reservation restores `available_qty`.
4. Consuming without an authorized `encounter_id` or from another clinic's encounter -> `404`/`422`; receptionist/finance role attempting clinical stock consumption -> `403`.
5. Consuming from an expired lot or quarantined lot -> `409`; FEFO picker skips expired/quarantined lots and orders valid lots by earliest `expiry_date`.
6. Direct SQL `UPDATE` or `DELETE` on `stock_movement` -> rejected by DB trigger (`IntegrityError`).
7. Dual-control self-approval (`requester_staff_id == approver_staff_id`) on stock adjustment -> `409`; approval by a second `clinic_owner`/`medical_director` succeeds and appends movement.
