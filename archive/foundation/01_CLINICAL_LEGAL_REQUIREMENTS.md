# 01 — Clinical and regulatory requirements specification

**Status:** draft requirements derived from selected official documents; final adoption must be reviewed by Vietnamese medical/legal counsel and the relevant Sở Y tế. Each row is an implementation hypothesis until qualified reviewers sign the legal-interpretation column.

## 1. Source register (checked 2026-11-17)

| ID | Level | Document / official link | Product effect |
|---|---|---|---|
| LEG-01 | A | [Thông tư 13/2025/TT-BYT, ngày 06/06/2025](https://xaydungchinhsach.chinhphu.vn/lo-trinh-trien-khai-ho-so-benh-an-dien-tu-tai-cac-benh-vien-119250610163849953.htm); legal text [reference](https://thuvienphapluat.vn/van-ban/The-thao-Y-te/Thong-tu-13-2025-TT-BYT-huong-dan-trien-khai-ho-so-benh-an-dien-tu-660113.aspx) | EMR lifecycle, deadlines, infrastructure, signing, transitional record handling. Effective 21/07/2025. |
| LEG-02 | A | [Thông tư 32/2023/TT-BYT, Chương X, Phụ lục XXVIII](https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=168125) | Clinical record content, documentation rules and dental record templates. |
| LEG-03 | A | [Phụ lục XXVIII — PDF tại website bệnh viện](https://bvdkthuanchau.vn/upload/1002761/fck/files/28__Phu_luc_XVIII__Mau_benh_an_2efd3.pdf) | Dental forms `13/BV-01` and outpatient `16/BV-01`. PDF is a hosted copy of the annex; validate against official signed original. |
| LEG-04 | A | [Thông tư 25/2026/TT-BYT](https://vanban.chinhphu.vn/?classid=1&docid=218704&pageid=27160&typegroupid=6) | Amends parts of TT32/2023; check scope and 2026 form versions. Published 30/06/2026, general effective 15/08/2026 with article-specific exceptions. |
| LEG-05 | A | [Chỉ thị 04/CT-BYT 07/04/2026](https://adminmoh.moh.gov.vn/web/guest/thong-tin-chi-dao-dieu-hanh/-/asset_publisher/DOHhlnDN87WZ/content/bo-truong-bo-y-te-ao-hong-lan-yeu-cau-ay-manh-trien-khai-benh-an-ien-tu-tai-co-so-kham-chua-benh) | Directs institutions to implement EMR by 31/12/2026; explicitly says hospitals no paper from 01/01/2027. |
| LEG-06 | A | [Quyết định 965/QĐ-BYT, giai đoạn 2026–2030](https://adminmoh.moh.gov.vn/web/guest/chuyen-doi-so-y-te/-/asset_publisher/bGrskQ5MmTm7/content/bo-y-te-at-muc-tieu-en-nam-2030-100-co-so-kham-chua-benh-tren-ca-nuoc-trien-khai-ho-so-benh-an-ien-tu) | Goal: 100% facilities use paperless EMR by 2030; does NOT automatically repeal TT13 deadline. |
| LEG-07 | B | [Công văn 365/TTYQG-GPQLCL](https://thuvienphapluat.vn/cong-van/Cong-nghe-thong-tin/Cong-van-365-TTYQG-GPQLCL-2025-yeu-cau-ky-thuat-trien-khai-phan-mem-ho-so-benh-an-dien-tu-671468.aspx) | EMR technical guidance: PDF, XML/JSON export, access, traceability, backups and deployment choices. Verify current official version. |
| LEG-08 | A | [Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15](https://vanban.chinhphu.vn/?docid=214590&pageid=27160&typegroupid=3), [Nghị định 356/2025/NĐ-CP](https://vanban.chinhphu.vn/?docid=216387&pageid=27160) | Both effective 01/01/2026; clinical data privacy and processors/controllers obligations require legal review. |
| LEG-09 | A | [Thông tư 33/2025/TT-BYT — lưu trữ hồ sơ ngành y tế](https://vanban.chinhphu.vn/?classid=1&docid=214427&orggroupid=4&pageid=27160) | Record retention classification and policy; exact dental-record periods MUST be checked from annexes. |
| LEG-10 | A | [Luật Khám bệnh, chữa bệnh 15/2023/QH15, Điều 69](https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=168125) | Clinical-record confidentiality, access and lawful use; cross-check actual statutory text. |
| LEG-11 | A | [Luật Giao dịch điện tử 20/2023/QH15](https://vanban.chinhphu.vn/) | Lawful electronic confirmation/signatures; select compliant provider and per-field signature policies after legal assessment. |

**Important deadlines:** Circular TT13 Article 4(2)(a) hospitals by 30/09/2025; Art 4(2)(b) other licensed treatment facilities offering inpatient, day-treatment or outpatient services by 31/12/2026. A typical licensed outpatient dental clinic is likely in the second group, but verify license and actual service scope. The 2030 plan is not blanket permission to defer.

**Status of prior circulars:** TT13 replaced TT46/2018 and certain EMR criteria from TT54/2017. Do not use the obsolete criteria as the controlling EMR rule without legal review. Some later facility resolutions cite old circulars; source precedence must be verified.

## 2. Forms inventory and mapped software fields

The Appendix XXVIII forms include `13/BV-01` (Răng Hàm Mặt) and `16/BV-01` (Bệnh án ngoại trú chuyên khoa Răng Hàm Mặt). The outpatient form's displayed text includes administrative information, presentation time, reason for consultation, medical/family history, clinical examination and specialist examination, assessments and follow-up/discharge summary. **The following grouping is a data architecture proposal, NOT a claim of verbatim form completeness.**

| Form group | Internal model | Mandatory design attributes |
|---|---|---|
| Facility/form metadata | `FormTemplateVersion`, `Clinic`, `Department` | form_id, schema version, source law/appendix, effective date, clinic setting |
| Patient identity/administrative | `Patient`, `PatientIdentifier`, `PatientContact`, `RelatedPerson` | immutable local ID; sourced/verified identifier; guardian/authorized contact distinct |
| Patient management | `Encounter`, `Referral`, `VisitPeriod` | timezone, clinic, practitioner, visit type, source and status |
| Reason and history | `ChiefComplaint`, `MedicalHistory`, `AllergyRecord` | explicit known/unknown/negative; author and timestamp |
| Exam findings | `ClinicalObservation`, `DentalFinding` | structured anatomy/tooth/surface + free text + status + evidence |
| Clinical assessment | `Diagnosis/Assessment` | author, date, code-system/version when used, verification status |
| Procedures | `ProcedureRecord` | planned/ordered/performed are separate facts; who did what and when |
| Imaging/other tests | `ImagingStudy`, `MediaAsset`, `TestResult` | patient/encounter binding, modality, file hash, provenance |
| Treatment planning | `TreatmentPlan`, `PlanVersion`, `Phase`, `Task` | author, approved version, dependencies, current vs proposed plan |
| Medical record finalization | `ClinicalDocument`, `DocumentVersion`, `SignatureEnvelope`, `Addendum` | snapshot content, signer identity, method, provider evidence, reason |
| Follow-up | `FollowupOrder`, `Appointment` | clinician order vs administrative booking separate |
| Archiving/export | `RecordArchive`, `ExportPackage` | retention schedule, complete snapshot, verification manifest |

An EMR can be represented in normalized domain tables but must reliably render/export the **complete applicable approved form**. Add field-level `RegulatoryFieldMap` rows such as:
```
form_id: 16/BV-01
form_version: verified_2026_candidate
source_clause: TT32/2023, Appendix XXVIII (review amendments)
field_path: encounter.reason_for_visit
required_when: condition_from_clinical_review
source: clinical entry / imported paper / patient-reported
signer_role: physician (when required by approved policy)
validation_rule: reviewed_not_guessable
```

**Never hard-code `required=True` for every printed box:** form requirements, applicability and completion conventions need medical review, including whether a field is non-applicable rather than missing. Use versioned schema and conditional required rules.

## 3. Regulatory traceability matrix (seed)

| ID | Requirement and authority | Product workflow | Invariant / test | Approval owner |
|---|---|---|---|---|
| CL-01 | TT13: electronic lifecycle | Clinical encounter & document service | signed and unsigned states distinguished | Medical/legal |
| CL-02 | TT13 + TT32: complete applicable record content | Versioned form renderer + data model | field-by-field audited mapping, PDF view | Clinical lead |
| CL-03 | TT13: identification interconnection | Patient identifier registry | duplicates flagged; identifiers verified under lawful access | Clinic/legal |
| CL-04 | TT13 Article 3: lawful sign/confirm | Signature adapter and signing policy | signed bytes match final document, identity valid | Legal + security |
| CL-05 | TT13: backup, availability and recovery | storage, backup, restore | full media+DB+keys restore drill | Security lead |
| CL-06 | Legal medical confidentiality & PDPL | RBAC+ABAC and patient-level access | unauthorized medical-record read denied and audited | Privacy/legal |
| CL-07 | TT32 record-writing requirements | authorship/time/clinical record version | no unsigned AI content silently committed | Clinical lead |
| CL-08 | Annex XXVIII: outpatient dental form | Form version 16/BV-01 | completeness report vs approved source | Medical/legal |
| CL-09 | 2026 TT25 amendments | legal schema/version registry | compare changed clauses before package release | Legal |
| CL-10 | Legacy paper transition TT13 Art 5 | scan/import/legacy link | paper origin never relabeled originally electronic | Clinic/legal |
| CL-11 | TT33 records retention | retention policy per record type | no deletion on subscription cancellation | Legal + DPO |
| CL-12 | Guidance 365 export/interoperability | controlled PDF/XML/JSON exports | integrity check, id and link preservation | Interop lead |
| CL-13 | Access to historical patients | actor purpose & policy engine | all non-routine access justified and recorded | Clinic/DPO |
| CL-14 | Real facility adoption governance | implementation/operation runbook | clinic-specific acceptance records and approval | Clinic management |

This matrix must be expanded until every form field, signature step, procedure, exception and applicable legal requirement has an owner and test. A commercial EMR claim requires more than row completion.

## 4. Clinical decision boundaries

- Only authorized clinicians create/approve diagnoses, treatment plans, completed procedures, clinical follow-up and finalized notes.
- Staff may draft administrative/clinical intake under scoped authority; such drafts are always distinguishable from clinician-confirmed observations.
- A treatment plan being *scheduled* does NOT prove a procedure occurred.
- A charge or paid invoice does NOT prove a procedure occurred; a performed procedure does NOT automatically prove a charge is legally or contractually due.
- Clinical treatment consent, privacy consent, marketing opt-in and financial agreement are separate purposes and records.
- Patient portal should expose only approved and authorized clinical information; staff free text is not automatically released to the patient.
- Laboratory partner receives minimum required case data, not full patient medical history.
- AI must never autonomously prescribe, change treatment, diagnose imaging or sign clinical documents.

## 5. Paper-to-digital migration requirements

**Two tracks:**
1. Historical paper record: store provenance (clinic, legacy ID, scan time, operator, source pages, SHA256, reviewer, known completeness gaps). Maintain paper-document status and custody/retention policy. OCR output untrusted until human review; don't forge old clinician timestamps/signatures.
2. New native electronic record: assigned new internal identifiers, created with controlled workflow and qualified signing method. Prior paper attachments may be referenced, but not silently rewritten.

Algorithm: inventory → assign batch ID → scan at controlled resolution → verify page count/legibility → check hash & patient linkage → optional extraction → human confirm critical fields → provenance package → archive according to approved policy. Quarantine ambiguous patient matches.

TT13 Art 5 contains transitional rules for paper records created before 21/07/2025. Validate specific applicability for old and ongoing episodes and document physical retention decisions instead of assuming all paper may be destroyed.

## 6. Clinical discovery required from each dental clinic

- Operating permit (`phòng khám chuyên khoa` vs other), approved services, location, Sở Y tế instructions; outpatient vs day care.
- Current paper record templates and versions, actual workflows for first visit, follow-up, orthodontics, prosthetic/implant where provided.
- Clinical authorship and signature policy; practitioners' lawful credentials and approval workflows.
- Patient identification, minors/guardians, referral, consent and communication practices.
- Device list: panoramic, intraoral X-ray, CBCT, cameras, scanners; DICOM/export support.
- Storage and retention, onsite computers, connectivity and existing backup behavior.
- Whether current cases span mixed paper/electronic records; count, quality and completeness of historic folders.
- A **realistic synthetic** patient journey signed off by supervising dentist for acceptance tests.

## 7. Legal questions requiring external confirmation

- Exact applicability and timing for each named clinic in its provincial Sở Y tế jurisdiction, including whether any later amendment or implementing instruction modifies the operational requirements.
- Which signed forms, acknowledgment methods and patient/guardian flows are valid for the clinic; identity proofing and qualified signature vendor terms.
- Specific retention periods by record category under TT33 and other applicable rules; record requests and deletion exceptions.
- Whether required public declaration/acceptance/administrative documentation is needed before paperless operation and applicable authority/process.
- Relevant technical data exchange requirements for local health and insurance systems, if clinic participates.
- Controller/processor roles, privacy notices, impact assessments, breach response and cross-border data transfers under 2026 law.

**Gate:** No production claim of 'EMR certified', 'paperless compliant', or 'meets TT13' from a software self-check alone.
