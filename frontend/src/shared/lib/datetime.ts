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

/** "08:00–08:20" */
export function formatTimeRange(start: string, end: string): string {
  return `${formatTime(start)}–${formatTime(end)}`;
}

/** "12/10/2026 20:05" — mốc thời gian trong lịch sử thay đổi. */
export function formatStamp(value: string): string {
  return formatInTimeZone(value, CLINIC_TZ, "dd/MM/yyyy HH:mm");
}

/** Ô ngày trên thẻ lịch hẹn: { weekday: "T7", day: "17", month: "Th10" }. */
export function dayBadge(value: string): { weekday: string; day: string; month: string } {
  const date = parseDay(clinicDay(value));
  return {
    weekday: WEEKDAY_SHORT[date.getUTCDay()] ?? "",
    day: String(date.getUTCDate()),
    month: `Th${date.getUTCMonth() + 1}`,
  };
}

/** Tháng "YYYY-MM" của một ngày "YYYY-MM-DD". */
export function monthOf(day: string): string {
  return day.slice(0, 7);
}

/** "2026-10" + 1 → "2026-11". */
export function addMonths(month: string, months: number): string {
  const [year, monthNumber] = month.split("-").map(Number) as [number, number];
  const date = new Date(Date.UTC(year, monthNumber - 1 + months, 1));
  return date.toISOString().slice(0, 7);
}

/** "Tháng 10/2026" */
export function formatMonth(month: string): string {
  const [year, monthNumber] = month.split("-").map(Number) as [number, number];
  return `Tháng ${monthNumber}/${year}`;
}

/** Các ngày của tháng, kèm số ô trống đầu tuần để lưới lịch bắt đầu từ Thứ Hai. */
export function monthGrid(month: string): { leading: number; days: string[] } {
  const first = parseDay(`${month}-01`);
  const leading = (first.getUTCDay() + 6) % 7; // Thứ Hai = 0
  const days: string[] = [];
  for (let day = `${month}-01`; monthOf(day) === month; day = addDays(day, 1)) days.push(day);
  return { leading, days };
}

/** Số ngày từ `from` tới `to` (cùng dạng "YYYY-MM-DD"). */
export function daysBetween(from: string, to: string): number {
  return Math.round((parseDay(to).getTime() - parseDay(from).getTime()) / 86_400_000);
}
