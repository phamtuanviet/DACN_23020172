// Chữ hiển thị cho lịch làm việc của bác sĩ và giờ mở cửa của phòng khám.
import { formatInTimeZone } from "date-fns-tz";

import type { WorkingHours } from "@/shared/api/types";
import { CLINIC_TZ, weekdayName } from "@/shared/lib/datetime";
import { CLINIC } from "@/shared/texts";

export type ScheduleLine = { days: string; hours: string };

const hhmm = (value: string) => value.slice(0, 5);

function formatDays(weekdays: number[]): string {
  const consecutive = weekdays.every((day, i) => i === 0 || day === (weekdays[i - 1] ?? 0) + 1);
  const first = weekdays[0];
  const last = weekdays.at(-1);
  if (consecutive && weekdays.length >= 3 && first !== undefined && last !== undefined) {
    return `${weekdayName(first)} đến ${weekdayName(last)}`;
  }
  return weekdays.map(weekdayName).join(", ");
}

/** Gộp các thứ có cùng giờ làm: "Thứ Hai đến Thứ Sáu: 08:00–11:30 và 13:30–17:00". */
export function summarizeWorkingHours(hours: WorkingHours[]): ScheduleLine[] {
  const byDay = new Map<number, string[]>();
  for (const item of [...hours].sort((a, b) => a.start_time.localeCompare(b.start_time))) {
    const ranges = byDay.get(item.weekday) ?? [];
    ranges.push(`${hhmm(item.start_time)}–${hhmm(item.end_time)}`);
    byDay.set(item.weekday, ranges);
  }
  const groups = new Map<string, number[]>();
  for (const day of [...byDay.keys()].sort((a, b) => a - b)) {
    const key = (byDay.get(day) ?? []).join(" và ");
    groups.set(key, [...(groups.get(key) ?? []), day]);
  }
  return [...groups.entries()].map(([key, days]) => ({ days: formatDays(days), hours: key }));
}

/** Phòng khám đang mở cửa không, mở đến mấy giờ (theo giờ Việt Nam). */
export function openStatus(now: Date = new Date()): { open: boolean; until?: string } {
  const weekday = Number(formatInTimeZone(now, CLINIC_TZ, "i"));
  const time = formatInTimeZone(now, CLINIC_TZ, "HH:mm");
  const hours = CLINIC.openingHours[weekday];
  if (!hours) return { open: false };
  const [from, to] = hours;
  return time >= from && time < to ? { open: true, until: to } : { open: false };
}
