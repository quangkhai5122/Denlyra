# Báo cáo Phiên Làm việc — 2026-11-25 (`T029` + `T030` + Chuẩn hóa PostgreSQL 16 `T002`)

### Session Summary
- **Task ID / Phạm vi:** Triển khai hoàn chỉnh hai gói nhiệm vụ `T029` (`OPS-003`, `FIN-012`, `AI-012`, `TRT-004`) và `T030` (`CRM-006`, `CRM-007`, `CRM-008`) theo quy trình kiểm thử phủ định trước (*negative-first TDD*), ban hành `ADR-020`, đồng thời khắc phục triệt để các điểm tương thích kiểu dữ liệu nghiêm ngặt của PostgreSQL 16 trên chuỗi migration Alembic (`alembic_version.version_num VARCHAR(128)`, `schema_migration_meta.revision_id VARCHAR(128)`, biểu thức boolean `NOT auto_charge_enabled` và tách câu lệnh trigger PL/pgSQL đơn lẻ) để job CI `postgres-concurrency-tests` (`T002`) vượt qua trên máy chủ `postgres:16`.
- **Tệp tạo mới / cập nhật:**
  - `backend/src/denlyra/iac_insurance_lora_plan_attestation.py`, `backend/src/denlyra/channel_contracts_zalo_sms_email.py`, `backend/alembic/versions/0015_iac_insurance_lora_plan_attestation_and_channels.py`
  - `backend/alembic/env.py`, `backend/alembic/versions/0002_hardening.py`, `backend/alembic/versions/0007_operations_audit_chain_and_pagination.py`, `backend/alembic/versions/0009_encounter_lifecycle_and_clinical_governance.py`
  - `backend/src/denlyra/models.py`, `backend/src/denlyra/schemas.py`, `backend/src/denlyra/api.py`
  - `backend/tests/test_iac_insurance_lora_and_plan_attestation.py`, `backend/tests/test_channel_contracts_zalo_sms_email.py`, `backend/tests/test_scheduling_concurrency.py`
  - `.github/workflows/ci.yml`, `scripts/smoke_baseline.py`, `scripts/generate_openapi_ts.py`, `scripts/generate_function_catalog.py`
  - `apps/clinic-web/src/lib/generated-api.ts`, `apps/clinic-web/src/app/page.tsx`, `apps/clinic-web/tests/frontend_contracts_and_a11y.test.mjs`
  - `docs/tasks/T029_EXTERNAL_VENDOR_ADAPTER_STUBS_AND_IAC_BLUEPRINTS.md`, `docs/tasks/T030_CHANNEL_SPECIFIC_MESSAGING_CONTRACTS_ZALO_SMS_EMAIL.md`, `docs/adr/ADR-020-iac-region-guard-insurance-sandbox-lora-lift-plan-attestation-and-channel-contracts.md`, `docs/product/FUNCTION_CATALOG.md`, `docs/engineering/API_CONTRACT.md`, `docs/architecture/DATABASE.md`, `docs/engineering/IMPLEMENTATION_STATUS.md`, `docs/engineering/ROADMAP.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`, `MANIFEST_SHA256.txt`

### Verification
- `pytest backend/tests -q`: **`109 passed, 1 skipped`** (bài skip cục bộ khi không đặt `DENLYRA_TEST_POSTGRES_URL`, được chạy tự động trên GitHub Actions `postgres-concurrency-tests` với `postgres:16`).
- `ruff check`, `compileall`, `node --check apps/demo-web/app.js`: **PASS (`exit 0`)**.
- `verify_artifact.py`: **PASS** (`222` mã danh mục, `216` cờ `D`, giữ nguyên toàn bộ cờ an toàn `False` và đường dẫn liên kết).
- `smoke_baseline.py`: **PASS** (`145` bảng miền tại head `0015_iac_insurance_lora_plan_attestation_and_channels`; `327` HTTP operations trên `256` đường dẫn).
- `run_dr_restore_drill.py`, `run_ai_eval_harness.py` (`8/8`), `verify_audit_chain.py`, `run_load_benchmark.py`, `generate_openapi_ts.py --check`, `alembic upgrade head --sql` (PostgreSQL offline DDL): **PASS (`exit 0`)**.
- `apps/clinic-web`: `npm test` (`4 pass, 0 fail`), `npm run typecheck` (`exit 0`), `npm run build` (`exit 0`), `npm audit --audit-level=moderate` (`0 vulnerabilities`).
- **Live PostgreSQL 16 (`T002` — GitHub Actions `postgres-concurrency-tests` Run `#45585785317`, commit `622d4cb9253a9fcb22535ce3da122f7861186ab9`):** **PASS (`completed / success`)** cả `python scripts/verify_postgres_live.py` (5 vòng đua `Barrier(2)` trên `EXCLUDE USING gist` trả về `[201, 409]`) lẫn `python -m pytest backend/tests/test_scheduling_concurrency.py -q` trên `postgres:16`.

### Architecture & Decisions
- Ban hành [ADR-020](../adr/ADR-020-iac-region-guard-insurance-sandbox-lora-lift-plan-attestation-and-channel-contracts.md): kiểm định blueprint IaC vùng Việt Nam & bắt buộc tham chiếu `secret_ref://` (`OPS-003`), cổng hồ sơ bảo hiểm nha khoa tư nhân chặn cứng cổng BHYT nhà nước & tự động quyết toán (`FIN-012`), cổng đánh giá LoRA dữ liệu ẩn danh có giấy phép & độ nâng F1 dương (`AI-012`), chứng thực phiên bản phác đồ mô phỏng gắn băm SHA-256 chặn tuyên bố phê duyệt pháp lý (`TRT-004`), cùng 3 hợp đồng kênh Zalo OA/ZNS (`CRM-006`), SMS DLR (`CRM-007`) và Email xác thực `SPF`/`DKIM`/`DMARC` giới hạn tốc độ `429` (`CRM-008`).

### Git Status
- Nhánh `main`, chuẩn bị commit với tiền tố `[T002][T029][T030]` và push fast-forward lên `origin/main`, sau đó xác minh trực tiếp kết quả GitHub Actions `postgres-concurrency-tests` trên máy chủ `postgres:16`.

### Project Progress
- Hoàn tất toàn bộ `T000`–`T030` (`ADR-006`..`ADR-020`), đạt **`216/222` mã `D` (`97.3%`)**. Đúng `6` mã còn giữ `—` (`AI-013`, `INT-006`, `INT-010`, `SEC-003`, `SEC-005`, `SEC-009`) là các cổng pháp lý/PKI/chính phủ/SaMD bắt buộc phê duyệt con người bên ngoài.

### Next Steps
1. **Cổng phê duyệt lâm sàng, pháp lý & bảo mật (`M0` / `T003` / `T004` / `T010` / `SEC-G1`):** Thu thập văn bản phê duyệt của bác sĩ RHM chịu trách nhiệm chuyên môn, cố vấn pháp lý y tế Việt Nam và kiểm định bảo mật độc lập theo `docs/clinical/NEEDS_CLINICAL_REVIEW.md` và `docs/operations/RETENTION_AND_DR_POLICY.md`.
2. **Tích hợp nhà cung cấp thực tế có hợp đồng (`INT-006`, `CRM-006`..`008`, `INT-008`):** Chỉ kết nối chứng thư số CA/PKI, Zalo OA, SMS Brandname, cổng thanh toán và Orthanc DICOM sau khi hoàn tất hợp đồng xử lý dữ liệu cá nhân (DPA) theo Luật Bảo vệ dữ liệu cá nhân `91/2025/QH15`.
