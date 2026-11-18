"""Maintain the product specification as stable machine-readable IDs + human acceptance text."""
from pathlib import Path
from collections import Counter

CATALOG = {
"ORG — Organization and staff identity": """
ORG-001|P0|Clinic/legal entity profile and licensed facility metadata|Store license type, scope, verification status; never infer permission from display name.
ORG-002|P0|Clinic branch registration and ownership|Each branch has distinct identifier; role grants scoped to permitted clinic/branch.
ORG-003|P0|Staff profile and employment status|Deactivate without deleting authored encounter history.
ORG-004|P0|Role-based access management|Deny all capabilities not granted; role changes audited.
ORG-005|P0|Session authentication and MFA|Sensitive actions require real identity; demo actor headers forbidden.
ORG-006|P0|Clinical professional permissions|Only credential-verified role can approve relevant clinical steps.
ORG-007|P1|Multiple branch owner dashboard|Owner can see authorized aggregates, not automatically all patient charts.
ORG-008|P1|Work schedule, vacation and staff availability|Availability updates invalidate pending booking suggestions.
ORG-009|P1|Delegation and temporary access|Access expires automatically and reason is audited.
ORG-010|P2|SSO/enterprise directory integration|OIDC group mapping tested; revoked staff loses access promptly.
ORG-011|P1|Emergency break-glass flow|Documented purpose, short duration and independent after-action review.
""",
"PAT — Patient registration and consent": """
PAT-001|P0|Register patient with durable internal ID|Never use phone number or national ID as PK; duplicate name allowed.
PAT-002|P0|Search patient by authorized fields|Search scoped to clinic; pagination and minimization enabled.
PAT-003|P0|Patient history and verified demographics|Unknown values distinct from negatives; record source and update actor.
PAT-004|P0|Related person/guardian relationships|Age/authority and scope checked before dependent consent.
PAT-005|P0|Suspected duplicate queue|Never merge automatically; show evidence and contradictions.
PAT-006|P1|Merge patient records with reversible linkage|Preserve all clinical/financial histories and source IDs; independent confirmation.
PAT-007|P0|Data source/provenance flag|Paper scan and digitally authored record never have same origin label.
PAT-008|P1|Patient contact preferences|Clinical/legal notice permissions separate from marketing opt-in.
PAT-009|P1|Patient identity confirmation at check-in|Record verifier and method; avoid publishing identity information.
PAT-010|P1|Document expiry and eligibility status|Flag missing/outdated forms without altering existing signed data.
PAT-011|P2|Patient data export and access request workflow|Apply legal retention restrictions and verify requester's authority.
""",
"SCH — Scheduling, chair and equipment": """
SCH-001|P0|Define dentist shifts and approved availability|No booking outside authorized clinician availability without reviewed override.
SCH-002|P0|Register chair/resource with clinic scope|Resource identity immutable after bookings exist.
SCH-003|P0|Book appointment with patient, doctor, chair|Simultaneous resources reserved atomically; conflict yields 409.
SCH-004|P0|Cancel appointment without deleting history|Resource released; audit event retained.
SCH-005|P0|Reschedule appointment preserving old slot history|Atomic release/rebook and notification after commit.
SCH-006|P0|Calendar views day/week/provider/chair|Timezone-correct; conflicting reservations visually obvious.
SCH-007|P1|Assistant/equipment resource constraints|Resource combination valid for planned service.
SCH-008|P1|Schedule waiting list|Privacy-safe outreach only with consent and staff confirmation.
SCH-009|P1|Appointment confirmation workflow|Track send/receipt/confirmation states; never infer from transport success.
SCH-010|P1|Check-in and waiting-room queue|Patient status transitions audited; accessible front desk view.
SCH-011|P1|Duration estimates by approved procedure template|Prediction suggests, staff decides; safe fallback.
SCH-012|P1|Scheduling CP-SAT optimizer|No alteration of confirmed appointments absent explicit user action.
SCH-013|P1|Appointment conflicts due to lab readiness|Show blockers and owner; clinician signs off on clinically relevant change.
SCH-014|P2|Cancellation recovery suggestion|Rank allowed slots; respect outreach consent and no clinical priority inference.
SCH-015|P1|Resource downtime and maintenance|Prevent booking chairs/devices marked unavailable.
""",
"EMR — Clinical encounters and chart records": """
EMR-001|P0|Open encounter with patient/clinician/clinic identity|No cross-clinic patient linkage; encounter has valid author.
EMR-002|P0|Record clinical observation with source and time|Unknown, negative and missing differentiated.
EMR-003|P0|Medical/allergy history review|Prominent risk fields; no auto negative from unanswered items.
EMR-004|P0|Versioned clinical draft note|Revision history never silently discarded; expected-version check.
EMR-005|P0|Lock reviewed snapshot in demo|May be demo_locked only; never presented as legal e-signature.
EMR-006|P0|Legal clinical authentication/signature adapter|Only after approved signer identity and legal workflow; hash binds exact content.
EMR-007|P0|Addendum and correction after signature|Original remains accessible; links, actor/time/reason preserved.
EMR-008|P0|Clinical form template registry|Mapping to approved 16/BV-01 version; completeness validation.
EMR-009|P0|Encounter state machine|No completed status without required approved process.
EMR-010|P1|Encounter findings and dental diagnosis|Only clinician-authorized; no LLM direct writes.
EMR-011|P1|Performed procedure evidence|Must be explicitly recorded by authorized clinician; not inferred from payment.
EMR-012|P1|Attachments and clinical photos|Object integrity manifest + patient and encounter associations.
EMR-013|P1|External referral documents|Reviewed origin, patient link and access controls.
EMR-014|P1|Clinical export PDF plus structured archive|Exact signed version, form version, metadata and attachment manifest.
EMR-015|P1|Close/archival workflow|Retention/hold policy applied, exports and events checked.
EMR-016|P2|Medical code sets and mapping|Versioned authoritative terminology; no guessed mappings.
EMR-017|P1|Audit access to sensitive clinical data|Record actor, scope, purpose; no PHI in operational logs.
EMR-018|P1|Workflow checklist on missing signatures|Notify responsible clinician; never fabricate approval.
""",
"ODN — Tooth/odontogram": """
ODN-001|P0|FDI tooth identifiers and quadrant awareness|Unique dental identifiers validated; permanent/primary distinction.
ODN-002|P0|Surface-level observations|Findings linked to specified tooth surface and visit.
ODN-003|P0|Historical odontogram timeline|Past observations retained, not overwritten by latest view.
ODN-004|P1|SVG chart interactive selection|Keyboard/touch accessible; selection mapped to correct tooth.
ODN-005|P0|Procedure-tooth association|Performed status requires clinician event not planned treatment.
ODN-006|P1|Legend / terminology personalization|Clinician-reviewed mapping; never remap history silently.
ODN-007|P1|Tooth restoration/prosthesis representations|Document source and date; chart visible with evidence.
ODN-008|P1|Odontogram export/print|Matches underlying event timeline and approved template.
ODN-009|P2|Longitudinal imaging overlay|No auto diagnosis or unlabeled generated visualization.
ODN-010|P1|Conflict and revision history|Concurrent edit revision failure instead of silent last-write-wins.
""",
"TRT — Multi-stage treatment journey": """
TRT-001|P0|Create draft plan for a patient|Scope to clinic/patient; no automatic clinical approval.
TRT-002|P0|Store immutable numbered plan versions|Old approved/reviewed versions remain accessible.
TRT-003|P0|Create tasks and phases with dependencies|Depend only on tasks in same version; reject cycles.
TRT-004|P0|Clinician plan review and approval adapter|Identity verified, exact version signed; demo uses clearly labeled simulation only.
TRT-005|P0|Begin new version when plan changes|Preserve prior events and approvals; no in-place mutation.
TRT-006|P0|Block task completion if prerequisites missing|Pending dependency -> 409, not forced progression.
TRT-007|P1|Document stage transitions and reassessment|New tasks/events for repeat work; no historical deletion.
TRT-008|P1|Link plan tasks to appointments|Schedule stays authoritative for time/resource booking.
TRT-009|P1|Link task to lab case requisition|Track readiness and scope of lab data shared.
TRT-010|P1|Link task to materials and invoice estimates|No inference performed=charged or paid=performed.
TRT-011|P1|Treatment acceptance and versioned estimate|Patient consent applies to exact version and quoted amount.
TRT-012|P1|Clinical milestone checklist|Clinician-defined criteria and override reason required.
TRT-013|P1|Timeline visualization and overdue work|Display owner, due, blocked reason, evidence.
TRT-014|P1|Treatment pause/cancel/terminate|Retain record, payment history and explanation; legal retention respected.
TRT-015|P2|Reusable templates by specialty|Templates must be clinic-reviewed; never generic medical protocol.
TRT-016|P2|Patient-facing treatment progress|Show only clinician-approved interpretation, not internal notes.
""",
"LAB — Dental laboratory coordination": """
LAB-001|P0|Create lab case linked to patient/clinic|Only share necessary case data; no full chart exposure.
LAB-002|P0|Workflow states requested→accepted→in_progress→ready→received→verified|Reject invalid transition; audit actor.
LAB-003|P1|Lab requisition and technical specification|Clinician-approved details and versions only.
LAB-004|P1|Deadline and delay alerts|Never silently reschedule a clinical appointment.
LAB-005|P1|File bundle and access-controlled share|Signed URL expiry; patient minimization, audit downloads.
LAB-006|P1|Shipment/hand-off receipt|Capture who transferred, when, condition, confirmation.
LAB-007|P1|Case revisions/remakes|Preserve original request, delta and financial consequences.
LAB-008|P1|Lab partner limited portal|Per-case scope and revocable access, no patient search.
LAB-009|P1|Quality verification after receipt|Delivered != clinically accepted; explicit reviewer.
LAB-010|P2|Lab price list and invoicing workflow|Reconcile contracted price and revisions without leaking PHI.
""",
"INV — Inventory, stock and suppliers": """
INV-001|P1|SKU/service material catalog|Stable identifiers, units and approved lot controls.
INV-002|P1|Supplier records|Authorized edits, duplicate detection and purchase provenance.
INV-003|P1|Purchase order and receipt|Separate ordered, delivered, inspected and available quantities.
INV-004|P1|Lot and expiry tracking|No inventory consumption without traceable lot where needed.
INV-005|P1|Stock movement append-only ledger|Never update balance directly; reclassifications via reversing movement.
INV-006|P1|Material reservation for a planned case|Reservation != consumption; release on cancellation.
INV-007|P1|Consumption linked to authorized procedure|No deduction just because an appointment was made.
INV-008|P1|Low stock and reorder alerts|Based on verified stock and projected demand, configurable thresholds.
INV-009|P2|FEFO picking recommendation|Only where applicable to approved material handling policy.
INV-010|P1|Stock reconciliation and adjustments|Dual control for sensitive corrections; audit & explanation.
""",
"FIN — Financial and revenue cycle": """
FIN-001|P0|Service price catalog per clinic|Versioned price list; no retroactive overwrite of agreed price.
FIN-002|P0|Treatment estimate and versioned acceptance|Exact estimate version and consent preserved.
FIN-003|P0|Record charge independent of clinical completion|Charge does not mark performed procedure.
FIN-004|P0|Record deposit/payment event|Integer VND, unique external reference handling when provider added.
FIN-005|P0|Allocate payments to charges|Cannot exceed available payment or outstanding charge.
FIN-006|P1|Refund/reversal as new ledger event|Original payment retained and cross-linked.
FIN-007|P1|Outstanding balance / aging view|Calculated from ledger, not editable balance field.
FIN-008|P1|Installment schedule and reminders|Configurable with reviewed consent; no automatic charge.
FIN-009|P1|Official invoice adapter|Only authorized invoice provider; separate legal and accounting validation.
FIN-010|P1|Daily cashier reconciliation|Reconcile cash/transfer/card separately, show unexplained differences.
FIN-011|P1|Clinic revenue dashboard|Distinguish billed, collected, refunded and planned production.
FIN-012|P2|Insurance/third-party claim processing|Only where applicable and partner-integrated.
FIN-013|P1|Receipts and signed financial exports|Source and version traceability; no fabricated bank receipts.
FIN-014|P1|Discount and override approval workflow|Immutable explanation for adjustments; no hidden treatment change.
""",
"CRM — Patient communications and retention": """
CRM-001|P1|Contact timeline|Internal and patient-visible content differentiated.
CRM-002|P1|Appointment reminder templates|Source-reviewed wording, approved send window and consent.
CRM-003|P1|Confirmations and response tracking|Delivered != read != confirmed.
CRM-004|P1|Treatment coordinator follow-up queue|Assigned owner, reason, due date, closure evidence.
CRM-005|P1|Patient recall programs|Clinician-approved timing, do-not-contact and opt-out respected.
CRM-006|P1|Zalo OA/ZNS integration|Only official APIs/contracts, legal basis and pricing confirmed.
CRM-007|P1|SMS integration|Provider-specific delivery evidence and opt-out controls.
CRM-008|P2|Email integration|Clinic-verified sender, rate limits, safe templates.
CRM-009|P1|Complaint and service recovery queue|Private notes limited to authorized staff.
CRM-010|P1|Consent-specific marketing automation|Separate from clinical care notices and signatures.
CRM-011|P1|Patient satisfaction form|Anonymization and confidentiality designed; not manipulative.
CRM-012|P2|Automated cancellation slot recovery|No clinical prioritization without approved clinic policy.
""",
"PORT — Patient portal": """
PORT-001|P1|Secure patient identity and portal access|Verified authentication, guardian-specific access scope.
PORT-002|P1|View approved appointments|No third-party personal data leaked.
PORT-003|P1|Confirm or request reschedule|Clinician/chair booking validated before change committed.
PORT-004|P1|View clinician-approved instructions|Only published approved content; no draft notes.
PORT-005|P1|Treatment timeline summary|Approved lay summary, not raw internal professional notes.
PORT-006|P1|Patient forms and intake|Versioned, provenance, legal consent distinguished from contact data.
PORT-007|P1|View balance and payment history|Financial scope and payer identity verified.
PORT-008|P2|Secure file upload|Malware scanning, content limits, quarantine, authorized review.
PORT-009|P2|Guardian portal access|Age/authority status, delegation & revocation.
PORT-010|P2|Patient support secure messaging|Triage urgency messages to human, no autonomous medical advice.
""",
"HR — Staff, quality and operations": """
HR-001|P1|Staff calendar and attendance|Does not affect licensed credentials or clinical authorship.
HR-002|P1|Assistant preparation checklists|Task ownership and close evidence per appointment.
HR-003|P1|Chair turnover / sanitation tasks|Site-approved protocols, no AI-generated procedural standards.
HR-004|P1|Equipment maintenance schedule|Blocks booking when unsafe/unavailable.
HR-005|P1|Staff task assignment and escalations|Overdue owner and action history.
HR-006|P1|Internal handoff messaging|Permissioned and tied to patient/task, audit access.
HR-007|P2|Commission/payroll support|Clinically performed vs financially collected separated; payroll legal review.
HR-008|P1|Quality incident reporting|Escalation, evidence and protected reporting; no diagnosis by AI.
HR-009|P2|Staff training and competency status|Expired competence prevents restricted procedures/assignments where policy applies.
HR-010|P1|Working hours and overtime analysis|Timezone-correct and clinic-approved policies.
""",
"RPT — Analytics and owner reporting": """
RPT-001|P1|Daily clinic operational dashboard|Metrics attributable to source events and clinic.
RPT-002|P1|Chair utilization and idle time|Scheduled ≠ actual utilized; show definition and source.
RPT-003|P1|Appointment no-show/cancellation analysis|No-show defined and corrected with evidence.
RPT-004|P1|Patient retention and follow-up rate|Denominator and exclusion definitions documented.
RPT-005|P1|Treatment plan pipeline|Draft, accepted, in progress, completed statuses distinct.
RPT-006|P1|Billing vs collection report|Accrual/service view not equated to cash.
RPT-007|P1|Laboratory turnaround exceptions|Actual milestones, not optimistic inferred dates.
RPT-008|P1|Inventory shrinkage and expiry dashboard|From confirmed movements and lot policies.
RPT-009|P2|Multi-branch aggregates|Owner permissions respected; patient charts not indiscriminately pooled.
RPT-010|P2|Report scheduled exports|No PHI by default; recipient and encryption controls.
RPT-011|P1|Metric dictionary and lineage|Every KPI has formula, events, refresh timestamp and review owner.
""",
"AI — Operational AI and evaluation": """
AI-001|P1|Vietnamese speech transcription draft|Audio consent, terminology benchmark, no direct EMR write.
AI-002|P1|Structured extraction from dictation|Schema validation, source transcript spans, abstention.
AI-003|P1|Draft clinical note for clinician review|Never auto-sign or claim completeness.
AI-004|P1|Longitudinal clinical timeline summary|Source-linked, clinic-scoped, no inferred diagnosis.
AI-005|P1|Policy-aware operations assistant|Allowlisted read tools and human-confirmed write tools only.
AI-006|P1|Patient communication drafting|Reviewed templates, escalation, consent controls.
AI-007|P2|No-show risk modeling|Calibrated, fair, human schedule confirmation, clear fallback.
AI-008|P2|Scheduling optimization with CP-SAT|Human approves changes; solver timeout leaves existing bookings.
AI-009|P1|AI evaluation harness|Held-out clinical cases labeled by expert, robust negative cases.
AI-010|P1|Prompt injection and exfiltration tests|Imported notes/files treated as untrusted data.
AI-011|P1|AI vendor/model registry|Exact model digest, license, data processor location, consent scope.
AI-012|P2|LoRA/QLoRA adaptation|Only licensed/deidentified data and measurable lift over baseline.
AI-013|P2|AI radiology diagnosis research|Blocked until device/medical AI regulatory and clinical validation.
AI-014|P1|AI feature switch and human override|Clinical core works without model/network.
""",
"INT — External integration and interchange": """
INT-001|P1|Versioned OpenAPI and typed TS client|No manually diverging duplicate schemas.
INT-002|P1|FHIR R4 Patient/Practitioner/Appointment/Encounter mapping|Versioned local profiles with structured validation.
INT-003|P1|Clinical document export including Provenance|Signer evidence only when real provider integrated.
INT-004|P1|DICOM gateway and OHIF viewer|Patient ID mapping verified, device support confirmed per clinic.
INT-005|P1|Laboratory partner adapter|Case-scoped records and evidence of delivery, retry idempotent.
INT-006|P1|Official e-signature provider integration|Vendor legal scope and signature validation required.
INT-007|P1|Messaging provider integration|Zalo/SMS consent, opt-out and delivery state.
INT-008|P1|Payment provider integration|Signed webhooks, replay protection, reconciliation and reversals.
INT-009|P1|e-invoice/accounting integration|No assumed government API, certified provider workflow where required.
INT-010|P2|Authorized government health data integration|Legal permission, tested data schema, identity and audit.
INT-011|P1|Transactional outbox and webhook retry|At-least-once event delivery with idempotent consumers.
INT-012|P1|Import/export from incumbent systems|Licensed data access, source hashes, mapping, reviewer signoff.
""",
"MIG — Paper/legacy data migration": """
MIG-001|P0|Legacy source inventory|Track origin, paper folder ID, page counts and creator.
MIG-002|P0|Scanning ingestion quarantine|No real documents in CI; encrypted quarantine, access limits.
MIG-003|P0|Page completeness verification|Missing pages block verified status.
MIG-004|P1|OCR extraction proposals with confidence|Human validates; OCR text not authoritative clinical record.
MIG-005|P1|Patient match candidate review|False merges detected, no auto finalization.
MIG-006|P1|Archive original scan and digest|Source provenance and chain of custody retained.
MIG-007|P1|Old signed document preservation|Cannot relabel old paper scan as newly digitally signed.
MIG-008|P1|Incremental import and reconciliation report|Counts, missing fields, invalid references, rollback plan.
MIG-009|P1|Former software adapter|Validate export rights, structure and historical integrity.
MIG-010|P1|Cutover and parallel-run plan|No uncontrolled double entry or patient safety risk.
""",
"SEC — Privacy, regulatory, authentication": """
SEC-001|P0|Real authentication and session management|MFA, rate limits, key/session rotation, revocation; demo headers removed.
SEC-002|P0|Clinic/branch and patient authorization|Negative tenant/role tests for every endpoint.
SEC-003|P0|Explicit legal signature governance|Human-approved provider/method, exact content and audit.
SEC-004|P0|Clinical record amendment policy|No unsigned mutation to signed history; additive corrections.
SEC-005|P0|Regulatory form requirements matrix|Direct legal citation, effective date, reviewer, acceptance test.
SEC-006|P0|Encrypted clinical data and keys|Encryption at rest and in transit, no keys in source or backups.
SEC-007|P0|Audit journal tamper evidence|Separate protected digest/immutable storage, tested integrity.
SEC-008|P0|Backup and full archive restore drill|DB+files+images+signatures+keys consistent.
SEC-009|P0|Data protection impact/compliance assessment|Qualified review before real patient data.
SEC-010|P1|Consent/withdrawal and data subject requests|Purpose and retention separated; no illegal clinical deletion.
SEC-011|P1|Retention and legal hold by document class|Exact rule approved; no arbitrary universal retention years.
SEC-012|P1|Incident response and breach workflow|Evidence preservation, triage, counsel guidance and notifications.
SEC-013|P1|Software supply chain hardening|Lockfiles, SBOM, signing, scan, vulnerability updates.
SEC-014|P1|Penetration and authorization testing|OWASP ASVS, role/tenant/CSRF/SSRF, file attack cases.
SEC-015|P0|Production release gating|Independent clinical and security signoff before enabled PHI processing.
""",
"OPS — Platform, DevOps, reliability": """
OPS-001|P0|Local synthetic setup and seed|No production deployment permitted from demo build.
OPS-002|P0|Versioned schema migrations|Production reviewed Alembic steps, backup before irreversible change.
OPS-003|P1|IaC for Vietnam-region hosting|Verified region and privacy contracts, secrets externalized.
OPS-004|P1|CI backend, web, API contract and DB tests|No PHI fixtures; fail on security invariant regressions.
OPS-005|P1|Application logging/tracing with redaction|Never record clinical note text or identifiable patient in telemetry.
OPS-006|P1|Encrypted media/object storage|Manifest, integrity hash, scoped retrieval and key rotation.
OPS-007|P1|PITR and cross-store disaster recovery|Restore metadata + images + signatures consistently.
OPS-008|P1|Autoscaling and load tests|Reference load, P95 and capacity report, never invented SLA.
OPS-009|P1|Release/rollback/runbook and change approvals|Canary deployment, migration compatibility, rollback/forward plan.
OPS-010|P1|Per-clinic onboarding/configuration workflow|Clinic role, service catalog, forms and data mapping separately configured.
OPS-011|P2|Multi-branch operator management|Shared owner dashboard while preserving clinical access scopes.
OPS-012|P1|Support tooling with customer consent|No silent access to live patient records or debug exports.
OPS-013|P2|Offline continuity policy and safe sync design|No last-write-wins for signed clinical data or bookings.
""",
}

IMPLEMENTED = {
    "ORG-002", "ORG-003", "ORG-004", "ORG-005", "ORG-006", "PAT-001", "PAT-004", "PAT-005",
    "PAT-007", "PAT-008", "SCH-002", "SCH-003", "SCH-004", "SCH-005", "SCH-007", "SCH-013",
    "EMR-001", "EMR-002", "EMR-004", "EMR-005", "EMR-006", "EMR-007", "EMR-008", "EMR-017",
    "TRT-001", "TRT-002", "TRT-003", "TRT-005", "TRT-006", "TRT-007", "TRT-008", "TRT-009",
    "TRT-010", "TRT-011", "TRT-013", "LAB-001", "LAB-002", "LAB-003", "LAB-004", "LAB-005",
    "LAB-006", "LAB-007", "LAB-008", "LAB-009", "ODN-001", "ODN-002", "ODN-003", "FIN-002",
    "FIN-003", "FIN-004", "FIN-005", "FIN-006", "FIN-007", "FIN-010", "FIN-011", "INT-005",
    "INT-011", "MIG-001", "MIG-002", "MIG-003", "MIG-004", "MIG-005", "MIG-006", "MIG-007",
    "MIG-008", "SEC-001", "SEC-002", "SEC-004", "SEC-010", "OPS-001", "OPS-002", "OPS-004",
}
# The codes marked "D" represent synthetic demo behavior ONLY, not production implementations.


def main():
    out = [
        "# Functional Specification — Denlyra complete product catalog",
        "",
        "Version 0.1 · 2026-11-17 · Proposed, requires clinic review · Generated by `scripts/generate_function_catalog.py`.",
        "",
        "**Status legend:** `D` = demo-only partial implementation (NOT secure/clinical-ready); `—` = not implemented. "
        "Priority `P0` = foundational before full single-clinic alpha; `P1` = operation depth; `P2` = later/conditional.",
        "",
        "**Release gate:** A row marked `D` does NOT meet production acceptance. Each medical/EMR feature requires review, security "
        "and legal evidence. Priority is not authorization to release.",
        "",
        "| ID | Priority | Status | Requirement | Acceptance / negative behavior |",
        "|---|---|---|---|---|",
    ]
    seen = set()
    n = 0
    for group, records in CATALOG.items():
        out += ["", f"## {group}", "", "| ID | Priority | Status | Requirement | Acceptance / negative behavior |", "|---|---|---|---|---|"]
        for line in records.strip().splitlines():
            key, priority, desc, accept = [x.strip() for x in line.split("|", 3)]
            assert key not in seen, key
            seen.add(key)
            assert priority in {"P0", "P1", "P2"}
            status = "D" if key in IMPLEMENTED else "—"
            out.append(f"| `{key}` | {priority} | {status} | {desc} | {accept} |")
            n += 1
    out += ["", f"**Total feature requirements: {n}.**", "",
            "## Feature completion protocol", "",
            "For each ID, create a task packet with preconditions, domain contracts, permission matrix, "
            "legal-source evidence, API/schema, negative tests, migration/rollback, documentation and reviewer. "
            "Only mark production implemented when every criterion, including integration/security/clinical sign-off, passes.",
            "", "## Invariant cross references", "",
            "See `docs/architecture/DOMAIN_MODEL.md` and `docs/engineering/TEST_STRATEGY.md` for cross-context "
            "business invariants and release gates. See `docs/clinical/REGULATORY_MATRIX.md` for legal ownership.", ""]
    path=Path("docs/product/FUNCTION_CATALOG.md")
    path.write_text("\n".join(out),encoding="utf-8",newline="\n")
    print("Generated",n,"functions across",len(CATALOG),"domains; demo flags",len(IMPLEMENTED))


if __name__ == "__main__":
    main()
