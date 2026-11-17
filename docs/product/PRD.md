# Denlyra PRD v0.1 — Full dental practice operating system

Owner: project lead · Date 2026-11-17 · Status: design hypotheses, requires 2–3 partner-clinic review.

## Vision and problem
For a Vietnamese private dental clinic, deliver a reliable operating system connecting patient registration, dentist/assistant/front desk workflow, charting, multi-stage treatment, scheduling, laboratory, consent, payment, supplies, communication, owner reporting and regulated record keeping, minimizing duplicate entry and silent mistakes.

**Do not position as a medical decision system.** Product is clinician-controlled. AI can draft and recommend administrative actions; only qualified users make clinical decisions and authenticate legal records.

## Target initial customer
Independent or small-group dental clinics (2–8 chairs) with multi-stage orthodontic, prosthetic, restorative or implant treatment; first validate in 2–3 actual clinics. Users: owner, clinical director, dentist, assistant, receptionist, treatment coordinator, finance/inventory manager, authorized lab partner, patient/guardian. Distinguish license-holding clinic entity vs commercial organization and operating branch.

## Key Jobs to Be Done
- **Owner:** see collections, patient retention, chair occupancy, treatment pipeline, operational exceptions without separate Excel spreadsheets.
- **Front desk:** find patient, schedule correct resources, check-in, follow up appointments and balances in 1–2 screens.
- **Dentist:** examine, record chart/findings, review imaging, approve plan and authenticate records without duplicate entry.
- **Assistant:** know chair preparation and instruments required for each scheduled visit, safely record assigned tasks.
- **Treatment coordinator:** track staged plan, consent, lab case, deadlines, follow-ups and patient communication.
- **Billing staff:** reconcile charge/deposit/allocation/refund and produce accurate reporting without deciding clinical completion.
- **Patient:** secure portal with approved appointment details, instructions and payment status; does not see other patients or internal notes.

## Primary commercial promise to test
Reduce handoff mistakes and administrative minutes per treatment journey, keep clinical evidence complete, and make every pending treatment action/charge visible. Assumptions must be measured against existing software, **not just Excel**.

## End-to-end golden workflows
1. New outpatient visit: intake → appointment → check-in → encounter → dental finding/chart → draft note → clinical approval/signature → payment → follow-up → reviewed export.
2. Orthodontic/complex plan: consultation → clinician-approved plan version → patient consent/financial plan → staged visits → reassessment → changes with approval → completion/retention.
3. Prosthetic lab: approved requisition → lab file bundle → acknowledgment → milestones → received/verified → dependent visit → remake with audit.
4. Paper-to-EMR conversion: physical folder provenance → scanned-page manifest → completeness checks → reviewed patient match → legacy archive + new native digital encounter.
5. Exception/revenue flow: appointment late, lab delayed, missing note signature, balance unpaid → assign staff → resolve with evidence → audit.
6. Staff and clinic ops: staff roster → shift → chair/resource booking → equipment/lot readiness → task completion → management report.

## Product priorities
**P0 — core usable clinical-operational workflow (after legal gates):** authenticated patient registry, calendar/booking, encounter + versioned clinical note, versioned treatment planning, billing, basic inventory/lab, roles/audit, export/backup, site-specific form compatibility.
**P1 — operational depth:** multi-branch, lab portal, imaging/DICOM, advanced booking, patient portal, CRM, automated communications, owner analytics, migration tooling, limited AI dictation.
**P2 — advanced:** resource optimization, richer insurance/claims where applicable, advanced AI and predictive no-show, connected ecosystem, approved e-prescription integrations if authorized, managed labs, deep analytics.

## Out of scope until legally and clinically approved
Autonomous diagnosis, prescriptions, treatment recommendation, AI image interpretation, real electronic signature, automatic irreversible financial postings, actual government EMR submissions, unconsented outbound patient messaging, unrestricted offline clinical sync.

## Product experience principles
Fast front-desk calendar; tablet-friendly dental chart; timeline of each treatment with pending task ownership; cross-role handoffs are explicit; health records show source, version, authored/reviewed by; dashboard distinct from source of truth; exportability and reliable patient migration; Vietnamese labels and timezone.

## Nonfunctional targets (hypotheses, not performance claims)
- P95 of common clinic interactions <500ms under tested clinic workload; set device/network baseline during pilot.
- Secure multiuser concurrency; no double-booking, cross-tenant leak or silent signed record overwrite under acceptance tests.
- Restore DB, images and signature evidence consistently in isolated disaster drill.
- Clinician can review AI draft with source before recording.
- Target uptime 99.9% only after verified infrastructure; RPO 15min and RTO 4h are design aspirations, not contracted guarantees.
- Accessibility WCAG 2.2 AA target where practical; keyboard support, screen-reader semantics, low-friction tablet interactions.

## Metrics / activation / retention
Time to register patient, appointment lead time and conflicts, clinical note completion, treatment step overdue rate, lab delay, account collections, corrections, patient portal usage, weekly active staff, net revenue retention, onboarding hours, support cases per clinic and export correctness. NO PHI analytics to third parties without lawful basis and formal security review.

## Commercial model hypotheses
Single-clinic tiers by chairs/roles/feature scope and onboarding migration fee. Prototype price range to validate 0.5–2.5m VND/month depending on support; **not a market fact**. Validate with paid pilot commitments. Cost driver likely clinic onboarding, regulatory assurance, migration and support, not only LLM compute.

## Stop / pivot conditions
If clinics cannot migrate safely, never force switching. If functional coverage is too low, use a restricted non-clinical workflow pilot. If multiple existing products solve the target workflow and clinics see no measurable improvement, reassess segment. Do not use regulatory deadline scare marketing without independent legal confirmation.
