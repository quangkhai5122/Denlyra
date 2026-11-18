# ADR-008 — Multi-dependency Treatment Journey coordination and Synthetic Signature Envelope

Date: 2026-11-18 · Status: Accepted for synthetic foundation (clinical/legal signing gates remain active) · Owners: Domain Architect + Clinical/Legal Reviewers (pending)

## Context & evidence
Following `T001` (`ADR-007`), `T002`, and `T003`, two P0 engineering capabilities remained in simplified R0 prototype form:
1. **Treatment Journey (`T005`):** `PlanTask` supported only a single `depends_on_task_id` column, lacked cycle detection for general directed acyclic graphs (DAGs), could not record clinical reassessments/repeats as new task instances (`PLAN-04`), lacked explicit cross-context coordination links (`schedule`, `lab`, `finance`), and lacked atomic appointment rescheduling (`SCH-005`) and append-only payment refunds (`FIN-006`, `OPS-03`).
2. **Clinical Document Signature Adapter (`T004`):** `ClinicalNote` only supported a basic `demo_locked` hash without a canonical snapshot envelope, `SignatureProvider` abstraction, provider timeout/mismatch failure handling (`NEG-03`, `NEG-14`), or `entered_in_error` workflow with mandatory reason.

## Alternatives
- **A) Direct foreign-table mutation across Treatment, Scheduling, Lab, and Finance:** Rejected; violates bounded-context authority (`ADR-002`, `DOMAIN_MODEL.md`) and risks falsely marking clinical care complete from financial or calendar events.
- **B) Explicit DAG edges + coordination links + transactional outbox + fake-only `SignatureProvider` envelope:** Chosen; preserves aggregate ownership, enforces cycle-free versions, records clinical loops via new versioned reassessment tasks, and tests cryptographic/provider failure modes without falsely claiming legal e-signature compliance.

## Decision
1. **Multi-dependency DAG & Reassessment (`T005`):**
   - Add `plan_task_dependency` (`task_id`, `depends_on_task_id` within same `plan_version_id`) while maintaining backward compatibility with `depends_on_task_id`.
   - Enforce topological cycle detection (DFS) whenever dependencies are added (`422` on self-dependency or cycle).
   - Add `owner_role`, `due_at`, `reassessed_from_task_id`, and `completion_evidence_note` on `plan_task`, plus `plan_reassessment` events. Reassessing a reviewed plan creates a new immutable plan version preserving prior task history while spawning traced follow-up/repeat tasks (`PLAN-04`).
2. **Cross-context Coordination & Outbox (`T005`):**
   - Add `treatment_coordination_link` connecting a `plan_task` to an `appointment`, `lab_case` (with `requires_verified_lab`), or `charge` without mutating foreign aggregates.
   - Completing a task whose linked `lab_case` is `received` or `in_progress` (not `verified`) when `requires_verified_lab=True` is rejected with `409 Conflict` (`NEG-09`). Lab delays surface as timeline blockers and NEVER auto-reschedule confirmed appointments (`SCH-013`).
   - Add atomic appointment reschedule (`POST /api/v1/appointments/{id}/reschedule`, `SCH-005`) preserving cancelled history (`rescheduled_from_id`) and writing a transactional `outbox_event` (`appointment.rescheduled`).
   - Add append-only `payment_refund` (`FIN-006`, `OPS-03`) bounded by unallocated/available payment balance, never mutating original `payment` rows or clinical states (`INV-013`).
3. **Canonical Document Snapshot & `SignatureProvider` Test Double (`T004`):**
   - Introduce `SignatureProvider` protocol and `FakeSyntheticSignatureProvider` in `backend/src/denlyra/signing.py`, plus `clinical_document_snapshot` storing canonical JSON bytes, `canonical_sha256`, template reference, signer staff ID, synthetic receipt JSON, archive manifest digest, `parent_snapshot_id`, and `entered_in_error` metadata.
   - Synthetic sealing produces status `synthetic_signed_NOT_legal`. Any request for `mode="legal_authenticated"` fails closed (`409 Conflict`) until `docs/clinical/NEEDS_CLINICAL_REVIEW.md` gates pass (`clinical_e_signature` remains `False`).
   - Provider timeouts (`503`), stale note revisions (`409`), content digest mismatches (`409`), and non-clinician/deactivated signers (`401`/`403`) all fail closed leaving the snapshot unsealed.
   - `entered_in_error` and `addendum` workflows require clinician authority and explicit reason while preserving original `canonical_json` and `canonical_sha256` bit-for-bit.

## Consequences
- Migration `0003_treatment_and_signing.py` upgrades `0002_hardening` cleanly without destructive changes.
- Clinical workflow templates and legal signature methods still require independent dentist and legal counsel sign-off before real patient use.

## Verification
- Automated suites in `backend/tests/test_treatment_journey_e2e.py` and `backend/tests/test_signature_documents.py`.
