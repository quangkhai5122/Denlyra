# ADR-002 — Clinical authority, immutable document versions and plan approvals
Date 2026-11-17 · Status Accepted in principle, pending dental/legal review

**Context:** Clinical events, treatment plans and payments can diverge; a signature binds an exact document version.
**Decision:** Encounter, ClinicalDocument, TreatmentPlan and RevenueAccount separate authoritative aggregates. Authenticated note immutable; correction is linked addendum; legal signatures use qualified reviewed provider/method, not hashes/checkboxes. In demo `demo_locked` and `demo_reviewed` intentionally have no clinical/legal authority.
**Consequences:** Better audit and health safety, more explicit state management and approval overhead. Need site-specific clinical form map and legal signature verification before live data.
