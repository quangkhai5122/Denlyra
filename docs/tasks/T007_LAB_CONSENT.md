# T007 — Lab case handoff, consent and scoped partner portal
Priority P1 · Owner: Lab/Engagement · Depends T001, T004

**Status (2026-11-18):** Completed for synthetic domain/API slice (`ADR-009`, `backend/tests/test_lab_consent_portal.py`). Clinical consent wording and external partner contracts remain subject to legal review before real patient use.

## Work
- Implemented purpose-separated `ConsentRecord` (`treatment`, `data_processing`, `marketing`, `financial`), enforcing guardian authority verification (`PAT-004`, `422`) and ensuring `marketing` withdrawal never alters `treatment` consent or clinical records (`INV-024`, `SEC-07`).
- Extended `LabCase` with `specification_demo`, `file_manifest_json`, `due_on`, delivery condition receipt (`POST /api/v1/lab-cases/{id}/receive`, `LAB-006`), and revision/remake lineage (`POST /api/v1/lab-cases/{id}/remakes`, `LAB-007`).
- Built scoped, time-bounded `LabPartnerGrant` tokens (`POST /api/v1/lab-cases/{id}/partner-grants`) and partner portal endpoints (`/api/v1/lab-portal/cases/{grant_token}`) that expose zero patient PII (`OPS-06`, `LAB-008`) and forbid partner self-verification (`403`, `LAB-009`).
- Added lab due-date delay alerts (`GET /api/v1/lab-cases/{id}/alerts`, `lab_due_after_appointment`) when `due_on` exceeds a linked appointment's start time without ever auto-rescheduling the appointment (`SCH-013`, `LAB-004`).
