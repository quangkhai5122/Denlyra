"""Demo database lifecycle. create_all is forbidden outside explicit demo mode.

Production requires reviewed Alembic migrations, PostgreSQL exclusion constraints,
clinically appropriate authorization, and verified encrypted backups.
"""
from collections.abc import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

SQLITE_BOOKING_OVERLAP_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS tr_no_overlapping_active_resource_booking
BEFORE INSERT ON resource_booking
WHEN NEW.state = 'active' AND EXISTS (
    SELECT 1 FROM resource_booking rb
    WHERE rb.clinic_id = NEW.clinic_id
      AND rb.resource_key = NEW.resource_key
      AND rb.state = 'active'
      AND rb.start_at < NEW.end_at
      AND rb.end_at > NEW.start_at
)
BEGIN
    SELECT RAISE(ABORT, 'no_overlapping_active_resource_booking');
END;
"""

SQLITE_ALLOCATION_BOUNDS_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS tr_payment_allocation_bounds
BEFORE INSERT ON payment_allocation
WHEN (
    (SELECT COALESCE(SUM(pa.amount_vnd), 0) FROM payment_allocation pa WHERE pa.charge_id = NEW.charge_id) + NEW.amount_vnd
    > (SELECT c.amount_vnd FROM charge c WHERE c.id = NEW.charge_id)
) OR (
    (SELECT COALESCE(SUM(pa.amount_vnd), 0) FROM payment_allocation pa WHERE pa.payment_id = NEW.payment_id)
    + (SELECT COALESCE(SUM(pr.amount_vnd), 0) FROM payment_refund pr WHERE pr.payment_id = NEW.payment_id)
    + NEW.amount_vnd
    > (SELECT p.amount_vnd FROM payment p WHERE p.id = NEW.payment_id)
)
BEGIN
    SELECT RAISE(ABORT, 'payment_allocation_bounds_exceeded');
END;
"""

SQLITE_STOCK_MOVEMENT_NO_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS tr_stock_movement_no_update
BEFORE UPDATE ON stock_movement
BEGIN
    SELECT RAISE(ABORT, 'stock_movement_append_only_no_update');
END;
"""

SQLITE_STOCK_MOVEMENT_NO_DELETE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS tr_stock_movement_no_delete
BEFORE DELETE ON stock_movement
BEGIN
    SELECT RAISE(ABORT, 'stock_movement_append_only_no_delete');
END;
"""

SQLITE_STOCK_MOVEMENT_BOUNDS_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS tr_stock_movement_lot_bounds
BEFORE INSERT ON stock_movement
WHEN NEW.quantity_delta < 0 AND (
    (SELECT COALESCE(SUM(sm.quantity_delta), 0) FROM stock_movement sm WHERE sm.lot_id = NEW.lot_id)
    + NEW.quantity_delta < 0
)
BEGIN
    SELECT RAISE(ABORT, 'stock_movement_lot_negative_balance');
END;
"""

SQLITE_DOWNTIME_BLOCK_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS tr_no_booking_during_downtime
BEFORE INSERT ON resource_booking
WHEN NEW.state = 'active' AND EXISTS (
    SELECT 1 FROM resource_downtime rd
    WHERE rd.clinic_id = NEW.clinic_id
      AND rd.resource_key = NEW.resource_key
      AND rd.status = 'active'
      AND rd.start_at < NEW.end_at
      AND rd.end_at > NEW.start_at
)
BEGIN
    SELECT RAISE(ABORT, 'resource_in_maintenance_downtime');
END;
"""

SQLITE_AUDIT_NO_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS tr_audit_event_no_update
BEFORE UPDATE ON audit_event
BEGIN
    SELECT RAISE(ABORT, 'audit_event_append_only_no_update');
END;
"""

SQLITE_AUDIT_NO_DELETE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS tr_audit_event_no_delete
BEFORE DELETE ON audit_event
BEGIN
    SELECT RAISE(ABORT, 'audit_event_append_only_no_delete');
END;
"""


class Base(DeclarativeBase):
    pass


def build_engine(url: str):
    kwargs = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    return engine


def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def init_demo_schema(engine):
    from denlyra import audit_chain, models  # noqa: F401
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            conn.execute(text(SQLITE_BOOKING_OVERLAP_TRIGGER))
            conn.execute(text(SQLITE_ALLOCATION_BOUNDS_TRIGGER))
            conn.execute(text(SQLITE_STOCK_MOVEMENT_NO_UPDATE_TRIGGER))
            conn.execute(text(SQLITE_STOCK_MOVEMENT_NO_DELETE_TRIGGER))
            conn.execute(text(SQLITE_STOCK_MOVEMENT_BOUNDS_TRIGGER))
            conn.execute(text(SQLITE_DOWNTIME_BLOCK_TRIGGER))
            conn.execute(text(SQLITE_AUDIT_NO_UPDATE_TRIGGER))
            conn.execute(text(SQLITE_AUDIT_NO_DELETE_TRIGGER))


def session_scope(factory) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
