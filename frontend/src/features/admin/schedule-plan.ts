// Trải ca làm lặp hằng tuần và ngày nghỉ ra một tuần cụ thể cho lưới AD-schedule. Thuần, không gọi
// API, để test được. Giờ ca làm là giờ địa phương "HH:MM:SS"; ngày nghỉ, lịch hẹn là thời điểm ISO.
import type { AdminAppointment, Shift, TimeOff } from "@/shared/api/types";
import { addDays, clinicDay, formatTime, isoWeekday } from "@/shared/lib/datetime";

export type Period = "morning" | "afternoon" | "evening";
export const PERIODS: Period[] = ["morning", "afternoon", "evening"];

export type ShiftBlock = {
  shift: Shift;
  start: string; // "07:00"
  end: string;
  booked: number; // lịch Đã đặt, Đã đến bắt đầu trong ca
  off: TimeOff | null; // ngày nghỉ chồng lên ca
};

export type DayPlan = {
  day: string;
  blocks: Record<Period, ShiftBlock[]>;
  timeOffs: { item: TimeOff; allDay: boolean; start: string; end: string }[];
};

export function hhmm(time: string): string {
  return time.slice(0, 5);
}

export function periodOf(start: string): Period {
  if (start < "12:00") return "morning";
  return start < "17:00" ? "afternoon" : "evening";
}

export function appliesOn(shift: Shift, day: string): boolean {
  return (
    shift.weekday === isoWeekday(day) &&
    shift.valid_from <= day &&
    (shift.valid_to === null || day <= shift.valid_to)
  );
}

/** Phần của ngày nghỉ rơi vào `day`, theo giờ phòng khám: "00:00"–"24:00" là cả ngày. */
function clip(item: TimeOff, day: string): { start: string; end: string } | null {
  const first = clinicDay(item.start_at);
  const last = clinicDay(item.end_at);
  if (day < first || day > last) return null;
  const start = day === first ? formatTime(item.start_at) : "00:00";
  const end = day === last ? formatTime(item.end_at) : "24:00";
  if (end === "00:00" || start === end) return null; // kết thúc đúng 00:00 của ngày này
  return { start, end };
}

export function weekPlan(
  monday: string,
  shifts: Shift[],
  timeOffs: TimeOff[],
  appointments: AdminAppointment[],
): DayPlan[] {
  return Array.from({ length: 7 }, (_, index) => {
    const day = addDays(monday, index);
    const offs = timeOffs.flatMap((item) => {
      const part = clip(item, day);
      if (!part) return [];
      const allDay = part.start === "00:00" && (part.end === "24:00" || part.end >= "23:59");
      return [{ item, allDay, ...part }];
    });
    const blocks: Record<Period, ShiftBlock[]> = { morning: [], afternoon: [], evening: [] };
    const active = appointments.filter(
      (a) => clinicDay(a.start_at) === day && (a.status === "BOOKED" || a.status === "ARRIVED"),
    );
    for (const shift of shifts.filter((s) => appliesOn(s, day))) {
      const start = hhmm(shift.start_time);
      const end = hhmm(shift.end_time);
      const booked = active.filter((a) => {
        const time = formatTime(a.start_at);
        return time >= start && time < end;
      }).length;
      const off = offs.find((o) => o.start < end && start < o.end)?.item ?? null;
      blocks[periodOf(start)].push({ shift, start, end, booked, off });
    }
    return { day, blocks, timeOffs: offs };
  });
}
