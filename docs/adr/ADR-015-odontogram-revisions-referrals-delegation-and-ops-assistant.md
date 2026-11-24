# ADR-015 — Optimistic Odontogram Revisions, Structured Clinical Export, Scoped Delegation & Allowlisted Ops Assistant

- **Status:** Accepted (synthetic foundation implemented in `T019` and `T020`)
- **Date:** 2026-11-24
- **Depends on:** `ADR-007` (Identity/RBAC), `ADR-010` (Encrypted Archive), `ADR-011` (AI Safety Harness), `ADR-013` (Patient Portal & KPI Lineage), `ADR-014` (Encounter Lifecycle & Procedure Evidence)

## Context
1. Longitudinal dental charting requires versioned legend mappings (`ODN-006`), optimistic concurrency on tooth restoration states (`ODN-007`, `ODN-010`), deterministic chart exports (`ODN-008`), reviewed external referrals (`EMR-013`), non-destructive document eligibility checks (`PAT-010`), and structured signed snapshot exports (`EMR-014`).
2. Multi-branch clinic operations require aggregate-only owner dashboards (`ORG-007`), time-boxed temporary permissions (`ORG-009`), auditable task escalations and patient-tied handoffs (`HR-005`, `HR-006`), strict separation of internal vs patient-visible communications and private complaint notes (`CRM-001`, `CRM-009`), and an allowlisted read-only operations assistant (`AI-005`).

## Decision
1. **Optimistic Tooth Restoration Revisions & Structured Clinical Export (`odontogram_referrals_export.py`):**
   - Version `odontogram_legend_entry` append-only and freeze `legend_version_number` inside each `odontogram_restoration_revision`. Enforce `expected_revision` on `odontogram_restoration_state` (`409` on stale writes).
   - Quarantine incoming `external_referral_document` records until reviewed by `dentist`/`medical_director`, evaluate `PAT-010` eligibility read-only without touching signed snapshots, and bind `EMR-014` structured exports to exact `canonical_sha256` + `ArchiveObject` digests.
2. **Scoped Multi-Branch Aggregates, Auto-Expiring Delegation, Handoffs, Complaints & Read-Only Ops Assistant (`org_crm_ops_assistant.py`):**
   - Enforce `temporary_delegation_grant` inside `auth.check_permission` strictly for allowlisted non-clinical-signing permissions while `now < expires_at` and `not revoked`.
   - Expose de-identified integer aggregates across explicitly granted `(clinic_id, branch_id)` scopes in `ORG-007` without cross-clinic chart access.
   - Redact `private_investigation_notes` on `service_complaint_case` for roles lacking `complaint.read_private`, exclude `internal_staff_only` `patient_contact_log` rows from `patient-portal/overview`, and restrict `AI-005` to RBAC-checked allowlisted read tools with `executed=False` proposals.

## Consequences
- Schema advances cleanly via forward-only migration `0010_odontogram_referrals_delegation_and_ops` (`75 -> 86` tables).
- All clinical, e-signature, and production authentication safety flags remain `False` until human clinical, legal, and security gates pass.
