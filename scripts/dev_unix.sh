#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install -c backend/constraints-baseline.txt -e './backend[dev]'
export DENLYRA_DEMO_MODE=1
export DENLYRA_DATABASE_URL='sqlite+pysqlite:///./local_data/denlyra-demo.db'
python -m denlyra
