# Denlyra testing, safety acceptance and release gates

## Starter demonstrated test scope
Backend tests cover explicit demo mode, loopback guard, patient/clinic-scoped operations, sequential appointment conflicts, cancellation, notes/revision locking/addenda, plan dependencies/version cloning, lab states, charge/payment allocation and money validation. Test count is not a clinical safety score. SQLite tests do NOT validate PostgreSQL concurrent exclusion or production authentication.

## Automated quality levels
**Unit/domain:** state machines, money, date/time, plan graph, tooth mapping, note immutability, provenance. **API:** auth/tenant/role object boundaries, validation, idempotency, version optimistic concurrency. **Database integration:** PostgreSQL migration from empty and previous version, active resource EXCLUDE race, FKs, rollback, isolation. **E2E:** role-specific workflow via Playwright, accessibility, mobile tablet. **Security:** ASVS, CSRF/XSS/SSRF/file upload attacks, auth bypass, PHI leakage, role escalation. **Clinical:** licensed dentist verifies content/form/record artifacts and observed workflows. **Ops:** backup restore across DB/objects/media/signatures, degraded provider, key loss, failover.

## Must-pass negative scenarios
| ID | Scenario | Expected result |
|---|---|---|
| NEG-01 | User A requests Clinic B patient | 403/404 and no leaked data |
| NEG-02 | Two concurrent chair bookings | exactly one successful transaction (PostgreSQL integration) |
| NEG-03 | Signer tries to authenticate modified content | fail and log, old authenticated version preserved |
| NEG-04 | Draft updated from stale revision | 409, no update |
| NEG-05 | Treatment plan reviewed version edited directly | 409; new version required |
| NEG-06 | Task completed before prerequisite | fail, no clinical procedure implied |
| NEG-07 | Payment created for not-performed plan | encounter/performed procedure state unchanged |
| NEG-08 | Duplicate payment webhook | one accepted financial event |
| NEG-09 | Labo delivered but not verified | appointment remains blocked if verification required |
| NEG-10 | Legacy scan missing page | cannot mark verified complete |
| NEG-11 | AI voice invents allergy/diagnosis/tooth number | flagged/rejected before clinical signing |
| NEG-12 | PHI in prompt injected instruction | no external calls/unauthorized access |
| NEG-13 | Object store restore missing X-ray | manifest consistency check fails |
| NEG-14 | Offline signature provider times out | document remains unsigned/draft |
| NEG-15 | Revoked staff accesses prior URL | access denied; signed historic record persists |
| NEG-16 | Form updated after prior signed record | old exact signed bytes remain verifiable |
| NEG-17 | Receipt accidentally re-submitted | idempotency prevents double posting |
| NEG-18 | Unauthorized patient/guardian views internal note | denied, audit |
| NEG-19 | Staff refreshes booking in two browser tabs | no duplicates; known state returned |
| NEG-20 | Changed regulation arrives unreviewed | no automatic EMR compliance claim/form activation |

## Golden end-to-end test flows
1. Outpatient 16/BV-01 compatible encounter from intake to validated authenticated export (future, blocked until clinical/legal review).
2. Orthodontic plan version 1 → changes → version 2, task dependencies, lab/finance separate.
3. Prosthetic lab handoff → received → quality verified → follow-up scheduling.
4. Paper folder migration with incomplete pages, metadata preservation, valid source linking.
5. PHI isolation in backend queries, object URLs, caches, AI retrieval, exports and logs.
6. Restore DB, DICOM objects, signed documents and encryption keys from disaster snapshot.

## Test hardware and baseline
Reference setup must include Windows 10/11 workstation with 8/16 GB RAM, a typical clinic tablet, Chrome/Edge and clinic-network test. Do not invent throughput/latency outcomes. Record exact machine, load, row counts, memory and P95. No clinical data in load fixtures.

## CI stages
`static` (secret scan, lint/typing, dependency/license review), `backend` (pytest), `schema` (migration checks), `postgres` (integration/concurrency), `web` (build/types/e2e), `security` (role and tenant tests, dependency vulnerability), `clinical` (reviewed regression artifacts), `release` (signed binaries/deployment and restores). Stages without infrastructure must be marked unverified, not green.

## Production release checklist
- Medical director signs off on workflows and form mapping for target clinic.
- Counsel validates legal compliance/scope and signature/retention methods.
- Independent security review and penetration testing with issues resolved.
- Postgres concurrency, authorization, migration, backup and restore verified.
- No AI generation is treated as clinician-authenticated without review.
- Operational owner, on-call, support, incident reporting, data export and exit plan documented.
- No high/critical unmitigated PHI or patient safety risks.
- Brand clearance and valid software/service terms completed.
