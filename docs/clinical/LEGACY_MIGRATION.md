# Paper records and incumbent-software migration strategy

## Objectives
Allow a paper-first clinic to enter digital workflows without losing provenance, forging historical signatures or silently merging patient identities. Migration is a high-risk clinical process, not merely file uploading.

## Staged pipeline
1. **Discovery:** inventory paper archives, folder counts, sheets/encounters, forms in use, imaging devices, patient identifiers and approved retention periods.
2. **Source manifest:** unique paper package ID, operator, timestamp, page count, scan modality, custody log. No patient scans in AI Agent repo.
3. **Quarantine ingestion:** encrypted storage, malware checks for electronic inputs, max file/page limits, SHA256 and access scope.
4. **Page completeness:** every page accounted for; missing/illegible page returns `needs_manual_review`.
5. **Extraction (optional):** OCR output labeled unverified, linked to original page, human validation required.
6. **Identity resolution:** candidate records matched by permitted fields, contradictory matches reviewed, never automatic merge by phone/name.
7. **Clinical validation:** qualified staff confirms correct patient and relevant form mappings, notes limitations/missing values.
8. **Archive:** store original scan and provenance as `legacy_scan`, not as newly signed electronic record.
9. **Cutover:** written SOP for paper handoff, unfinished care, new native records, historic retrieval and legal retention.
10. **Rollback/disaster drill:** independent reconciliation report and signed owner acceptance before broad switch.

## Import contract
`MigrationBatch`: clinic, source system/paper cabinet, manifest hash, adapter version, operator, status, count submitted/verified/missing, time. `MigrationItem`: source ref, patient candidate IDs, clinical references, file hashes, reviewer, decision, exception reason. `MigrationAudit`: append-only, cannot silently rewrite result.

## Minimum migration regression tests
- Same name/similar age are two different people → no merge.
- Same phone for relatives → no merge.
- Paper folder missing page 3/5 → archive as incomplete, not complete EMR.
- Former software exports a modified date format → adapter refuses until versioned mapping approved.
- Historical paper treatment remains source=paper even if OCR text is structured.
- Export/import cycle preserves all clinical document and charge associations.
- Wrong image patient ID triggers quarantine, not an automatic association.
- Cutover fails halfway → original records still available and new writes isolated and recoverable.

## Partner-clinic tasks
Obtain a redacted/fictional sample of every form and file type; document staff steps with screenshots made using fake records; obtain licensed clinician approval; consult counsel on historical paper retention and digital conversion obligations. No AI Agent handles real patient data by default.
