/**
 * T009 Frontend contract, fixed timezone (R-011), pessimistic 409 handling,
 * security storage hygiene, and WCAG/keyboard accessibility verification suite.
 *
 * Uses Node 24's built-in test runner and native TypeScript module support (zero extra npm bloat).
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  CLINIC_TIMEZONE,
  buildHoChiMinhIso,
  formatClinicDateTime,
  formatClinicSlot,
  formatVndInteger,
  getClinicDateKey,
} from "../src/lib/timezone.ts";
import {
  DenlyraApiClient,
  OPENAPI_OPERATIONS,
} from "../src/lib/generated-api.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC_DIR = path.resolve(__dirname, "..", "src");

test("R-011: clinic timestamps format strictly in Asia/Ho_Chi_Minh (+07:00) across UTC date rollover", () => {
  assert.equal(CLINIC_TIMEZONE, "Asia/Ho_Chi_Minh");
  // 2026-12-01T18:30:00Z is 2026-12-02 01:30 in Ho Chi Minh City (+07:00)
  assert.equal(getClinicDateKey("2026-12-01T18:30:00Z"), "2026-12-02");
  const formatted = formatClinicDateTime("2026-12-01T02:00:00Z");
  assert.match(formatted, /09:00/);
  assert.match(formatted, /GMT\+7/);

  const slot = formatClinicSlot("2026-12-05T02:00:00Z", "2026-12-05T03:00:00Z");
  assert.match(slot, /09:00–10:00/);
  assert.match(slot, /2026-12-05/);

  assert.equal(buildHoChiMinhIso("2026-12-05", "09:15"), "2026-12-05T09:15:00+07:00");
});

test("INV-019: VND formatter accepts integers and rejects floating-point numbers", () => {
  assert.match(formatVndInteger(18000000), /₫$/);
  assert.throws(() => formatVndInteger(150.5), /INV-019/);
});

test("INT-001 & NEG-02: generated DenlyraApiClient sends Bearer token and surfaces HTTP 409 conflicts pessimistically", async () => {
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/auth/token"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/archive/backups/{backup_id}/restore-drill"));
  assert.ok(OPENAPI_OPERATIONS.includes("DELETE /api/v1/archive/objects/{object_id}"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/inventory/consumptions"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/interop/fhir/r4/patients/{patient_id}/bundle"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ai/drafts/dictation-extract"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ai/evaluations/run"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/audit-events/verify-chain"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/patients/page"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/operations/checkins"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/operations/recalls"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/patients/merges"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/auth/break-glass"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/patient-portal/overview"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/finance/price-catalog"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/reports/kpi-lineage"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/patients/{patient_id}/medical-risk-reviews"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/encounters/{encounter_id}/close-demo"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/encounters/{encounter_id}/performed-procedures"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/operations/waitlist"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/finance/installments"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/operations/incidents"));
  assert.ok(OPENAPI_OPERATIONS.includes("PUT /api/v1/patients/{patient_id}/odontogram/restorations/{tooth_code}"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/patients/{patient_id}/odontogram/export"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/clinical-documents/{snapshot_id}/structured-export"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/org/multi-branch-aggregates"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/auth/delegations"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ai/ops-assistant/query"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/org/facility-profile"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/scheduling/optimizer/propose"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/finance/payments/{payment_id}/receipt-exports"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/hr/attendance"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ai/communication-drafts"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/crm/satisfaction/submit"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/migration/cutover-plans"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ops/telemetry-events"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ops/support/diagnostic-export"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/security/incidents"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/security/supply-chain/verify"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/patients/{patient_id}/access-requests"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/patient-portal/uploads"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/patient-portal/support-messages"));
  assert.ok(OPENAPI_OPERATIONS.includes("GET /api/v1/hr/commission-preview"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/terminology/mappings"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/treatment-plans/from-specialty-template"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/lab-cases/{lab_case_id}/invoice-reconciliations"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/patients/{patient_id}/odontogram/imaging-overlays"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/reports/scheduled-exports"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ops/releases"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ops/offline-sync"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ai/scheduling/cpsat-optimize"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/crm/cancellation-outreach-policies"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ops/load-benchmarks/run"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/auth/oidc/directory-sync"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/integrations/messaging-sandbox/send"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/integrations/payment-sandbox/webhook"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/interop/dicom/studies/ingest-manifest"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/ai/speech-drafts/transcribe"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/finance/accounting-exports"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/security/adversarial-suite/run"));
  assert.ok(OPENAPI_OPERATIONS.includes("POST /api/v1/security/release-gates/evaluate"));

  const capturedCalls = [];
  const origFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    capturedCalls.push({ url, init });
    return new Response(
      JSON.stringify({ detail: "Resource already booked for overlapping interval" }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    );
  };

  try {
    const api = new DenlyraApiClient({
      baseUrl: "http://127.0.0.1:3000/api/demo",
      clinicId: "11111111-1111-4111-8111-111111111111",
      accessToken: "synthetic-jwt-in-memory",
    });
    const res = await api.createAppointment({
      patient_id: "pat-1",
      practitioner_id: "doc-1",
      chair_id: "chair-1",
      start_at: "2026-12-05T09:00:00+07:00",
      end_at: "2026-12-05T10:00:00+07:00",
    });
    assert.equal(res.ok, false);
    if (!res.ok) {
      assert.equal(res.status, 409);
      assert.equal(res.conflict, true);
      assert.match(res.detail, /overlapping interval/);
    }
    assert.equal(capturedCalls.length, 1);
    assert.equal(capturedCalls[0].init.headers.Authorization, "Bearer synthetic-jwt-in-memory");
    assert.equal(
      capturedCalls[0].init.headers["X-Demo-Clinic"],
      "11111111-1111-4111-8111-111111111111",
    );
  } finally {
    globalThis.fetch = origFetch;
  }
});

test("Security & Accessibility: FDI Odontogram SVG keyboard support, ARIA roles, and zero Web Storage usage", () => {
  const odontogramSrc = fs.readFileSync(
    path.join(SRC_DIR, "components", "OdontogramSvg.tsx"),
    "utf-8",
  );
  // Permanent (11-48) and Primary (51-85) tooth codes present
  for (const code of ["18", "11", "21", "28", "48", "41", "31", "38", "55", "51", "85", "75"]) {
    assert.ok(odontogramSrc.includes(`"${code}"`), `Missing FDI tooth ${code}`);
  }
  // Keyboard activation (Enter and Space) + ARIA attributes
  assert.match(odontogramSrc, /e\.key === "Enter" \|\| e\.key === " "/);
  assert.match(odontogramSrc, /aria-pressed=\{isSelected\}/);
  assert.match(odontogramSrc, /role="tablist"/);
  assert.match(odontogramSrc, /tabIndex=\{0\}/);

  // Verify zero localStorage / sessionStorage / dangerouslySetInnerHTML across entire clinic-web src
  const walk = (dir) => {
    const out = [];
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, ent.name);
      if (ent.isDirectory()) out.push(...walk(p));
      else if (/\.(ts|tsx)$/.test(ent.name)) out.push(p);
    }
    return out;
  };
  for (const file of walk(SRC_DIR)) {
    const text = fs.readFileSync(file, "utf-8");
    assert.ok(!/\blocalStorage\b/.test(text), `Forbidden localStorage in ${file}`);
    assert.ok(!/\bsessionStorage\b/.test(text), `Forbidden sessionStorage in ${file}`);
    assert.ok(!/dangerouslySetInnerHTML/.test(text), `Forbidden dangerouslySetInnerHTML in ${file}`);
  }

  const pageSrc = fs.readFileSync(path.join(SRC_DIR, "app", "page.tsx"), "utf-8");
  assert.match(pageSrc, /role="alert"/);
  assert.match(pageSrc, /SYNTHETIC DEMO ONLY/);
  assert.match(pageSrc, /synthetic_signed_NOT_legal/);

  const proxySrc = fs.readFileSync(
    path.join(SRC_DIR, "app", "api", "demo", "[...path]", "route.ts"),
    "utf-8",
  );
  assert.match(proxySrc, /isLoopbackSameOrigin/);
  assert.match(proxySrc, /export \{ forward as GET, forward as POST, forward as PUT, forward as DELETE \}/);
});
