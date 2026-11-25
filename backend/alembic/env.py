from logging.config import fileConfig
import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from denlyra.db import Base
from denlyra import models  # noqa: F401

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def _resolve_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    env_url = os.getenv("DENLYRA_DATABASE_URL")
    if env_url and configured and "127.0.0.1:5433/denlyra_demo" in configured:
        return env_url
    return configured


def run_migrations_offline():
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    section = dict(config.get_section(config.config_ini_section) or {})
    section["sqlalchemy.url"] = _resolve_url()
    engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "version_num VARCHAR(128) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
            )
            connection.exec_driver_sql(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
            )
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
