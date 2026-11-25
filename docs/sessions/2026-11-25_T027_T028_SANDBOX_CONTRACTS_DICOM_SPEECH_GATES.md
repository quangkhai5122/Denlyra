# Báo cáo Phiên Làm việc — 2026-11-25 (`T027` + `T028`)

### Session Summary
- **Task ID / Phạm vi:** Triển khai hoàn chỉnh hai gói nhiệm vụ `T027` (`CRM-012`, `OPS-008`, `ORG-010`, `INT-007`, `INT-008`) và `T028` (`INT-004`, `AI-001`, `FIN-009`, `INT-009`, `SEC-014`, `SEC-015`) theo quy trình kiểm thử phủ định trước (*negative-first TDD*), ban hành `ADR-019`, mở rộng chuỗi migration tiến-lên-duy-nhất lên `0014_sandbox_contracts_dicom_speech_and_release_gates` (`135` bảng miền, `308` HTTP operations trên `242` đường dẫn) và nâng danh mục tính năng demo lên `209/222` mã `D`.
- **Tệp tạo mới / cập nhật:**
  - `backend/src/denlyra/sandbox_contracts_benchmark_oidc.py`, `backend/src/denlyra/dicom_speech_accounting_security.py`, `backend/alembic/versions/0014_sandbox_contracts_dicom_speech_and_release_gates.py`
  - `backend/src/denlyra/models.py`, `backend/src/denlyra/schemas.py`, `backend/src/denlyra/api.py`
  - `backend/tests/test_cancellation_benchmark_oidc_and_webhooks.py`, `backend/tests/test_dicom_speech_accounting_and_security_gates.py`, `backend/tests/test_scheduling_concurrency.py`
  - `scripts/run_load_benchmark.py`, `scripts/smoke_baseline.py`, `scripts/generate_openapi_ts.py`, `scripts/generate_function_catalog.py`
  - `apps/clinic-web/src/lib/generated-api.ts`, `apps/clinic-web/src/app/page.tsx`, `apps/clinic-web/tests/frontend_contracts_and_a11y.test.mjs`
  - `docs/tasks/T027_CANCELLATION_POLICY_BENCHMARK_AND_SANDBOX_INTEGRATION_CONTRACTS.md`, `docs/tasks/T028_DICOM_GATEWAY_QUARANTINE_SPEECH_CONSENT_AND_FAIL_CLOSED_COMPLIANCE_GATES.md`, `docs/adr/ADR-019-sandbox-provider-contracts-dicom-quarantine-speech-consent-and-release-gates.md`, `docs/product/FUNCTION_CATALOG.md`, `docs/engineering/API_CONTRACT.md`, `docs/architecture/DATABASE.md`, `docs/engineering/IMPLEMENTATION_STATUS.md`, `docs/engineering/ROADMAP.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`, `MANIFEST_SHA256.txt`

### Verification
- `pytest backend/tests -q`: **`103 passed, 1 skipped`** (bài skip yêu cầu biến môi trường `DENLYRA_TEST_POSTGRES_URL`).
- `ruff check` (backend + alembic + scripts), `compileall`, `node --check apps/demo-web/app.js`: **PASS (`exit 0`)**.
- `verify_artifact.py`: **PASS** (`222` mã danh mục, `209` cờ `D`, giữ nguyên toàn bộ cờ an toàn `False` và đường dẫn liên kết).
- `smoke_baseline.py`: **PASS** (`135` bảng miền tại head `0014_sandbox_contracts_dicom_speech_and_release_gates`; `308` HTTP operations).
- `run_dr_restore_drill.py`, `run_ai_eval_harness.py` (`8/8`), `verify_audit_chain.py`, `run_load_benchmark.py`, `generate_openapi_ts.py --check`, `alembic upgrade head --sql` (PostgreSQL offline DDL): **PASS (`exit 0`)**.
- `apps/clinic-web`: `npm test` (`4 pass, 0 fail`), `npm run typecheck` (`exit 0`), `npm run build` (`exit 0`), `npm audit --audit-level=moderate` (`0 vulnerabilities`).
- **Kiểm thử chưa chạy:** Kiểm thử tranh chấp khóa `EXCLUDE USING gist` trực tiếp trên máy chủ PostgreSQL 16 sống (`scripts/verify_postgres_live.py`) và kiểm thử xâm nhập độc lập bên ngoài (`SEC-G1`).

### Architecture & Decisions
- Ban hành [ADR-019](../adr/ADR-019-sandbox-provider-contracts-dicom-quarantine-speech-consent-and-release-gates.md): tiếp cận ca hủy theo chính sách lãnh đạo phòng khám cấm suy đoán cấp cứu lâm sàng (`CRM-012`), bộ đo kiểm độ trễ/năng lực cục bộ không bịa đặt SLA đám mây (`OPS-008`), đồng bộ nhóm OIDC thu hồi tức thì qua `token_version` (`ORG-010`), hợp đồng sandbox nhắn tin tôn trọng `STOP`/`HUY` không lộ chẩn đoán (`INT-007`), webhook thanh toán ký HMAC-SHA256 chống phát lại & hoàn trả có giới hạn (`INT-008`), cổng cách ly metadata DICOM kiểm khớp `PatientID` và thiết bị xác nhận (`INT-004`), bản nháp ghi âm tiếng Việt bắt buộc đồng thuận âm thanh không tự ghi EMR (`AI-001`), xuất sổ kế toán không PHI khóa cứng hóa đơn thuế/API nhà nước (`FIN-009`/`INT-009`), cùng bộ kiểm thử đối kháng SSRF/traversal và cổng chặn kích hoạt PHI sản xuất (`SEC-014`/`SEC-015`).

### Git Status
- Nhánh `main`, chuẩn bị commit với tiền tố `[T027][T028]` và push fast-forward lên `origin/main` (xem `git log -1` để lấy mã băm chính thức của commit chứa tệp báo cáo này).

### Project Progress
- Hoàn tất `T000`–`T028` (`ADR-006`..`ADR-019`), đạt `209/222` mã `D` (`94.1%`). `13` mã `—` còn lại đều là các hạng mục bắt buộc hợp đồng nhà cung cấp thực tế, hạ tầng đám mây vùng Việt Nam hoặc phê duyệt pháp lý/lâm sàng/SaMD bên ngoài.

### Next Steps
1. **Cổng hạ tầng PostgreSQL 16 (`T002`):** Thực thi `scripts/verify_postgres_live.py` trên máy chủ PostgreSQL 16 sống hoặc thu biên nhận từ CI `postgres-concurrency-tests`.
2. **Cổng phê duyệt lâm sàng, pháp lý & bảo mật (`M0` / `T003` / `T004` / `T010` / `SEC-G1`):** Hoàn tất ký duyệt của bác sĩ nha khoa chịu trách nhiệm chuyên môn, cố vấn pháp lý và kiểm định bảo mật độc lập trước khi mở khóa `TRT-004`, `SEC-003`, `SEC-005`, `SEC-009`.
3. **Gói `T029` (Tùy chọn hợp đồng cổng ngoài fail-closed còn lại — `CRM-006`..`008`, `FIN-012`, `OPS-003`, `AI-012`):** Nếu cần hoàn thiện bộ khung hợp đồng kiểm thử offline cho mẫu cấu hình IaC vùng Việt Nam externalized-secrets, bộ đánh giá lift LoRA dữ liệu ẩn danh được cấp phép và khung đối soát yêu cầu bảo hiểm đối tác không tự động quyết toán.
