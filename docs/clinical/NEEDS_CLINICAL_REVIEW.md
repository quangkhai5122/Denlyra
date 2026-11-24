# Clinical & Legal Review Gate — Outpatient Dental EMR Forms (`T003` / `T004`)

Date: 2026-11-24 · Status: **BLOCKED ON NAMED HUMAN REVIEWERS** · Tasks affected: `T003`, `T004`, `T010`, `M0`, `M3`

> **Hard Safety Rule (`AGENTS.md`):** No AI Coding Agent may self-approve regulatory mappings, clinical form completeness, retention schedules, or electronic signature validity. Until a licensed Vietnamese dentist (Clinical Director) and qualified legal counsel sign off on the items below, `FormRegistry` templates remain locked in `quarantined_synthetic_draft` state and official EMR export/signing endpoints fail closed (`409 Conflict`).

## 1. Required authoritative source verification
1. **Circular 32/2023/TT-BYT (Appendix XXVIII):**
   - Obtain the official Ministry of Health PDF for Inpatient/RHM form **`13/BV-01`** and Outpatient RHM form **`16/BV-01`**.
   - Record the exact file `SHA256`, publication date, effective date, and page numbers.
2. **Circular 25/2026/TT-BYT (effective 15 Aug 2026):**
   - Diff all clauses amending Circular 32/2023 to confirm whether any administrative, clinical, or signature fields on `13/BV-01` or `16/BV-01` were modified.
3. **Circular 13/2025/TT-BYT & Provincial Sở Y tế guidance:**
   - Confirm each partner clinic's exact operating license classification (`phòng khám chuyên khoa Răng Hàm Mặt` vs. multi-specialty clinic vs. hospital department) and outpatient/day-care applicability.
4. **Circular 33/2025/TT-BYT (Record retention — `T010`):**
   - Confirm exact retention durations per dental record category and legal-hold rules upon patient export or clinic subscription termination. Technical enforcement (`ArchiveObject.retention_until`, `legal_hold`, and `409` physical deletion block) is implemented in conservative 20-year quarantine mode per [RETENTION_AND_DR_POLICY.md](../operations/RETENTION_AND_DR_POLICY.md) awaiting counsel sign-off.

## 2. Field-by-field clinical review checklist (`16/BV-01`)
For each section of `16/BV-01`, the named Clinical Director must confirm:
- **Section I — Hành chính (Administrative):** Required vs. conditional fields; pediatric guardian rules (`PAT-004`); handling of patients without national ID at initial intake.
- **Section II — Quản lý người bệnh (Patient management):** Outpatient visit start/end timestamp semantics (`occurred_at` vs. `recorded_at`), referral provenance.
- **Section III — Chẩn đoán (Diagnosis):** Primary vs. secondary diagnosis coding scheme (ICD-10 / Ministry code set version) and stage at which diagnosis is mandatory.
- **Section IV — Tình trạng ra viện / kết thúc đợt điều trị ngoại trú:** Required outcomes and follow-up instructions.
- **Section A — Bệnh án (Clinical history & examination):**
  - Lý do vào viện / đến khám (`reason_for_visit`)
  - Quá trình bệnh lý (`illness_history`)
  - Tiền sử bệnh bản thân & gia đình, dị ứng (`allergy_history` — must preserve `unknown` vs. `explicit_negative` vs. `present` per `INV-022`)
  - Khám toàn thân & Khám chuyên khoa Răng Hàm Mặt (FDI tooth/surface mapping rules, primary vs. permanent dentition)
  - Tóm tắt bệnh án, Tiên lượng, Hướng điều trị tiếp theo
- **Section B — Tổng kết bệnh án (Outpatient Episode Summary):**
  - Quá trình bệnh lý và diễn biến lâm sàng
  - Tóm tắt kết quả xét nghiệm / X-quang / CBCT có giá trị chẩn đoán
  - Phương pháp điều trị đã thực hiện (must derive from clinician-authored procedure events, never from payment/charge rows per `INV-013`)
  - Tình trạng người bệnh khi kết thúc điều trị và hướng điều trị tiếp theo
  - Bàn giao hồ sơ / chữ ký của Bác sĩ điều trị và Người có thẩm quyền của cơ sở khám bệnh, chữa bệnh.

## 3. Electronic signature and confirmation gate (`T004`)
- Identify lawful signature/confirmation mechanisms per signer role (`dentist`, `medical_director`, `patient/guardian`, `record_archivist`) under Law 15/2023/QH15, Law 20/2023/QH15 on Electronic Transactions, and Circular 13/2025/TT-BYT.
- Confirm canonical snapshot format (PDF/A + structured JSON/XML) and cryptographic verification evidence required for offline/long-term audit (`INV-006`, `INV-020`).

## 4. What is implemented safely in code today (`T003` synthetic foundation)
- `FormTemplateVersion` and `FormFieldMap` tables and `FormRegistry` service (`backend/src/denlyra/models.py`, `backend/src/denlyra/services.py`).
- Immutable `(official_code, schema_version)` registration; historical versions cannot be overwritten (`NEG-16`).
- Tri-state value semantics (`present`, `explicit_negative`, `unknown`, `not_applicable`, `missing`) enforcing `INV-022`.
- Synthetic validation preview (`POST /api/v1/clinical-forms/validate-preview`) returning completeness diagnostics with `"synthetic_only": True` and `"clinical_approval": False`.
- Fail-closed guard on template approval (`POST /api/v1/clinical-forms/templates/{id}/approve`) and official EMR export (`POST /api/v1/clinical-forms/official-export`), both rejecting requests with HTTP `409 Conflict` until external clinical/legal sign-off artifacts are provided.
