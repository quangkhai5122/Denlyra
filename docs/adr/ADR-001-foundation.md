# ADR-001 — Synthetic domain starter and modular monolith
Date 2026-11-17 · Status Accepted for Research, not Production

**Context:** Need AI-Agent-friendly maintainable system spanning medical records, scheduling, multi-stage plans, lab and finance. Cannot claim clinical compliance without site data.
**Decision:** FastAPI + SQLAlchemy modular monolith; SQLite localhost-only demo, PostgreSQL production target; static working UI, Next.js TypeScript optional prototype. Real authentication, signing, image, money provider and clinical AI disabled.
**Alternatives:** immediate microservices, raw FHIR-backed data model, all-in-one JavaScript monorepo, cloud production-first. Rejected for initial complexity/integrity risk.
**Consequences:** small vertical slices and executable tests; no client use until security and regulatory validation. PostgreSQL schema migration must be tested before code promotion.
