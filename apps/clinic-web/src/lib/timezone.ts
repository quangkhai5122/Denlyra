/**
 * Fixed clinic timezone and integer VND utilities (T009 / R-011 / INV-019).
 *
 * All clinical and scheduling timestamps are stored in UTC on the server and MUST be
 * displayed and authored in explicit clinic timezone `Asia/Ho_Chi_Minh` (UTC+07:00),
 * independent of the workstation browser's OS timezone setting.
 */

export const CLINIC_TIMEZONE = "Asia/Ho_Chi_Minh" as const;
export const CLINIC_OFFSET_SUFFIX = "+07:00" as const;

const dtfDateTime = new Intl.DateTimeFormat("vi-VN", {
  timeZone: CLINIC_TIMEZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const dtfDateKey = new Intl.DateTimeFormat("en-CA", {
  timeZone: CLINIC_TIMEZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const dtfTimeOnly = new Intl.DateTimeFormat("vi-VN", {
  timeZone: CLINIC_TIMEZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function parseIsoInstant(isoUtc: string): Date {
  const normalized =
    isoUtc.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(isoUtc) ? isoUtc : `${isoUtc}Z`;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) {
    throw new Error(`Invalid ISO timestamp: ${isoUtc}`);
  }
  return d;
}

export function formatClinicDateTime(isoUtc: string): string {
  const d = parseIsoInstant(isoUtc);
  return `${dtfDateTime.format(d)} (GMT+7)`;
}

export function getClinicDateKey(isoUtc: string): string {
  return dtfDateKey.format(parseIsoInstant(isoUtc));
}

export function formatClinicSlot(startUtc: string, endUtc: string): string {
  const s = parseIsoInstant(startUtc);
  const e = parseIsoInstant(endUtc);
  return `${dtfTimeOnly.format(s)}–${dtfTimeOnly.format(e)} · ${dtfDateKey.format(s)} (+07:00)`;
}

export function buildHoChiMinhIso(dateYmd: string, timeHm: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateYmd)) {
    throw new Error("Date must be YYYY-MM-DD");
  }
  if (!/^\d{2}:\d{2}$/.test(timeHm)) {
    throw new Error("Time must be HH:MM");
  }
  return `${dateYmd}T${timeHm}:00${CLINIC_OFFSET_SUFFIX}`;
}

export function formatVndInteger(amountVnd: number): string {
  if (!Number.isInteger(amountVnd)) {
    throw new Error("INV-019 violation: VND currency must be an exact integer");
  }
  return `${amountVnd.toLocaleString("vi-VN")} ₫`;
}
