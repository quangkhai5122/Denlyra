# T005, T004 (Synthetic Slice) & T002 PostgreSQL Verifier/CI — Session Report (2026-11-18)

### Session Summary
- **Task ID / Phạm vi:** `T005` (`docs/tasks/T005_TREATMENT_E2E.md`), `T004` synthetic adapter slice (`docs/tasks/T004_SIGNATURE_DOCUMENTS.md`), và bộ công cụ + CI job kiểm chứng PostgreSQL cho `T002` (`scripts/verify_postgres_live.py`, `.github/workflows/ci.yml`).
- **Mục tiêu phiên làm việc:**
  1. Triển khai trọn vẹn vertical slice `T005` cho hành trình điều trị nhiều giai đoạn: đồ thị DAG đa phụ thuộc có phát hiện chu trình DFS, gắn vai trò phụ trách (`owner_role`) và hạn hoàn thành (`due_at`), liên kết lịch hẹn / ca labo (`requires_verified_lab`) / khoản thu qua `treatment_coordination_link` + `outbox_event`, dời lịch nguyên tử giữ lịch sử (`SCH-005`), hoàn tiền append-only có kiểm tra giới hạn số dư chưa phân bổ (`FIN-006`, `OPS-03`), sự kiện tái đánh giá tạo task mới có truy vết (`PLAN-04`), và timeline phân tách trạng thái lâm sàng với tài chính.
  2. Triển khai `T004` synthetic adapter slice: giao diện `SignatureProvider` + `FakeSyntheticSignatureProvider` (`backend/src/denlyra/signing.py`), đóng gói `ClinicalDocumentSnapshot` bất biến (`canonical_json`, `canonical_sha256`, `manifest_sha256`), luồng tạo `addenda` và `entered_in_error` bắt buộc lý do mà không sửa đổi byte gốc, kiểm thử đầy đủ các kịch bản lỗi `NEG-03`, `NEG-14`, `NEG-15`, và chặn đóng (`409`) chế độ ký pháp lý thật `legal_authenticated` theo `NEEDS_CLINICAL_REVIEW.md`.
  3. Bổ sung script kiểm chứng trực tiếp PostgreSQL 16 (`scripts/verify_postgres_live.py`) và job `postgres-concurrency-tests` dùng service container `postgres:16` trong `.github/workflows/ci.yml` cho `T002`.
- **Các file thêm mới / cập nhật:**
  - Thêm mới: `backend/src/denlyra/signing.py`, `backend/alembic/versions/0003_treatment_and_signing.py`, `backend/tests/test_treatment_journey_e2e.py`, `backend/tests/test_signature_documents.py`, `scripts/verify_postgres_live.py`, `docs/adr/ADR-008-treatment-journey-and-signature-envelope.md`, `docs/sessions/2026-11-18_T004_T005_TREATMENT_AND_SIGNING.md`.
  - Cập nhật: `backend/src/denlyra/{auth.py,models.py,schemas.py,services.py,api.py}`, `.github/workflows/ci.yml`, `scripts/{smoke_baseline.py,generate_function_catalog.py}`, `backend/tests/test_scheduling_concurrency.py`, `docs/tasks/{T002_POSTGRES_BOOKING.md,T004_SIGNATURE_DOCUMENTS.md,T005_TREATMENT_E2E.md}`, `docs/engineering/{API_CONTRACT.md,IMPLEMENTATION_STATUS.md,ROADMAP.md}`, `docs/architecture/{DATABASE.md,DOMAIN_MODEL.md}`, `docs/product/FUNCTION_CATALOG.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`, `MANIFEST_SHA256.txt`.

### Verification
- **Negative-Tests-First:** Đã chạy `pytest backend/tests/test_treatment_journey_e2e.py backend/tests/test_signature_documents.py -q` trước khi cài đặt logic nghiệp vụ và xác nhận cả 3 suite đều fail (`FFF`).
- **Kết quả sau triển khai (từ repository root, Windows `.venv` CPython 3.12.14, Node 24.11.1):**
  - `./.venv/Scripts/python.exe -m pytest backend/tests -q` → **PASS:** `43 passed, 1 skipped, 1 warning`.
  - `./.venv/Scripts/python.exe -m ruff check backend/src backend/tests` → **PASS:** `All checks passed!`.
  - `./.venv/Scripts/python.exe -m ruff check --config backend/pyproject.toml scripts/smoke_baseline.py scripts/update_manifest.py scripts/verify_artifact.py scripts/verify_postgres_live.py` → **PASS:** `All checks passed!`.
  - `./.venv/Scripts/python.exe -m compileall -q backend/src` → **PASS:** Exit 0.
  - `node --check apps/demo-web/app.js` → **PASS:** Exit 0.
  - `./.venv/Scripts/python.exe scripts/generate_function_catalog.py` → **PASS:** `222 functions / 18 domains / 47 demo flags`.
  - `./.venv/Scripts/python.exe scripts/verify_artifact.py` → **PASS:** `Artifact guard PASS: 222 catalog IDs, 20 mandatory files, safety flags, links`.
  - `./.venv/Scripts/python.exe scripts/smoke_baseline.py` → **PASS:** `SQLite Alembic smoke PASS: 29 domain tables; head 0003_treatment_and_signing` + `CLI/HTTP smoke PASS: opt-in refusal; loopback; Denlyra UI/header/OpenAPI; 60 operations`.
  - Tại `backend/`: `../.venv/Scripts/python.exe -m alembic upgrade head --sql` → **PASS:** Sinh thành công SQL tĩnh PostgreSQL qua 3 bước `0001_demo` → `0002_hardening` → `0003_treatment_and_signing`.
  - Tại `apps/clinic-web/`: `npm run typecheck` & `npm run build` → **PASS:** Exit 0.
  - `./.venv/Scripts/python.exe scripts/update_manifest.py --check` → **PASS**.
- **Chưa kiểm chứng trên máy cục bộ:**
  - `scripts/verify_postgres_live.py` đã sẵn sàng và được cấu hình tự động trong GitHub Actions (`postgres-concurrency-tests`), nhưng chưa chạy trên máy local vì host Windows hiện tại không cài Docker/PostgreSQL.
  - Chưa có phê duyệt lâm sàng/pháp lý thật cho biểu mẫu `16/BV-01`, mẫu quy trình chuyên khoa và nhà cung cấp chữ ký số (`NEEDS_CLINICAL_REVIEW.md`).

### Architecture & Decisions
- **ADR-008 (`docs/adr/ADR-008-treatment-journey-and-signature-envelope.md`):** Chốt mô hình DAG nhiều phụ thuộc (`plan_task_dependency`), hợp đồng phối hợp liên ngữ cảnh (`treatment_coordination_link` + `outbox_event`), hoàn tiền bất biến (`payment_refund`), tái đánh giá sinh phiên bản mới giữ lịch sử (`plan_reassessment`), và phong bì tài liệu chuẩn hóa `ClinicalDocumentSnapshot` dùng `FakeSyntheticSignatureProvider`.

### Git Status
- **Branch:** `main`
- **Commit & Push:** Xem commit subject gắn nhãn `[T004][T005][T002]` trong `git log -1 --format=fuller` và đối chiếu `origin/main` qua `git ls-remote origin refs/heads/main`.

### Project Progress
- **Completed (Synthetic Foundation Slices):** `T000`, `T001`, `T005`, và phần synthetic adapter của `T004` + `FormRegistry` cách ly của `T003` + migration/concurrency/CI harness của `T002`.
- **Catalog:** `47 / 222` cờ demo một phần (`D`), `175 / 222` chưa triển khai (`—`).
- **Next Recommended Tasks:** `T007` (`docs/tasks/T007_LAB_CONSENT.md`), `T008` (`docs/tasks/T008_FINANCE_LEDGER.md`), và `T006` (`docs/tasks/T006_PAPER_IMPORT.md` synthetic quarantine slice).

### Next Steps
1. **P1 — `T007` (`docs/tasks/T007_LAB_CONSENT.md`):** Triển khai hồ sơ đồng thuận tách biệt theo mục đích (`treatment`, `data_processing`, `marketing`, `financial` — thu hồi marketing không xóa bệnh án), phiếu chỉ định labo có phạm vi dữ liệu tối thiểu, cảnh báo trễ hạn labo, và token/link truy cập giới hạn theo ca cho đối tác labo (kiểm thử hết hạn, sai phòng khám, giao hàng vs. nghiệm thu lâm sàng).
2. **P1 — `T008` (`docs/tasks/T008_FINANCE_LEDGER.md`):** Nâng cấp phân bổ/hoàn tiền thành sổ cái bất biến hoàn chỉnh có `idempotency_key` cho thu tiền/phân bổ/hoàn tiền, bảng giá & phiên bản báo giá (`estimate_version`), đối soát ca thu ngân hàng ngày và báo cáo tách bạch `billed / collected / refunded / planned`.
3. **P1 — `T006` (`docs/tasks/T006_PAPER_IMPORT.md` — Synthetic Quarantine Importer):** Triển khai pipeline cách ly hồ sơ giấy giả lập (`MigrationBatch`, `MigrationItem`, kiểm tra đủ trang `DR-01`, hàng đợi nghi trùng bệnh nhân `PAT-005`/`DR-02`, bảo toàn nhãn nguồn `legacy_scan` không bao giờ gắn nhãn đã ký số `DR-03`, và rollback theo lô).
