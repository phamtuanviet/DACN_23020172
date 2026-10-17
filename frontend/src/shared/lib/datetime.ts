// Mọi ngày giờ hiển thị theo giờ phòng khám, bất kể múi giờ máy người dùng (docs mục 7.6).
import { vi } from "date-fns/locale";
import { formatInTimeZone } from "date-fns-tz";

export const CLINIC_TZ = "Asia/Ho_Chi_Minh";

// Thiết kế dùng "T6 16/10" và "Chủ nhật" (không theo cách viết hoa của date-fns).
const WEEKDAY_SHORT = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
const WEEKDAY_LONG = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];

export function formatDateTime(value: Date | string): string {
  return formatInTimeZone(value, CLINIC_TZ, "EEEE, dd/MM/yyyy HH:mm", { locale: vi });
}

export function formatTime(value: Date | string): string {
  return formatInTimeZone(value, CLINIC_TZ, "HH:mm", { locale: vi });
}

/** Ngày địa phương "YYYY-MM-DD" (như date_from của API) → Date lúc 00:00 UTC, chỉ để tính thứ. */
function parseDay(day: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!match) throw new Error(`Ngày không hợp lệ: ${day}`);
  return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
}

function dayMonth(date: Date): string {
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}`;
}

export function isValidDay(day: string): boolean {
  try {
    return parseDay(day).toISOString().slice(0, 10) === day;
  } catch {
    return false;
  }
}

/** "T6 16/10" */
export function formatDayShort(day: string): string {
  const date = parseDay(day);
  return `${WEEKDAY_SHORT[date.getUTCDay()]} ${dayMonth(date)}`;
}

/** "Thứ Sáu 16/10" */
export function formatDayLong(day: string): string {
  const date = parseDay(day);
  return `${WEEKDAY_LONG[date.getUTCDay()]} ${dayMonth(date)}`;
}

/** "Thứ Bảy, 17/10/2026" */
export function formatDayFull(day: string): string {
  const date = parseDay(day);
  return `${WEEKDAY_LONG[date.getUTCDay()]}, ${dayMonth(date)}/${date.getUTCFullYear()}`;
}

/** Tên thứ theo số của API: 1 = Thứ Hai … 7 = Chủ nhật. */
export function weekdayName(isoWeekday: number): string {
  return WEEKDAY_LONG[isoWeekday % 7] ?? "";
}

/** Ngày địa phương của một thời điểm, dạng "YYYY-MM-DD". */
export function clinicDay(value: Date | string): string {
  return formatInTimeZone(value, CLINIC_TZ, "yyyy-MM-dd");
}

export function todayInClinic(): string {
  return clinicDay(new Date());
}

export function addDays(day: string, days: number): string {
  const date = parseDay(day);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** Giờ bắt đầu một khung: "T6 16/10, 08:00". */
export function formatSlot(value: string): string {
  return `${formatDayShort(clinicDay(value))}, ${formatTime(value)}`;
}

/** "Thứ Sáu 16/10, 08:00" */
export function formatSlotLong(value: string): string {
  return `${formatDayLong(clinicDay(value))}, ${formatTime(value)}`;
}
