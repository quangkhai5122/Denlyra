# Security threat model — dental clinical platform

**Status: target controls, NOT implemented in current demo.** Current demo has no real authentication and unencrypted SQLite, so no real patient data may be processed. A short official security/legal assessment cannot be replaced by AI claims.

## Assets, trust boundaries and actors
Assets: patient identifiers, clinical notes, dentist authentication, medical images (DICOM/CBCT), treatment plans, consents and signatures, financial ledger, staff roles, encryption keys, backups, audit, trusted integration credentials, AI inputs/outputs. Actors: clinic staff (different roles), doctor, patient, lab partner, support engineer, external provider, malicious browser/page, compromised local device, attacker with server/storage access.

Trust boundaries: untrusted browser/phone → identity/API; clinic data → shared control plane; server → clinic DB & encrypted media; server → payment/Zalo/signature provider; document/record → AI worker; on-prem imaging device → DICOM gateway; backup → recovery environment. All request header values and external texts are untrusted.

## High-risk STRIDE-style register
| Threat | Severity | Current reality | Production mitigation |
|---|---|---|---|
| Unauthenticated access via demo headers | Critical | OPEN in demo | OIDC/MFA, backend policy engine, session revocation, remove demo mode in deployable build |
| Data leaked between clinics | Critical | App filter only | Authenticated tenant context, DB grants/tenant router, negative cross-tenant tests |
| Wrong clinician signs chart | Critical | Signing disabled | Verified credential, authority, identity proof, approved signature adapter |
| Original signed note modified | Critical | Demo hash only | Immutable snapshot, protected signature evidence and independent audit |
| Patient photo X-ray attached to wrong patient | Critical | Media disabled | Patient/study ID matching, quarantine, confirm and manifest audit |
| AI exfiltrates patient data through tool/prompt | Critical | AI disabled | Permission-scoped minimal context, no external model default, injection tests |
| Unreviewed clinical AI creates diagnosis | Critical | AI diagnosis disabled | Clinical validation, regulatory classification, human approval |
| Wrong booking caused by race | High | SQLite sequential check only | PostgreSQL exclusion and concurrent load tests |
| Duplicate payment webhook | High | No provider integration | Provider verification, inbox idempotency, protected ledger |
| Encrypt key leak or unrecoverable archive | Critical | Not implemented | KMS/HSM controls, rotation, escrow and recovery exercise |
| Ransomware / lost disk | Critical | No backup | Encrypted offline/cross-location backup and restore tests |
| Malicious PDF/DICOM or image | High | Upload disabled | sandboxed parser, size/pages, malware scanning, anti-zip-bomb |
| False legal compliance marketing | High | Documentation warns | Independent clinical+legal signoff, versioned regulatory evidence |
| Cross-tenant object URLs | Critical | Storage absent | Short-lived scoped signed URLs, deny-by-default, access audit |
| CSRF/XSS/SSRF / supply-chain | High | Basic Host/Origin demo guards | ASVS implementation, headers, token session, input checks, SBOM, scanning |

## Production access-control blueprint
RBAC roles: clinic_owner, medical_director, dentist, assistant, receptionist, treatment_coordinator, finance, inventory, lab_partner, patient/guardian, limited_support. ABAC conditions: clinic membership, licensed scope/credential, care-team relationship, data classification, record state, purpose, location/session assurance. Patient identity and guardian relation must be verified separately; one phone number cannot authorize all family members.

## Consent taxonomy
Treatment/clinical consent, data processing notice/authorization, communications consent, marketing consent, billing acceptance and guardian delegation are distinct records. Consent revocation handling requires privacy/legal review; it must not erase legally protected clinical history.

## Audit design
Audit actions include patient view (purpose), sensitive export, clinical note draft/revision/authentication, document addendum, care plan approval/version, appointment creation/cancel, payment correction, file view/download, role changes, break-glass and external integration sends. Log IDs and minimal action metadata but not clinical narrative or patient identifiers in external monitoring. Production audit integrity via append-only independent storage/WORM-style digest; a hash in the same writable DB alone is not tamper-proof.

## Security gates before PHI
No actual patient ingestion before: real auth, tenant/role security, encryption/key management, full archive backup, legal data protection review, privacy notices and processor agreements, penetration testing, encrypted connection, clinical authorizer/EMR form workflow, incident response and signed releases. Record approvals with independent named human roles.
