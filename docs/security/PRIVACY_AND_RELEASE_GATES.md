# Privacy and clinical launch authorization register

## Baseline
Vietnam Law 91/2025/QH15 and Decree 356/2025/ND-CP are relevant to medical and patient personal data. The provider must obtain qualified local counsel review concerning role as data processor/controller, permitted processing, subprocessor arrangements, localization/transfer, security, subject rights, data deletion/retention and incident obligations. Medical records also have healthcare-law retention and authentication constraints. Local deployment does not automatically waive these requirements.

## Privacy by design
Data minimization by role/workflow; purpose-scoped queries; consent registry; no default third-party analytics; clear patient/guardian identity controls; data mapping of all flows; key separation and encrypted backups; support staff break-glass governance; temporary access; incident response; deletion constrained by legal hold/retention. AI input must be explicit and minimized; raw audio and prompts not logged.

## Three independent go-live signoffs
- **CLINICAL:** licensed dentist validates forms, fields, odontogram, treatment workflow, professional roles, after-hours SOP and patient safety cases.
- **LEGAL/PRIVACY:** counsel validates Circular 13/2025 scope, current Circular 32/2023 form amendments, signature/consent, retention, processor agreements and site-specific Sở Y tế requirements.
- **TECHNICAL/SECURITY:** verified production identity, DB concurrency, encryption, media archive, restore tests, penetration test, monitoring, updater, incident runbook.

No individual AI Agent or engineering lead may self-approve all three. If one fails, no real patient deployment.

## Consent and export risk
Do not confuse a check-in checkbox with legally valid clinical consent, marketing opt-in, e-signature or patient acceptance of payment terms. Clearly record exact version, action, signer identity/method and applicable scope. Export patient's lawful data without falsely inventing a signed document; preserve original signatures/provenance where they exist.

## Regulatory source version policy
Store authority, original URL, file digest, issue/effective dates, relevant article/form/page, reviewer, date reviewed, supersession links, affected modules and test IDs. When a new regulation is discovered, quarantine until human review and regression. Do not auto-infer 2026/2027 deadlines from news summaries.

## Brand/product terms
Denlyra is a development codename; complete trademark/IP review before commercial use. Third-party model, SDK, FHIR library, PACS, notification provider and open-source licenses must be reviewed before redistribution.
