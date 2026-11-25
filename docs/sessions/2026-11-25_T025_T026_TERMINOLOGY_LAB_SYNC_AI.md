# Báo cáo Phiên Làm việc — 2026-11-25 (`T025` + `T026`)

### Session Summary
- **Task ID / Phạm vi:** Triển khai hoàn chỉnh hai gói nhiệm vụ `T025` (`EMR-016`, `TRT-015`, `LAB-010`, `ODN-009`, `RPT-009`, `RPT-010`) và `T026` (`OPS-009`, `OPS-011`, `OPS-013`, `AI-007`, `AI-008`) theo quy trình viết kiểm thử âm tính trước (negative-first TDD), ban hành `ADR-018`, mở rộng chuỗi migration tiến-lên-duy-nhất lên `0013_terminology_templates_lab_reports_sync_and_ai` (`121` bảng miền, `284` HTTP operations trên `222` đường dẫn) và nâng danh mục tính năng demo lên `198/222` mã `D`.
- **Tệp tạo mới / cập nhật:**
  - `backend/src/denlyra/terminology_templates_lab_reports.py`, `backend/src/denlyra/release_sync_and_scheduling_ai.py`, `backend/alembic/versions/0013_terminology_templates_lab_reports_sync_and_ai.py`
  - `backend/src/denlyra/models.py`, `backend/src/denlyra/schemas.py`, `backend/src/denlyra/api.py`
  - `backend/tests/test_terminology_templates_lab_reports.py`, `backend/tests/test_release_sync_and_scheduling_ai.py`, `backend/tests/test_scheduling_concurrency.py`
  - `scripts/smoke_baseline.py`, `scripts/generate_openapi_ts.py`, `scripts/generate_function_catalog.py`
  - `apps/clinic-web/src/lib/generated-api.ts`, `apps/clinic-web/src/app/page.tsx`, `apps/clinic-web/tests/frontend_contracts_and_a11y.test.mjs`
  - `docs/tasks/T025_TERMINOLOGY_SPECIALTY_TEMPLATES_LAB_BILLING_AND_REPORT_EXPORTS.md`, `docs/tasks/T026_RELEASE_GOVERNANCE_OFFLINE_SYNC_AND_SCHEDULING_INTELLIGENCE.md`, `docs/adr/ADR-018-terminology-specialty-templates-lab-billing-offline-sync-and-scheduling-ai.md`, `docs/product/FUNCTION_CATALOG.md`, `docs/engineering/API_CONTRACT.md`, `docs/architecture/DATABASE.md`, `docs/engineering/IMPLEMENTATION_STATUS.md`, `docs/engineering/ROADMAP.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`, `MANIFEST_SHA256.txt`

### Verification
- `pytest backend/tests -q`: **`97 passed, 1 skipped`** (bài skip yêu cầu biến môi trường `DENLYRA_TEST_POSTGRES_URL`).
- `ruff check` (backend + alembic + scripts), `compileall`, `node --check apps/demo-web/app.js`: **PASS (`exit 0`)**.
- `verify_artifact.py`: **PASS** (`222` mã danh mục, `198` cờ `D`, giữ nguyên toàn bộ cờ an toàn `False` và đường dẫn liên kết).
- `smoke_baseline.py`: **PASS** (`121` bảng miền tại head `0013_terminology_templates_lab_reports_sync_and_ai`; `284` HTTP operations).
- `run_dr_restore_drill.py`, `run_ai_eval_harness.py` (`8/8`), `verify_audit_chain.py`, `generate_openapi_ts.py --check`, `alembic upgrade head --sql` (PostgreSQL offline DDL): **PASS (`exit 0`)**.
- `apps/clinic-web`: `npm test` (`4 pass, 0 fail`), `npm run typecheck` (`exit 0`), `npm run build` (`exit 0`), `npm audit --audit-level=moderate` (`0 vulnerabilities`).
- **Kiểm thử chưa chạy:** Kiểm thử tranh chấp khóa `EXCLUDE USING gist` trực tiếp trên máy chủ PostgreSQL 16 sống (`scripts/verify_postgres_live.py`) và pentest độc lập bên ngoài.

### Architecture & Decisions
- Ban hành [ADR-018](../adr/ADR-018-terminology-specialty-templates-lab-billing-offline-sync-and-scheduling-ai.md): từ điển thuật ngữ y khoa phân phiên bản cấm đoán mã (`EMR-016`), mẫu kế hoạch chuyên khoa bắt buộc bác sĩ phòng khám duyệt (`TRT-015`), đối soát bảng giá & hóa đơn lab không lộ PHI (`LAB-010`), lớp phủ hình ảnh theo dõi dọc gắn nhãn phi chẩn đoán (`ODN-009`), xuất báo cáo KPI mã hóa `DLY1` không chứa PHI (`RPT-009`/`RPT-010`), phê duyệt phát hành canary 2 người (`OPS-009`), phân quyền vận hành đa chi nhánh không làm lộ bệnh án (`OPS-011`), đồng bộ ngoại tuyến cấm `last-write-wins` (`OPS-013`), cùng dự báo nguy cơ vắng mặt công bằng và bộ giải CP-SAT an toàn khi timeout (`AI-007`/`AI-008`).

### Git Status
- Nhánh `main`, chuẩn bị commit với tiền tố `[T025][T026]` và push fast-forward lên `origin/main` (xem `git log -1` để lấy mã băm chính thức của commit chứa tệp báo cáo này).

### Project Progress
- Hoàn tất `T000`–`T026` (`ADR-006`..`ADR-018`), đạt `198/222` mã `D` (toàn bộ `24` mã `—` còn lại đều là cổng tích hợp nhà cung cấp bên ngoài/hạ tầng đám mây hoặc cổng phê duyệt pháp lý/lâm sàng).

### Next Steps
1. **`T027` (`CRM-012`, `OPS-008`, `ORG-010`, `INT-006`, `INT-007`, `INT-008`, `INT-009`):** Chính sách phục hồi ca hủy tự động có kiểm soát của phòng khám, bộ đo hiệu năng/độ trễ cục bộ có thể tái lập không bịa SLA, cùng các adapter kiểm thử hợp đồng fail-closed cho OIDC group sync, webhook thanh toán chống phát lại, trạng thái gửi/từ chối nhận tin nhắn và phong bì hóa đơn/chữ ký số.
2. **Cổng hạ tầng PostgreSQL 16 (`T002`):** Thực thi `scripts/verify_postgres_live.py` trên máy chủ PostgreSQL 16 sống hoặc thu biên nhận từ CI `postgres-concurrency-tests`.
3. **Cổng phê duyệt lâm sàng, pháp lý & bảo mật (`M0` / `T003` / `T004` / `T010` / `SEC-G1`):** Hoàn tất ký duyệt của bác sĩ nha khoa, cố vấn pháp lý và kiểm định bảo mật độc lập trước khi xử lý dữ liệu thật.
