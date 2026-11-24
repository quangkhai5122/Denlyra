# Retention, Legal Hold, and Disaster Recovery Policy (Synthetic Pre-Production Draft)

**Status:** Quarantined technical implementation (`T010` / [ADR-010](../adr/ADR-010-encrypted-archive-dr-and-role-workspaces.md)) — **awaits Vietnamese healthcare legal counsel sign-off** ([NEEDS_CLINICAL_REVIEW.md](../clinical/NEEDS_CLINICAL_REVIEW.md)). No real PHI may be stored under this draft policy.

## 1. Archive Scope & Coordinated Stores (`INV-024`)

A complete clinic recovery point requires **five coordinated artifacts** scoped strictly to a single `clinic_id`:

| Store | Contents | Synthetic implementation (`0.1.0`) | Production target before PHI |
|---|---|---|---|
| Relational DB | Patients, encounters, notes, snapshots, consents, ledger, audit | SQLite / PostgreSQL 16 (`0001_demo`..`0005_archive_and_dr`) | PostgreSQL 16 + `pgBackRest` continuous WAL PITR |
| Encrypted Object Store | Clinical attachments, quarantined paper scans (`T006`), snapshot exports | `local_data/archive/objects/<clinic_id>/<id>.bin` (`DLY1` Encrypt-then-MAC) | Versioning-enabled WORM S3/GCS bucket in Vietnam-compliant region |
| Imaging / DICOM Store | Intraoral radiographs, panoramic/CBCT studies | `dicom_study_stub` objects with SHA-256 & study manifest | Orthanc/DICOMweb object store with immutable study UID manifest |
| Signature Evidence | `ClinicalDocumentSnapshot.provider_receipt_json` + canonical SHA-256 | `FakeSyntheticSignatureProvider` receipt verified during drill | Timestamped PKI / MoH-compliant CA signature bundle + OCSP/CRL staple |
| Key Material | Per-clinic versioned wrapped DEKs (`tenant_encryption_key`) | Wrapped under `DENLYRA_ARCHIVE_MASTER_SECRET` (never plaintext in DB) | Dual-custody Cloud KMS / HSM key ring separate from backup storage |

## 2. Provisional Retention & Legal Hold Rules (`INV-018`, `DR-08`)

> [!IMPORTANT]
> Exact statutory retention periods by medical record category (outpatient dental chart, minor/pediatric patient record, implant/surgical record, radiology study, accounting voucher) under **Law 15/2023/QH15** and **Circular 33/2025/TT-BYT** MUST be confirmed by licensed legal counsel before enabling archive expiration in production.

Until legal counsel signs off the retention schedule in [NEEDS_CLINICAL_REVIEW.md](../clinical/NEEDS_CLINICAL_REVIEW.md):
1. **Default conservative quarantine hold:** Every `archive_object` is assigned a provisional `retention_until` of **20 years (7,300 days)** from creation (`clinical_emr_quarantined`, `radiology_dicom_quarantined`, or `financial_record`).
2. **Explicit legal hold:** `clinic_owner` or `medical_director` can place `legal_hold = true` with an audited reason (`POST /api/v1/archive/objects/{id}/legal-hold`) for disputes, quality incidents, or regulatory inquiries.
3. **Fail-closed deletion block (`DR-08`):** `DELETE /api/v1/archive/objects/{id}` is rejected with `409 Conflict` whenever `legal_hold == true` or `utcnow() < retention_until`, recording `archive.deletion_blocked_retention` in `audit_event`. Withdrawing marketing consent (`T007`) never triggers clinical or financial archive deletion.

## 3. Cross-Store Checkpoint Alignment & RPO/RTO Targets

- **Cross-store ordering rule (`DR-05`):** An object-store backup checkpoint MUST NOT be older than any `archive_object` referenced by the relational DB checkpoint (`object_store_checkpoint_at >= max(archive_object.created_at)`). Recommended backup sequence: flush/seal object writes -> checkpoint object bucket -> capture DB checkpoint -> sign `backup_manifest`.
- **Target objectives (to be benchmarked on production sizing before PHI):**
  - **RPO target:** `<= 5 minutes` WAL lag, `0 missing referenced objects` (`rpo_lag_ms` measured in every drill).
  - **RTO target:** `<= 60 minutes` for full single-clinic isolated restore + cryptographic verification (`rto_ms` measured in every drill).

## 4. Mandatory Automated Restore Drill (`DR-04`, `NEG-13`)

Every release candidate and scheduled weekly operational check executes `python scripts/run_dr_restore_drill.py` (or `POST /api/v1/archive/backups/{id}/restore-drill`), which restores into a fresh isolated database and verifies:
1. **Tenant isolation:** Restoring `Clinic A` backup into `Clinic B` fails with `403`.
2. **Manifest integrity:** Tampered `manifest_json` / `manifest_hmac` fails with `409`.
3. **Cross-store freshness (`DR-05`):** Stale `object_store_checkpoint_at` fails with `409` (`stale_object_store_checkpoint`).
4. **Object completeness (`NEG-13`) & tamper detection:** Missing `.bin` blob or altered ciphertext/tag fails with `409`.
5. **Key lifecycle:** Wrong master secret or `revoked` tenant encryption key fails with `409`; rotated `retired_decrypt_only` keys continue to decrypt historical objects cleanly.
6. **Signature verification (`DR-04`):** Missing or invalid `SignatureReceipt` on any `synthetic_signed_NOT_legal` snapshot fails with `409`.
