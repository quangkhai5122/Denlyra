# Vietnamese dental EMR regulatory traceability matrix

Date: 2026-11-17 · **Research baseline, not a legal opinion or certification.** Primary law must be retrieved in force and qualified counsel + clinic medical director sign off for clinic-specific deployment. This document records evidence and **unresolved** decisions, not automatic legal compliance.

## 1. Verified official sources and metadata
| Source | Official URL | Status / significance |
|---|---|---|
| Circular 13/2025/TT-BYT (electronic medical records) | https://vanban.chinhphu.vn/ (search document no. 13/2025/TT-BYT); detailed government explanation: https://xaydungchinhsach.chinhphu.vn/lo-trinh-trien-khai-ho-so-benh-an-dien-tu-tai-cac-benh-vien-119250610163849953.htm | Published 6 Jun 2025; effective 21 Jul 2025; Clause 2 Article 4 deadline for non-hospital facilities treating outpatient/inpatient/day-care patients by **31 Dec 2026**; verify clinic's exact license and scope. |
| Circular 32/2023/TT-BYT, Appendix XXVIII | Official ministry/government gazette original | Dental form **13/BV-01** and outpatient dental **16/BV-01**; field-by-field mapping requires authoritative PDF inspection and dentist review. |
| Circular 25/2026/TT-BYT (amendments to 32/2023) | https://vanban.chinhphu.vn/?classid=1&docid=218704&pageid=27160&typegroupid=6 | Issued 30 Jun 2026; effective 15 Aug 2026; applicability and affected form sections must be diffed. |
| Circular 33/2025/TT-BYT (health records retention) | https://vanban.chinhphu.vn/?classid=1&docid=214427&orggroupid=4&pageid=27160 | Issued/effective 1 Jul 2025; exact dental record retention schedule unverified in this package. |
| Law 15/2023/QH15 on Medical Examination and Treatment | https://vanban.chinhphu.vn/ (search document no. 15/2023/QH15) | Governs healthcare records and professional responsibilities. Review live consolidated text before implementation. |
| Decree 96/2023/ND-CP | https://vanban.chinhphu.vn/ (search document no. 96/2023/ND-CP) | Licensing and clinic activity conditions; site-specific scope review. |
| Law 91/2025/QH15 on Personal Data Protection | https://vanban.chinhphu.vn/?docid=214590&pageid=27160 | Effective 1 Jan 2026; health data sensitive, compliance analysis required. |
| Decree 356/2025/ND-CP | https://vanban.chinhphu.vn/?docid=216387&pageid=27160 | Data protection implementation; security/processing rights review. |
| Ministry technical guidance 365/TTYQG-GPQLCL | Refer to previous `archive/foundation/01_CLINICAL_LEGAL_REQUIREMENTS.md` primary pointer and confirm current issue | Deployment, PDF/XML/JSON/data traceability guidance; not a replacement for controlling laws. |

### Key chronology clarification
The rule for non-hospital outpatient providers in Circular 13/2025 is **31 Dec 2026**, not simply “all dental clinics must stop paper by 1 Jan 2027 because hospitals do.” Hospital-specific directives and 2030 nationwide policy targets should not silently erase the Circular's deadline. Actual applicability still requires the dental clinic’s operating license and local Sở Y tế guidance.

### Site-specific legal inquiry needed
- Is each partner a licensed **specialist dental clinic** or hospital department? Does it conduct outpatient care as the Circular defines?
- What implementation guidance or inspection/acceptance documents has the relevant Provincial/City Health Department issued since 2026?
- Which electronic signatures/confirmations are lawful for each clinical record type, and who must authenticate?
- Which form templates and preservation classes apply to the clinic’s treatments and records?
- Are any reporting, interoperability, insurance or e-prescription integrations legally required? Verify rather than guess.
- What legal processing basis and role does the clinic and SaaS provider have for patient/guardian data, imaging and AI dictation?

## 2. Traceability matrix
| Legal/clinical concern | Proposed engineering requirement | Artifact/API/test | Approver | Gate |
|---|---|---|---|---|
| Correct form for outpatient dental encounter | FormRegistry with versioned 16/BV-01 field map | `EMR-008`, `FORM-FIELD-*`, PDF/structured export fixture | Clinic medical director + legal counsel | CLIN-G1 |
| Complete content and source | Distinguish required/optional/unknown fields; exact source events | `EMR-001/002/014`, completeness tests | Clinician | CLIN-G1 |
| Authorship and signature | Authenticated clinician identity, content digest, licensed method, evidence | `EMR-006`, signer mock, verification tests | Legal reviewer, clinical lead | CLIN-G2 |
| Addendum after authentication | Immutable original + linked amendment and reason | `EMR-007`, old digest unchanged tests | Clinician | CLIN-G2 |
| Sensitive data segregation | Access control per clinic, role, patient case and purpose | `SEC-002`, adversarial tests | Security/privacy officer | SEC-G1 |
| Legacy paper conversion | Source scans, manifest, page completeness, human verification | `MIG-001..010`, migration tests | Clinic record officer | CLIN-G1 |
| Record retention and legal hold | Per-class retention policy sourced to official annex | `SEC-011`, retention matrix | Legal/clinic record owner | CLIN-G3 |
| Backup/recovery and integrity | DB+media+DICOM+signatures+key restore, manifest | `OPS-007`, DR tests | Security/operations | OPS-G1 |
| Third-party processor / cloud hosting | Agreement, data locality/legal transfer review, subprocessor list | `SEC-009`, vendor assessment | Legal/privacy officer | SEC-G2 |
| AI clinical text processing | Explicit authorization/consent, clinical review, no auto-sign | `AI-001..014`, clinical error benchmark | Clinician, privacy lead | AI-G1 |
| Authorized external interfaces | Partner contracts/API validation; no fabricated government endpoints | `INT-001..012`, contract tests | Integration/legal owner | INT-G1 |

## 3. Source classification and approval states
`observed_primary_link → official_pdf_fetched → article_and_form_verified → clinical/legal_reviewed → approved_for_specific_use`.
A crawler or AI Agent can discover and extract into quarantine, NEVER self-approve. Store issue date, publication date, effective interval, form version, source SHA256, exact page/article, authority, reviewer and test fixture. Keep superseded versions for historical records.

## 4. Clinic-specific compliance worksheet template
```
Clinic legal name and license number: [DO NOT WRITE REAL VALUE INTO AGENT REPOSITORY]
License type, permitted scope, outpatient/day/inpatient: ____________________
Province and regulating Sở Y tế: ____________________
Official correspondence/date/source URL: ____________________
In-force EMR regulations and clinic applicability: ____________________
Form inventory: [13/BV-01, 16/BV-01, others with evidence]
Who authors/supervises/signs each record and consent? ____________________
Chosen legal signature/confirmation mechanism and vendor: ____________________
Paper archive/migration/retention policy: ____________________
DICOM/imaging devices/interfaces: ____________________
Security/data processing/vendor assessment: ____________________
Clinical lead and counsel approvals: ____________________
Remaining questions / DO NOT RELEASE flags: ____________________
```

## 5. Release gate
No claims “certified EMR,” “satisfies Ministry standards,” “can replace paper now” or “legally signed” before independently validated site-specific clinical/legal, signature, archival, security and deployment review. README/UI must remain visibly labeled synthetic demo until then.
