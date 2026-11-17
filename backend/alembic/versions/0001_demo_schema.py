"""Demonstration schema only; not a reviewed production EMR migration.

Revision ID: 0001_demo
Revises:
"""
from alembic import op
from denlyra.db import Base
from denlyra import models  # noqa: F401

revision = "0001_demo"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute("""
          ALTER TABLE resource_booking
          ADD CONSTRAINT no_overlapping_active_resource_booking
          EXCLUDE USING gist (
              clinic_id WITH =,
              resource_key WITH =,
              tsrange(start_at, end_at, '[)') WITH &&
          ) WHERE (state = 'active')
        """)


def downgrade():
    raise RuntimeError("Destructive downgrade prohibited: restore a verified backup instead")
