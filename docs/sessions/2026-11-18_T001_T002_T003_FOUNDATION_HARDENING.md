# T001, T002 & T003 — Identity Hardening, Booking Concurrency & Quarantined FormRegistry (2026-11-18)

### Session Summary
- **Task ID / Phạm vi:** `T001` (`docs/tasks/T001_HARDEN_IDENTITY.md`), `T002` (`docs/tasks/T002_POSTGRES_BOOKING.md`), và `T003` (`docs/tasks/T003_FORM_MAPPING.md` + `docs/clinical/NEEDS_CLINICAL_REVIEW.md`).
- **Mục tiêu phiên làm việc:**
  1. Triển khai nền tảng xác thực token/session giả lập có kiểm chứng chữ ký HMAC-SHA256, kiểm tra trạng thái nhân sự đang hoạt động trên DB, phân quyền RBAC/ABAC deny-by-default, thu hồi phiên (`jti`) và vô hiệu hóa tức thì khi ngừng kích hoạt nhân sự, cấp phát signed URL một lần theo phạm vi phòng khám, và ghi nhận nhật ký truy cập dữ liệu lâm sàng nhạy cảm (`T001` / `ADR-007`).
  2. Thay thế `Base.metadata.create_all` động trong migration `0001_demo` bằng DDL tường minh cố định (`R-010`), bổ sung migration `0002_hardening`, hỗ trợ đặt lịch nguyên tử nhiều tài nguyên (`dentist` + `chair` + `device`), hỗ trợ `idempotency_key`, bắt `IntegrityError` -> rollback toàn phần -> trả HTTP `409`, thêm SQLite trigger chống trùng lịch ở tầng DB cục bộ và bộ kiểm thử 2 kết nối đồng thời có `threading.Barrier(2)` (`T002`).
  3. Lập hồ sơ cổng rà soát chuyên môn/pháp lý `docs/clinical/NEEDS_CLINICAL_REVIEW.md` và triển khai `FormRegistry` giả lập an toàn ở trạng thái cách ly (`quarantined_synthetic_draft`), bảo toàn phiên bản biểu mẫu bất biến (`NEG-16`), thực thi ngữ nghĩa 3 trạng thái `present` / `explicit_negative` / `unknown` / `missing` (`INV-022`), và chặn đóng (`409`) mọi yêu cầu tự phê duyệt biểu mẫu hoặc xuất bệnh án chính thức (`T003`).
  4. Khắc phục triệt để lỗi xung đột quyền truy cập thư mục tạm/cache của `pytest` khi chuyển đổi giữa các công cụ/sandbox Agent khác nhau trên Windows (`backend/tests/conftest.py`, `backend/pyproject.toml`).
- **Các file hoặc module đã thay đổi / thêm mới:**
  - Backend: `backend/src/denlyra/auth.py` (mới), `backend/src/denlyra/config.py`, `backend/src/denlyra/models.py`, `backend/src/denlyra/db.py`, `backend/src/denlyra/schemas.py`, `backend/src/denlyra/services.py`, `backend/src/denlyra/api.py`, `backend/pyproject.toml`.
  - Migrations: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_demo_schema.py`, `backend/alembic/versions/0002_hardening.py` (mới).
  - Frontend proxy: `apps/clinic-web/src/app/api/demo/[...path]/route.ts` (chuyển tiếp `Authorization`, `Origin`, `Sec-Fetch-Site` để xử lý `R-009`).
  - Tests: `backend/tests/conftest.py`, `backend/tests/test_identity_auth.py` (mới), `backend/tests/test_scheduling_concurrency.py` (mới), `backend/tests/test_form_registry.py` (mới).
  - Scripts & Catalog: `scripts/smoke_baseline.py`, `scripts/generate_function_catalog.py`, `docs/product/FUNCTION_CATALOG.md`, `MANIFEST_SHA256.txt`.
  - Tài liệu & ADR: `docs/adr/ADR-007-identity-and-authorization.md` (mới), `docs/clinical/NEEDS_CLINICAL_REVIEW.md` (mới), `docs/tasks/T001_HARDEN_IDENTITY.md`, `docs/tasks/T002_POSTGRES_BOOKING.md`, `docs/tasks/T003_FORM_MAPPING.md`, `docs/engineering/API_CONTRACT.md`, `docs/architecture/DOMAIN_MODEL.md`, `docs/architecture/DATABASE.md`, `docs/engineering/ROADMAP.md`, `docs/engineering/IMPLEMENTATION_STATUS.md`, `docs/PROJECT_STATE.md`, `AGENTS.md`.

### Verification
- Viết negative tests trước khi sửa mã nguồn nghiệp vụ:
  - Khi chạy `pytest` trước khi cập nhật `services.py` / `db.py` / `api.py`, các bài kiểm thử mới đều fail đúng kỳ vọng, đặc biệt `test_two_connection_barrier_concurrent_booking_race` đã tái hiện trực tiếp lỗi race condition `[201, 201]` trên mã nguồn cũ.
- Kết quả sau khi triển khai (chạy từ repository root trên Windows, `.venv` CPython 3.12.14, Node 24.11.1):
  - `./.venv/Scripts/python.exe -m pytest backend/tests -q` → **PASS:** `40 passed, 1 skipped, 1 warning` (không cần truyền cờ `--basetemp` thủ công nhờ cơ chế thư mục tạm theo phiên trong `conftest.py`). Bài skip duy nhất là `test_live_postgresql_exclusion_constraint_and_race` khi biến môi trường `DENLYRA_TEST_POSTGRES_URL` chưa được cấu hình.
  - `./.venv/Scripts/python.exe -m ruff check backend/src backend/tests` → **PASS:** `All checks passed!`.
  - `./.venv/Scripts/python.exe -m ruff check --config backend/pyproject.toml scripts/smoke_baseline.py scripts/update_manifest.py scripts/verify_artifact.py` → **PASS:** `All checks passed!`.
  - `./.venv/Scripts/python.exe -m compileall -q backend/src` → **PASS:** Exit 0.
  - `node --check apps/demo-web/app.js` → **PASS:** Exit 0.
  - `./.venv/Scripts/python.exe scripts/generate_function_catalog.py` → **PASS:** `Generated 222 functions across 18 domains; demo flags 33`.
  - `./.venv/Scripts/python.exe scripts/verify_artifact.py` → **PASS:** `Artifact guard PASS: 222 catalog IDs, 20 mandatory files, safety flags, links`.
  - `./.venv/Scripts/python.exe scripts/smoke_baseline.py` → **PASS:** `SQLite Alembic smoke PASS: 23 domain tables; head 0002_hardening` + `CLI/HTTP smoke PASS: opt-in refusal; loopback; Denlyra UI/header/OpenAPI; 48 operations`.
  - Tại `backend/`: `../.venv/Scripts/python.exe -m alembic upgrade head --sql` → **PASS:** Sinh thành công SQL tĩnh cho cả `0001_demo` và `0002_hardening` (có `CREATE EXTENSION IF NOT EXISTS btree_gist` và `no_overlapping_active_resource_booking`).
  - Tại `apps/clinic-web/`: `npm run typecheck` và `npm run build` (`NEXT_TELEMETRY_DISABLED=1`) → **PASS:** Exit 0.
  - `./.venv/Scripts/python.exe scripts/update_manifest.py --check` → **PASS**.
- **Chưa kiểm chứng:**
  - Chưa chạy `test_live_postgresql_exclusion_constraint_and_race` trên PostgreSQL 16 thật vì máy hiện tại không có Docker/PostgreSQL server.
  - Chưa có đánh giá bảo mật độc lập (`SEC-G1`), chưa có phê duyệt của bác sĩ Răng Hàm Mặt và cố vấn pháp lý cho biểu mẫu `16/BV-01` (`CLIN-G1`, `CLIN-G2`).

### Architecture & Decisions
- **ADR-007 (`docs/adr/ADR-007-identity-and-authorization.md`):** Chốt kiến trúc xác thực OIDC mục tiêu (Keycloak/managed OIDC có MFA) kết hợp bộ kiểm tra chính sách RBAC+ABAC tại backend và `SyntheticIdentityIssuer` cục bộ cho kiểm thử tự động. Giữ `"production_auth": False` trên `/api/v1/capabilities` để không tuyên bố sai về độ sẵn sàng sản xuất trước khi qua cổng `SEC-G1`.
- **Chiến lược Migration (`R-010`):** Đóng băng DDL của `0001_demo` (18 bảng gốc) thay vì gọi `Base.metadata.create_all(bind=bind)`, và tách các thay đổi của `T001`/`T002`/`T003` sang `0002_hardening` kèm bảng `schema_migration_meta`. Đã kiểm thử cả nâng cấp từ DB rỗng và nâng cấp từ DB `0001_demo` có sẵn dữ liệu.
- **Cổng an toàn lâm sàng (`T003`):** Tuân thủ nghiêm ngặt quy tắc `AGENTS.md`: tạo `docs/clinical/NEEDS_CLINICAL_REVIEW.md` và chỉ triển khai `FormRegistry` ở trạng thái cách ly `quarantined_synthetic_draft`, chặn mọi hành vi tự phê duyệt hoặc xuất bệnh án hợp pháp (`409 Conflict`).

### Git Status
- **Branch:** `main`
- **Commit & Push:** Xem commit subject gắn nhãn `[T001][T002][T003]` trong `git log -1 --format=fuller` và trạng thái đồng bộ `origin/main` qua `git status --short --branch` / `git ls-remote origin refs/heads/main`.

### Project Progress
- **Milestone hiện tại:** Đã hoàn tất `R0` và phần nền tảng mã nguồn của `T001`, phần migration/race harness của `T002`, và khung `FormRegistry` cách ly của `T003`.
- **Completed Tasks:**
  - `T000` — Repository onboarding & baseline.
  - `T001` — Synthetic authentication, RBAC/ABAC deny-by-default, membership deactivation invalidation, token revocation, and single-use signed URL foundation (`ADR-007`).
- **In-Progress / Blocked Tasks:**
  - `T002` — Đã hoàn tất mã nguồn, chuỗi migration `0001_demo` -> `0002_hardening`, đặt lịch đa tài nguyên nguyên tử, `IntegrityError` -> `409` rollback, `idempotency_key` và bài kiểm thử 2 kết nối đồng thời; **chờ PostgreSQL server thật (`DENLYRA_TEST_POSTGRES_URL`) để đóng nghiệm thu cuối**.
  - `T003` — Đã hoàn tất khung `FormRegistry` cách ly và kiểm thử ngữ nghĩa `INV-022`; **bị chặn kích hoạt lâm sàng cho tới khi bác sĩ và cố vấn pháp lý phê duyệt `docs/clinical/NEEDS_CLINICAL_REVIEW.md`**.
  - `T004` — Bị chặn cho phần chữ ký pháp lý thật bởi `T003`, nhưng có thể triển khai giao diện `SignatureProvider` giả lập (fake test double) + trạng thái tài liệu/addendum bất biến.
- **Pending Backlog:** `T004` (safe synthetic adapter), `T005`, `T006`, `T007`, `T008`, `T009`, `T010`.

### Next Steps
1. **P0 — `T005` (`docs/tasks/T005_TREATMENT_E2E.md`):** Mở rộng đồ thị kế hoạch điều trị nhiều giai đoạn (multi-dependency DAG, phát hiện chu trình, sự kiện tái đánh giá/lặp giai đoạn tạo task instance mới thay vì ghi đè lịch sử, liên kết lịch hẹn/labo/tài chính qua hợp đồng sự kiện không ghi trực tiếp bảng miền khác).
   - **Điều kiện bắt đầu:** `T001` đã hoàn tất; có thể bắt đầu ngay với dữ liệu tổng hợp.
2. **P0 — `T004` (`docs/tasks/T004_SIGNATURE_DOCUMENTS.md` — Synthetic Adapter Slice):** Triển khai giao diện `SignatureProvider` với fake test double, canonical snapshot hash + manifest và kiểm thử âm tính (nội dung bị sửa đổi, người ký bị thu hồi quyền, provider timeout -> giữ nguyên trạng thái chưa xác thực `NEG-03`, `NEG-14`) trong khi vẫn chặn chữ ký pháp lý thật theo `NEEDS_CLINICAL_REVIEW.md`.
   - **Điều kiện bắt đầu:** Có thể thực hiện ngay trên nền `T001` và `T003`.
3. **P0 — Nghiệm thu PostgreSQL trực tiếp cho `T002`:** Khi có môi trường Docker hoặc PostgreSQL 16 cục bộ, cài đặt `psycopg[binary]` và chạy `DENLYRA_TEST_POSTGRES_URL=postgresql+psycopg://... ./.venv/Scripts/python.exe -m pytest backend/tests/test_scheduling_concurrency.py -q` để đóng hoàn toàn `T002`.
