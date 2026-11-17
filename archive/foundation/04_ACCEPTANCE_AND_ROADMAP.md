# 04 — Acceptance strategy and implementation roadmap

**Status:** Proposed verification program. Tests are specified but **not yet implemented or executed**. No production clinic use should begin until legal/privacy/clinical gates and independent testing are satisfied.

## 1. Definition of Ready (DoR) before a coding agent implements a feature

Each task card needs: named workflow owner; expected user role; source documentation; patient-data sensitivity class; aggregate and transaction owner; state transition; legal scope if any; acceptance examples and negative tests; backward compatibility; API schema, audit requirements and rollout flag. Unanswered clinical questions are blockers, not excuses for AI-generated defaults.

## 2. Baseline release gates

| Gate | Before | Required evidence |
|---|---|---|
| G0 Domain | first shared schema migrations | clinical owners review terms and invariants; architect signs ADRs |
| G1 Security | any patient-identifying test data | approved processing agreement, auth, tenancy, encrypted backup, incident runbook |
| G2 EMR | claim of paperless clinical record | signed regulatory form map + required signing scheme + complete workflow tests + clinic approval |
| G3 External pilot | real clinic use | staged migration rehearsal, restore drill, on-call, physician acceptance, privacy review |
| G4 AI | any patient-facing or clinical assistant | expert-labeled held-out eval set, no unsafe auto-write, user interface limitations |
| G5 SaaS paid | public product launch | support process, availability proof, pricing contract, exit/export policy, security assessment |

**Most important distinction:** Clinical workflow prototype may be built with synthetic data before G1. No unaudited prototype becomes compliant EMR by simply turning on a production flag.

## 3. Integration and negative acceptance cases (minimum catalog)

### Clinical identity and documentation (CLIN)
- CLIN-01: two patients share a telephone number → distinct identities; no false unique constraint.
- CLIN-02: same name/DOB creates candidate duplicate → cannot auto-merge.
- CLIN-03: merge approved by authorized operator → all encounters, imaging and signature links retained; merged history exported.
- CLIN-04: pediatric patient uses guardian with valid authority; guardian consent restricted by scope.
- CLIN-05: draft clinical note can be saved and reviewed without asserting it is signed.
- CLIN-06: document signature binds content digest; concurrent modification yields conflict, not silent signature.
- CLIN-07: signed note edit attempt rejected; addendum accepted and linked to original.
- CLIN-08: clinician revoked from clinic cannot create new clinical signatures; prior authored records persist.
- CLIN-09: AI generated note requires clinician review; AI cannot finalize or sign.
- CLIN-10: signed note/export references exact form version and current data snapshot.
- CLIN-11: outpatient dental form completeness cross-checked against expert-approved 16/BV-01 mapping.
- CLIN-12: person-specific medication or allergy history 'not asked' distinguished from 'negative'.

### Treatment journey (PLAN)
- PLAN-01: plan approved version 2; modification generates v3 draft, v2 remains unchanged.
- PLAN-02: task blocked by unmet authorized precondition cannot be auto-marked complete.
- PLAN-03: cancellation of appointment doesn't erase clinical encounter, performed procedure or signed note.
- PLAN-04: treatment repeat/re-evaluation creates new task instance, history preserved.
- PLAN-05: lab case marked delivered without quality verification remains separate status.
- PLAN-06: user trying to directly alter medically approved plan without clinician authority denied and audited.

### Scheduling (SCH)
- SCH-01: two concurrent reception users book same chair: exactly one transaction succeeds.
- SCH-02: clinician available but required equipment busy → booking rejected.
- SCH-03: atomic booking of clinician+chair+equipment; failure on last resource rolls back all reservations.
- SCH-04: reschedule retains previous event and notifies patient only after successful commit.
- SCH-05: recommendation solver timeout leaves confirmed schedules untouched.
- SCH-06: cancelled appointment frees resources without deleting historical plan task.

### Finance, inventory, laboratory (OPS)
- OPS-01: patient pays deposit before performed procedure; clinical completion stays false.
- OPS-02: performed procedure recorded with no invoice; system flags finance review, not creates unapproved invoice.
- OPS-03: refund creates reversal entry; original receipt and payment evidence retained.
- OPS-04: duplicate webhook event does not double-post payments or inventory adjustments.
- OPS-05: expired or quarantined lot cannot be chosen where approved policy forbids it; override if allowed is audited.
- OPS-06: lab download link restricted to authorized case files; full patient chart inaccessible.

### Privacy and tenant isolation (SEC)
- SEC-01: clinic A user cannot enumerate/search/export B patient identifiers.
- SEC-02: signed object URL for A cannot be reused to fetch B or after token expiration.
- SEC-03: clinic A patient data cannot appear in a model prompt or vector search for B.
- SEC-04: changes to staff membership immediately revoke data access and session where required.
- SEC-05: support engineer without approved purpose cannot see plaintext chart or media.
- SEC-06: audit entry for sensitive access includes actor and purpose; direct SQL bypass triggers detection/independent logs where designed.
- SEC-07: marketing opt-in withdrawal does not silently alter clinical consent record.

### Migration, archival and failure recovery (DR)
- DR-01: paper form missing page 3/5 → quarantined, operator cannot mark verified complete.
- DR-02: two paper folders same name matched → requires human identity resolution.
- DR-03: imported paper note marked source=legacy_scan, not backdated as digitally signed.
- DR-04: restore DB plus image objects plus signature manifests + KMS key restores full patient record.
- DR-05: object restore older than DB checkpoint detected; referenced missing files blocked/flagged.
- DR-06: database upgraded across two versions still renders old signed document bit-for-bit or preserving verified signed artifact.
- DR-07: network outage does not create 'signed' state when remote signature provider failed.
- DR-08: user asks to delete protected medical record; retention/legal hold rules applied, with explanation and escalation.

## 4. Workflow-level E2E goldens to co-design with partner clinics

**Journey A — routine outpatient visit:** patient registration → appointment → check-in → physician documentation using approved 16/BV-01 field mapping → exam findings/odontogram → procedure → clinician signing → payment/receipt → follow-up → PDF/structured export + restore verification.

**Journey B — multi-stage orthodontic:** initial consultation → clinician-approved versioned plan → treatment acceptance/financial agreement → appointment sequence → tasks, corrections and reassessment → approved phase transition → signed notes/clinical record and ledger → completion/follow-up. No predetermined treatment advice from software.

**Journey C — prosthetic laboratory:** approved case requisition → scoped lab case bundle → lab acceptance → manufacturing/milestones → receipt and quality verification → dependent appointment → revision/remake with traceable version → patient treatment record.

**Journey D — paper conversion:** unverified paper folder → scanned pages + hashes → human completeness verification → identity resolution → legacy linked documents → new native digital encounter → compliant sign/confirm and no provenance forgery.

## 5. Incremental milestones (independent of arbitrary delivery promises)

| Milestone | Implementation target | Exit conditions |
|---|---|---|
| M0 Evidence | 2 partner-clinic process maps, form inventory, Sở Y tế/legal confirmation | signed clinical workflow and regulatory matrix |
| M1 Foundations | auth, tenant routing, provenance, migrations, security, backups | tenant isolation and restore tests |
| M2 Patient/encounter | identity, contacts, encounters, legacy importer | patient and paper migration goldens |
| M3 Clinical core | odontogram, notes, diagnoses/findings, clinical documents, signing adapter | form 16/BV-01 mapping, immutable signature evidence |
| M4 Scheduling | shifts, chair/clinician bookings, waiting list and conflicts | concurrency and safety constraints validated |
| M5 Treatment journey | plan versions, tasks, lab dependencies | clinic-approved multi-stage goldens |
| M6 Finance/inventory | charges, deposits, ledger, stock movements, reports | transaction/inventory consistency verified |
| M7 Interop | export official forms, DICOM adapter, FHIR mapping as required | complete export/import tests without ID mismatch |
| M8 Pilot | secure environment, staff training, failover SOP, operations | explicit clinic signoff, no unresolved critical defects |
| M9 AI | dictation, assistant, safe operations suggestions | expert evaluation, provenance and clinician review |

**Parallelism recommendation:** After M1, clinical form/domain and UX prototypes can run in parallel; avoid building billing integration before clinical/finance aggregate contracts are frozen. AI and imaging experiments use only synthetic/de-identified licensed test data until approved.

## 6. Operational validation at a clinic

Target 2–3 clinics, one paper-first and one existing digital software if possible. Observe 5 consecutive sample visits each with staff supervision (not a representative study); map time to find chart, complete note, schedule return, confirm availability and produce invoice. Pilot measurement should compare identical work, not feature counts. Clinical safety and legal compliance are **hard gates** independent of time saved.

## 7. Agent coding protocol

1. Inspect all doc files + ADRs before writing code; report unresolved source/clinical questions.
2. Take one feature or invariant per change; produce data contract, migration, tests, minimal UI.
3. Write negative tests first for cross-clinic access, signed record edits, duplicate booking, failure rollback and incomplete form.
4. Run unit, integration, contract, migration, load, restore and role authorization tests applicable to the change; report precisely what ran.
5. Never add medical claim, consent text, signature method or retention duration without signed domain/legal owner input.
6. Update architecture decision register, tests and source-to-requirement traceability at each accepted change.
7. Never use real patient files in coding agent context, PR attachments, CI, image/LLM services or demo without approved governance.
8. Before pilot, independent human clinical and security review must inspect deployment and all data-handling paths.

## 8. Immediate deliverables to commission from coding agents

- `ADR-001`: tenant isolation and data ownership, with realistic restore/run cost evaluation.
- `ADR-002`: signed clinical-document lifecycle, signature provider abstraction and correction process.
- `ADR-003`: identity/encounter/odontogram relationships validated against 16/BV-01 and clinical workflows.
- Domain-event inventory with outbox contract for scheduling, clinical signatures and payments.
- PostgreSQL schema + cross-tenant FKs, resource booking exclusion and migrations.
- Typed state machines (encounter, document, plan, lab, payment); pure domain tests.
- Form regulatory mapping registry with evidence, versioning and proof of full record export.
- Deployment threat model, VPN/secrets/KMS, backup restore playbook and local patient-data policy.
- Synthetic test scenario corpus, failure injection and CI quality gates.

## 9. What must not be inferred from the research

- No certified compliance or legal approval was obtained.
- No specific dentist/clinic work process has been directly observed or validated in this research session.
- No live infrastructure or database migration was deployed/tested.
- No quantified performance of proposed AI or optimization algorithms has been measured.
- No medical treatment protocol has been endorsed by a licensed dentist.
