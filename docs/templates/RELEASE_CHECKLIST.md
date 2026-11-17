# Denlyra release gate — NO PHI without independent approvals

- [ ] Denlyra commercial brand/trademark clearance documented.
- [ ] Clinical scope and site-specific medical license verified.
- [ ] Current in-force official legal source versions and form mappings reviewed.
- [ ] Medical director signed off on actual workflows, forms and professional actions.
- [ ] Legal reviewer approved electronic signature, patient consent, retention and processing agreements.
- [ ] Production auth (OIDC/MFA), roles and clinic/patient authorization verified.
- [ ] PostgreSQL booking race and payment concurrency tests pass on actual server.
- [ ] Signed record immutability/append-only corrections tested and approved.
- [ ] Encrypted DB/media/DICOM archive, backup/restore/keys tested.
- [ ] Security review, OWASP and third-party dependency/license scan completed.
- [ ] Incident response, support contacts and monitoring defined without PHI in logs.
- [ ] Patient data export/cutover/exit plan verified.
- [ ] AI cannot auto diagnose, sign or leak data; model evaluation/consent reviewed.
- [ ] Owner and independent clinical/legal/security reviewers sign dated go-live record.

Unreviewed box = release blocker, no exceptions by coding agent.
