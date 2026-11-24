# T020 — Multi-Branch Aggregates, Auto-Expiring Delegation, Staff Handoffs, Complaint Recovery & Allowlisted Ops Assistant
Priority P1 (`ORG` / `HR` / `CRM` / `AI`) · Owner: Platform Authorization, Operations & Safe AI · Depends T001, T012, T013, T015, T016

**Status (2026-11-24):** Completed (aggregate-only multi-branch owner view, auto-expiring temporary delegation, staff task escalations & patient/task-tied handoffs, differentiated contact timeline & restricted complaint recovery notes, and allowlisted read-only ops assistant verified in `test_delegation_handoffs_complaints_ops_assistant.py`). See [ADR-015](../adr/ADR-015-odontogram-revisions-referrals-delegation-and-ops-assistant.md) and [PROJECT_STATE.md](../PROJECT_STATE.md).

## Domain Rules & Safety Invariants
1. **Multi-Branch Owner Aggregate Dashboard (`ORG-007`):**
   - `owner_branch_scope_grant` authorizes de-identified aggregate KPIs across granted clinics/branches without pooling individual patient charts (`404`/`403` preserved on cross-clinic chart access).
2. **Auto-Expiring Temporary Delegation (`ORG-009`):**
   - `temporary_delegation_grant` grants allowlisted operational permissions (forbidding clinical signing/diagnosis/key custody delegation -> `422`), audits every delegated use, and expires automatically (`403` once expired or revoked).
3. **Staff Task Escalations & Permissioned Internal Handoffs (`HR-005`, `HR-006`):**
   - `staff_operational_task` + `staff_operational_task_event` track overdue owners and escalation history.
   - `internal_handoff_note` must bind to `patient_id` or `task_id` (`422` if untethered), restricts access to care/coordination roles (`403` for `finance`), and audits reads/writes.
4. **Differentiated Contact Timeline & Restricted Complaint Notes (`CRM-001`, `CRM-009`):**
   - `patient_contact_log` separates `internal_staff_only` from `patient_visible` items (portal overview never leaks `internal_staff_only`).
   - `service_complaint_case` redacts `private_investigation_notes` for general staff while allowing `clinic_owner`/`medical_director` full review (`CRM-009`).
5. **Policy-Aware Read-Only Operations Assistant (`AI-005`):**
   - Executes ONLY allowlisted read tools permitted by caller RBAC, enforces prompt-injection firewall (`409`) and kill-switch (`503`), rejects autonomous write tools (`422`), and returns human-confirmed action proposals (`executed=False`).

## Mandatory Negative Tests (Written Before Domain Code)
1. Multi-branch owner aggregate returns counts/VND totals with zero PHI while direct cross-clinic patient chart read still fails (`404`/`403`); delegating forbidden `clinical_doc.sign` -> `422`; expired/revoked operational delegation -> `403`.
2. Untethered internal handoff note -> `422`; `finance` reading clinical handoffs -> `403`; `internal_staff_only` contact log never appears in `patient-portal/overview`; `receptionist` reading complaint queue gets redacted `private_investigation_notes`.
3. Ops assistant invoked with unallowlisted write tool or prompt injection -> `422`/`409`; unauthorized role invoking restricted ops read tool -> `403`.
