# T014 — Hash-Chained Tamper-Evident Audit Journal & Clinic-Scoped Cursor Pagination
Priority P0/P1 (`SEC-007`, `PAT-002`, `R-012`) · Owner: Security / Platform · Depends T001, T010

**Status (2026-11-24):** Completed (per-clinic SHA-256 hash-chained `audit_event` journal, SQLite `no_update`/`no_delete` triggers, genesis-to-head tamper verifier, and HMAC-signed clinic-scoped cursor pagination verified in `test_audit_chain_and_pagination.py` & `verify_audit_chain.py`; external WORM log sink remains a pre-PHI production gate). See [ADR-012](../adr/ADR-012-clinic-operations-tamper-evident-audit-and-pagination.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Security & Scalability Invariants
1. **Per-Clinic Cryptographic Hash Chain on `audit_event` (`SEC-007`):**
   - Every `AuditEvent` row carries `chain_seq` (`1, 2, ...` monotonic per `clinic_id`), `prev_hash` (`"0" * 64` for genesis `chain_seq == 1`, otherwise the exact `entry_hash` of `chain_seq - 1`), and `entry_hash` (`SHA-256` over canonical fields `clinic_id|chain_seq|prev_hash|actor_demo|action|subject_type|subject_id|metadata_json|created_at`).
   - Preventive layer: SQLite `BEFORE UPDATE` and `BEFORE DELETE` triggers (`tr_audit_event_no_update`, `tr_audit_event_no_delete`) block SQL mutation or deletion of audit rows (`IntegrityError`).
   - Detective layer: `GET /api/v1/audit-events/verify-chain` recomputes every link from genesis `chain_seq = 1` through head, detecting any out-of-band disk tampering, altered action/actor/metadata, or deleted middle sequence number (`409 Conflict` with `broken_at_seq`).
2. **Signed Opaque Clinic-Scoped Cursor Pagination (`PAT-002`, `R-012`):**
   - Cursor tokens are Base64URL JSON payloads `{clinic_id, seq_or_ts, id}` authenticated with constant-time `HMAC-SHA256` (`Settings.auth_secret`).
   - Endpoints:
     - `GET /api/v1/patients/page?q=...&limit=...&cursor=...` (clinic-scoped search + minimized patient projection)
     - `GET /api/v1/appointments/page?limit=...&cursor=...`
     - `GET /api/v1/audit-events/page?limit=...&cursor=...`
   - Tampered cursor signatures (`422`) and **cross-tenant cursor replay** (`Clinic A` cursor replayed under `Clinic B` token -> `403`) fail closed.

## Mandatory Negative Tests (Written Before Domain Code)
1. Direct SQL `UPDATE` or `DELETE` on `audit_event` -> blocked by DB immutability trigger (`IntegrityError`).
2. Simulated privileged/out-of-band DB file tamper (mutating `action` or deleting a middle row after dropping trigger on raw SQLite file) -> `GET /api/v1/audit-events/verify-chain` fails closed with `409 Conflict` and identifies `broken_at_seq`.
3. Cursor pagination across multiple pages returns exact non-overlapping deterministic union scoped to `clinic_id`; tampered cursor token -> `422`; `Clinic A` cursor replayed by `Clinic B` -> `403`.
