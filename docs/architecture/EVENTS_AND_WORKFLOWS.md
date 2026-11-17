# Cross-context workflows, commands, events and failure patterns

## Rule of one authority
A command changes exactly its owning aggregate. Other contexts are informed via explicit events or orchestration. Events are descriptive, not instructions from LLM. The event/outbox data should carry tenant, aggregate ID, version, event ID, timestamp, causation ID, actor and minimal payload.

## Example 1: appointment confirm
1. Authenticate front desk; verify clinic role and patient access.
2. Validate doctor availability, duration, consent/outreach constraints and chair/equipment suitability.
3. Under a transaction insert Appointment, clinician+chair resource reservations, Event and Outbox.
4. Let PostgreSQL EXCLUDE detect overlap across concurrent requests; on conflict respond with 409 and safe slot suggestions.
5. Worker processes outbox, looks up allowed contact preference, sends reminder only through authorized provider; retry idempotently.
6. If SMS fails, appointment remains confirmed; delivery status is accurately `failed` not `cancelled`.

## Example 2: multi-stage plan
1. Dentist drafts plan version N, tasks/phases and prerequisites.
2. Human patient consent (separate object) and clinician signature of exact approved plan version where required.
3. Treatment coordinator converts approved task to scheduling requests; no direct DB booking outside scheduling.
4. When lab dependencies exist, lab order created with minimal scoped data; a deadline alert does not clinically decide reschedule.
5. A changed course of treatment creates version N+1; prior approved version and progress history remain.
6. Financial estimate version and payments are linked but not conflated with procedures completed.

## Example 3: note authentication
Draft → optional AI proposed content with transcription spans → clinician edits and confirms → verified identity/e-signature provider signs exact snapshot → immutable archival and audit → later correction through addendum. Failure at any step cannot result in `authenticated` without validated evidence.

## Example 4: patient paper import
Scanned folder with page hashes → quarantine → completeness check → identity matching reviewed → legacy archive attached to patient → new native digital encounter independently created and signed according to approved process. Historical paper scans are never backdated to appear legally digitally signed.

## Failure and idempotency table
| Event | Failure | Correct action |
|---|---|---|
| Payment provider webhook duplicate | Same provider ID re-sent | Idempotency inbox, no second allocation |
| Labo dispatch email times out | Unknown recipient state | Retry with unique id; don't mark received |
| Schedule race | Two users take same resource | DB constraint rejects one, no partial bookings |
| AI service unavailable | Draft generation fails | Manual clinical documentation still works |
| Document archive unavailable | Signed artifact cannot be persisted | Do not claim authentication success; reconcile external signer evidence |
| Consent withdrawal | Marketing consent withdrawn | Stop marketing only, preserve lawfully retained clinical records |
| Staff permission revoked | Cached token still active | Invalidate token/session, deny new sensitive access |
| Network outage | Front desk disconnected | No fake appointment confirmation, incident SOP for continuity |
