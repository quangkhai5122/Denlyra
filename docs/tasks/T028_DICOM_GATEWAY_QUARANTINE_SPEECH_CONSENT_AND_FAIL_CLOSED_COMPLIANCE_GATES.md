# T028 — DICOM Quarantine Gateway, Speech Dictation Audio Consent, Accounting Export & Fail-Closed Release Gates

- **Status:** Completed (synthetic quarantine/sandbox harnesses verified; real Orthanc/PKI/Tax/PHI activation remain fail-closed)
- **Feature IDs:** `INT-004`, `AI-001`, `FIN-009`, `INT-009`, `SEC-014`, `SEC-015`
- **Governing ADR:** [ADR-019](../adr/ADR-019-sandbox-provider-contracts-dicom-quarantine-speech-consent-and-release-gates.md)
- **Related Risks:** `R-004` (clinical/legal sign-off), `R-006` (DICOM wrong-patient attachment), `R-007` (external tax/AI providers)

## 1. Objective & Bounded Scope
Implement honest synthetic quarantine gateways and fail-closed compliance harnesses for:
1. **`INT-004` — Per-Clinic Confirmed Modality & DICOM Study Quarantine Gateway:** Verify clinic modality confirmation and exact `dicom_patient_id_tag == patient_id` matching before registering an `HTEST` OHIF study descriptor; block wrong-patient studies and SaMD diagnostic claims (`409`).
2. **`AI-001` — Zero-Egress Speech Dictation Audio Consent & Terminology Draft:** Require verified audio recording consent + active `data_processing` consent, block prompt injection (`409`), score deterministic Vietnamese dental terminology coverage, and prohibit direct EMR writes (`wrote_to_emr=False`).
3. **`FIN-009` & `INT-009` — PHI-Free Accounting Journal Export & Fail-Closed E-Invoice Gate:** Export canonical SHA-256 integer-VND accounting batches without patient PHI while hard-blocking (`409`) uncertified official tax e-invoice issuance or government API calls.
4. **`SEC-014` & `SEC-015` — Automated Adversarial Security Suite & Fail-Closed PHI Release Gate:** Execute SSRF/path-traversal/cross-origin/RBAC negative probes (`independent_external_pentest_complete=False`) and hard-block (`409`) enabling production PHI processing until all human clinical, legal, and security gates are closed.

## 2. Negative Cases (Red-First)
- Ingesting a DICOM study manifest with mismatched `dicom_patient_id_tag`, unconfirmed modality, or `claim_diagnostic_samd=True` -> `409 Conflict`.
- Submitting speech dictation without `audio_recording_consent_verified=True` (`403`) or with prompt injection (`409`).
- Requesting accounting export with `include_patient_clinical_phi=True` (`422`) or `issue_official_tax_einvoice=True` / `call_government_tax_api=True` (`409`).
- Evaluating production release gate with `target_environment="production_phi"` or `enable_real_phi_processing=True` -> `409 Conflict`.
