# T007, T008 & T006 — Consent/Lab Portal, Idempotent Finance Ledger & Paper Quarantine Importer (2026-11-18)

### Session Summary
- **Task ID / Phạm vi:** `T007` (`docs/tasks/T007_LAB_CONSENT.md`), `T008` (`docs/tasks/T008_FINANCE_LEDGER.md`), và lát cắt cách ly dữ liệu tổng hợp `T006` (`docs/tasks/T006_PAPER_IMPORT.md`).
- **Mục tiêu phiên làm việc:**
  1. Triển khai phân loại đồng thuận tách biệt theo mục đích (`ConsentRecord`: `treatment`, `data_processing`, `marketing`, `financial`), xác minh thẩm quyền người giám hộ (`PAT-004`), thu hồi `marketing` không ảnh hưởng hồ sơ lâm sàng (`SEC-07`), cùng cổng đối tác labo giới hạn theo từng ca (`LabPartnerGrant` tối thiểu hóa dữ liệu không lộ tên/SĐT bệnh nhân, chặn `verified` `403`, từ chối link hết hạn/chéo phòng khám), biên bản giao nhận vs kiểm định, quy trình làm lại (`remakes`), và cảnh báo trễ hạn labo (`lab_due_after_appointment`) không tự đổi lịch hẹn (`T007`).
  2. Triển khai sổ cái doanh thu bất biến (`LedgerEntry`), báo giá có phiên bản bất biến (`EstimateVersion`), chống trùng lặp `idempotency_key` trên toàn bộ thao tác thu/phân bổ/hoàn tiền (`NEG-08`, `NEG-17`), trigger DB + khóa đồng thời cho phân bổ thanh toán (`tr_payment_allocation_bounds`), và đối soát thu ngân cuối ngày theo từng phương thức thanh toán (`CashierReconciliation`, `FIN-010`) (`T008`).
  3. Triển khai pipeline cách ly hồ sơ giấy cũ (`MigrationBatch`, `MigrationItem`), kiểm tra đủ trang & độ rõ (`NEG-10`, `DR-01`), phát hiện nghi trùng tên/SĐT bắt buộc người dùng duyệt (`PAT-005`, `DR-02`), bảo toàn nguồn gốc `legacy_scan` không bao giờ giả mạo chữ ký số (`DR-03`), báo cáo đối soát lô và rollback an toàn (`MIG-008`) (`T006`).
- **Các file thêm mới / cập nhật:**
  - Thêm mới: `backend/alembic/versions/0004_lab_consent_finance_and_migration.py`, `backend/tests/test_lab_consent_portal.py`, `backend/tests/test_finance_ledger.py`, `backend/tests/test_paper_import_quarantine.py`, `docs/adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md`, `docs/sessions/2026-11-18_T006_T007_T008_LAB_FINANCE_MIGRATION.md`.
  - Cập nhật: `backend/src/denlyra/{auth.py,db.py,models.py,schemas.py,services.py,api.py}`, `scripts/{smoke_baseline.py,generate_function_catalog.py}`, `backend/tests/test_scheduling_concurrency.py`, `docs/tasks/{T006_PAPER_IMPORT.md,T007_LAB_CONSENT.md,T008_FINANCE_LEDGER.md}`, `docs/engineering/{API_CONTRACT.md,IMPLEMENTATION_STATUS.md,ROADMAP.md}`, `docs/architecture/{DATABASE.md,DOMAIN_MODEL.md}`, `docs/product/FUNCTION_CATALOG.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`, `MANIFEST_SHA256.txt`.

### Verification
- **Negative-Tests-First:** Đã chạy `pytest backend/tests/test_lab_consent_portal.py backend/tests/test_finance_ledger.py backend/tests/test_paper_import_quarantine.py -q` trước khi cài đặt nghiệp vụ và xác nhận cả 5 test mới đều fail (`FFFFF`).
- **Kết quả sau triển khai (từ repository root, Windows `.venv` CPython 3.12.14, Node 24.11.1):**
  - `./.venv/Scripts/python.exe -m pytest backend/tests -q` → **PASS:** `48 passed, 1 skipped, 1 warning`.
  - `./.venv/Scripts/python.exe -m ruff check backend/src backend/tests` → **PASS:** `All checks passed!`.
  - `./.venv/Scripts/python.exe -m ruff check --config backend/pyproject.toml scripts/smoke_baseline.py scripts/update_manifest.py scripts/verify_artifact.py scripts/verify_postgres_live.py` → **PASS:** `All checks passed!`.
  - `./.venv/Scripts/python.exe -m compileall -q backend/src` → **PASS:** Exit 0.
  - `node --check apps/demo-web/app.js` → **PASS:** Exit 0.
  - `./.venv/Scripts/python.exe scripts/generate_function_catalog.py` → **PASS:** `222 functions / 18 domains / 72 demo flags`.
  - `./.venv/Scripts/python.exe scripts/verify_artifact.py` → **PASS:** `Artifact guard PASS: 222 catalog IDs, 20 mandatory files, safety flags, links`.
  - `./.venv/Scripts/python.exe scripts/smoke_baseline.py` → **PASS:** `SQLite Alembic smoke PASS: 36 domain tables; head 0004_lab_consent_finance_and_migration` + `CLI/HTTP smoke PASS: opt-in refusal; loopback; Denlyra UI/header/OpenAPI; 78 operations`.
  - Tại `backend/`: `../.venv/Scripts/python.exe -m alembic upgrade head --sql` → **PASS:** Sinh SQL tĩnh PostgreSQL qua đủ 4 bước `0001_demo` → `0004_lab_consent_finance_and_migration`.
  - Tại `apps/clinic-web/`: `npm run typecheck` & `npm run build` → **PASS:** Exit 0.
  - `./.venv/Scripts/python.exe scripts/update_manifest.py --check` → **PASS**.
- **Chưa kiểm chứng:**
  - Chạy PostgreSQL 16 trực tiếp (`DENLYRA_TEST_POSTGRES_URL`) cho `T002` và kiểm thử concurrent row-lock phân bổ tài chính trên PostgreSQL thật.
  - Chưa có phê duyệt chuyên môn/pháp lý thật (`NEEDS_CLINICAL_REVIEW.md`, `CLIN-G1/G2`, `SEC-G1`), chưa triển khai mã hóa lưu trữ/backup-restore (`T010`) và bộ workspace Next.js đầy đủ theo vai trò (`T009`).

### Architecture & Decisions
- **ADR-009 (`docs/adr/ADR-009-lab-consent-finance-ledger-and-paper-quarantine.md`):** Chuẩn hóa mô hình đồng thuận đa mục đích, token cổng labo không lộ PII bệnh nhân, sổ cái tài chính idempotent có trigger/row-lock giới hạn phân bổ, và pipeline cách ly hồ sơ giấy giữ nguyên nguồn gốc `legacy_scan`.

### Git Status
- **Branch:** `main`
- **Commit & Push:** Xem commit subject gắn nhãn `[T006][T007][T008]` trong `git log -1 --format=fuller` và đối chiếu `origin/main` qua `git ls-remote origin refs/heads/main`.

### Project Progress
- **Completed (Synthetic Foundation Slices):** `T000`, `T001`, `T005`, `T006`, `T007`, `T008`, và phần synthetic interface của `T003`/`T004` + CI/race harness của `T002`.
- **Catalog:** `72 / 222` cờ demo một phần (`D`), `150 / 222` chưa triển khai (`—`).
- **Remaining Core Engineering Tasks:** `T009` (Role-based React/Next.js frontend & Playwright E2E) và `T010` (Encrypted archive manifest & Disaster Recovery drill), cùng với việc nghiệm thu `T002` trên PostgreSQL thật và mở cổng `NEEDS_CLINICAL_REVIEW.md`.

### Next Steps
1. **P0 before PHI — `T010` (`docs/tasks/T010_BACKUP_RESTORE.md`):** Xây dựng mô hình manifest mã hóa/toàn vẹn cho DB + tài liệu ký số + hồ sơ giấy/ảnh + quản lý khóa (`TenantKeyPolicy`), kịch bản kiểm thử mất/hỏng file, sai khóa giải mã, backup lệch thời điểm DB (`NEG-13`, `DR-04`, `DR-05`), và diễn tập khôi phục tự động vào môi trường cô lập.
2. **P1 — `T009` (`docs/tasks/T009_REACT_FRONTEND.md`):** Sinh client TypeScript chuẩn hóa từ OpenAPI (`/openapi.json`), xây dựng workspace Next.js phân quyền theo vai trò (Lễ tân lịch hẹn 409, Bác sĩ sơ đồ răng FDI & ghi chú/báo giá, Điều phối viên timeline hành trình điều trị & cảnh báo labo, Thu ngân đối soát & sổ cái), xử lý timezone `Asia/Ho_Chi_Minh` nhất quán (`R-011`) và kiểm thử Playwright/accessibility.
3. **P0 — Nghiệm thu thực địa & Chuyên môn:** Theo dõi kết quả CI `postgres-concurrency-tests` trên GitHub Actions (hoặc chạy `scripts/verify_postgres_live.py` trên PostgreSQL local) để đóng `T002`, đồng thời hoàn tất ký duyệt biểu mẫu `16/BV-01` & chữ ký số với bác sĩ và cố vấn pháp lý theo `docs/clinical/NEEDS_CLINICAL_REVIEW.md`.
