# ADR-004 — AI as reviewable assistant, not autonomous clinician
Date 2026-11-17 · Status Accepted

**Decision:** AI services optional and isolated, no direct EMR signing, diagnosis, prescriptions, treatment decisions or external patient messages. Use synthetic/deidentified licensed data, schema constrained outputs, source-linked drafts and clinician confirmation. Non-AI workflows must work without GPU/cloud.
**Reason:** High patient safety, legal and privacy impact; hallucinations and wrong tooth/allergy/negation are unacceptable.
**Consequences:** Delayed clinical AI ambitions, stronger validation, reproducibility and simpler first product. Clinical or diagnostic model to be separately classified under relevant medical-device/AI regulation.
