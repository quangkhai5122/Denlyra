# User journeys — role-specific daily workflows

Each story must be observed with a clinic partner before becoming a release requirement. Examples below are synthetic and do not prescribe clinical treatment.

## UJ-01 First patient visit
Receptionist searches duplicate candidates → creates patient after identity review → schedules licensed dentist and suitable chair → check-in → doctor records history, dental findings and approved form → drafts and authenticates note via approved signature provider → cashier records charge/deposit independently → patient confirms allowed follow-up → owner sees event-based dashboard. Failure cases: guardian missing, same phone different patient, doctor absent, signed form mismatch, payment delayed, network failure.

## UJ-02 Multi-stage orthodontic course
Doctor records versioned plan and clinician-approved preconditions → patient consent to correct version → coordinator sets milestones → receptionist schedules resources → assistant confirms equipment → doctor records encounter events → stage transitions by authorized review → unexpected course creates new version with original preserved → clinician-approved follow-up and billing schedule. Failure: phase cannot auto-complete from date or payment, task dependency blocked, patient no-show recorded without clinical inference.

## UJ-03 Prosthetic laboratory case
Clinician approves requisition → coordinator creates case with minimal specs and allowed files → lab accepts (scoped permissions) → production status → delivery/receipt → clinic verifies fit/quality as appropriate → dependent appointment cleared after verified readiness. Failure: delayed case triggers warning, but no automatic clinical reschedule; remake keeps original versions and cost trail.

## UJ-04 Front desk rush-hour
At 8:30 two staff book same chair. Server transaction exclusion denies one with conflict and suggests safe options; patient is not falsely confirmed; staff selects alternate chair/time and informs patient. Waiting room/check-in states track real events, no forced clinical/financial change.

## UJ-05 Charge, deposit and payment
A draft treatment estimate may have a deposit even before a procedure; cashier records money independently. Doctor marks procedure only via authorized clinical event. Payment allocation across charges cannot exceed a charge nor the available payment. Refund/adjustment is a reversing event, not deletion.

## UJ-06 Legacy paper migration
Clinic scans paper folder with page manifest, verifies identity and completeness, stores source provenance, associates original to patient. New visits use native digital records; historical scans retain source=legacy, never falsely certified as digitally signed.

## UJ-07 Patient portal
Authenticated patient/guardian sees appointments, clinically published instructions, consent documents and permitted financial balance. Can request changes and contact clinic; cannot view internal notes or alter clinician-authenticated content.

## UJ-08 Owner multi-branch reporting
Owner sees authorized aggregates for locations, provider schedules, outstanding balances and exception workload; opening a clinical chart requires separate patient/care role and reason. Staff access to one branch never implicitly grants another.

## User adoption test per journey
Observe number of screens, field duplications, interruptions, error corrections, time, staff roles, completion evidence, staff confidence and remaining external Excel/Zalo steps; compare with clinic's incumbent software and repeat one week later.
