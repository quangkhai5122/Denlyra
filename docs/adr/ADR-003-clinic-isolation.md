# ADR-003 — Per-clinic logical database target and explicit tenant routing
Date 2026-11-17 · Status Proposed target; current demo NOT isolated securely

**Decision:** Shared stateless application, dedicated logical PostgreSQL DB and archive namespace per licensed clinic initially, separate control plane for non-PHI metadata; verified role+clinic claims from identity provider; never user-supplied context. Dedicated deployment optional.
**Alternatives:** shared DB with RLS, fully isolated apps. Both possible but choose DB-per-clinic initially to simplify backup/restore. Reevaluate operational scaling when clinics exceed measured thresholds.
**Consequences:** Connection pooling and migrations across databases, site-level restore, protected tenant-router control plane. Current demo uses forgeable headers, only to test schema scoping; do not carry into production.
