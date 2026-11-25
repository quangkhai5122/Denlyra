# Báo cáo Phiên — 2026-11-25: Khởi chạy Trải nghiệm Trực tiếp & Kiểm thử E2E Giao diện/Ứng dụng (`T009` / `T010` / `T014` / `T025`)

### Session Summary
- **Task ID / Phạm vi:** Kiểm thử E2E trực tiếp trên trình duyệt toàn bộ giao diện ứng dụng cục bộ (`http://127.0.0.1:3000`, `http://127.0.0.1:8766`, `http://127.0.0.1:8766/api/docs`) và vá dứt điểm các lỗi đồng thời/tích hợp phát hiện trong vận hành thực tế (`T009`, `T010`, `T014`, `T025`).
- **Mục tiêu:** Khởi chạy song song hai máy chủ (`FastAPI` trên `127.0.0.1:8766` và `Next.js 15.5.29` trên `127.0.0.1:3000`) với dữ liệu giả lập sạch để người dùng trải nghiệm trực tiếp, đồng thời kiểm thử tự động E2E toàn bộ 5 phân hệ vai trò (`receptionist`, `dentist`, `treatment_coordinator`, `finance`, `clinic_owner`), các rào chắn xung đột `HTTP 409`, giao diện tĩnh `demo-web` và tài liệu `Swagger UI`.
- **Công việc hoàn thành:**
  1. Phát hiện và sửa dứt điểm lỗi đua ghi đồng thời (`race condition`) trên chuỗi băm kiểm toán `audit_event.chain_seq` khi giao diện React gọi song song `Promise.all` các API `audit_read=True` (`BEGIN IMMEDIATE` cho SQLite và `pg_advisory_xact_lock` theo `clinic_id` cho PostgreSQL).
  2. Sửa lỗi gọi hàm `compute_kpi_lineage_report` và đồng bộ khóa chủ `cfg.archive_master_secret` (thay vì `cfg.auth_secret`) khi xuất báo cáo KPI định kỳ mã hóa phong bì `DLY1` không chứa PHI (`RPT-010`).
  3. Bổ sung quyền đọc tiêu đề kế hoạch hành chính (`plan.read`) cho vai trò `finance` để lập báo giá bất biến mà không vi phạm ranh giới bảo mật bệnh án lâm sàng (`note.read`, `encounter.read`, `finding.read`, `odontogram.read`, `plan.review` vẫn bị chặn `403`).
  4. Bổ sung huy hiệu `Đã check-in` trực quan trên thẻ lịch ghế Lễ tân và nút `Ký niêm phong phụ lục` cho các snapshot phụ lục ở trạng thái `ready_for_signature`, giúp đóng lượt khám (`EMR-009`) mượt mà ngay cả sau khi lập phụ lục.
  5. Kiểm thử hồi quy E2E trực tiếp trên trình duyệt xác nhận **0 lỗi `HTTP 500` và 0 lỗi `HTTP 403` ngoài ý muốn** trên toàn bộ luồng nghiệp vụ.
- **Tệp thực tế đã thay đổi:**
  - `backend/src/denlyra/audit_chain.py`
  - `backend/src/denlyra/terminology_templates_lab_reports.py`
  - `backend/src/denlyra/api.py`
  - `backend/src/denlyra/auth.py`
  - `apps/clinic-web/src/app/page.tsx`
  - `backend/tests/test_audit_chain_and_pagination.py`
  - `backend/tests/test_terminology_templates_lab_reports.py`
  - `backend/tests/test_identity_auth.py`
  - `docs/PROJECT_STATE.md`
  - `MANIFEST_SHA256.txt`

### Verification
- `./.venv/Scripts/python.exe -m pytest -q` (cwd: repo root): **110 passed, 1 skipped** (bao gồm bài test mới bắn đồng thời 16 luồng `ThreadPoolExecutor(max_workers=8)` vào `/notes` & `/snapshots` + xác minh `verify-chain`, test tương thích khóa KEK giữa `archive` và `scheduled-exports`, và test RBAC `finance` `plan.read`).
- `./.venv/Scripts/python.exe -m ruff check backend/src backend/tests`: **All checks passed!**
- `./.venv/Scripts/python.exe scripts/verify_artifact.py`: **Artifact guard PASS** (`222` catalog IDs, `20` mandatory files, safety flags, links).
- `./.venv/Scripts/python.exe scripts/update_manifest.py --check`: **Manifest PASS** (`239` source files).
- `npm test && npm run typecheck && npm run build` (cwd: `apps/clinic-web`): **4/4 pass**, TypeScript `tsc --noEmit` exit `0`, Next.js `15.5.29` production build thành công.
- **Live Browser E2E Verification (`http://127.0.0.1:3000`, `http://127.0.0.1:8766`, `http://127.0.0.1:8766/api/docs`):** Đạt **100%** trên cả 5 không gian làm việc theo vai trò, xác nhận các hàng rào `HTTP 409` (trùng lịch ghế/bác sĩ, tường lửa Prompt Injection `AI-010`, xóa tệp đang giữ `LEGAL HOLD` `DR-08`), đóng lượt khám kèm phụ lục đã niêm phong (`EMR-009`), xuất báo cáo mã hóa `DLY1` không PHI (`RPT-010`), và kiểm chứng toàn vẹn chuỗi băm kiểm toán (`SEC-007`).
- **Kiểm thử tích hợp/bảo mật chưa chạy:** Kiểm thử thâm nhập độc lập bên ngoài (`SEC-G1`), OIDC/MFA thật, Cloud KMS/HSM thật và chữ ký số PKI/CA hợp pháp.

### Architecture & Decisions
- Tuân thủ đầy đủ `ADR-007`..`ADR-020`; không thay đổi diễn giải pháp lý/lâm sàng (`demo_locked` và `synthetic_signed_NOT_legal` vẫn hoàn toàn là mô phỏng kỹ thuật, tuyệt đối không có giá trị pháp lý).
- **Tác động mô hình dữ liệu & migration:** Không thay đổi schema hay chuỗi Alembic `0001_demo`..`0015_iac_insurance_lora_plan_attestation_and_channels`.
- **Phê duyệt con người bắt buộc trước vận hành thật:** Ký duyệt của Bác sĩ Răng Hàm Mặt có chứng chỉ hành nghề, Cố vấn pháp lý y tế Việt Nam và Kiểm định bảo mật độc lập (`SEC-G1`) trong `docs/clinical/NEEDS_CLINICAL_REVIEW.md` và `docs/operations/RETENTION_AND_DR_POLICY.md`.

### Git Status
- Nhánh `main`, đồng bộ cùng `origin/main` sau khi cập nhật manifest và đẩy commit vá lỗi kiểm thử E2E trực tiếp.

### Project Progress
- Đã hoàn tất và kiểm chứng toàn bộ nền tảng kỹ thuật giả lập `T000`–`T030` (`145` bảng, `327` HTTP operations, `216/222` cờ `D`, `110` bài kiểm thử tự động + kiểm thử E2E trực tiếp trên trình duyệt + kiểm thử đồng thời `postgres:16` trên GitHub Actions).
- `6` mục còn lại (`AI-013`, `INT-006`, `INT-010`, `SEC-003`, `SEC-005`, `SEC-009`) là các cổng pháp lý/chứng nhận bên ngoài không được phép giả lập.

### Next Steps
1. **P0 — Thẩm định Lâm sàng, Pháp lý & Bảo mật (`M0` / `T003` / `T004` / `T010` / `SEC-G1`):** Thu thập chữ ký phê duyệt chính thức của Bác sĩ RHM, Luật sư y tế Việt Nam và đơn vị Pentest độc lập cho `docs/clinical/NEEDS_CLINICAL_REVIEW.md` và `docs/operations/RETENTION_AND_DR_POLICY.md`.
2. **P1 — Thỏa thuận DPA & Kết nối Sandbox Nhà cung cấp (`Law 91/2025/QH15`):** Ký kết hợp đồng xử lý dữ liệu trước khi cấu hình OIDC/MFA, Cloud KMS, CA/PKI, Zalo OA/ZNS, SMS Brandname, cổng thanh toán hoặc máy chủ DICOM Orthanc.
