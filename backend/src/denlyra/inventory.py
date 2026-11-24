"""T011 Append-Only Inventory Lot, Reservation, FEFO & Dual-Control Reconciliation Ledger.

Enforces:
- INV-001: Clinic tenant scoping across suppliers, SKUs, POs, lots, movements, reservations, adjustments.
- INV-003: Ordered != delivered != inspected_accepted != available quantities.
- INV-004: Expired and quarantined lots blocked from procedure consumption and FEFO picks.
- INV-005: Append-only StockMovement ledger (backed by DB no-update / no-delete / bounds triggers).
- INV-006 / INV-023: Reservation != consumption (reservations hold allocatable stock without mutating physical stock).
- INV-007: Procedure consumption requires an active clinic Encounter; booking appointments never auto-deducts stock.
- INV-010: Dual-control stock adjustments (requester_staff_id != approver_staff_id).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models as m, services as svc
from .schemas import (
    PurchaseOrderCreate,
    PurchaseOrderReceiveRequest,
    SkuCreate,
    StockAdjustmentApproveRequest,
    StockAdjustmentCreate,
    StockConsumptionCreate,
    StockReservationCreate,
    StockReservationReleaseRequest,
    SupplierCreate,
)


def _today_ymd(override: str | None = None) -> str:
    if override:
        date.fromisoformat(override)
        return override
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def lot_physical_qty(db: Session, lot_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(m.StockMovement.quantity_delta), 0)).where(
                m.StockMovement.lot_id == lot_id
            )
        )
        or 0
    )


def lot_reserved_qty(db: Session, lot_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(m.StockReservation.reserved_qty), 0)).where(
                m.StockReservation.lot_id == lot_id,
                m.StockReservation.status == "active",
            )
        )
        or 0
    )


def create_supplier(
    db: Session, clinic_id: str, data: SupplierCreate, actor: str
) -> m.InventorySupplier:
    tax_clean = data.tax_code_demo.strip()
    dup = db.scalar(
        select(m.InventorySupplier).where(
            m.InventorySupplier.clinic_id == clinic_id,
            m.InventorySupplier.tax_code_demo == tax_clean,
        )
    )
    if dup is not None:
        raise HTTPException(409, "Supplier tax_code_demo already registered in this clinic (INV-002)")
    sup = m.InventorySupplier(
        clinic_id=clinic_id,
        name=data.name.strip(),
        tax_code_demo=tax_clean,
        actor_demo=actor,
    )
    db.add(sup)
    db.flush()
    svc.audit(db, clinic_id, actor, "inventory.supplier_created", "inventory_supplier", sup.id)
    db.commit()
    return sup


def create_sku(db: Session, clinic_id: str, data: SkuCreate, actor: str) -> m.InventorySku:
    code_clean = data.sku_code.strip().upper()
    dup = db.scalar(
        select(m.InventorySku).where(
            m.InventorySku.clinic_id == clinic_id,
            m.InventorySku.sku_code == code_clean,
        )
    )
    if dup is not None:
        raise HTTPException(409, "SKU code already exists in this clinic (INV-001)")
    sku = m.InventorySku(
        clinic_id=clinic_id,
        sku_code=code_clean,
        name=data.name.strip(),
        unit=data.unit.strip(),
        lot_tracked=data.lot_tracked,
        reorder_threshold=data.reorder_threshold,
        actor_demo=actor,
    )
    db.add(sku)
    db.flush()
    svc.audit(db, clinic_id, actor, "inventory.sku_created", "inventory_sku", sku.id)
    db.commit()
    return sku


def create_purchase_order(
    db: Session, clinic_id: str, data: PurchaseOrderCreate, actor: str
) -> m.PurchaseOrder:
    svc.ensure(db, m.InventorySupplier, data.supplier_id, clinic_id)
    svc.ensure(db, m.InventorySku, data.sku_id, clinic_id)
    po = m.PurchaseOrder(
        clinic_id=clinic_id,
        supplier_id=data.supplier_id,
        sku_id=data.sku_id,
        ordered_qty=data.ordered_qty,
        status="ordered",
        actor_demo=actor,
    )
    db.add(po)
    db.flush()
    svc.audit(db, clinic_id, actor, "inventory.po_created", "purchase_order", po.id)
    db.commit()
    return po


def receive_purchase_order(
    db: Session,
    clinic_id: str,
    po_id: str,
    data: PurchaseOrderReceiveRequest,
    actor: str,
) -> dict:
    po = svc.ensure(db, m.PurchaseOrder, po_id, clinic_id)
    if po.status != "ordered":
        raise HTTPException(409, f"Purchase order in status '{po.status}' cannot be received again")
    if data.inspected_accepted_qty > data.delivered_qty:
        raise HTTPException(
            422, "inspected_accepted_qty cannot exceed delivered_qty (INV-003)"
        )
    date.fromisoformat(data.expiry_date)

    lot_no = data.lot_number.strip()
    dup_lot = db.scalar(
        select(m.InventoryLot).where(
            m.InventoryLot.clinic_id == clinic_id,
            m.InventoryLot.sku_id == po.sku_id,
            m.InventoryLot.lot_number == lot_no,
        )
    )
    if dup_lot is not None:
        raise HTTPException(409, f"Lot '{lot_no}' already exists for this SKU in clinic")

    po.delivered_qty = data.delivered_qty
    po.inspected_accepted_qty = data.inspected_accepted_qty
    po.status = "received"

    lot = m.InventoryLot(
        clinic_id=clinic_id,
        sku_id=po.sku_id,
        purchase_order_id=po.id,
        lot_number=lot_no,
        expiry_date=data.expiry_date,
        quarantined=data.quarantined,
        actor_demo=actor,
    )
    db.add(lot)
    db.flush()

    mv = None
    if data.inspected_accepted_qty > 0:
        mv = m.StockMovement(
            clinic_id=clinic_id,
            sku_id=po.sku_id,
            lot_id=lot.id,
            movement_type="receipt_accepted",
            quantity_delta=data.inspected_accepted_qty,
            reference_type="purchase_order",
            reference_id=po.id,
            note_demo=f"PO received: ordered={po.ordered_qty} delivered={data.delivered_qty} accepted={data.inspected_accepted_qty}",
            actor_demo=actor,
        )
        db.add(mv)
        db.flush()

    svc.audit(
        db,
        clinic_id,
        actor,
        "inventory.po_received",
        "inventory_lot",
        lot.id,
        {
            "po_id": po.id,
            "delivered_qty": data.delivered_qty,
            "inspected_accepted_qty": data.inspected_accepted_qty,
            "quarantined": data.quarantined,
        },
    )
    db.commit()
    return {
        "purchase_order": {
            "id": po.id,
            "status": po.status,
            "ordered_qty": po.ordered_qty,
            "delivered_qty": po.delivered_qty,
            "inspected_accepted_qty": po.inspected_accepted_qty,
        },
        "lot": {
            "id": lot.id,
            "sku_id": lot.sku_id,
            "lot_number": lot.lot_number,
            "expiry_date": lot.expiry_date,
            "quarantined": lot.quarantined,
        },
        "movement_id": mv.id if mv else None,
    }


def get_sku_stock_summary(db: Session, clinic_id: str, sku_id: str) -> dict:
    sku = svc.ensure(db, m.InventorySku, sku_id, clinic_id)
    lots = db.scalars(
        select(m.InventoryLot)
        .where(m.InventoryLot.clinic_id == clinic_id, m.InventoryLot.sku_id == sku.id)
        .order_by(m.InventoryLot.expiry_date.asc(), m.InventoryLot.created_at.asc())
    ).all()
    lots_out = []
    total_phys = 0
    total_res = 0
    for lot in lots:
        phys = lot_physical_qty(db, lot.id)
        res = lot_reserved_qty(db, lot.id)
        avail = phys - res
        total_phys += phys
        total_res += res
        lots_out.append(
            {
                "lot_id": lot.id,
                "lot_number": lot.lot_number,
                "expiry_date": lot.expiry_date,
                "quarantined": lot.quarantined,
                "physical_on_hand_qty": phys,
                "active_reserved_qty": res,
                "available_qty": avail,
            }
        )
    total_avail = total_phys - total_res
    return {
        "sku_id": sku.id,
        "sku_code": sku.sku_code,
        "name": sku.name,
        "unit": sku.unit,
        "reorder_threshold": sku.reorder_threshold,
        "physical_on_hand_qty": total_phys,
        "active_reserved_qty": total_res,
        "available_qty": total_avail,
        "low_stock": total_avail <= sku.reorder_threshold,
        "lots": lots_out,
    }


def get_fefo_picks(
    db: Session,
    clinic_id: str,
    sku_id: str,
    required_qty: int,
    as_of_date: str | None = None,
) -> dict:
    if required_qty < 1:
        raise HTTPException(422, "required_qty must be >= 1")
    sku = svc.ensure(db, m.InventorySku, sku_id, clinic_id)
    ref_ymd = _today_ymd(as_of_date)
    lots = db.scalars(
        select(m.InventoryLot)
        .where(m.InventoryLot.clinic_id == clinic_id, m.InventoryLot.sku_id == sku.id)
        .order_by(m.InventoryLot.expiry_date.asc(), m.InventoryLot.created_at.asc())
    ).all()

    remaining = required_qty
    picks = []
    excluded = []
    for lot in lots:
        phys = lot_physical_qty(db, lot.id)
        res = lot_reserved_qty(db, lot.id)
        avail = phys - res
        if lot.quarantined:
            excluded.append({"lot_id": lot.id, "lot_number": lot.lot_number, "reason": "quarantined"})
            continue
        if lot.expiry_date < ref_ymd:
            excluded.append({"lot_id": lot.id, "lot_number": lot.lot_number, "reason": "expired"})
            continue
        if avail <= 0 or remaining <= 0:
            continue
        take = min(avail, remaining)
        picks.append(
            {
                "lot_id": lot.id,
                "lot_number": lot.lot_number,
                "expiry_date": lot.expiry_date,
                "pick_qty": take,
            }
        )
        remaining -= take

    return {
        "sku_id": sku.id,
        "sku_code": sku.sku_code,
        "as_of_date": ref_ymd,
        "required_qty": required_qty,
        "fulfilled": remaining == 0,
        "shortfall_qty": remaining,
        "picks": picks,
        "excluded_lots": excluded,
    }


def create_reservation(
    db: Session, clinic_id: str, data: StockReservationCreate, actor: str
) -> m.StockReservation:
    sku = svc.ensure(db, m.InventorySku, data.sku_id, clinic_id)
    lot = svc.ensure(db, m.InventoryLot, data.lot_id, clinic_id)
    if lot.sku_id != sku.id:
        raise HTTPException(422, "Lot does not belong to specified SKU")
    svc.ensure(db, m.Patient, data.patient_id, clinic_id)
    if data.appointment_id:
        svc.ensure(db, m.Appointment, data.appointment_id, clinic_id)
    if lot.quarantined:
        raise HTTPException(409, "Cannot reserve stock from a quarantined lot")

    avail = lot_physical_qty(db, lot.id) - lot_reserved_qty(db, lot.id)
    if data.reserved_qty > avail:
        raise HTTPException(
            409,
            f"Insufficient allocatable stock on lot {lot.lot_number}: requested {data.reserved_qty}, available {avail}",
        )

    res = m.StockReservation(
        clinic_id=clinic_id,
        sku_id=sku.id,
        lot_id=lot.id,
        patient_id=data.patient_id,
        appointment_id=data.appointment_id,
        reserved_qty=data.reserved_qty,
        status="active",
        actor_demo=actor,
    )
    db.add(res)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "inventory.stock_reserved_not_consumed",
        "stock_reservation",
        res.id,
        {"lot_id": lot.id, "reserved_qty": res.reserved_qty},
    )
    db.commit()
    return res


def release_reservation(
    db: Session,
    clinic_id: str,
    reservation_id: str,
    data: StockReservationReleaseRequest,
    actor: str,
) -> m.StockReservation:
    res = svc.ensure(db, m.StockReservation, reservation_id, clinic_id)
    if res.status != "active":
        raise HTTPException(409, f"Reservation in status '{res.status}' cannot be released")
    res.status = "released"
    res.release_reason = data.reason.strip()
    svc.audit(
        db,
        clinic_id,
        actor,
        "inventory.reservation_released",
        "stock_reservation",
        res.id,
        {"reason": res.release_reason},
    )
    db.commit()
    return res


def consume_for_procedure(
    db: Session,
    clinic_id: str,
    data: StockConsumptionCreate,
    actor: str,
) -> m.StockMovement:
    lot = svc.ensure(db, m.InventoryLot, data.lot_id, clinic_id)
    enc = svc.ensure(db, m.Encounter, data.encounter_id, clinic_id)
    ref_ymd = _today_ymd(data.as_of_date)

    if lot.quarantined:
        raise HTTPException(409, f"Lot {lot.lot_number} is quarantined; consumption blocked (INV-004)")
    if lot.expiry_date < ref_ymd:
        raise HTTPException(
            409,
            f"Lot {lot.lot_number} expired on {lot.expiry_date} (as_of={ref_ymd}); consumption blocked (INV-004)",
        )

    if data.reservation_id:
        res = svc.ensure(db, m.StockReservation, data.reservation_id, clinic_id)
        if res.lot_id != lot.id or res.status != "active":
            raise HTTPException(409, "Linked reservation is not active for this lot")
        res.status = "fulfilled"
        db.flush()

    avail = lot_physical_qty(db, lot.id) - lot_reserved_qty(db, lot.id)
    if data.consumed_qty > avail:
        db.rollback()
        raise HTTPException(
            409,
            f"Consumption exceeds available lot balance ({data.consumed_qty} > {avail})",
        )

    try:
        mv = m.StockMovement(
            clinic_id=clinic_id,
            sku_id=lot.sku_id,
            lot_id=lot.id,
            movement_type="procedure_consumed",
            quantity_delta=-data.consumed_qty,
            reference_type="encounter",
            reference_id=enc.id,
            note_demo=data.procedure_note_demo.strip(),
            actor_demo=actor,
        )
        db.add(mv)
        db.flush()
        svc.audit(
            db,
            clinic_id,
            actor,
            "inventory.procedure_consumed",
            "stock_movement",
            mv.id,
            {"lot_id": lot.id, "encounter_id": enc.id, "consumed_qty": data.consumed_qty},
        )
        db.commit()
        return mv
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Concurrent lot balance underflow rejected") from exc


def request_stock_adjustment(
    db: Session,
    clinic_id: str,
    requester_staff_id: str,
    data: StockAdjustmentCreate,
    actor: str,
) -> m.StockAdjustmentRequest:
    if data.delta_qty == 0:
        raise HTTPException(422, "Adjustment delta_qty cannot be zero")
    lot = svc.ensure(db, m.InventoryLot, data.lot_id, clinic_id)
    req = m.StockAdjustmentRequest(
        clinic_id=clinic_id,
        sku_id=lot.sku_id,
        lot_id=lot.id,
        delta_qty=data.delta_qty,
        reason=data.reason.strip(),
        status="pending_dual_approval",
        requester_staff_id=requester_staff_id,
    )
    db.add(req)
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "inventory.adjustment_requested",
        "stock_adjustment_request",
        req.id,
        {"lot_id": lot.id, "delta_qty": req.delta_qty},
    )
    db.commit()
    return req


def approve_stock_adjustment(
    db: Session,
    clinic_id: str,
    adjustment_id: str,
    approver_staff_id: str,
    data: StockAdjustmentApproveRequest,
    actor: str,
) -> m.StockAdjustmentRequest:
    req = svc.ensure(db, m.StockAdjustmentRequest, adjustment_id, clinic_id)
    if req.status != "pending_dual_approval":
        raise HTTPException(409, f"Adjustment in status '{req.status}' cannot be approved")
    if req.requester_staff_id == approver_staff_id:
        svc.audit(
            db,
            clinic_id,
            actor,
            "inventory.adjustment_self_approval_blocked",
            "stock_adjustment_request",
            req.id,
        )
        db.commit()
        raise HTTPException(
            409,
            "Dual-control policy violation: requester cannot self-approve stock adjustment (INV-010)",
        )

    if req.delta_qty < 0:
        avail = lot_physical_qty(db, req.lot_id) - lot_reserved_qty(db, req.lot_id)
        if abs(req.delta_qty) > avail:
            raise HTTPException(409, "Negative stock adjustment exceeds available unreserved stock")

    mv_type = "adjustment_in" if req.delta_qty > 0 else "adjustment_out"
    mv = m.StockMovement(
        clinic_id=clinic_id,
        sku_id=req.sku_id,
        lot_id=req.lot_id,
        movement_type=mv_type,
        quantity_delta=req.delta_qty,
        reference_type="stock_adjustment_request",
        reference_id=req.id,
        note_demo=f"{req.reason} | Approved: {data.approval_note.strip()}"[:260],
        actor_demo=actor,
    )
    db.add(mv)
    req.status = "approved"
    req.approver_staff_id = approver_staff_id
    req.approval_note = data.approval_note.strip()
    req.approved_at = m.utcnow()
    db.flush()
    svc.audit(
        db,
        clinic_id,
        actor,
        "inventory.adjustment_dual_approved",
        "stock_adjustment_request",
        req.id,
        {"movement_id": mv.id, "delta_qty": req.delta_qty},
    )
    db.commit()
    return req


def get_inventory_alerts(
    db: Session, clinic_id: str, as_of_date: str | None = None
) -> dict:
    ref_ymd = _today_ymd(as_of_date)
    near_ymd = (date.fromisoformat(ref_ymd) + timedelta(days=90)).isoformat()

    skus = db.scalars(
        select(m.InventorySku).where(m.InventorySku.clinic_id == clinic_id)
    ).all()
    low_stock_skus = []
    for sku in skus:
        summary = get_sku_stock_summary(db, clinic_id, sku.id)
        if summary["low_stock"]:
            low_stock_skus.append(
                {
                    "sku_id": sku.id,
                    "sku_code": sku.sku_code,
                    "name": sku.name,
                    "available_qty": summary["available_qty"],
                    "reorder_threshold": sku.reorder_threshold,
                }
            )

    lots = db.scalars(
        select(m.InventoryLot).where(m.InventoryLot.clinic_id == clinic_id)
    ).all()
    expired_lots = []
    near_expiry_lots = []
    for lot in lots:
        phys = lot_physical_qty(db, lot.id)
        if phys <= 0:
            continue
        if lot.expiry_date < ref_ymd:
            expired_lots.append(
                {
                    "lot_id": lot.id,
                    "sku_id": lot.sku_id,
                    "lot_number": lot.lot_number,
                    "expiry_date": lot.expiry_date,
                    "physical_on_hand_qty": phys,
                }
            )
        elif lot.expiry_date <= near_ymd:
            near_expiry_lots.append(
                {
                    "lot_id": lot.id,
                    "sku_id": lot.sku_id,
                    "lot_number": lot.lot_number,
                    "expiry_date": lot.expiry_date,
                    "physical_on_hand_qty": phys,
                }
            )

    shrinkage = db.scalars(
        select(m.StockMovement)
        .where(
            m.StockMovement.clinic_id == clinic_id,
            m.StockMovement.movement_type == "adjustment_out",
        )
        .order_by(m.StockMovement.created_at.desc())
    ).all()

    return {
        "as_of_date": ref_ymd,
        "low_stock_skus": low_stock_skus,
        "expired_lots": expired_lots,
        "near_expiry_lots": near_expiry_lots,
        "shrinkage_movements": [
            {
                "movement_id": mv.id,
                "lot_id": mv.lot_id,
                "quantity_delta": mv.quantity_delta,
                "note_demo": mv.note_demo,
                "created_at": mv.created_at.isoformat() + "Z",
            }
            for mv in shrinkage
        ],
    }
