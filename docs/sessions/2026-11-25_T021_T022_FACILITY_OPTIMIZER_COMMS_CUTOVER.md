# Báo cáo Phiên Làm việc — 2026-11-25 (`T021` + `T022`)

### Session Summary
- **Task ID / Phạm vi:** Triển khai hoàn chỉnh hai gói nhiệm vụ `T021` (`ORG-001`, `SCH-011`, `SCH-012`, `FIN-013`, `HR-001`, `HR-010`) và `T022` (`CRM-002`, `CRM-011`, `AI-006`, `INT-012`, `MIG-009`, `MIG-010`) theo quy trình viết kiểm thử âm tính trước (negative-first TDD), ban hành `ADR-016`, mở rộng chuỗi migration tiến-lên-duy-nhất lên `0011_facility_optimizer_receipts_comms_and_cutover` (`97` bảng miền, `234` HTTP operations trên `187` đường dẫn) và nâng danh mục tính năng demo lên `176/222` mã `D`.
- **Tệp tạo mới / cập nhật:**
  - `backend/src/denlyra/facility_optimizer_receipts_hr.py`, `backend/src/denlyra/comms_satisfaction_cutover.py`, `backend/alembic/versions/0011_facility_optimizer_receipts_comms_and_cutover.py`
  - `backend/src/denlyra/models.py`, `backend/src/denlyra/schemas.py`, `backend/src/denlyra/api.py`
  - `backend/tests/test_facility_optimizer_receipts_hr.py`, `backend/tests/test_comms_satisfaction_cutover.py`, `backend/tests/test_scheduling_concurrency.py`
  - `scripts/smoke_baseline.py`, `scripts/generate_openapi_ts.py`, `scripts/generate_function_catalog.py`
  - `apps/clinic-web/src/lib/generated-api.ts`, `apps/clinic-web/src/app/page.tsx`, `apps/clinic-web/tests/frontend_contracts_and_a11y.test.mjs`
  - `docs/tasks/T021_FACILITY_LICENSING_OPTIMIZER_AND_RECEIPTS.md`, `docs/tasks/T022_REVIEWED_COMMS_SATISFACTION_AND_CUTOVER.md`, `docs/adr/ADR-016-facility-licensing-optimizer-receipts-comms-and-cutover.md`, `docs/product/FUNCTION_CATALOG.md`, `docs/engineering/API_CONTRACT.md`, `docs/architecture/DATABASE.md`, `docs/engineering/IMPLEMENTATION_STATUS.md`, `docs/engineering/ROADMAP.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`, `MANIFEST_SHA256.txt`

### Verification
- `pytest backend/tests -q`: **`85 passed, 1 skipped`** (bài skip yêu cầu biến môi trường `DENLYRA_TEST_POSTGRES_URL`).
- `ruff check` (backend + alembic + scripts), `compileall`, `node --check apps/demo-web/app.js`: **PASS (`exit 0`)**.
- `verify_artifact.py`: **PASS** (`222` mã danh mục, `176` cờ `D`, giữ nguyên toàn bộ cờ an toàn `False` và đường dẫn liên kết).
- `smoke_baseline.py`: **PASS** (`97` bảng miền tại head `0011_facility_optimizer_receipts_comms_and_cutover`; `234` HTTP operations).
- `run_dr_restore_drill.py`, `run_ai_eval_harness.py` (`8/8`), `verify_audit_chain.py`, `generate_openapi_ts.py --check`, `alembic upgrade head --sql` (PostgreSQL offline DDL): **PASS (`exit 0`)**.
- `apps/clinic-web`: `npm test` (`4 pass, 0 fail`), `npm run typecheck` (`exit 0`), `npm run build` (`exit 0`), `npm audit --audit-level=moderate` (`0 vulnerabilities`).
- **Kiểm thử chưa chạy:** Kiểm thử tranh chấp khóa `EXCLUDE USING gist` trực tiếp trên máy chủ PostgreSQL 16 sống (`scripts/verify_postgres_live.py`) và kiểm thử thâm nhập độc lập bên ngoài.

### Architecture & Decisions
- Ban hành [ADR-016](../adr/ADR-016-facility-licensing-optimizer-receipts-comms-and-cutover.md): tách biệt siêu dữ liệu phạm vi giấy phép khỏi tên hiển thị (`ORG-001`), bộ tối ưu hóa lịch hẹn chỉ đề xuất không tự dời ca đã xác nhận (`SCH-012`), phiếu xác nhận thu tiền gắn mã băm/HMAC chặn mạo danh sao kê ngân hàng (`FIN-013`), chấm công/tăng ca theo múi giờ `Asia/Ho_Chi_Minh` độc lập quyền ký lâm sàng (`HR-001`/`HR-010`), bản nháp truyền thông kiểm soát khung giờ/đồng ý/tường lửa injection (`CRM-002`/`AI-006`), khảo sát hài lòng ẩn danh tách bảng token (`CRM-011`) và kiểm định mã băm + khóa ghi hệ thống cũ trước cutover (`INT-012`/`MIG-009`/`MIG-010`).
- **Không thay đổi diễn giải pháp lý/lâm sàng:** Hệ thống tiếp tục là bản trình diễn nghiên cứu dữ liệu giả lập; cổng ký số hợp pháp và biểu mẫu Bộ Y tế vẫn khóa tại [NEEDS_CLINICAL_REVIEW.md](../clinical/NEEDS_CLINICAL_REVIEW.md).

### Git Status
- Nhánh `main`, chuẩn bị commit với tiền tố `[T021][T022]` và push fast-forward lên `origin/main` (xem `git log -1` để lấy mã băm chính thức của commit chứa tệp báo cáo này).

### Project Progress
- Hoàn tất `T000`–`T022` (`ADR-006`..`ADR-016`), đạt `176/222` mã `D`.
- Điểm nghẽn bên ngoài giữ nguyên: biên nhận chạy PostgreSQL 16 sống (`T002`) và chữ ký phê duyệt của bác sĩ nha khoa + cố vấn pháp lý (`M0`/`T003`/`T004`/`T010`).

### Next Steps
1. **`T023` (`OPS-005`, `OPS-010`, `OPS-012`, `SEC-012`, `SEC-013`):** Bộ lọc ẩn danh log/telemetry không chứa PHI, quy trình cấu hình onboarding tách biệt theo từng phòng khám, trích xuất chẩn đoán hỗ trợ kỹ thuật có đồng ý của chủ phòng khám, quy trình ứng phó sự cố bảo mật và kiểm chứng toàn vẹn SBOM/lockfile.
2. **`T024` (`PAT-011`, `SCH-014`, `PORT-008`, `PORT-010`, `HR-007`, `HR-009`):** Quy trình yêu cầu trích xuất dữ liệu của bệnh nhân tuân thủ thời hạn lưu trữ, gợi ý lấp lịch trống do hủy hẹn tôn trọng đồng ý liên hệ, kiểm dịch tệp tải lên & tin nhắn hỗ trợ trên cổng bệnh nhân không tự tư vấn y khoa, cùng kiểm soát chứng chỉ đào tạo và đối soát lương/hoa hồng tách biệt lâm sàng – tài chính.
3. **Cổng hạ tầng & pháp lý (`T002` & `M0`):** Chạy `verify_postgres_live.py` trên PostgreSQL 16 và hoàn tất phê duyệt [NEEDS_CLINICAL_REVIEW.md](../clinical/NEEDS_CLINICAL_REVIEW.md).
