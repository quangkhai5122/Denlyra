"""Disposable synthetic checks for Denlyra CLI/HTTP and SQLite Alembic bootstrap.

This is not a browser, PostgreSQL concurrency, security or clinical acceptance suite.
Run from any cwd after installing backend[dev]. No persistent demo data is modified.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]


def migration_smoke(temp):
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend/alembic"))
    url = f"sqlite+pysqlite:///{temp / 'migration.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0001_demo")
    command.upgrade(config, "0002_hardening")
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "resource_booking" in tables and "alembic_version" in tables
        assert "revoked_token" in tables and "form_template_version" in tables
        assert "plan_task_dependency" in tables and "clinical_document_snapshot" in tables
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == "0003_treatment_and_signing"
    finally:
        engine.dispose()
    print(f"SQLite Alembic smoke PASS: {len(tables) - 1} domain tables; head 0003_treatment_and_signing")


def cli_smoke(temp):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {key: value for key, value in os.environ.items() if not key.startswith("DENLYRA_")}
    env["DENLYRA_DATABASE_URL"] = f"sqlite+pysqlite:///{temp / 'http.db'}"
    denied = subprocess.run([sys.executable, "-m", "denlyra"], check=False, env=env, cwd=ROOT,
                            capture_output=True, text=True, timeout=10)
    assert denied.returncode != 0 and "DENLYRA_DEMO_MODE=1 required" in denied.stderr
    env.update(DENLYRA_DEMO_MODE="1", DENLYRA_HOST="127.0.0.1", DENLYRA_PORT=str(port))
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    process = subprocess.Popen([sys.executable, "-m", "denlyra"], env=env, cwd=ROOT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(base + "/health", timeout=1) as response:
                    assert json.load(response)["demo_only"] is True
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError(process.communicate()[1].decode(errors="replace"))
                time.sleep(0.1)
        else:
            raise RuntimeError("Demo startup timed out")
        with urllib.request.urlopen(base, timeout=5) as response:
            assert "Denlyra" in response.read().decode("utf-8")
            assert response.headers["X-Denlyra-Demo-Only"] == "no-real-patient-data"
        with urllib.request.urlopen(base + "/api/v1/demo/context", timeout=5) as response:
            assert len(json.load(response)["clinics"]) == 2
        with urllib.request.urlopen(base + "/openapi.json", timeout=5) as response:
            schema = json.load(response)
            assert schema["info"]["title"].startswith("Denlyra")
            methods = {"get", "post", "put", "patch", "delete"}
            operations = sum(key in methods for path in schema["paths"].values() for key in path)
        print(f"CLI/HTTP smoke PASS: opt-in refusal; loopback; Denlyra UI/header/OpenAPI; {operations} operations")
    finally:
        process.terminate()
        process.communicate(timeout=10)


def main():
    local = ROOT / "local_data"
    local.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="baseline-", dir=local) as directory:
        temp = Path(directory)
        migration_smoke(temp)
        cli_smoke(temp)
    print("Smoke process stopped; disposable synthetic databases removed")


if __name__ == "__main__":
    main()
